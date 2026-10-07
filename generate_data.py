"""
Synthetic retail data generator with PLANTED promotion effects.

Every number this script writes is a deterministic function of SEED, so the
data set itself is reproducible and its checksum is recorded in
data/data_manifest.json.

Demand model (per store s, SKU k, week t):

    mean[s,k,t] = base[k] * format_scale[s] * store_level[s]
                  * trend[s](t) * store_season[s](t) * category_season[k](t)
                  * holiday[k](t) * store_week_shock[s,t]
                  * (1 + planted_effect)   <- only for treated store x SKU x promo weeks
    units ~ Poisson(mean)

Deliberate traps for a weak method:
  * Seasonality amplitude differs by store FORMAT and trend differs by REGION,
    so stores are NOT interchangeable as controls.
  * Treated stores are skewed toward Hyper stores in a promo's favoured region,
    so "all untreated stores" is a biased control group and a naive
    promoted-vs-not comparison mostly measures store size.
  * A holdout rule keeps >= 3 untreated stores in every format x region cell,
    as a retailer running test-and-control would.
  * Holiday weeks, overlapping promotions on the same SKUs, a NULL promo (0%)
    and a NEGATIVE promo (-6%) are included.

Run:  python data_gen/generate_data.py  [--out data] [--seed 20261007]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261007
N_WEEKS = 104
START = date(2024, 10, 7)  # a Monday
N_STORES = 100

REGIONS = ["North", "South", "East", "West"]
REGION_TREND_PER_YEAR = {"North": 0.10, "South": -0.06, "East": 0.03, "West": 0.0}
REGION_SEASON_PHASE = {"North": 0.0, "South": 0.6, "East": 0.3, "West": -0.3}
FORMATS = ["Hyper", "Super", "Express"]
FORMAT_PROBS = [0.30, 0.45, 0.25]
FORMAT_SCALE = {"Hyper": 2.2, "Super": 1.0, "Express": 0.4}
FORMAT_SEASON_AMP = {"Hyper": 0.18, "Super": 0.07, "Express": -0.06}
FORMAT_SQFT = {"Hyper": (80_000, 120_000), "Super": (30_000, 50_000), "Express": (5_000, 10_000)}
STORE_WEEK_SHOCK_SD = 0.02

CATEGORIES = {
    # category: (subcategory, brands, base price range, seasonal amp, peak week-of-year)
    "Coffee": ("Ground Coffee", ["Bean & Co", "Morning Ritual"], (6.5, 11.0), 0.05, 2),
    "Personal Care": ("Shampoo", ["Silkara", "PureRoot"], (4.0, 8.5), 0.02, 26),
    "Beverages": ("Soda", ["FizzUp", "Cola Royale"], (1.5, 3.0), 0.20, 28),
    "Snacks": ("Potato Chips", ["CrunchCo", "Golden Crisp"], (2.0, 4.0), 0.06, 30),
    "Breakfast": ("Cereal", ["SunGrain", "OatHarvest"], (3.5, 6.0), 0.04, 36),
    "Home Care": ("Detergent", ["CleanWave", "Brightex"], (7.0, 14.0), 0.02, 10),
    "Dairy": ("Yogurt", ["Alpine Farms", "CreamyCo"], (1.0, 2.5), 0.05, 24),
    "Confectionery": ("Chocolate", ["CocoaJoy", "Velvetta"], (2.5, 5.0), 0.08, 50),
    "Pantry": ("Pasta", ["Nonna's", "Durum Gold"], (1.2, 2.8), 0.04, 45),
    "Frozen": ("Frozen Pizza", ["Pizzeria Uno-Mas", "OvenStar"], (4.5, 8.0), 0.10, 2),
}
SKUS_PER_CATEGORY = 4

HOLIDAY_LIFT = {
    "Thanksgiving / Black Friday": 1.30,
    "Christmas": 1.40,
    "New Year": 1.12,
    "Easter": 1.12,
    "Independence Day": 1.10,
    "Labor Day": 1.06,
}
EASTER = {2025: date(2025, 4, 20), 2026: date(2026, 4, 5)}

# The planted ground truth. true_uplift is a multiplicative effect on units
# in treated stores x promo SKUs x promo weeks (week indices are 0-based).
PROMOS = [
    # id,  name,                               category,        mechanic,  disc, start, weeks, true, favoured region, funding
    ("P01", "Spring Coffee Feature Display",     "Coffee",        "Display", 0.00, 28, 4, 0.08, "North", 9_000),
    ("P02", "Shampoo 10% Off",                   "Personal Care", "TPR",     0.10, 30, 5, 0.04, "East", 6_000),
    ("P03", "Summer Soda 20% Off",               "Beverages",     "TPR",     0.20, 36, 6, 0.22, "North", 8_000),
    ("P04", "Chips Buy-One-Get-One",             "Snacks",        "BOGO",    0.50, 38, 4, 0.30, "West", 15_000),
    ("P05", "Breakfast Bundle Deal",             "Breakfast",     "Bundle",  0.15, 44, 5, 0.12, "North", 6_000),
    ("P06", "Detergent Loyalty Points",          "Home Care",     "Loyalty", 0.00, 46, 6, 0.00, "South", 4_000),
    ("P07", "Yogurt 15% Off",                    "Dairy",         "TPR",     0.15, 50, 5, 0.15, "North", 4_000),
    ("P08", "Snacks Endcap Relocation",          "Snacks",        "Display", 0.00, 54, 6, -0.06, "East", 3_000),
    ("P09", "Holiday Chocolate Gifting",         "Confectionery", "TPR",     0.20, 60, 5, 0.18, "North", 7_000),
    ("P10", "Yogurt 10% Off (Repeat)",           "Dairy",         "TPR",     0.10, 66, 5, 0.10, "West", 5_000),
    ("P11", "Pasta Pantry Saver",                "Pantry",        "TPR",     0.10, 72, 5, 0.05, "South", 2_500),
    ("P12", "Frozen Pizza Buy-One-Get-One",      "Frozen",        "BOGO",    0.50, 80, 6, 0.25, "North", 12_000),
]
N_TREATED = 15
MIN_HOLDOUT = 3   # business rule: >= 3 untreated stores per format x region cell


def _week_starts() -> list[date]:
    return [START + timedelta(weeks=i) for i in range(N_WEEKS)]


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(weeks=n - 1)


def _holiday_dates(year: int) -> dict[str, date]:
    out = {
        "Thanksgiving / Black Friday": _nth_weekday(year, 11, 3, 4),
        "Christmas": date(year, 12, 25),
        "New Year": date(year, 1, 1),
        "Independence Day": date(year, 7, 4),
        "Labor Day": _nth_weekday(year, 9, 0, 1),
    }
    if year in EASTER:
        out["Easter"] = EASTER[year]
    return out


def build_calendar() -> pd.DataFrame:
    weeks = _week_starts()
    holidays = {}
    for y in range(START.year, weeks[-1].year + 2):
        for name, d in _holiday_dates(y).items():
            holidays[d] = name
    rows = []
    for i, ws in enumerate(weeks):
        event = ""
        for d, name in holidays.items():
            if ws <= d < ws + timedelta(days=7):
                event = name
        m = ws.month
        season = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
                  6: "Summer", 7: "Summer", 8: "Summer"}.get(m, "Autumn")
        rows.append({
            "week_idx": i,
            "week_start": ws.isoformat(),
            "iso_week": ws.isocalendar()[1],
            "year": ws.year,
            "fiscal_period": f"FY{ws.year if m >= 10 else ws.year - 1}-P{((m - 10) % 12) + 1:02d}",
            "season": season,
            "is_holiday_week": int(bool(event)),
            "event_name": event,
        })
    return pd.DataFrame(rows)


def build_stores(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for i in range(N_STORES):
        region = REGIONS[i % 4]
        fmt = rng.choice(FORMATS, p=FORMAT_PROBS)
        lo, hi = FORMAT_SQFT[fmt]
        rows.append({
            "store_id": f"S{i + 1:03d}",
            "store_name": f"{region} {fmt} #{i + 1}",
            "region": region,
            "format": fmt,
            "size_sqft": int(rng.integers(lo, hi)),
            "footfall_index": round(float(FORMAT_SCALE[fmt] * rng.lognormal(0, 0.1)), 3),
            "open_year": int(rng.integers(1995, 2021)),
        })
    return pd.DataFrame(rows)


def build_products(rng: np.random.Generator) -> pd.DataFrame:
    rows, n = [], 1
    for cat, (sub, brands, (plo, phi), _, _) in CATEGORIES.items():
        for j in range(SKUS_PER_CATEGORY):
            brand = brands[j % len(brands)]
            price = round(float(rng.uniform(plo, phi)), 2)
            rows.append({
                "sku_id": f"K{n:03d}",
                "sku_name": f"{brand} {sub} {['Classic', 'Lite', 'Family Pack', 'Premium'][j]}",
                "category": cat,
                "subcategory": sub,
                "brand": brand,
                "base_price": price,
                "unit_cost": round(price * float(rng.uniform(0.55, 0.7)), 2),
            })
            n += 1
    return pd.DataFrame(rows)


def _assign_treated(stores: pd.DataFrame, w: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Weighted (non-random!) selection of treated stores under a holdout rule:
    every format x region cell keeps at least MIN_HOLDOUT untreated stores."""
    cell = (stores["format"] + "|" + stores["region"]).to_numpy()
    untreated_left = pd.Series(cell).value_counts().to_dict()
    chosen = []
    for s in rng.choice(len(stores), len(stores), replace=False, p=w / w.sum()):
        if untreated_left[cell[s]] - 1 >= MIN_HOLDOUT:
            chosen.append(s)
            untreated_left[cell[s]] -= 1
        if len(chosen) == N_TREATED:
            break
    return np.sort(np.array(chosen))


def generate(out_dir: Path, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    calendar = build_calendar()
    stores = build_stores(rng)
    products = build_products(rng)
    n_s, n_k, n_w = len(stores), len(products), N_WEEKS
    t = np.arange(n_w)
    iso = calendar["iso_week"].to_numpy()

    # --- store-level structure --------------------------------------------
    store_level = rng.lognormal(0, 0.15, n_s)
    fmt_scale = stores["format"].map(FORMAT_SCALE).to_numpy()
    trend_rate = stores["region"].map(REGION_TREND_PER_YEAR).to_numpy() + rng.normal(0, 0.015, n_s)
    trend = (1 + trend_rate[:, None]) ** (t[None, :] / 52.0)                       # (S, W)
    amp = stores["format"].map(FORMAT_SEASON_AMP).to_numpy()
    phase = stores["region"].map(REGION_SEASON_PHASE).to_numpy()
    store_season = 1 + amp[:, None] * np.sin(2 * np.pi * (iso[None, :] - 13) / 52 + phase[:, None])
    shock = rng.lognormal(-STORE_WEEK_SHOCK_SD ** 2 / 2, STORE_WEEK_SHOCK_SD, (n_s, n_w))
    store_week = store_level[:, None] * fmt_scale[:, None] * trend * store_season * shock   # (S, W)

    # --- SKU-level structure (common to all stores) -------------------------
    base = rng.uniform(100, 200, n_k)
    cat_amp = products["category"].map({c: v[3] for c, v in CATEGORIES.items()}).to_numpy()
    cat_peak = products["category"].map({c: v[4] for c, v in CATEGORIES.items()}).to_numpy()
    cat_season = 1 + cat_amp[:, None] * np.cos(2 * np.pi * (iso[None, :] - cat_peak[:, None]) / 52)
    hol = calendar["event_name"].map(lambda e: HOLIDAY_LIFT.get(e, 1.0)).to_numpy()
    hol_k = np.tile(hol, (n_k, 1))
    choc = (products["category"] == "Confectionery").to_numpy()
    xmas = (calendar["event_name"] == "Christmas").to_numpy()
    hol_k[np.ix_(choc, xmas)] *= 1.25                                   # chocolate gifting spike
    sku_week = base[:, None] * cat_season * hol_k                       # (K, W)

    mean = sku_week[:, None, :] * store_week[None, :, :]                # (K, S, W)
    counterfactual_mean = mean.copy()

    # --- promotions with planted effects -----------------------------------
    promo_rows, assign_rows, truth_rows = [], [], []
    on_promo = np.zeros((n_k, n_s, n_w), dtype=bool)
    discount = np.zeros((n_k, n_s, n_w))
    for pid, name, cat, mech, disc, start, weeks, effect, fav_region, funding in PROMOS:
        sku_idx = np.where(products["category"] == cat)[0]
        w = stores["format"].map({"Hyper": 4.0, "Super": 1.5, "Express": 0.5}).to_numpy()
        w = w * np.where(stores["region"] == fav_region, 2.5, 1.0)
        treated = _assign_treated(stores, w, rng)
        weeks_idx = np.arange(start, start + weeks)
        cell = np.ix_(sku_idx, treated, weeks_idx)
        mean[cell] *= (1 + effect)
        on_promo[cell] = True
        discount[cell] = disc
        expected_incr = float((mean[cell] - counterfactual_mean[cell]).sum())
        promo_rows.append({
            "promo_id": pid, "promo_name": name, "category": cat, "mechanic": mech,
            "discount_pct": disc, "sku_ids": "|".join(products["sku_id"].iloc[sku_idx]),
            "start_week": calendar["week_start"].iloc[start],
            "end_week": calendar["week_start"].iloc[start + weeks - 1],
            "duration_weeks": weeks, "funding_cost": funding,
            "owner": ["Category Mgmt", "Trade Marketing", "Shopper Marketing"][int(pid[1:]) % 3],
        })
        tset = set(treated.tolist())
        for s in range(n_s):
            assign_rows.append({"promo_id": pid, "store_id": stores["store_id"].iloc[s],
                                "is_treated": int(s in tset)})
        truth_rows.append({
            "promo_id": pid, "true_uplift_pct": effect,
            "expected_incremental_units": round(expected_incr, 1),
            "scenario": ("null effect - must NOT be called significant" if effect == 0 else
                         "negative effect (cannibalisation)" if effect < 0 else
                         "weak effect - sensitivity check" if effect < 0.06 else
                         "holiday-window promo" if pid == "P09" else
                         "repeat promo - baseline overlaps earlier promo" if pid == "P10" else
                         "standard positive effect"),
        })

    units = rng.poisson(mean)

    # --- assemble long table -----------------------------------------------
    K, S, W = np.meshgrid(np.arange(n_k), np.arange(n_s), np.arange(n_w), indexing="ij")
    price = products["base_price"].to_numpy()[K] * (1 - discount)
    # BOGO is recorded as 50% effective price; small everyday price noise otherwise
    price = price * np.where(on_promo, 1.0, rng.normal(1.0, 0.01, price.shape))
    sales = pd.DataFrame({
        "week_start": calendar["week_start"].to_numpy()[W.ravel()],
        "store_id": stores["store_id"].to_numpy()[S.ravel()],
        "sku_id": products["sku_id"].to_numpy()[K.ravel()],
        "units": units.ravel(),
        "avg_selling_price": np.round(price.ravel(), 2),
        "on_promo": on_promo.ravel().astype(int),
    })
    sales["net_revenue"] = np.round(sales["units"] * sales["avg_selling_price"], 2)
    sales = sales[["week_start", "store_id", "sku_id", "units", "net_revenue",
                   "avg_selling_price", "on_promo"]].sort_values(["week_start", "store_id", "sku_id"])

    files = {
        "stores.csv": stores,
        "products.csv": products,
        "calendar.csv": calendar,
        "promotions.csv": pd.DataFrame(promo_rows),
        "promo_store_assignment.csv": pd.DataFrame(assign_rows),
        "sales_weekly.csv": sales,
        "ground_truth_effects.csv": pd.DataFrame(truth_rows),
    }
    checksums = {}
    for fname, df in files.items():
        path = out_dir / fname
        df.to_csv(path, index=False, lineterminator="\n")
        checksums[fname] = hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "generator": "data_gen/generate_data.py",
        "seed": seed,
        "n_stores": n_s, "n_skus": n_k, "n_weeks": n_w,
        "first_week": calendar["week_start"].iloc[0], "last_week": calendar["week_start"].iloc[-1],
        "rows_sales_weekly": len(sales),
        "parameters": {
            "region_trend_per_year": REGION_TREND_PER_YEAR,
            "format_season_amplitude": FORMAT_SEASON_AMP,
            "format_scale": FORMAT_SCALE,
            "holiday_lift": HOLIDAY_LIFT,
            "store_week_shock_sd": STORE_WEEK_SHOCK_SD,
            "treated_stores_per_promo": N_TREATED,
            "min_holdout_per_format_region": MIN_HOLDOUT,
        },
        "hidden_from_method": ["ground_truth_effects.csv"],
        "sha256": checksums,
    }
    (out_dir / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data"))
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    m = generate(Path(a.out), a.seed)
    print(f"Wrote {len(m['sha256'])} files to {a.out}  ({m['rows_sales_weekly']:,} sales rows, seed={m['seed']})")
