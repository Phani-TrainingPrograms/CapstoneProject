# Method changelog

Every change to the attribution method (anything in `attribution/` or
`method_config.yaml` that can move a reported number) gets a version bump and
an entry here. The merge gate (`python gate.py`) checks that the version was
bumped and that the planted effects are still recovered.

## [1.2.0] - 2026-10-07
### Changed
- Control selection is now **per treated store**. Candidates must share
  `format` and `region` (`exact_match_on`); the constraint relaxes one
  attribute at a time only if fewer than `controls_per_treated` remain, and
  the level used is reported for every store.
- Inference is a **two-stage store bootstrap** (Poisson re-weighting of
  control stores + resampling of treated stores). v1.1 resampled treated
  stores only and its 95% intervals covered the planted effect ~75% of the
  time across 15 synthetic worlds; v1.2 covers ~95% (see
  `reports/tolerance_calibration.json`).
### Validation
- Reference data: 12/12 planted effects recovered, max error < 1pp.
- 30-world calibration: 99% of estimates within ±2.0pp.

## [1.1.0] - 2026-09-15
### Changed
- Replaced the single pooled control group with nearest-neighbour matching on
  normalised pre-period sales.
### Known issues (fixed in 1.2.0)
- Pooled matching failed recovery on 8/12 promos (max error 9.3pp): stores in
  a fast-growing region could only be matched to slower-growing stores.

## [1.0.0] - 2026-08-01
- First codified method: 13-week pre-period baseline, holiday and
  overlapping-promotion weeks excluded, difference-in-differences against all
  untreated stores. Replaced the per-analyst spreadsheets.
