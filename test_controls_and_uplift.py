"""Control selection and uplift estimator tests on small hand-built worlds."""
import numpy as np
import pandas as pd
import pytest

from attribution.controls import select_controls
from attribution.uplift import bootstrap, control_matrix, estimate

CTRL = {"strategy": "matched", "controls_per_treated": 2, "exact_match_on": ["format", "region"]}


def _world(effect=0.0, n_weeks=30, promo=(24, 28), seed=0):
    """6 stores: 0,1 treated. Stores share format/region in pairs and a seasonal shape."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_weeks)
    shape_a = 1 + 0.2 * np.sin(t / 4)
    shape_b = 1 + 0.2 * np.cos(t / 3)
    level = np.array([100, 200, 110, 190, 150, 120.0])
    shapes = np.array([shape_a, shape_a, shape_a, shape_a, shape_b, shape_b])
    sw = level[:, None] * shapes * rng.normal(1, 0.001, (6, n_weeks))
    sw[:2, promo[0]:promo[1]] *= 1 + effect
    stores = pd.DataFrame({"format": ["Hyper", "Hyper", "Hyper", "Hyper", "Super", "Super"],
                           "region": ["N", "N", "N", "N", "N", "N"]})
    return sw, stores, np.array([0, 1]), list(range(0, 20)), list(range(promo[0], promo[1]))


def test_controls_are_never_treated_and_share_attributes():
    sw, stores, treated, match, _ = _world()
    sel = select_controls(sw, treated, match, CTRL, np.random.default_rng(0), stores)
    assert set(sel.control_idx) == {2, 3}
    assert not set(sel.control_idx) & set(treated)
    assert all(p["match_level"] == "format+region" for p in sel.pairs)
    np.testing.assert_allclose(sel.weights.sum(axis=1), 1.0)


def test_relaxes_constraint_when_pool_too_small():
    sw, stores, treated, match, _ = _world()
    sel = select_controls(sw, treated, match, {**CTRL, "controls_per_treated": 3}, np.random.default_rng(0), stores)
    assert all(p["match_level"] == "any" and p["fallback"] for p in sel.pairs)


def test_matching_prefers_same_trajectory_without_attributes():
    sw, stores, treated, match, _ = _world()
    sel = select_controls(sw, treated, match, {**CTRL, "exact_match_on": []}, np.random.default_rng(0), stores)
    assert set(sel.control_idx) == {2, 3}          # shape_a stores, not shape_b


def test_strategies():
    sw, stores, treated, match, _ = _world()
    rng = np.random.default_rng(0)
    assert not select_controls(sw, treated, match, {"strategy": "none"}, rng, stores).weights.any()
    allc = select_controls(sw, treated, match, {"strategy": "all_untreated"}, rng, stores)
    assert set(allc.control_idx) == {2, 3, 4, 5}
    with pytest.raises(ValueError):
        select_controls(sw, treated, match, {"strategy": "magic"}, rng, stores)


@pytest.mark.parametrize("effect", [0.0, 0.07, 0.25, -0.1])
def test_estimator_recovers_planted_effect_exactly_in_noise_free_world(effect):
    sw, stores, treated, match, post = _world(effect=effect)
    sel = select_controls(sw, treated, match, CTRL, np.random.default_rng(0), stores)
    est = estimate(sw[treated], control_matrix(sw, sel.weights), list(range(8, 20)), post)
    assert est.uplift == pytest.approx(effect, abs=0.003)


def test_common_shock_cancels():
    sw, stores, treated, match, post = _world(effect=0.1)
    sw[:, post] *= 1.5                                # market-wide event during the promo
    sel = select_controls(sw, treated, match, CTRL, np.random.default_rng(0), stores)
    est = estimate(sw[treated], control_matrix(sw, sel.weights), list(range(8, 20)), post)
    assert est.uplift == pytest.approx(0.1, abs=0.003)


def test_bootstrap_is_seeded_and_brackets_estimate():
    sw, stores, treated, match, post = _world(effect=0.1, seed=3)
    sel = select_controls(sw, treated, match, CTRL, np.random.default_rng(0), stores)
    pre = list(range(8, 20))
    est = estimate(sw[treated], control_matrix(sw, sel.weights), pre, post)
    a = bootstrap(sw[treated], sw, sel.weights, pre, post, 500, 0.95, np.random.default_rng(42))
    b = bootstrap(sw[treated], sw, sel.weights, pre, post, 500, 0.95, np.random.default_rng(42))
    assert (a.uplift_low, a.uplift_high) == (b.uplift_low, b.uplift_high)
    assert a.uplift_low <= est.uplift <= a.uplift_high
