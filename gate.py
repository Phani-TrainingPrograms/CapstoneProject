"""
Method-change gate CLI.  Exit code 0 = PASS (merge allowed), 1 = BLOCK.

    python gate.py                                         # gate the current method_config.yaml
    python gate.py --config configs/proposals/<file>.yaml  # gate a proposed method change
    python gate.py --all-proposals                         # demo: gate every proposal

Used by .github/workflows/method-gate.yml on every pull request.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from attribution import load_config, load_dataset
from attribution.gate import PROPOSALS_DIR, run_gate

ROOT = Path(__file__).resolve().parent


def _print(report: dict) -> None:
    bar = "=" * 78
    print(bar)
    print(f" GATE: {report['label']}")
    print(f" method {report['current_version']} -> {report['proposed_version']}   "
          f"config {report['current_config_hash']} -> {report['proposed_config_hash']}")
    print(bar)
    if report["diff"]:
        print(" Changed settings:")
        for d in report["diff"]:
            print(f"   {d['key']:<38} {d['current']!s:>14} -> {d['proposed']!s}")
    print("\n Promo  planted   estimate   95% CI               error   result")
    for r in report["recovery"]["rows"]:
        if r["status"] != "ok":
            print(f"  {r['promo_id']}  REFUSED  {r['checks']}")
            continue
        print(f"  {r['promo_id']}  {r['true_uplift_pct']:+7.1%}  {r['estimated_uplift_pct']:+8.2%}   "
              f"[{r['ci_low']:+6.2%}, {r['ci_high']:+6.2%}]  {r['error_pp']:+6.2f}pp  "
              f"{'ok' if r['passed'] else 'FAIL'}")
    print()
    for c in report["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['id']} {c['name']}: {c['detail']}")
    print(f"\n VERDICT: {report['verdict']}  ({report['seconds']}s)\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "method_config.yaml"), help="proposed method config")
    ap.add_argument("--baseline-config", default=str(ROOT / "method_config.yaml"),
                    help="config currently on main (for diff / version-bump check)")
    ap.add_argument("--all-proposals", action="store_true")
    ap.add_argument("--json", help="write the full report(s) to this path")
    a = ap.parse_args()

    ds = load_dataset()
    current = load_config(a.baseline_config)
    targets = sorted(PROPOSALS_DIR.glob("*.yaml")) if a.all_proposals else [Path(a.config)]
    reports = []
    for t in targets:
        rep = run_gate(ds, load_config(t), current, label=None if a.all_proposals else "")
        _print(rep)
        reports.append(rep)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(reports if a.all_proposals else reports[0], indent=2, default=str))
    if a.all_proposals:
        return 0  # demo mode never fails the shell
    return 0 if reports[0]["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
