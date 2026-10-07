# Promotion attribution method

> The method is the deliverable as much as the number. Any change to it is
> version-bumped, logged in `CHANGELOG.md`, and must pass the recovery gate.

Settings live in `method_config.yaml`, the code in `attribution/`, and every
result is stamped with `method_version`, a config hash and a data hash.

## 1. The question

For a promotion *P* that ran on SKUs *K* in treated stores *S* during weeks *W*:

> How many units would *S* have sold of *K* during *W* if *P* had not run?

That quantity is the **counterfactual**. Everything else follows from it:

| Output | Definition |
|---|---|
| Uplift | actual units ÷ counterfactual units − 1 |
| Incremental units | actual units − counterfactual units |
| Incremental revenue | incremental units × average promo selling price |
| Incremental margin | incremental units × (promo price − unit cost) |
| ROI | (incremental margin − funding cost) ÷ funding cost |

Uplift is measured over the promotion weeks only, on the promoted SKUs in the
treated stores. Halo, cannibalisation of other SKUs, and post-promotion dips
are out of scope for v1.x.

## 2. Baseline definition (`attribution/baseline.py`)

The baseline is the set of pre-promotion weeks that represents normal trading.
It is chosen **by rule**, walking backwards from launch:

| Rule | Setting | Default | Why |
|---|---|---|---|
| B1 Skip a buffer before launch | `gap_weeks` | 1 | pantry de-loading and leaked announcements distort the week before |
| B2 Skip holiday weeks | `exclude_holiday_weeks` | true | holidays are not normal trading |
| B3 Skip weeks with another promotion on the same SKUs | `exclude_promo_weeks` | true | an earlier promotion inflates the baseline |
| B4 Stop at N valid weeks, or at the look-back limit | `pre_period_weeks`, `max_lookback_weeks` | 13, 30 | about one quarter of history |
| B5 Refuse if too few valid weeks | `min_valid_weeks` | 8 | no number is better than one built on a thin baseline |

Every excluded week is reported with its reason on the promotion page.

## 3. Control selection (`attribution/controls.py`)

Treated stores are rarely a random sample. They tend to be larger stores in
the region the category team cares about. Comparing them with "all other
stores" mostly measures store differences.

For **each treated store**:

1. Candidates are stores that did not run the promotion.
2. **Hard constraint:** candidates must share `exact_match_on` (default
   `format`, `region`). If fewer than `controls_per_treated` remain, the
   constraint is relaxed one attribute at a time (format + region → format →
   any). The level used is recorded and shown, and relaxed pairs are flagged.
3. **Trajectory match:** candidates are ranked by normalised RMSE between their
   weekly sales of the promoted SKUs and the treated store's sales over the
   `match_window_weeks` before launch (with the baseline exclusions applied).
4. The `controls_per_treated` closest candidates (default 3) become that
   store's controls. A control may serve several treated stores.

## 4. Uplift calculation (`attribution/uplift.py`)

The estimator is difference-in-differences in ratio form, computed per treated store *i*:

```
C_i(t)              = mean weekly units of store i's controls
scale_i             = T_i(baseline weeks) / C_i(baseline weeks)
counterfactual_i(t) = C_i(t) × scale_i
uplift              = Σ_i T_i(promo weeks) / Σ_i counterfactual_i(promo weeks) − 1
```

Anything that moves a treated store and its controls alike (seasonality,
holidays, trend, a market-wide shock) cancels in the ratio. A unit test checks
that a market-wide +50% shock during the promotion leaves the uplift unchanged.

## 5. Uncertainty (`attribution/uplift.py`)

The 95% interval comes from a two-stage store bootstrap with
`bootstrap_iterations` draws:

1. Each control store gets a Poisson(1) weight, because control noise shared by
   several treated stores must be counted once per store, not once per pair.
2. Treated stores are resampled with replacement, keeping their own
   counterfactual.

The percentile interval is reported. **Significant** means the interval
excludes zero. The bootstrap RNG is seeded from `inference.seed` plus the
promotion id, so intervals are reproducible and don't depend on run order.

## 6. Validation against synthetic ground truth (`attribution/validation.py`)

`data_gen/generate_data.py` builds a retail world with **planted** effects
(+4% to +30%, one 0%, one −6%) and deliberate traps: seasonality that differs
by format, trend that differs by region, non-random treatment, holidays, and
repeat promotions. The method runs blind. It passes when:

| Check | Criterion |
|---|---|
| V1 | every estimate is within `tolerance_pp` (2.0pp) of the planted effect |
| V2 | the 0% promotion is **not** called significant |
| V3 | at least `min_ci_coverage` (80%) of intervals contain the truth |
| V4 | two runs give the same result fingerprint |

**Stated tolerance: ±2.0 percentage points.** `scripts/calibrate_tolerance.py`
regenerates the world under 30 different seeds. Across those 360 estimates,
v1.2.0 had a median error of about 0.5pp, a 99th-percentile error of about
1.7pp, and 99% of estimates inside ±2.0pp. Mean CI coverage was about 95%.

## 7. Method-change gate (`attribution/gate.py`, `gate.py`, CI)

A method change merges only if, on the pinned reference data:

| Check | Criterion |
|---|---|
| G1 | recovery passes (V1 to V3) |
| G2 | two independent runs give the same fingerprint |
| G3 | `method_version` was bumped if any method setting changed |
| G4 | reference data matches the checksums in `data_manifest.json` |
| G5 | the proposal did not change the validation thresholds it is judged by |

The CI workflow runs the full test suite, a coverage floor on the baseline
module, and `python gate.py` on every pull request that touches the method.

## 8. Known limitations

- Effects are assumed multiplicative and constant within the promotion window.
- Controls can be contaminated by spill-over, such as shoppers switching stores.
  This is not modelled.
- If a format × region cell has fewer than three untreated stores, the
  constraint is relaxed and accuracy degrades. Such pairs are flagged on the
  promotion page. Keep holdout stores when planning promotions.
