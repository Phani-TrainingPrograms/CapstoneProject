"""
BASELINE DEFINITION  (METHOD.md section 2)

The baseline is the set of pre-promotion weeks that represents "normal trading"
for the promoted SKUs. It is defined ONLY by the rules below; nothing about the
baseline is chosen by the analyst.

Rules, applied walking backwards from the week before launch:
  B1  The `gap_weeks` weeks immediately before launch are skipped (buffer).
  B2  Holiday weeks are skipped when `exclude_holiday_weeks` is true.
  B3  Weeks in which another promotion ran on the same SKUs are skipped when
      `exclude_promo_weeks` is true.
  B4  Collection stops once `pre_period_weeks` valid weeks are found or the
      walk reaches `max_lookback_weeks` (or the start of history).
  B5  If fewer than `min_valid_weeks` valid weeks are found, the promotion is
      NOT attributed - an InsufficientBaselineError is raised instead of
      quietly reporting a number built on a thin baseline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class InsufficientBaselineError(ValueError):
    pass


@dataclass
class BaselineWindow:
    weeks: list[int]                                   # valid baseline weeks, ascending
    excluded: list[tuple[int, str]] = field(default_factory=list)  # (week, reason)

    def __len__(self) -> int:
        return len(self.weeks)


REASON_GAP = "pre-launch buffer"
REASON_HOLIDAY = "holiday week"
REASON_PROMO = "other promotion on same SKUs"


def select_baseline_weeks(promo_start: int, holiday_weeks: set[int], blocked_weeks: set[int],
                          cfg: dict, n_valid: int | None = None) -> BaselineWindow:
    """Apply rules B1-B5. `n_valid` overrides pre_period_weeks (used for the match window)."""
    want = cfg["pre_period_weeks"] if n_valid is None else n_valid
    gap = int(cfg.get("gap_weeks", 0))
    lookback = int(cfg.get("max_lookback_weeks", want + gap))
    if n_valid is not None:
        lookback = max(lookback, want + gap)
    if want <= 0:
        raise ValueError("pre_period_weeks must be positive")
    if promo_start < 0:
        raise ValueError("promo_start must be >= 0")

    valid: list[int] = []
    excluded: list[tuple[int, str]] = []
    earliest = max(0, promo_start - lookback)
    for w in range(promo_start - 1, earliest - 1, -1):
        if len(valid) >= want:
            break
        if w >= promo_start - gap:
            excluded.append((w, REASON_GAP))
        elif cfg.get("exclude_holiday_weeks", True) and w in holiday_weeks:
            excluded.append((w, REASON_HOLIDAY))
        elif cfg.get("exclude_promo_weeks", True) and w in blocked_weeks:
            excluded.append((w, REASON_PROMO))
        else:
            valid.append(w)

    min_valid = int(cfg.get("min_valid_weeks", 1)) if n_valid is None else 1
    if len(valid) < min_valid:
        raise InsufficientBaselineError(
            f"only {len(valid)} valid baseline weeks found before week {promo_start}; "
            f"method requires {min_valid}")
    return BaselineWindow(weeks=sorted(valid), excluded=sorted(excluded))


def baseline_scale(treated: np.ndarray, control: np.ndarray, weeks: list[int]) -> np.ndarray | float:
    """Ratio of treated to control volume over the baseline weeks (per row for 2-D input).

    The counterfactual is control * scale. With no control group (strategy
    'none') pass control = ones, which turns the baseline into the treated
    store's own average weekly run-rate.
    """
    if len(weeks) == 0:
        raise InsufficientBaselineError("no baseline weeks")
    t = np.asarray(treated, dtype=float)[..., weeks].sum(axis=-1)
    c = np.asarray(control, dtype=float)[..., weeks].sum(axis=-1)
    if np.any(c <= 0):
        raise InsufficientBaselineError("control volume over baseline weeks is zero")
    out = t / c
    return float(out) if np.ndim(out) == 0 else out
