"""Loading the input data into dense arrays the method works on."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Files the method is allowed to see. ground_truth_effects.csv is deliberately absent.
METHOD_INPUTS = ["stores.csv", "products.csv", "calendar.csv", "promotions.csv",
                 "promo_store_assignment.csv", "sales_weekly.csv"]


@dataclass
class Dataset:
    stores: pd.DataFrame
    products: pd.DataFrame
    calendar: pd.DataFrame
    promotions: pd.DataFrame
    assignment: pd.DataFrame
    units: np.ndarray          # (n_sku, n_store, n_week)
    revenue: np.ndarray        # (n_sku, n_store, n_week)
    data_hash: str
    data_dir: Path
    store_index: dict = field(default_factory=dict)
    sku_index: dict = field(default_factory=dict)

    @property
    def n_weeks(self) -> int:
        return self.units.shape[2]

    @property
    def holiday_weeks(self) -> set[int]:
        return set(self.calendar.index[self.calendar["is_holiday_week"] == 1].tolist())

    def promo(self, promo_id: str) -> pd.Series:
        rows = self.promotions[self.promotions["promo_id"] == promo_id]
        if rows.empty:
            raise KeyError(f"Unknown promo_id {promo_id}")
        return rows.iloc[0]

    def treated_store_idx(self, promo_id: str) -> np.ndarray:
        a = self.assignment
        ids = a[(a["promo_id"] == promo_id) & (a["is_treated"] == 1)]["store_id"]
        return np.array(sorted(self.store_index[s] for s in ids))

    def blocked_weeks(self, promo_id: str) -> set[int]:
        """Weeks in which ANOTHER promotion ran on any of this promo's SKUs."""
        me = self.promo(promo_id)
        my_skus = set(me["sku_list"])
        out: set[int] = set()
        for _, p in self.promotions.iterrows():
            if p["promo_id"] == promo_id or not (my_skus & set(p["sku_list"])):
                continue
            out.update(range(p["start_idx"], p["end_idx"] + 1))
        return out


def _hash_files(data_dir: Path) -> str:
    h = hashlib.sha256()
    for f in METHOD_INPUTS:
        h.update(f.encode())
        h.update((data_dir / f).read_bytes())
    return h.hexdigest()[:16]


@lru_cache(maxsize=4)
def load_dataset(data_dir: str | Path = DEFAULT_DATA_DIR) -> Dataset:
    data_dir = Path(data_dir)
    stores = pd.read_csv(data_dir / "stores.csv")
    products = pd.read_csv(data_dir / "products.csv")
    calendar = pd.read_csv(data_dir / "calendar.csv").set_index("week_idx", drop=False)
    promotions = pd.read_csv(data_dir / "promotions.csv")
    assignment = pd.read_csv(data_dir / "promo_store_assignment.csv")
    sales = pd.read_csv(data_dir / "sales_weekly.csv")

    week_index = {w: i for i, w in enumerate(calendar["week_start"])}
    store_index = {s: i for i, s in enumerate(stores["store_id"])}
    sku_index = {k: i for i, k in enumerate(products["sku_id"])}

    promotions["sku_list"] = promotions["sku_ids"].str.split("|")
    promotions["start_idx"] = promotions["start_week"].map(week_index)
    promotions["end_idx"] = promotions["end_week"].map(week_index)

    shape = (len(products), len(stores), len(calendar))
    k = sales["sku_id"].map(sku_index).to_numpy()
    s = sales["store_id"].map(store_index).to_numpy()
    w = sales["week_start"].map(week_index).to_numpy()
    units = np.zeros(shape)
    revenue = np.zeros(shape)
    units[k, s, w] = sales["units"].to_numpy()
    revenue[k, s, w] = sales["net_revenue"].to_numpy()

    return Dataset(stores=stores, products=products, calendar=calendar, promotions=promotions,
                   assignment=assignment, units=units, revenue=revenue,
                   data_hash=_hash_files(data_dir), data_dir=data_dir,
                   store_index=store_index, sku_index=sku_index)


def load_ground_truth(data_dir: str | Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Only the validation harness may call this - never the method."""
    return pd.read_csv(Path(data_dir) / "ground_truth_effects.csv")
