"""
SYNTHETIC GROUND-TRUTH VALIDATION  (METHOD.md section 6)

The method is run blind on synthetic data whose true effects were planted by
data_gen/generate_data.py. It passes only if:

  V1  every promotion's estimate is within `tolerance_pp` percentage points
      of the planted effect;
  V2  every promotion with a planted effect of zero is NOT called significant;
  V3  at least `min_ci_coverage` of the confidence intervals contain the
      planted effect;
  V4  two independent runs produce an identical result fingerprint.
"""
from __future__ import annotations

import time

from .data import Dataset, load_ground_truth
from .engine import attribute_all, config_hash, fingerprint


def recovery_report(ds: Dataset, cfg: dict, results: list[dict] | None = None) -> dict:
    truth = load_ground_truth(ds.data_dir).set_index("promo_id")
    results = results if results is not None else attribute_all(ds, cfg)
    tol = cfg["validation"]["tolerance_pp"]
    rows = []
    for r in results:
        t = truth.loc[r["promo_id"]]
        true = float(t["true_uplift_pct"])
        if r["status"] != "ok":
            rows.append({"promo_id": r["promo_id"], "promo_name": r["promo_name"], "true_uplift_pct": true,
                         "status": r["status"], "passed": False, "checks": {"refused": r.get("reason")}})
            continue
        err_pp = (r["uplift_pct"] - true) * 100
        covered = r["ci_low"] <= true <= r["ci_high"]
        checks = {"within_tolerance": abs(err_pp) <= tol}
        if true == 0:
            checks["null_not_significant"] = not r["significant"]
        rows.append({
            "promo_id": r["promo_id"], "promo_name": r["promo_name"], "scenario": t["scenario"],
            "status": "ok", "true_uplift_pct": true, "estimated_uplift_pct": r["uplift_pct"],
            "ci_low": r["ci_low"], "ci_high": r["ci_high"], "error_pp": round(err_pp, 3),
            "ci_covers_truth": covered, "significant": r["significant"],
            "naive_pre_post": r["naive_estimates"]["pre_post_no_control"],
            "checks": checks, "passed": all(checks.values()),
        })
    ok = [x for x in rows if x["status"] == "ok"]
    coverage = sum(x["ci_covers_truth"] for x in ok) / len(rows) if rows else 0.0
    summary = {
        "method_version": cfg["method_version"], "config_hash": config_hash(cfg),
        "tolerance_pp": tol, "n_promos": len(rows), "n_passed": sum(x["passed"] for x in rows),
        "max_abs_error_pp": round(max((abs(x["error_pp"]) for x in ok), default=float("nan")), 3),
        "mean_abs_error_pp": round(sum(abs(x["error_pp"]) for x in ok) / max(len(ok), 1), 3),
        "ci_coverage": round(coverage, 3), "min_ci_coverage": cfg["validation"]["min_ci_coverage"],
        "V1_all_within_tolerance": all(x["checks"].get("within_tolerance", False) for x in rows),
        "V2_nulls_not_significant": all(x["checks"].get("null_not_significant", True) for x in rows),
        "V3_coverage_ok": coverage >= cfg["validation"]["min_ci_coverage"],
    }
    summary["passed"] = summary["V1_all_within_tolerance"] and summary["V2_nulls_not_significant"] and summary["V3_coverage_ok"]
    return {"summary": summary, "rows": rows}


def reproducibility_report(ds: Dataset, cfg: dict, runs: int = 3) -> dict:
    out = []
    for i in range(runs):
        t0 = time.perf_counter()
        fp = fingerprint(attribute_all(ds, cfg))
        out.append({"run": i + 1, "fingerprint": fp, "seconds": round(time.perf_counter() - t0, 3)})
    return {"runs": out, "identical": len({r["fingerprint"] for r in out}) == 1,
            "method_version": cfg["method_version"], "config_hash": config_hash(cfg),
            "data_hash": ds.data_hash}
