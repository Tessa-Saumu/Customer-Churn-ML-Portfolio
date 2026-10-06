# Legacy evaluation archive — historical, do not present as current

These two files are **byte-identical copies** of the model comparison that this
repository published before Phase 2 (2026-10-05). They are kept so the original
result stays recoverable and comparable, exactly as `FLAGSHIP_IMPLEMENTATION_PLAN.md`'s
metric-preservation rule requires.

| File | Copied from | SHA-256 |
|---|---|---|
| `model_comparison_single_split.md` | `evaluation/model_comparison.md` | `a976bb7b75f47a45bf59856c0d8d3c4fcd79700127bf34ff8c3f7ea82073bcf3` |
| `model_comparison_single_split.csv` | `evaluation/model_comparison.csv` | `04d35816cc5300ee7dad379ed69874b13a2bfe253e28550009cc0fd4247053af` |

`tests/test_reproducibility.py::TestMetricsArtifacts` fails if the tracked files
ever stop matching these copies, so the archive cannot drift out of sync silently.

## Protocol that produced these numbers (why they are labelled historical)

- **Single** stratified 80/20 train/test split (`training/train_test_split.py`:
  `TEST_SIZE = 0.2`, `RANDOM_STATE = 42`, `stratify=y`) → 5,634 training rows,
  1,409 test rows.
- Five candidates (Logistic Regression, Decision Tree, Random Forest, XGBoost,
  LightGBM), default hyperparameters except `LogisticRegression(max_iter=1000)`,
  all with `random_state=42`.
- Winner selected by **ROC AUC on that same held-out test set** — so the test set
  was used for model selection and is *not* an untouched final estimate.
- **No baseline** (no majority/prior classifier) is reported.
- Leakage-free: `churn_score`, `churn_reason`, `cltv`, identifiers and geography
  are excluded by `training/preprocessing.py` (the correction documented in
  `README.md` and `dashboard/business_report.md`).
- The dataset is a static snapshot with no time index, so no temporal validation
  claim is possible.

## Source revision and environment

- **Bytes taken from:** commit `b86c1b9dc68a3f8dafbf7df14fcbb3f13c78bcec` of this
  portfolio repository (the base of the Phase 1/Phase 2 work). This checkout is
  shallow, so the upstream commit that last regenerated these exact bytes cannot be
  confirmed locally; `PROJECT_EVIDENCE_CHURN.md` attributes the leakage-free rerun to
  `c2ea20e` (2026-07-24) in the original team repository.
- **Environment: unknown and unpinned.** These values were produced before
  dependencies were pinned. That matters: the same protocol in the pinned
  environment gives Logistic Regression accuracy 0.799148 / ROC AUC 0.849562 rather
  than 0.801987 / 0.849448 — see
  [`../reproduction/2026-10-05-pinned-single-split/`](../reproduction/2026-10-05-pinned-single-split/)
  and [`../../docs/reproduction_record.md`](../../docs/reproduction_record.md).
- The fitted model pickle these numbers came from was **never committed**
  (`models/` is gitignored). Do not claim the historical binary was preserved; only
  its reported metrics were.

## Status

Historical evidence of the leakage-corrected, single-split comparison. It is no
longer what `/model-metrics` serves.

**Superseded on 2026-10-06 by Phase 3** (audit item FGA-05), which implemented the
protocol this archive's description says it lacked: a naive baseline, model
selection by training-side cross-validation, and one frozen final estimate on the
untouched holdout. `evaluation/model_comparison.md` is now that protocol's output
(Logistic Regression, untouched-holdout ROC AUC 0.8496 / accuracy 0.7991; the naive
prior baseline reaches ROC AUC 0.5), and `README.md` quotes the new numbers. The
bytes here are unchanged and stay frozen: they are the predecessor result, useful
for showing exactly what the old selection bias consisted of, and `tests/test_reproducibility.py::TestMetricsArtifacts`
asserts they keep their recorded hashes. Do not present them as a current estimate
or compare them directly with the new protocol's numbers.

The `evaluation/reproduction/2026-10-05-pinned-single-split/` folder remains as the
pinned re-run of *this* protocol; the Phase 3 protocol's run log lives in
`evaluation/reproduction/2026-10-06-phase3-cv-holdout/`.
