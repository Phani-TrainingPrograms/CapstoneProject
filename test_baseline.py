"""Baseline definition tests - one or more tests per rule B1-B5 in attribution/baseline.py."""
import numpy as np
import pytest

from attribution.baseline import (REASON_GAP, REASON_HOLIDAY, REASON_PROMO, InsufficientBaselineError,
                                  baseline_scale, select_baseline_weeks)


# ---- B1 gap ----------------------------------------------------------------
def test_gap_weeks_are_skipped(bcfg):
    w = select_baseline_weeks(20, set(), set(), bcfg)
    assert w.weeks == [15, 16, 17, 18]
    assert (19, REASON_GAP) in w.excluded


def test_zero_gap_uses_week_before_launch(bcfg):
    bcfg["gap_weeks"] = 0
    assert select_baseline_weeks(20, set(), set(), bcfg).weeks == [16, 17, 18, 19]


def test_baseline_never_includes_promo_weeks_or_later(bcfg):
    w = select_baseline_weeks(20, set(), set(), bcfg)
    assert max(w.weeks) < 20


# ---- B2 holidays ---------------------------------------------------------------
def test_holiday_weeks_are_skipped_and_replaced(bcfg):
    w = select_baseline_weeks(20, {17}, set(), bcfg)
    assert 17 not in w.weeks
    assert w.weeks == [14, 15, 16, 18]
    assert (17, REASON_HOLIDAY) in w.excluded


def test_holidays_kept_when_rule_disabled(bcfg):
    bcfg["exclude_holiday_weeks"] = False
    assert 17 in select_baseline_weeks(20, {17}, set(), bcfg).weeks


# ---- B3 other promotions ----------------------------------------------------
def test_other_promo_weeks_are_skipped(bcfg):
    w = select_baseline_weeks(20, set(), {16, 17}, bcfg)
    assert w.weeks == [13, 14, 15, 18]
    assert (16, REASON_PROMO) in w.excluded and (17, REASON_PROMO) in w.excluded


def test_other_promo_weeks_kept_when_rule_disabled(bcfg):
    bcfg["exclude_promo_weeks"] = False
    assert select_baseline_weeks(20, set(), {16, 17}, bcfg).weeks == [15, 16, 17, 18]


def test_week_that_is_holiday_and_promo_is_reported_once(bcfg):
    w = select_baseline_weeks(20, {17}, {17}, bcfg)
    assert [r for wk, r in w.excluded if wk == 17] == [REASON_HOLIDAY]


# ---- B4 stopping ---------------------------------------------------------------
def test_stops_at_requested_number_of_weeks(bcfg):
    bcfg["pre_period_weeks"] = 6
    assert len(select_baseline_weeks(40, set(), set(), bcfg)) == 6


def test_lookback_limit_is_respected(bcfg):
    bcfg["max_lookback_weeks"] = 6
    w = select_baseline_weeks(20, {15, 16}, set(), bcfg)
    assert min(w.weeks) >= 14
    assert w.weeks == [14, 17, 18]


def test_start_of_history_is_respected(bcfg):
    w = select_baseline_weeks(4, set(), set(), bcfg)
    assert w.weeks == [0, 1, 2]


def test_weeks_returned_in_ascending_order(bcfg):
    w = select_baseline_weeks(30, {25}, {27}, bcfg)
    assert w.weeks == sorted(w.weeks)


# ---- B5 refusal ------------------------------------------------------------------
def test_refuses_when_too_few_valid_weeks(bcfg):
    with pytest.raises(InsufficientBaselineError):
        select_baseline_weeks(3, set(), set(), bcfg)


def test_refuses_when_everything_is_blocked(bcfg):
    with pytest.raises(InsufficientBaselineError):
        select_baseline_weeks(20, set(range(0, 20)), set(), bcfg)


def test_invalid_inputs_raise(bcfg):
    with pytest.raises(ValueError):
        select_baseline_weeks(-1, set(), set(), bcfg)
    bcfg["pre_period_weeks"] = 0
    with pytest.raises(ValueError):
        select_baseline_weeks(10, set(), set(), bcfg)


def test_match_window_override_ignores_min_valid(bcfg):
    w = select_baseline_weeks(30, set(), set(), bcfg, n_valid=12)
    assert len(w) == 12


# ---- baseline scale --------------------------------------------------------------
def test_scale_is_ratio_over_baseline_weeks_only():
    t = np.array([10, 10, 10, 99.0])
    c = np.array([5, 5, 5, 1.0])
    assert baseline_scale(t, c, [0, 1, 2]) == pytest.approx(2.0)


def test_scale_vectorised_per_store():
    t = np.array([[10, 10], [30, 30.0]])
    c = np.array([[5, 5], [10, 10.0]])
    np.testing.assert_allclose(baseline_scale(t, c, [0, 1]), [2.0, 3.0])


def test_scale_with_flat_control_is_run_rate():
    t = np.array([8, 12, 10.0])
    assert baseline_scale(t, np.ones(3), [0, 1, 2]) == pytest.approx(10.0)


def test_scale_refuses_zero_control_and_empty_window():
    with pytest.raises(InsufficientBaselineError):
        baseline_scale(np.ones(3), np.zeros(3), [0, 1])
    with pytest.raises(InsufficientBaselineError):
        baseline_scale(np.ones(3), np.ones(3), [])


# ---- the rules on the real reference data -----------------------------------------
def test_repeat_promo_baseline_excludes_earlier_promo_weeks(ds, cfg):
    from attribution import attribute_promo
    r = attribute_promo(ds, "P10", cfg)          # Yogurt repeat; P07 ran on the same SKUs earlier
    p07 = ds.promo("P07")
    p07_weeks = set(ds.calendar["week_start"].iloc[p07["start_idx"]:p07["end_idx"] + 1])
    assert not p07_weeks & set(r["baseline_weeks"])
    assert any(e["reason"] == REASON_PROMO for e in r["excluded_weeks"])


def test_holiday_promo_baseline_excludes_thanksgiving(ds, cfg):
    from attribution import attribute_promo
    r = attribute_promo(ds, "P09", cfg)
    hol = set(ds.calendar.loc[ds.calendar["is_holiday_week"] == 1, "week_start"])
    assert not hol & set(r["baseline_weeks"])
    assert len(r["baseline_weeks"]) == cfg["baseline"]["pre_period_weeks"]
