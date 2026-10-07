Part (a): Data needed for the Promotion Attribution demo
The workspace is empty. Python 3.13 and git are installed, but Node is not, so I'll build everything in Python.

What the demo has to prove, and the data each claim needs
Claim the demo makes	Data it needs
Uplift is measured against a fixed, agreed baseline	Sales history from before each promotion (the pre-period)
Control selection with a counterfactual	Stores that didn't run the promo, plus store attributes to match on
A confidence interval (CI), not just a headline number	Sales at store level, so there's real variance to bootstrap from
The service recovers a planted effect within a tolerance	A hidden ground-truth file holding the true uplift we inserted
The method isn't fooled by other things that move sales	Seasonality, trend, holidays and noise built into the sales data
Synthetic data files (in data/)
stores.csv (about 60 rows): store_id, store_name, region, format (Hyper/Super/Express), size_sqft, footfall_index, open_year. Used to match control stores.
products.csv (about 40 SKUs): sku_id, sku_name, category, subcategory, brand, base_price, unit_cost.
calendar.csv (104 weeks over 2 years): week_start, week_no, fiscal_period, season, is_holiday_week, event_name. Used so baselines aren't distorted by holidays.
sales_weekly.csv (about 250k rows), one row per store × SKU × week: week_start, store_id, sku_id, units, net_revenue, avg_selling_price, on_promo.
Built from a base level × trend × seasonality × holiday lift × store effect × random noise, with the promo effect added only for treated store-SKU-weeks.
promotions.csv (about 12 promos): promo_id, promo_name, mechanic (TPR / BOGO / Display / Bundle), discount_pct, sku_ids, start_week, end_week, funding_cost, owner.
promo_store_assignment.csv: promo_id, store_id, is_treated. Says which stores ran each promo. Treated stores are deliberately not a random sample (they skew to large stores), so a naive comparison gives the wrong answer and careful control selection is needed to get the right one.
ground_truth_effects.csv, kept hidden from the method: promo_id, true_uplift_pct, true_incremental_units. It deliberately includes:
strong positive promos (+15–30%)
weak ones (+3–5%), to test sensitivity
one null promo (0%), where the service must report "not significant"
one negative promo that cannibalised sales
data_manifest.json: the generator seed, parameters and a file checksum, so anyone can regenerate the exact same data.
The method's settings (pre-period length, control-matching rule, number of controls, bootstrap count, seed) will go in a version-controlled method_config.yaml rather than in the data.

Part (b): Planned build
Stack: a Python FastAPI service that runs the attribution and also serves a single-page web UI (Plotly charts loaded from a CDN). It starts with one command and needs no Node.

The method, as documented and versioned code (attribution/):

Baseline: pre-period run-rate, adjusted for seasonality using the calendar.
Control selection: among untreated stores, rank by how closely their pre-period sales track the treated stores (correlation and distance), then keep the top k.
Uplift: difference-in-differences (treated vs control, before vs during), plus the counterfactual series.
Confidence interval: a bootstrap over stores with a fixed seed.
Every result is stamped with method_version and a hash of the config.
Tests and the merge gate:

Unit tests for the baseline definition (holiday exclusion, window edges, empty pre-period), with a coverage report.
A recovery test: every planted effect must be recovered within ±2 percentage points and fall inside the 95% CI, and the null promo must come out not significant.
A reproducibility test: running N times must give identical results and an identical output hash.
A merge gate: a GitHub Actions workflow plus a local gate.py script. I'll include a deliberately broken method change, such as dropping control selection, so you can watch the gate fail and block it.
UI pages:

Portfolio: all promos with their uplift, CI, significance and ROI.
Promo deep-dive: actual vs counterfactual chart, CI band, the chosen control stores, pre-period fit quality and incremental units/revenue.
Method: the baseline, control and uplift definitions, current version and changelog.
Validation: planted vs recovered effect for each promo, with the tolerance band and pass/fail.
Reproducibility: run it N times live and show the identical hashes.
Method-change gate: compare the current method with a proposed change and get a gate verdict.