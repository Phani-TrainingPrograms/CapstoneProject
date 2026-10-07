"""
Monte-Carlo calibration of the stated tolerance.

Regenerates the synthetic world under N different seeds, runs the current
method blind on each, and reports the distribution of |estimate - planted|.
The tolerance in method_config.yaml should sit comfortably above the
observed 95th-99th percentile error, otherwise the gate will be flaky.

Run:  python scripts/calibrate_tolerance.py --seeds 10
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data_gen"))

from attribution import load_config, load_dataset, recovery_report  # noqa: E402
from generate_data import generate  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--config", default=str(ROOT / "method_config.yaml"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "tolerance_calibration.json"))
    a = ap.parse_args()
    cfg = load_config(a.config)
    errors, coverage, nulls_ok, per_seed = [], [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(a.seeds):
            seed = 1000 + i
            d = Path(tmp) / f"s{seed}"
            generate(d, seed)
            rep = recovery_report(load_dataset(str(d)), cfg)
            errs = [abs(r["error_pp"]) for r in rep["rows"] if r["status"] == "ok"]
            errors += errs
            coverage.append(rep["summary"]["ci_coverage"])
            nulls_ok.append(rep["summary"]["V2_nulls_not_significant"])
            per_seed.append({"seed": seed, "max_abs_error_pp": max(errs), "passed": rep["summary"]["passed"]})
            print(f"seed {seed}: max |err| {max(errs):.2f}pp  coverage {coverage[-1]:.2f}  passed={rep['summary']['passed']}")
    e = np.array(errors)
    summary = {
        "method_version": cfg["method_version"], "seeds": a.seeds, "estimates": len(e),
        "tolerance_pp": cfg["validation"]["tolerance_pp"],
        "abs_error_pp": {"mean": round(float(e.mean()), 3), "p50": round(float(np.percentile(e, 50)), 3),
                         "p95": round(float(np.percentile(e, 95)), 3), "p99": round(float(np.percentile(e, 99)), 3),
                         "max": round(float(e.max()), 3)},
        "share_within_tolerance": round(float((e <= cfg["validation"]["tolerance_pp"]).mean()), 4),
        "mean_ci_coverage": round(float(np.mean(coverage)), 3),
        "null_false_positive_rate": round(1 - float(np.mean(nulls_ok)), 3),
        "worlds_passing_gate": f"{sum(s['passed'] for s in per_seed)}/{a.seeds}",
        "per_seed": per_seed,
    }
    Path(a.out).parent.mkdir(exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "per_seed"}, indent=2))


if __name__ == "__main__":
    main()
