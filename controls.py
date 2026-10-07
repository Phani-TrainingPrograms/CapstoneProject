"""
CONTROL SELECTION  (METHOD.md section 3)

Candidates are stores that did NOT run the promotion. Each treated store gets
its own control set; the counterfactual for that store is the average of its
controls, scaled to the store's own baseline level (see uplift.py).

Strategies:
  matched        (default) For each treated store, restrict candidates to stores
                 with the same `exact_match_on` attributes (e.g. format), then
                 rank them by normalised RMSE between their weekly sales of the
                 promoted SKUs and the treated store's sales over the match
                 window. Keep the `controls_per_treated` closest. A control may
                 serve several treated stores. If fewer than the required
                 number share ALL the attributes, the constraint is relaxed
                 one attribute at a time from the right (format+region ->
                 format -> any) and the level used is recorded per store.
  all_untreated  Every untreated store, equally weighted, for every treated store.
  random         `controls_per_treated` untreated stores drawn with the method seed.
  none           No control group - the treated store's own baseline run-rate
                 is the counterfactual (the "spreadsheet" method).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

STRATEGIES = ("matched", "all_untreated", "random", "none")


@dataclass
class ControlSelection:
    strategy: str
    weights: np.ndarray                   # (n_treated, n_stores); each row sums to 1 (all-zero for 'none')
    pairs: list[dict] = field(default_factory=list)   # per treated store: controls + scores
    candidates: int = 0

    @property
    def control_idx(self) -> np.ndarray:
        return np.where(self.weights.sum(axis=0) > 0)[0]


def normalise(x: np.ndarray) -> np.ndarray:
    m = x.mean(axis=-1, keepdims=True)
    return x / np.where(m > 0, m, 1.0)


def match_scores(target: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    """Normalised RMSE between one target series (W,) and candidate series (n, W)."""
    return np.sqrt(((normalise(candidates) - normalise(target)) ** 2).mean(axis=-1))


def select_controls(store_week: np.ndarray, treated_idx: np.ndarray, match_weeks: list[int],
                    cfg: dict, rng: np.random.Generator, stores: pd.DataFrame | None = None) -> ControlSelection:
    strategy = cfg.get("strategy", "matched")
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown control strategy '{strategy}', expected one of {STRATEGIES}")
    n_stores = store_week.shape[0]
    candidates = np.setdiff1d(np.arange(n_stores), treated_idx)
    weights = np.zeros((len(treated_idx), n_stores))
    if strategy == "none":
        return ControlSelection(strategy, weights, [], len(candidates))
    if len(candidates) == 0:
        raise ValueError("no untreated stores available as controls")

    k = min(int(cfg.get("controls_per_treated", 3)), len(candidates))
    attrs = list(cfg.get("exact_match_on", []) or [])
    pairs = []
    for row, t in enumerate(treated_idx):
        pool, level = candidates, "any"
        if stores is not None:
            for n_attr in range(len(attrs), 0, -1):
                use = attrs[:n_attr]
                same = np.all([stores[a].to_numpy()[candidates] == stores[a].iloc[t] for a in use], axis=0)
                if same.sum() >= k:
                    pool, level = candidates[same], "+".join(use)
                    break
        scores = match_scores(store_week[t, match_weeks], store_week[pool][:, match_weeks])
        if strategy == "matched":
            pick = np.argsort(scores, kind="stable")[:k]
        elif strategy == "random":
            pick = np.sort(rng.choice(len(candidates), k, replace=False))
            pool = candidates
            scores = match_scores(store_week[t, match_weeks], store_week[pool][:, match_weeks])
        else:  # all_untreated
            pool = candidates
            scores = match_scores(store_week[t, match_weeks], store_week[pool][:, match_weeks])
            pick = np.arange(len(pool))
        chosen = pool[pick]
        weights[row, chosen] = 1.0 / len(chosen)
        pairs.append({"treated": int(t), "controls": chosen.tolist(),
                      "scores": scores[pick].tolist(),
                      "match_level": level if strategy == "matched" else strategy,
                      "fallback": strategy == "matched" and level != "+".join(attrs) and bool(attrs)})
    return ControlSelection(strategy, weights, pairs, len(candidates))
