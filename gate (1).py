"""
METHOD-CHANGE GATE  (METHOD.md section 7)

A proposed method (a full config, optionally with code changes already on the
branch) may merge only if ALL of these hold on the pinned reference data:

  G1  Recovery    - the synthetic ground-truth validation passes (V1-V3).
  G2  Reproducible- two independent runs give an identical result fingerprint.
  G3  Versioned   - if any method-defining setting changed, method_version was bumped.
  G4  Data pinned - the reference data matches the checksums in data_manifest.json.
  G5  Thresholds  - the validation tolerance is owned by main; a proposal may not
                    loosen the bar it is judged against.

Recovery is always judged with the CURRENT validation thresholds.

The same function backs the CLI (gate.py), the CI workflow and the UI.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .data import METHOD_INPUTS, Dataset
from .engine import ROOT, attribute_all, config_hash, fingerprint, load_config, merge_config
from .validation import recovery_report

PROPOSALS_DIR = ROOT / "configs" / "proposals"
GATE_LOG = ROOT / "reports" / "gate_log.jsonl"


def flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def config_diff(current: dict, proposed: dict) -> list[dict]:
    a = flatten({k: v for k, v in current.items() if k != "proposal"})
    b = flatten({k: v for k, v in proposed.items() if k != "proposal"})
    return [{"key": k, "current": a.get(k), "proposed": b.get(k)}
            for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


def data_pinned(ds: Dataset) -> tuple[bool, list[str]]:
    manifest = json.loads((ds.data_dir / "data_manifest.json").read_text())
    bad = [f for f in METHOD_INPUTS
           if hashlib.sha256((ds.data_dir / f).read_bytes()).hexdigest() != manifest["sha256"].get(f)]
    return not bad, bad


def list_proposals() -> list[dict]:
    out = []
    for p in sorted(PROPOSALS_DIR.glob("*.yaml")):
        cfg = load_config(p)
        meta = cfg.get("proposal", {})
        out.append({"file": p.name, "title": meta.get("title", p.stem), "author": meta.get("author", ""),
                    "rationale": meta.get("rationale", ""), "method_version": cfg.get("method_version")})
    return out


def run_gate(ds: Dataset, proposed: dict, current: dict | None = None, label: str = "",
             log: bool = True) -> dict:
    current = current or load_config()
    t0 = time.perf_counter()
    diff = config_diff(current, proposed)
    method_changed = any(d["key"] != "method_version" for d in diff)
    thresholds_changed = [d["key"] for d in diff if d["key"].startswith("validation.")]
    proposed = merge_config(proposed, {"validation": current["validation"]})
    version_bumped = proposed.get("method_version") != current.get("method_version")

    res1 = attribute_all(ds, proposed)
    res2 = attribute_all(ds, proposed)
    fp1, fp2 = fingerprint(res1), fingerprint(res2)
    recovery = recovery_report(ds, proposed, res1)
    pinned, bad_files = data_pinned(ds)

    checks = [
        {"id": "G1", "name": "Planted effects recovered", "passed": recovery["summary"]["passed"],
         "detail": (f"{recovery['summary']['n_passed']}/{recovery['summary']['n_promos']} promos within +/-"
                    f"{proposed['validation']['tolerance_pp']}pp; max error "
                    f"{recovery['summary']['max_abs_error_pp']}pp; CI coverage "
                    f"{recovery['summary']['ci_coverage']:.0%}")},
        {"id": "G2", "name": "Reproducible across runs", "passed": fp1 == fp2,
         "detail": f"run 1 {fp1[:12]}... vs run 2 {fp2[:12]}..."},
        {"id": "G3", "name": "Method version bumped for a method change",
         "passed": (not method_changed) or version_bumped,
         "detail": ("no method-defining change" if not method_changed else
                    f"{current.get('method_version')} -> {proposed.get('method_version')}"
                    if version_bumped else "settings changed but method_version was not bumped")},
        {"id": "G4", "name": "Reference data pinned", "passed": pinned,
         "detail": "checksums match data_manifest.json" if pinned else f"modified: {', '.join(bad_files)}"},
        {"id": "G5", "name": "Validation thresholds untouched", "passed": not thresholds_changed,
         "detail": "judged against main's tolerance" if not thresholds_changed else
                   f"proposal tried to change {', '.join(thresholds_changed)}"},
    ]
    verdict = "PASS" if all(c["passed"] for c in checks) else "BLOCK"
    report = {
        "label": label or proposed.get("proposal", {}).get("title", "proposed method"),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verdict": verdict,
        "current_version": current.get("method_version"), "proposed_version": proposed.get("method_version"),
        "current_config_hash": config_hash(current), "proposed_config_hash": config_hash(proposed),
        "diff": diff, "checks": checks, "recovery": recovery, "fingerprint": fp1,
        "seconds": round(time.perf_counter() - t0, 2),
    }
    if log:
        GATE_LOG.parent.mkdir(exist_ok=True)
        with open(GATE_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: report[k] for k in ("timestamp", "label", "verdict", "current_version",
                                                         "proposed_version", "proposed_config_hash")}) + "\n")
    return report


def read_gate_log(limit: int = 50) -> list[dict]:
    if not GATE_LOG.exists():
        return []
    lines = GATE_LOG.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(x) for x in reversed(lines[-limit:])]
