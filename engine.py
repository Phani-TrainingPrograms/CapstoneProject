"""Orchestrates baseline -> controls -> uplift -> inference for one or all promotions."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from .baseline import InsufficientBaselineError, select_baseline_weeks
from .controls import select_controls
from .data import Dataset
from .uplift import bootstrap, control_matrix, estimate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "method_config.yaml"
DISPLAY_WEEKS_AFTER = 6


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def merge_config(base: dict, overrides: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_config(out[k], v)
        else:
            out[k] = v
    return out


def config_hash(cfg: dict) -> str:
    """Hash of the method-defining parts of the config (metadata keys excluded)."""
    core = {k: v for k, v in cfg.items() if k not in ("proposal",)}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:12]


def _promo_seed(seed: int, promo_id: str) -> list[int]:
    # independent of run order: each promo gets its own stream derived from the method seed
    return [int(seed), int(hashlib.sha256(promo_id.encode()).hexdigest()[:8], 16)]


def _r(x: float, nd: int = 6) -> float:
    return float(round(float(x), nd))


def _store(stores, i) -> dict:
    r = stores.iloc[int(i)]
    return {"store_id": r["store_id"], "store_name": r["store_name"], "region": r["region"], "format": r["format"]}


def attribute_promo(ds: Dataset, promo_id: str, cfg: dict) -> dict:
    p = ds.promo(promo_id)
    start, end = int(p["start_idx"]), int(p["end_idx"])
    post = list(range(start, end + 1))
    sku_idx = [ds.sku_index[k] for k in p["sku_list"]]
    store_week = ds.units[sku_idx].sum(axis=0)                 # (stores, weeks)
    treated = ds.treated_store_idx(promo_id)
    holidays, blocked = ds.holiday_weeks, ds.blocked_weeks(promo_id)
    header = {
        "promo_id": promo_id, "promo_name": p["promo_name"], "category": p["category"],
        "mechanic": p["mechanic"], "discount_pct": float(p["discount_pct"]),
        "start_week": p["start_week"], "end_week": p["end_week"],
        "duration_weeks": int(p["duration_weeks"]), "funding_cost": float(p["funding_cost"]),
        "owner": p["owner"], "sku_ids": list(p["sku_list"]),
        "method_version": cfg["method_version"], "config_hash": config_hash(cfg),
        "data_hash": ds.data_hash,
    }
    try:
        base = select_baseline_weeks(start, holidays, blocked, cfg["baseline"])
        match = select_baseline_weeks(start, holidays, blocked, cfg["baseline"],
                                      n_valid=cfg["controls"].get("match_window_weeks", 26))
    except InsufficientBaselineError as e:
        return {**header, "status": "refused", "reason": str(e)}

    rng = np.random.default_rng(_promo_seed(cfg["inference"]["seed"], promo_id))
    ctrl = select_controls(store_week, treated, match.weeks, cfg["controls"], rng, ds.stores)
    T = store_week[treated]
    est = estimate(T, control_matrix(store_week, ctrl.weights), base.weeks, post)
    ci = bootstrap(T, store_week, ctrl.weights, base.weeks, post, cfg["inference"]["bootstrap_iterations"],
                   cfg["inference"]["confidence_level"], rng)

    # --- money ---------------------------------------------------------------
    cells = np.ix_(sku_idx, treated, post)
    promo_units = ds.units[cells].sum()
    asp = ds.revenue[cells].sum() / promo_units
    cost = ds.products.set_index("sku_id").loc[list(p["sku_list"]), "unit_cost"].to_numpy()
    unit_cost = float((ds.units[cells].sum(axis=(1, 2)) * cost).sum() / promo_units)
    inc_rev = est.incremental_units * asp
    inc_margin = est.incremental_units * (asp - unit_cost)
    funding = float(p["funding_cost"])

    # --- fit quality over the baseline weeks ----------------------------------
    tb, cb = est.treated_series[base.weeks], est.counterfactual_series[base.weeks]
    pre_mape = float(np.mean(np.abs(tb - cb) / tb))

    # --- naive numbers people quote from spreadsheets (for contrast only) ------
    t_series = est.treated_series
    naive_pre = list(range(max(0, start - 13), start))
    untreated = np.setdiff1d(np.arange(store_week.shape[0]), treated)
    naive = {
        "pre_post_no_control": _r(t_series[post].mean() / t_series[naive_pre].mean() - 1),
        "promoted_vs_unpromoted_stores": _r(T[:, post].sum(1).mean() / store_week[untreated][:, post].sum(1).mean() - 1),
    }

    # --- series for the counterfactual chart ----------------------------------
    lo_w = min(match.weeks + base.weeks)
    hi_w = min(end + DISPLAY_WEEKS_AFTER, ds.n_weeks - 1)
    weeks = list(range(lo_w, hi_w + 1))
    cf = est.counterfactual_series
    in_promo = np.array([w in post for w in weeks])
    band_lo = np.where(in_promo, cf[weeks] * (1 + est.uplift) / (1 + ci.uplift_high), np.nan)
    band_hi = np.where(in_promo, cf[weeks] * (1 + est.uplift) / (1 + ci.uplift_low), np.nan)
    excluded = dict(base.excluded)
    week_role = []
    for w in weeks:
        role = ("promo" if w in post else "baseline" if w in base.weeks
                else "excluded" if w in excluded else "match-only" if w in match.weeks else "other")
        week_role.append(role)

    significant = bool(ci.uplift_low > 0 or ci.uplift_high < 0)
    verdict = ("Significant uplift" if ci.uplift_low > 0 else
               "Significant decline" if ci.uplift_high < 0 else "No measurable effect")
    stores = ds.stores
    return {
        **header,
        "status": "ok",
        "uplift_pct": _r(est.uplift),
        "ci_low": _r(ci.uplift_low), "ci_high": _r(ci.uplift_high),
        "confidence_level": cfg["inference"]["confidence_level"],
        "p_value": _r(ci.p_value, 4), "significant": significant, "verdict": verdict,
        "actual_units": _r(est.actual_promo_units, 1),
        "counterfactual_units": _r(est.counterfactual_promo_units, 1),
        "incremental_units": _r(est.incremental_units, 1),
        "incremental_units_low": _r(ci.incremental_low, 1), "incremental_units_high": _r(ci.incremental_high, 1),
        "avg_promo_price": _r(asp, 4), "avg_unit_cost": _r(unit_cost, 4),
        "incremental_revenue": _r(inc_rev, 2), "incremental_margin": _r(inc_margin, 2),
        "roi": _r((inc_margin - funding) / funding, 4),
        "pre_period_mape": _r(pre_mape),
        "baseline_weeks": [ds.calendar["week_start"].iloc[w] for w in base.weeks],
        "excluded_weeks": [{"week": ds.calendar["week_start"].iloc[w], "reason": r} for w, r in base.excluded],
        "match_window": [ds.calendar["week_start"].iloc[match.weeks[0]], ds.calendar["week_start"].iloc[match.weeks[-1]]],
        "control_strategy": ctrl.strategy, "control_candidates": int(ctrl.candidates),
        "treated_stores": [_store(stores, i) for i in treated],
        "control_stores": [{**_store(stores, j), "times_used": int((ctrl.weights[:, j] > 0).sum())}
                           for j in ctrl.control_idx],
        "pairs": [{
            "treated": _store(stores, pr["treated"]),
            "controls": [{**_store(stores, j), "match_score": _r(sc, 4)} for j, sc in zip(pr["controls"], pr["scores"])][:5],
            "n_controls": len(pr["controls"]), "fallback": pr["fallback"], "match_level": pr["match_level"],
            "actual_promo_units": _r(est.store_actual_promo[i], 1),
            "counterfactual_promo_units": _r(est.store_cf_promo[i], 1),
            "uplift_pct": _r(est.store_actual_promo[i] / est.store_cf_promo[i] - 1),
        } for i, pr in enumerate(ctrl.pairs)],
        "naive_estimates": naive,
        "bootstrap_draws": [_r(x, 5) for x in np.sort(ci.draws)[:: max(1, len(ci.draws) // 200)]],
        "series": {
            "weeks": [ds.calendar["week_start"].iloc[w] for w in weeks],
            "role": week_role,
            "actual": [_r(x, 1) for x in est.treated_series[weeks]],
            "counterfactual": [_r(x, 1) for x in cf[weeks]],
            "band_low": [None if np.isnan(x) else _r(x, 1) for x in band_lo],
            "band_high": [None if np.isnan(x) else _r(x, 1) for x in band_hi],
            "holiday": [bool(ds.calendar["is_holiday_week"].iloc[w]) for w in weeks],
        },
    }


def attribute_all(ds: Dataset, cfg: dict) -> list[dict]:
    return [attribute_promo(ds, pid, cfg) for pid in ds.promotions["promo_id"]]


FINGERPRINT_KEYS = ("promo_id", "status", "uplift_pct", "ci_low", "ci_high", "p_value",
                    "incremental_units", "pairs", "baseline_weeks",
                    "method_version", "config_hash", "data_hash")


def fingerprint(results: list[dict]) -> str:
    """SHA-256 of every reported number - identical runs must give identical fingerprints."""
    core = [{k: r.get(k) for k in FINGERPRINT_KEYS} for r in results]
    return hashlib.sha256(json.dumps(core, sort_keys=True, default=str).encode()).hexdigest()
