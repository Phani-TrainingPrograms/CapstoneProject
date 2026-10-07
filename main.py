"""
Promotion Attribution Service - HTTP API + web UI.

    uvicorn app.main:app --port 8000        (or: python run.py)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attribution import (attribute_all, config_hash, load_config, load_dataset, merge_config,  # noqa: E402
                         recovery_report, reproducibility_report)
from attribution.data import load_ground_truth  # noqa: E402
from attribution.gate import PROPOSALS_DIR, config_diff, list_proposals, read_gate_log, run_gate  # noqa: E402
from app.ask import AskEngine  # noqa: E402

app = FastAPI(title="Promotion Attribution Service", version="1.0")
STATIC = Path(__file__).parent / "static"
REPORTS = ROOT / "reports"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_cache: dict[str, list[dict]] = {}
SUMMARY_KEYS = ("promo_id", "promo_name", "category", "mechanic", "discount_pct", "start_week", "end_week",
                "duration_weeks", "status", "uplift_pct", "ci_low", "ci_high", "p_value", "significant",
                "verdict", "incremental_units", "incremental_revenue", "incremental_margin", "funding_cost",
                "roi", "pre_period_mape", "owner", "naive_estimates", "method_version", "config_hash")


def _cfg(proposal: str | None = None) -> dict:
    if not proposal:
        return load_config()
    path = (PROPOSALS_DIR / proposal).resolve()
    if path.parent != PROPOSALS_DIR.resolve() or not path.exists():
        raise HTTPException(404, f"unknown proposal {proposal}")
    return load_config(path)


def _results(cfg: dict) -> list[dict]:
    key = config_hash(cfg)
    if key not in _cache:
        _cache[key] = attribute_all(load_dataset(), cfg)
    return _cache[key]


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    ds, cfg = load_dataset(), load_config()
    manifest = json.loads((ds.data_dir / "data_manifest.json").read_text())
    return {"method_version": cfg["method_version"], "config_hash": config_hash(cfg), "data_hash": ds.data_hash,
            "n_promotions": len(ds.promotions), "n_stores": len(ds.stores), "n_skus": len(ds.products),
            "weeks": [manifest["first_week"], manifest["last_week"]], "tolerance_pp": cfg["validation"]["tolerance_pp"],
            "confidence_level": cfg["inference"]["confidence_level"]}


@app.get("/api/promotions")
def promotions(proposal: str | None = None):
    return [{k: r.get(k) for k in SUMMARY_KEYS} for r in _results(_cfg(proposal))]


@app.get("/api/promotions/{promo_id}")
def promotion(promo_id: str, proposal: str | None = None):
    for r in _results(_cfg(proposal)):
        if r["promo_id"] == promo_id:
            return r
    raise HTTPException(404, f"unknown promotion {promo_id}")


@app.get("/api/method")
def method():
    cfg = load_config()
    read = lambda p: p.read_text(encoding="utf-8") if p.exists() else None  # noqa: E731
    cov = json.loads(read(REPORTS / "coverage.json")) if (REPORTS / "coverage.json").exists() else None
    coverage = None
    if cov:
        coverage = {"total": round(cov["totals"]["percent_covered"], 1),
                    "files": {Path(f).name: round(v["summary"]["percent_covered"], 1)
                              for f, v in cov["files"].items()}}
    calib = REPORTS / "tolerance_calibration.json"
    return {"config": cfg, "config_yaml": read(ROOT / "method_config.yaml"), "config_hash": config_hash(cfg),
            "method_md": read(ROOT / "METHOD.md"), "changelog_md": read(ROOT / "CHANGELOG.md"),
            "coverage": coverage, "calibration": json.loads(calib.read_text()) if calib.exists() else None,
            "tests": json.loads(read(REPORTS / "test_summary.json")) if (REPORTS / "test_summary.json").exists() else None}


@app.get("/api/validation")
def validation(proposal: str | None = None):
    cfg = _cfg(proposal)
    return recovery_report(load_dataset(), cfg, _results(cfg))


class ReproRequest(BaseModel):
    runs: int = 5


@app.post("/api/reproducibility")
def reproducibility(req: ReproRequest):
    runs = max(2, min(req.runs, 20))
    load_dataset.cache_clear()          # reload data from disk: nothing is reused between sessions
    return reproducibility_report(load_dataset(), load_config(), runs)


@app.get("/api/proposals")
def proposals():
    cur = load_config()
    out = []
    for p in list_proposals():
        p["diff"] = config_diff(cur, load_config(PROPOSALS_DIR / p["file"]))
        out.append(p)
    return out


class GateRequest(BaseModel):
    proposal: str | None = None        # file in configs/proposals
    overrides: dict | None = None      # ad-hoc change built in the UI
    method_version: str | None = None
    title: str | None = None


@app.post("/api/gate")
def gate(req: GateRequest):
    current = load_config()
    if req.proposal:
        proposed = _cfg(req.proposal)
    else:
        proposed = merge_config(current, req.overrides or {})
        if req.method_version:
            proposed["method_version"] = req.method_version
        proposed["proposal"] = {"title": req.title or "Ad-hoc change from UI"}
    try:
        return run_gate(load_dataset(), proposed, current)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"invalid method configuration: {e}")


@app.get("/api/gate/log")
def gate_log():
    return read_gate_log()


@app.post("/api/ci/run")
def ci_run():
    """Run the same test suite CI runs, with coverage."""
    REPORTS.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--cov=attribution",
         f"--cov-report=json:{REPORTS / 'coverage.json'}", f"--junitxml={REPORTS / 'junit.xml'}"],
        cwd=ROOT, capture_output=True, text=True)
    load_dataset.cache_clear()
    tests = []
    if (REPORTS / "junit.xml").exists():
        for tc in ET.parse(REPORTS / "junit.xml").getroot().iter("testcase"):
            failed = tc.find("failure") is not None or tc.find("error") is not None
            tests.append({"file": tc.get("classname", "").split(".")[-1], "name": tc.get("name"),
                          "seconds": float(tc.get("time", 0)), "passed": not failed})
    summary = {"passed": proc.returncode == 0, "n_tests": len(tests), "n_failed": sum(not t["passed"] for t in tests),
               "seconds": round(time.perf_counter() - t0, 1), "tests": tests,
               "output_tail": "\n".join(proc.stdout.strip().splitlines()[-15:])}
    (REPORTS / "test_summary.json").write_text(json.dumps(summary, indent=2))
    return {**summary, "coverage": method()["coverage"]}


@app.get("/api/data")
def data_overview():
    ds = load_dataset()
    manifest = json.loads((ds.data_dir / "data_manifest.json").read_text())
    files = []
    for f in sorted(ds.data_dir.glob("*.csv")):
        with open(f, encoding="utf-8") as fh:
            n = sum(1 for _ in fh) - 1
        files.append({"file": f.name, "rows": n, "size_kb": round(f.stat().st_size / 1024, 1),
                      "hidden_from_method": f.name in manifest["hidden_from_method"],
                      "sha256": manifest["sha256"].get(f.name, "")[:16]})
    truth = load_ground_truth().to_dict("records")
    stores = ds.stores.groupby(["region", "format"]).size().unstack(fill_value=0)
    return {"manifest": manifest, "files": files, "ground_truth": truth,
            "store_mix": {"regions": stores.index.tolist(), "formats": stores.columns.tolist(),
                          "counts": stores.values.tolist()}}


@app.get("/api/data/{name}")
def data_preview(name: str, limit: int = 15):
    path = (load_dataset().data_dir / name).resolve()
    if path.parent != load_dataset().data_dir.resolve() or not path.exists() or path.suffix != ".csv":
        raise HTTPException(404, "unknown file")
    import pandas as pd
    df = pd.read_csv(path, nrows=max(1, min(limit, 200)))
    return {"columns": df.columns.tolist(), "rows": df.astype(object).where(df.notna(), None).values.tolist()}


# ----------------------------------------------------------------------------- Ask
_gate_cache: dict[str, list[dict]] = {}


def _all_gates() -> list[dict]:
    cur = load_config()
    key = config_hash(cur)
    if key not in _gate_cache:
        _gate_cache[key] = [run_gate(load_dataset(), load_config(PROPOSALS_DIR / p["file"]), cur, log=False)
                            for p in list_proposals()]
    return _gate_cache[key]


class AskRequest(BaseModel):
    question: str
    context: dict | None = None


@app.post("/api/ask")
def ask(req: AskRequest):
    cfg = load_config()
    calib = REPORTS / "tolerance_calibration.json"
    engine = AskEngine(
        results=_results(cfg), cfg=cfg,
        method_md=(ROOT / "METHOD.md").read_text(encoding="utf-8"),
        validation=lambda: recovery_report(load_dataset(), cfg, _results(cfg)),
        calibration=json.loads(calib.read_text()) if calib.exists() else None,
        gate=_all_gates,
    )
    return engine.answer(req.question[:500], req.context)
