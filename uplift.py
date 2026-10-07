"""
UPLIFT CALCULATION AND INFERENCE  (METHOD.md sections 4-5)

Estimator 'did_ratio' (difference-in-differences, ratio form), per treated store i:

    C_i(t)          = average weekly units of store i's control stores
    scale_i         = T_i(baseline weeks) / C_i(baseline weeks)
    counterfactual_i(t) = C_i(t) * scale_i

and aggregated over treated stores:

    uplift      = sum_i T_i(promo) / sum_i counterfactual_i(promo) - 1
    incremental = sum_i T_i(promo) - sum_i counterfactual_i(promo)

Anything that moves a treated store and its controls alike (seasonality,
holidays, trend, a market-wide shock) cancels in the ratio.

Inference: two-stage store bootstrap. In every draw
  (1) each control store receives a Poisson(1) resampling weight, so control
      noise shared by several treated stores is propagated correctly, and
  (2) treated stores are resampled with replacement together with their
      re-weighted counterfactual;
the estimator is recomputed and the percentile interval is reported. The
bootstrap RNG is seeded from the method config, so the interval is
reproducible bit-for-bit.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .baseline import baseline_scale


@dataclass
class Estimate:
    uplift: float
    incremental_units: float
    actual_promo_units: float
    counterfactual_promo_units: float
    treated_series: np.ndarray          # (W,) sum over treated stores
    counterfactual_series: np.ndarray   # (W,) sum of per-store counterfactuals
    store_actual_promo: np.ndarray      # (n_treated,)
    store_cf_promo: np.ndarray          # (n_treated,)


@dataclass
class Interval:
    uplift_low: float
    uplift_high: float
    incremental_low: float
    incremental_high: float
    p_value: float
    draws: np.ndarray


def control_matrix(store_week: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """(n_treated, W) weighted control series; flat ones when there are no controls."""
    if not weights.any():
        return np.ones((weights.shape[0], store_week.shape[1]))
    return weights @ store_week


def estimate(T: np.ndarray, CM: np.ndarray, pre: list[int], post: list[int]) -> Estimate:
    """T: (n_treated, W) treated units; CM: (n_treated, W) matching control series."""
    scale = baseline_scale(T, CM, pre)                     # (n_treated,)
    cf = CM * scale[:, None]
    a_i, c_i = T[:, post].sum(axis=1), cf[:, post].sum(axis=1)
    actual, counterfactual = float(a_i.sum()), float(c_i.sum())
    return Estimate(uplift=actual / counterfactual - 1, incremental_units=actual - counterfactual,
                    actual_promo_units=actual, counterfactual_promo_units=counterfactual,
                    treated_series=T.sum(axis=0), counterfactual_series=cf.sum(axis=0),
                    store_actual_promo=a_i, store_cf_promo=c_i)


def bootstrap(T: np.ndarray, store_week: np.ndarray, weights: np.ndarray, pre: list[int], post: list[int],
              iterations: int, confidence: float, rng: np.random.Generator) -> Interval:
    n_t = T.shape[0]
    t_pre, t_post = T[:, pre].sum(axis=1), T[:, post].sum(axis=1)
    if weights.any():
        c_pre, c_post = store_week[:, pre].sum(axis=1), store_week[:, post].sum(axis=1)
        m = rng.poisson(1.0, (iterations, store_week.shape[0])).astype(float)       # control re-weighting
        wm = weights[None, :, :] * m[:, None, :]                                     # (B, n_t, n_s)
        empty = wm.sum(axis=2) == 0
        wm = np.where(empty[:, :, None], weights[None, :, :], wm)                    # keep >=1 control
        ratio = (wm @ c_post) / (wm @ c_pre)                                         # (B, n_t)
        cf_store = t_pre[None, :] * ratio
    else:
        cf_store = np.broadcast_to(t_pre / len(pre) * len(post), (iterations, n_t))
    idx = rng.integers(0, n_t, (iterations, n_t))                                    # treated resample
    rows = np.arange(iterations)[:, None]
    a = t_post[idx].sum(axis=1)
    c = cf_store[rows, idx].sum(axis=1)
    up, inc = a / c - 1, a - c
    alpha = (1 - confidence) / 2
    p = 2 * min((up <= 0).mean(), (up >= 0).mean())
    return Interval(uplift_low=float(np.quantile(up, alpha)), uplift_high=float(np.quantile(up, 1 - alpha)),
                    incremental_low=float(np.quantile(inc, alpha)), incremental_high=float(np.quantile(inc, 1 - alpha)),
                    p_value=float(max(p, 1 / iterations)), draws=up)
