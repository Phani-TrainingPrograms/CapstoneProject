# Promotion Performance Attribution

Promotion post-mortems get argued instead of measured. This project turns the
attribution into a **service**: the baseline definition, control selection and
uplift calculation are written into version-controlled code
(see [METHOD.md](METHOD.md)). Results are shown with the **counterfactual and
confidence interval**. The method is **validated against synthetic data with
planted effects**, and **merges are gated** on recovering them.

## Quick start

```bash
pip install -r requirements.txt
python data_gen/generate_data.py      # optional: data/ is already generated (deterministic)
python run.py                          # -> http://127.0.0.1:8000
```

Other entry points:

```bash
pytest --cov=attribution                                         # 89 tests: baseline, controls, recovery, reproducibility, gate, API, Ask eval set
python gate.py                                                   # gate the current method (exit 1 = BLOCK)
python gate.py --config configs/proposals/v1.3.0_match_on_format_only.yaml
python gate.py --all-proposals                                   # demo every proposed change
python scripts/calibrate_tolerance.py --seeds 30                 # is the ±2pp tolerance honest?
```

## Demo walkthrough (about 10 minutes)

| # | Page | What to show | Talking point |
|---|---|---|---|
| 1 | **Portfolio** | Forest plot: dot = uplift, whisker = 95% CI; hollow dot = spreadsheet answer | Every promo is measured the same way. P06 is "no measurable effect", not a win. |
| 2 | **Promotion deep-dive** → P09 | Actual vs counterfactual, shaded baseline / excluded / promo weeks, CI band | The holiday spike is in the counterfactual too, so it isn't credited to the promo. |
|   |  | "One promotion, three answers" | Pre/post says +25%, promoted-vs-unpromoted says +100%, the method says +18.6% (planted 18%). |
|   |  | Matched-pairs table | Every treated store is compared with same-format, same-region stores that tracked it before launch. |
| 2b | **Ask** | "How did P09 perform?" → "What about its ROI?" → click an **E1** citation | Plain-English answers, every number traced to evidence and checked: "15/15 numbers verified". |
| 3 | **The method** | METHOD.md, config, changelog, 100% baseline coverage, **Run test suite now** | The method is the deliverable: documented, versioned, tested. |
| 4 | **Ground-truth validation** | Planted (diamond) vs recovered (dot) within the ±2pp band; 30-world calibration | 12/12 recovered, max error < 1pp; the tolerance is calibrated, not hoped for. |
| 5 | **Reproducibility** | Run 5× → identical SHA-256 fingerprints | Same data + same method version = same number, whoever runs it. |
| 6 | **Method-change gate** | Run "Bootstrap 2000" → PASS; "Match on format only" → **BLOCKED** (2.6pp miss); "Use every untreated store" → BLOCKED | A reasonable-sounding change can't ship unmeasured. |
|   |  | "Build your own change" → set tolerance to 50 | G5 blocks a proposal that tries to loosen its own bar. |
| 7 | **Data** | Files, checksums, the traps, hidden ground truth | The synthetic world is built to make naive methods fail. |

Deep links: run a gate with `http://127.0.0.1:8000/#/gate/v1.3.0_all_untreated_controls.yaml`, or pre-ask questions with
`http://127.0.0.1:8000/#/ask/How did P09 perform?|What about its ROI?` (separate questions with `|`).

## Ask (grounded Q&A)

`app/ask.py` answers questions about promotions, rankings, mechanic and category averages, the method, validation and
the gate. It is **deterministic**: no AI model, so the same question always gets the same answer. Each answer:
- cites **evidence items** `[E1]`, `[E2]`, ... taken straight from the attribution results, the config, METHOD.md or the gate;
- passes a **number check**: every number in the text must match a number in its evidence, or a warning is shown;
- shows a **trace**: detected intent, resolved promotions (including follow-ups like "its ROI"), and the evidence count.

`tests/test_ask.py` is the evaluation set: 17 questions with expected intent, promotions and content, plus tests that
the number checker catches wrong numbers, money and dates.

## Success metrics: where each is demonstrated

| Metric | Evidence |
|---|---|
| Recovery of the planted effect within a stated tolerance | Validation page; `tests/test_recovery.py` (one test per promo, ±2.0pp); 30-world calibration in `reports/tolerance_calibration.json` (99% within ±2pp) |
| Baseline-definition test coverage | `tests/test_baseline.py` (rules B1 to B5); `attribution/baseline.py` at 100% line coverage, with a 95% floor enforced in CI |
| Reproducibility across runs | Reproducibility page; `tests/test_reproducibility.py` (repeat runs, fresh load, order independence, generator byte-for-byte) |
| Gate demonstration on a method change | Gate page; `gate.py`; `tests/test_gate_and_api.py`; `.github/workflows/method-gate.yml` |

## Project layout

```
attribution/            THE METHOD (version-controlled code)
  baseline.py           baseline definition, rules B1-B5
  controls.py           matched control selection
  uplift.py             DiD ratio estimator + two-stage store bootstrap
  engine.py             orchestration, provenance stamps, fingerprint
  validation.py         planted-effect recovery + reproducibility reports
  gate.py               merge-gate checks G1-G5
method_config.yaml      the method's settings (method_version 1.2.0)
METHOD.md, CHANGELOG.md method specification and history
configs/proposals/      five proposed method changes for the gate demo
data_gen/generate_data.py  synthetic world with planted effects (seeded)
data/                   generated CSVs + data_manifest.json (checksums)
app/                    FastAPI service + single-page UI (Plotly bundled, works offline)
  ask.py                grounded Q&A engine with evidence citations + number check
tests/                  pytest suite
gate.py                 gate CLI (exit 1 = BLOCK)
scripts/                tolerance calibration, coverage floor
.github/workflows/method-gate.yml   CI gate on every PR
```

## Data

| File | Rows | Contents |
|---|---|---|
| `stores.csv` | 100 | store_id, region, format, size, footfall index |
| `products.csv` | 40 | SKU, category, brand, base price, unit cost |
| `calendar.csv` | 104 | weeks Oct-2024 to Sep-2026, season, holiday flags |
| `promotions.csv` | 12 | mechanic, discount, SKUs, dates, funding cost |
| `promo_store_assignment.csv` | 1,200 | which stores ran each promotion |
| `sales_weekly.csv` | 416,000 | store × SKU × week units, revenue, price, promo flag |
| `ground_truth_effects.csv` | 12 | **planted** uplift per promo (hidden from the method) |
| `data_manifest.json` | – | seed, generator parameters, SHA-256 per file |
