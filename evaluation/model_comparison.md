# Customer Churn Model Comparison

**Protocol:** Phase 3 (2026-10-06) -- model selection by cross-validation on the training portion only, then one frozen evaluation of the selected model and a naive baseline on the untouched holdout.

This supersedes the earlier single-split comparison, which used the same holdout to select and to score its winner. That result is archived as historical evidence in [`legacy/`](legacy/README.md); its ROC AUC of 0.8494 is not an untouched final estimate and is **not comparable** to the values below.

## Protocol

- **Target:** `churn_value` (0/1), from the `customers` table.
- **Input:** `data/raw/telco_churn_raw.csv`, SHA-256 `e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34` (7,043 rows, loaded through the ETL pipeline into SQLite).
- **Excluded inputs (identifiers, geography, leakage):** `customer_id`, `country`, `state`, `city`, `zip_code`, `lat_long`, `latitude`, `longitude`, `churn_label`, `churn_reason`, `cltv`, `churn_score`. The outcome-derived columns were removed during Issue #14 (see `README.md` and `dashboard/business_report.md`).
- **Engineered features:** `TenureBucket`, `TotalServicesCount`, `AvgMonthlySpend` (`training/feature_engineering.py`); the preprocessor one-hot-encodes categoricals and passes numerics through.
- **Outer split:** stratified 80/20, `random_state=42` -- the training portion is used for selection and refit, the 20% holdout is scored once, after the winner is frozen.
- **Selection:** 5-fold `StratifiedKFold(shuffle=True, random_state=42)` over the training portion only; criterion is the mean fold ROC AUC (`roc_auc`), the same criterion the earlier comparison used, now applied where it cannot see the holdout. Preprocessing is refit inside every fold.
- **Candidates:** Logistic Regression (`max_iter=1000`), Decision Tree, Random Forest, XGBoost (`eval_metric="logloss"`) and LightGBM -- all `random_state=42`, default hyperparameters, no tuning.
- **Baseline:** `DummyClassifier(strategy="prior")`, scored on the same folds. It is reported for reference and is never eligible for selection.
- **Environment:** Python 3.11.2, pandas 3.0.6, numpy 2.4.6, scikit-learn 1.9.1, xgboost 3.2.0, lightgbm 4.7.0.

## Selected Model

**Logistic Regression**

### Performance (untouched holdout, evaluated once)

- Accuracy: 0.7991
- Precision: 0.6435
- Recall: 0.5455
- ROC AUC: 0.8496
- Confusion Matrix: [[922, 113], [170, 204]] (TN, FP, FN, TP)

### Baseline on the same holdout

| model_name                 |   accuracy |   precision |   recall |   roc_auc | confusion_matrix         |
|:---------------------------|-----------:|------------:|---------:|----------:|:-------------------------|
| Logistic Regression        |   0.799148 |    0.643533 | 0.545455 |  0.849562 | [[922, 113], [170, 204]] |
| DummyClassifier (baseline) |   0.734564 |    0        | 0        |  0.5      | [[1035, 0], [374, 0]]    |

The baseline predicts the training class prior for every row, so it never predicts churn: its precision and recall are 0 by construction, its accuracy is the majority-class share, and its ROC AUC is 0.5. It is the floor the selected model has to beat -- the model must be better than always guessing the majority class.

## Model selection (5-fold cross-validation, training portion only)

| model_name                 |   accuracy |   precision |   recall |   roc_auc |   roc_auc_std | confusion_matrix          |
|:---------------------------|-----------:|------------:|---------:|----------:|--------------:|:--------------------------|
| Logistic Regression        |   0.813278 |    0.67464  | 0.572575 |  0.859133 |    0.0142445  | [[3726, 413], [639, 856]] |
| Decision Tree              |   0.743522 |    0.515738 | 0.523077 |  0.673281 |    0.0227209  | [[3407, 732], [713, 782]] |
| Random Forest              |   0.7989   |    0.65395  | 0.51505  |  0.839627 |    0.00975799 | [[3731, 408], [725, 770]] |
| XGBoost                    |   0.784347 |    0.608426 | 0.528428 |  0.838703 |    0.00792188 | [[3629, 510], [705, 790]] |
| LightGBM                   |   0.796239 |    0.640393 | 0.529766 |  0.851774 |    0.00757808 | [[3694, 445], [703, 792]] |
| DummyClassifier (baseline) |   0.734647 |    0        | 0        |  0.5      |    0          | [[4139, 0], [1495, 0]]    |

Values are means over the five folds; confusion-matrix counts are summed across folds. `roc_auc_std` is the sample standard deviation of the fold ROC AUC values. Per-model fold ROC AUC, in fold order:

- Logistic Regression: 0.8615, 0.8386, 0.8517, 0.8707, 0.8732
- Decision Tree: 0.6766, 0.6778, 0.7004, 0.6373, 0.6744
- Random Forest: 0.8359, 0.8275, 0.8418, 0.8387, 0.8543
- XGBoost: 0.8342, 0.8272, 0.8420, 0.8432, 0.8469
- LightGBM: 0.8537, 0.8395, 0.8501, 0.8587, 0.8569
- DummyClassifier (baseline): 0.5000, 0.5000, 0.5000, 0.5000, 0.5000

`evaluation/model_comparison.csv` is generated from this table by `scripts/generate_model_comparison_csv.py`.

## Limits

- One outer split and one seed: the holdout is untouched by selection, but a single 1,409-row holdout gives a point estimate, not a confidence interval. Fold variation is reported above.
- The dataset is a static snapshot with no time index, so no temporal or out-of-time validation claim is possible.
- No hyperparameter search was performed (deliberately out of scope). The five definitions are defaults except `LogisticRegression(max_iter=1000)`.
- Logistic Regression does not converge within `max_iter=1000` on these unscaled one-hot features (`ConvergenceWarning` during training). Recorded as an open problem, not fixed here, because changing it would move the reported metrics.
- Class imbalance is handled by stratification only; no resampling, class weighting or threshold tuning is applied.
- Metrics come from a locally reconstructed dataset; see `docs/data_provenance.md` for the input's provenance and rights status.

## Reproduce

```bash
python database/init_db.py && python etl/load_to_db.py && python database/init_views.py
python training/evaluate_models.py
```

The pinned environment and the full command sequence are recorded in `docs/reproduction_record.md`.
