"""
THE RECOVERY TEST - the merge gate's core.

The method is run blind on the pinned synthetic data and must recover every
planted effect within the tolerance stated in method_config.yaml.
"""
import inspect

import pytest

from attribution import attribute_all, load_ground_truth, recovery_report
import attribution.baseline
import attribution.controls
import attribution.engine
import attribution.uplift

TRUTH = load_ground_truth().set_index("promo_id")


@pytest.fixture(scope="module")
def results(ds, cfg):
    return {r["promo_id"]: r for r in attribute_all(ds, cfg)}


@pytest.mark.parametrize("promo_id", TRUTH.index.tolist())
def test_planted_effect_recovered_within_tolerance(results, cfg, promo_id):
    r = results[promo_id]
    assert r["status"] == "ok", r.get("reason")
    true = TRUTH.loc[promo_id, "true_uplift_pct"]
    err_pp = abs(r["uplift_pct"] - true) * 100
    assert err_pp <= cfg["validation"]["tolerance_pp"], (
        f"{promo_id}: planted {true:+.1%}, estimated {r['uplift_pct']:+.2%} ({err_pp:.2f}pp off)")


def test_null_promotion_not_called_significant(results):
    for pid in TRUTH.index[TRUTH["true_uplift_pct"] == 0]:
        assert not results[pid]["significant"], f"{pid} has no planted effect but was called significant"


def test_real_effects_have_correct_sign_and_are_detected(results):
    for pid, row in TRUTH[TRUTH["true_uplift_pct"].abs() >= 0.05].iterrows():
        r = results[pid]
        assert r["significant"] and (r["uplift_pct"] > 0) == (row["true_uplift_pct"] > 0)


def test_confidence_interval_coverage(ds, cfg):
    s = recovery_report(ds, cfg)["summary"]
    assert s["ci_coverage"] >= cfg["validation"]["min_ci_coverage"]
    assert s["passed"]


def test_method_cannot_see_ground_truth():
    for mod in (attribution.baseline, attribution.controls, attribution.uplift, attribution.engine):
        assert "ground_truth" not in inspect.getsource(mod)
