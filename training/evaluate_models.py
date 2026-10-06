"""
Model evaluation protocol (Phase 3, audit item FGA-05).

What changed and why
--------------------
Until 2026-10-06 this module trained all five candidates on one stratified
80/20 split and selected the winner on **that same held-out test set**
(`sort_values("roc_auc").iloc[0]`). The audit recorded the consequence: the
reported "test" metric was also the selection metric, so it was not an
untouched final estimate, and no baseline was ever reported.

The protocol implemented here is the one FLAGSHIP_IMPLEMENTATION_PLAN.md
Phase 3 prescribes:

1. One fixed stratified 80/20 outer split (`training/train_test_split.py`,
   `RANDOM_STATE = 42`). The 20% holdout is *frozen*: it is not touched until
   the winner has been chosen and refitted.
2. Model selection runs only on the 80% training portion, as 5-fold
   `StratifiedKFold` with a fixed seed and the existing criterion, mean ROC AUC
   over folds. The incumbent Logistic Regression competes against the other four
   candidates in exactly the same folds.
3. A `DummyClassifier(strategy="prior")` baseline is scored on the same folds
   so the comparison has a floor. It is *reported*, never selected.
4. The winning candidate is refitted on the full training portion, and only
   then are the selected model and the baseline evaluated -- once -- on the
   untouched holdout.

No model family, hyperparameter or threshold was added or tuned. The five
candidate definitions are unchanged, and so is the public API contract
(`models/best_model.pkl` is still a fitted `Pipeline` used by `predict.py`).

Metric preservation (plan rule): the earlier single-split comparison is a
different protocol and is archived, byte-identical, in `evaluation/legacy/`.
Its ROC AUC (0.8494) is not comparable to the numbers this protocol reports.
"""

import hashlib
import logging
import platform
import statistics
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from sklearn.base import ClassifierMixin, clone

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from typing import Any
import pandas as pd
import joblib
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.model_selection import StratifiedKFold

from training.train_models import (
    BASELINE_MODEL_NAME,
    build_baseline_model,
    build_candidate_models,
    build_pipeline,
)
from training.train_test_split import RANDOM_STATE, split_training_data

# Set up logging
logger = logging.getLogger(__name__)
# Model directory
MODEL_PATH = REPO_ROOT / "models"
MODEL_PATH.mkdir(parents=True, exist_ok=True)

# --- Protocol constants (recorded in the report; change only with a new record) ---
CV_N_SPLITS = 5
CV_RANDOM_STATE = RANDOM_STATE  # 42, same seed as the outer split
SELECTION_METRIC = "roc_auc"

# Input whose checksum is recorded in the report, so a regenerated report can be
# traced to the exact dataset the metrics came from (Phase 2 / FGA-03).
INPUT_CSV = REPO_ROOT / "data" / "raw" / "telco_churn_raw.csv"

# Packages whose versions materially affect the fitted numbers. Recorded in the
# report so a metric difference can be read as drift vs. a code change.
_PROVENANCE_PACKAGES = (
    "pandas",
    "numpy",
    "scikit-learn",
    "xgboost",
    "lightgbm",
)


# Define a function to evaluate a single model
def evaluate_model(
    model_name: str,
    model: ClassifierMixin,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    """
    Evaluate a trained model on the test set and return evaluation metrics.
    """
    logger.info("Evaluating %s model...", model_name)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    # zero_division=0 keeps the naive baseline (which predicts no positives)
    # from emitting an UndefinedMetricWarning. It does not change any value for
    # a model that does predict positives: the score is 0.0 either way.
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_proba)
    conf_matrix = confusion_matrix(y_test, y_pred)

    logger.info(
        "%s model evaluation complete. Accuracy: %.4f, Precision: %.4f, Recall: %.4f, ROC AUC: %.4f",
        model_name,
        accuracy,
        precision,
        recall,
        roc_auc,
    )

    return {
        "model_name": model_name,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "roc_auc": roc_auc,
        "confusion_matrix": conf_matrix.tolist(),
    }


def cross_validate_model(
    model_name: str,
    model: ClassifierMixin,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cv: StratifiedKFold,
) -> dict[str, Any]:
    """
    Score one model on the training portion with the shared inner folds.

    Each fold builds a fresh `Pipeline` (`build_pipeline`) and fits it on that
    fold's training rows only, so the preprocessor -- including the one-hot
    encoder's category vocabulary -- never sees validation rows. Metrics are
    means over the folds; the confusion matrix is the sum of the fold counts,
    which stays integral and readable.

    The returned `fold_roc_auc` list is what the report quotes as fold
    variation; `roc_auc_std` is the sample standard deviation of those folds.
    """
    fold_metrics: list[dict[str, Any]] = []

    for fold_number, (train_idx, validation_idx) in enumerate(
        cv.split(X_train, y_train), start=1
    ):
        X_fold_train = X_train.iloc[train_idx]
        y_fold_train = y_train.iloc[train_idx]
        X_fold_validation = X_train.iloc[validation_idx]
        y_fold_validation = y_train.iloc[validation_idx]

        fold_pipeline = build_pipeline(clone(model), X_fold_train)
        fold_pipeline.fit(X_fold_train, y_fold_train)

        fold_metrics.append(
            evaluate_model(
                f"{model_name} (fold {fold_number}/{cv.n_splits})",
                fold_pipeline,
                X_fold_validation,
                y_fold_validation,
            )
        )

    fold_roc_auc = [metrics["roc_auc"] for metrics in fold_metrics]
    confusion_totals = [
        sum(metrics["confusion_matrix"][row][column] for metrics in fold_metrics)
        for row in range(2)
        for column in range(2)
    ]

    return {
        "model_name": model_name,
        "accuracy": statistics.fmean(m["accuracy"] for m in fold_metrics),
        "precision": statistics.fmean(m["precision"] for m in fold_metrics),
        "recall": statistics.fmean(m["recall"] for m in fold_metrics),
        "roc_auc": statistics.fmean(fold_roc_auc),
        "roc_auc_std": statistics.stdev(fold_roc_auc),
        "fold_roc_auc": fold_roc_auc,
        "n_folds": len(fold_metrics),
        "confusion_matrix": [
            confusion_totals[0:2],
            confusion_totals[2:4],
        ],
    }


def select_best_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cv: StratifiedKFold | None = None,
) -> tuple[str, pd.DataFrame]:
    """
    Compare the candidates and the baseline on the training portion only, and
    freeze the winner.

    This function's only data inputs are `X_train`/`y_train` -- there is no
    parameter that could receive holdout rows, which is the structural half of
    the "selection must not see the final test set" guarantee (the behavioural
    half is tested in tests/test_models.py).

    Returns `(best_model_name, selection_results)` where the DataFrame has one
    row per candidate plus one for the baseline, in the order the models were
    built (baseline last). The baseline participates in the same folds but is
    excluded from the selection itself: it is a reference, not a competitor.
    """
    if cv is None:
        cv = StratifiedKFold(
            n_splits=CV_N_SPLITS,
            shuffle=True,
            random_state=CV_RANDOM_STATE,
        )

    candidates = build_candidate_models()
    rows = [
        cross_validate_model(model_name, model, X_train, y_train, cv)
        for model_name, model in candidates.items()
    ]
    rows.append(
        cross_validate_model(
            BASELINE_MODEL_NAME, build_baseline_model(), X_train, y_train, cv
        )
    )
    selection_results = pd.DataFrame(rows)

    candidates_only = selection_results[
        selection_results["model_name"] != BASELINE_MODEL_NAME
    ]
    best_model_name = (
        candidates_only.sort_values(
            SELECTION_METRIC, ascending=False, kind="stable"
        ).iloc[0]["model_name"]
    )

    return best_model_name, selection_results


def _sha256_or_unavailable(path: Path) -> str:
    """SHA-256 of `path`, or a clear marker if the file is not present."""
    if not path.exists():
        return f"unavailable ({path.relative_to(REPO_ROOT)} not present)"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_versions() -> dict[str, str]:
    """Installed versions of the packages that determine the fitted numbers."""
    versions = {}
    for package in _PROVENANCE_PACKAGES:
        try:
            versions[package] = package_version(package)
        except PackageNotFoundError:  # pragma: no cover - defensive
            versions[package] = "not installed"
    return versions


def _format_confusion_matrix(confusion: list[list[int]]) -> str:
    """`[[tn, fp], [fn, tp]]` -> readable '[[922, 113], [170, 204]]' string."""
    return str(confusion)


def write_comparison_report(
    report_path: Path,
    selection_results: pd.DataFrame,
    holdout_results: pd.DataFrame,
) -> None:
    """
    Write the Markdown comparison report.

    Structure that other code depends on -- do not reorder without updating the
    readers:

    * the first `- Accuracy:` / `- Precision:` / `- Recall:` / `- ROC AUC:`
      bullet lines in the file are the selected model's *holdout* metrics.
      `app/services/metrics_service.py` (via `re.search`) and
      `scripts/verify_endpoints.sh` (`sed ... | head -n 1`) both read the first
      occurrence, so the protocol/limits sections must not use that shape.
    * the table under the `## Model selection` heading is the one
      `scripts/generate_model_comparison_csv.py` converts to CSV.
    """
    selected = holdout_results.iloc[0]

    fold_lines = []
    for _, row in selection_results.iterrows():
        folds = ", ".join(f"{score:.4f}" for score in row["fold_roc_auc"])
        fold_lines.append(f"- {row['model_name']}: {folds}")

    versions = _package_versions()
    environment = ", ".join(f"{name} {value}" for name, value in versions.items())
    input_checksum = _sha256_or_unavailable(INPUT_CSV)

    with report_path.open("w", encoding="utf-8") as file:
        file.write("# Customer Churn Model Comparison\n\n")

        file.write("**Protocol:** Phase 3 (2026-10-06) -- model selection by "
                   "cross-validation on the training portion only, then one "
                   "frozen evaluation of the selected model and a naive "
                   "baseline on the untouched holdout.\n\n")
        file.write(
            "This supersedes the earlier single-split comparison, which used "
            "the same holdout to select and to score its winner. That result "
            "is archived as historical evidence in "
            "[`legacy/`](legacy/README.md); its ROC AUC of 0.8494 is not an "
            "untouched final estimate and is **not comparable** to the values "
            "below.\n\n"
        )

        file.write("## Protocol\n\n")
        file.write("- **Target:** `churn_value` (0/1), from the `customers` table.\n")
        file.write(
            "- **Input:** `data/raw/telco_churn_raw.csv`, "
            f"SHA-256 `{input_checksum}` (7,043 rows, loaded through the ETL "
            "pipeline into SQLite).\n"
        )
        file.write(
            "- **Excluded inputs (identifiers, geography, leakage):** "
            "`customer_id`, `country`, `state`, `city`, `zip_code`, `lat_long`, "
            "`latitude`, `longitude`, `churn_label`, `churn_reason`, `cltv`, "
            "`churn_score`. The outcome-derived columns were removed during "
            "Issue #14 (see `README.md` and `dashboard/business_report.md`).\n"
        )
        file.write(
            "- **Engineered features:** `TenureBucket`, `TotalServicesCount`, "
            "`AvgMonthlySpend` (`training/feature_engineering.py`); the "
            "preprocessor one-hot-encodes categoricals and passes numerics "
            "through.\n"
        )
        file.write(
            f"- **Outer split:** stratified 80/20, `random_state="
            f"{RANDOM_STATE}` -- the training portion is used for selection and "
            "refit, the 20% holdout is scored once, after the winner is "
            "frozen.\n"
        )
        file.write(
            f"- **Selection:** {CV_N_SPLITS}-fold `StratifiedKFold"
            f"(shuffle=True, random_state={CV_RANDOM_STATE})` over the training "
            f"portion only; criterion is the mean fold ROC AUC "
            f"(`{SELECTION_METRIC}`), the same criterion the earlier comparison "
            "used, now applied where it cannot see the holdout. Preprocessing "
            "is refit inside every fold.\n"
        )
        file.write(
            "- **Candidates:** Logistic Regression (`max_iter=1000`), Decision "
            "Tree, Random Forest, XGBoost (`eval_metric=\"logloss\"`) and "
            f"LightGBM -- all `random_state={RANDOM_STATE}`, default "
            "hyperparameters, no tuning.\n"
        )
        file.write(
            "- **Baseline:** `DummyClassifier(strategy=\"prior\")`, scored on "
            "the same folds. It is reported for reference and is never "
            "eligible for selection.\n"
        )
        file.write(
            "- **Environment:** "
            f"Python {platform.python_version()}, {environment}.\n\n"
        )

        file.write("## Selected Model\n\n")
        file.write(f"**{selected['model_name']}**\n\n")
        file.write("### Performance (untouched holdout, evaluated once)\n\n")
        file.write(f"- Accuracy: {selected['accuracy']:.4f}\n")
        file.write(f"- Precision: {selected['precision']:.4f}\n")
        file.write(f"- Recall: {selected['recall']:.4f}\n")
        file.write(f"- ROC AUC: {selected['roc_auc']:.4f}\n")
        file.write(
            "- Confusion Matrix: "
            f"{_format_confusion_matrix(selected['confusion_matrix'])} "
            "(TN, FP, FN, TP)\n\n"
        )

        file.write("### Baseline on the same holdout\n\n")
        file.write(holdout_results.to_markdown(index=False))
        file.write("\n\n")
        file.write(
            "The baseline predicts the training class prior for every row, so "
            "it never predicts churn: its precision and recall are 0 by "
            "construction, its accuracy is the majority-class share, and its "
            "ROC AUC is 0.5. It is the floor the selected model has to beat "
            "-- the model must be better than always guessing the majority "
            "class.\n\n"
        )

        file.write(
            "## Model selection "
            f"({CV_N_SPLITS}-fold cross-validation, training portion only)\n\n"
        )
        file.write(
            selection_results.drop(columns=["fold_roc_auc", "n_folds"]).to_markdown(
                index=False
            )
        )
        file.write("\n\n")
        file.write(
            "Values are means over the five folds; confusion-matrix counts are "
            "summed across folds. `roc_auc_std` is the sample standard "
            "deviation of the fold ROC AUC values. Per-model fold ROC AUC, in "
            "fold order:\n\n"
        )
        file.write("\n".join(fold_lines))
        file.write("\n\n")
        file.write(
            "`evaluation/model_comparison.csv` is generated from this table by "
            "`scripts/generate_model_comparison_csv.py`.\n\n"
        )

        file.write("## Limits\n\n")
        file.write(
            "- One outer split and one seed: the holdout is untouched by "
            "selection, but a single 1,409-row holdout gives a point estimate, "
            "not a confidence interval. Fold variation is reported above.\n"
        )
        file.write(
            "- The dataset is a static snapshot with no time index, so no "
            "temporal or out-of-time validation claim is possible.\n"
        )
        file.write(
            "- No hyperparameter search was performed (deliberately out of "
            "scope). The five definitions are defaults except "
            "`LogisticRegression(max_iter=1000)`.\n"
        )
        file.write(
            "- Logistic Regression does not converge within `max_iter=1000` "
            "on these unscaled one-hot features (`ConvergenceWarning` during "
            "training). Recorded as an open problem, not fixed here, because "
            "changing it would move the reported metrics.\n"
        )
        file.write(
            "- Class imbalance is handled by stratification only; no "
            "resampling, class weighting or threshold tuning is applied.\n"
        )
        file.write(
            "- Metrics come from a locally reconstructed dataset; see "
            "`docs/data_provenance.md` for the input's provenance and rights "
            "status.\n"
        )

        file.write("\n## Reproduce\n\n")
        file.write(
            "```bash\npython database/init_db.py && python etl/load_to_db.py "
            "&& python database/init_views.py\npython "
            "training/evaluate_models.py\n```\n\n"
        )
        file.write(
            "The pinned environment and the full command sequence are recorded "
            "in `docs/reproduction_record.md`.\n"
        )


# Define a function to evaluate all models
def evaluate_all_models(report_dir: Path | str | None = None) -> pd.DataFrame:
    """
    Run the Phase 3 protocol end-to-end and return the selection results.

    Steps: outer split -> inner cross-validation on the training portion ->
    freeze the winner -> refit it on the full training portion -> score the
    refit winner and the baseline once on the untouched holdout -> persist the
    fitted pipeline and the report.

    Returns the *selection* DataFrame (one row per candidate plus the baseline,
    cross-validated metrics), which is the fair all-models comparison. The
    final holdout numbers for the selected model and the baseline are logged
    and written to the report; they are not used to change the selection.

    report_dir
        Directory that `model_comparison.md` is written to. The default (None)
        keeps the historical behaviour: `Path("evaluation")`, resolved against
        the current working directory -- i.e. run this from the repo root, as
        the README documents. The parameter lets the test suite redirect the
        report so `pytest` never rewrites the tracked file (NEW-02).
    """
    logger.info("Splitting the dataset into the outer training/holdout portions...")
    X_train, X_test, y_train, y_test, _unused_preprocessor = split_training_data()

    cv = StratifiedKFold(
        n_splits=CV_N_SPLITS,
        shuffle=True,
        random_state=CV_RANDOM_STATE,
    )
    logger.info(
        "Selecting a model with %d-fold stratified cross-validation on the "
        "%d-row training portion (holdout of %d rows is not used)...",
        CV_N_SPLITS,
        len(X_train),
        len(X_test),
    )
    best_model_name, selection_results = select_best_model(X_train, y_train, cv=cv)

    best_row = selection_results.loc[
        selection_results["model_name"] == best_model_name
    ].iloc[0]
    logger.info(
        "Best model: %s (mean CV ROC AUC %.4f, fold std %.4f)",
        best_model_name,
        best_row["roc_auc"],
        best_row["roc_auc_std"],
    )

    logger.info("Refitting %s on the full training portion...", best_model_name)
    best_model = build_pipeline(
        clone(build_candidate_models()[best_model_name]), X_train
    )
    best_model.fit(X_train, y_train)

    logger.info("Fitting the %s baseline on the same training portion...", BASELINE_MODEL_NAME)
    baseline_model = build_pipeline(build_baseline_model(), X_train)
    baseline_model.fit(X_train, y_train)

    logger.info(
        "Evaluating the frozen winner and the baseline once on the untouched "
        "holdout (%d rows)...",
        len(X_test),
    )
    holdout_results = pd.DataFrame(
        [
            evaluate_model(best_model_name, best_model, X_test, y_test),
            evaluate_model(BASELINE_MODEL_NAME, baseline_model, X_test, y_test),
        ]
    )

    # save model
    joblib.dump(
        best_model,
        MODEL_PATH / "best_model.pkl",
    )

    logger.info(
        "Best model (%s) saved successfully.",
        best_model_name,
    )
    logger.info("Evaluation complete.\n%s", holdout_results)

    # Generate a markdown report for model comparison
    REPORT_DIR = Path(report_dir) if report_dir is not None else Path("evaluation")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "model_comparison.md"
    logger.info("Writing model comparison report to %s", report_path)
    write_comparison_report(report_path, selection_results, holdout_results)

    return selection_results


# If the script is run directly, set up logging and call the evaluate_all_models function
if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    results = evaluate_all_models()
    logger.info("\n%s", results)
