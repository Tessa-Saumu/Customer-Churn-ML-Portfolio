"""
Issue #17 -- Model Training & Prediction Testing -- tests/test_models.py

Owner: Theresia --
authored entirely from scratch, no content carried over from
Latifah's (#11) implementation.

Which predict() this file tests
--------------------------------
Two prediction modules exist in this codebase:

    1. predict.py (repo root)      -- Latifah's Issue #11 contract,
       later wrapped by Praise's Issue #14 field-adapter. This is the
       one app/api/routes.py actually imports and calls. Per
       Project_Specification.md section 4, this is the locked
       interface: predict(customer_data: dict) -> {"churn_probability":
       float, "churn_prediction": bool}.

    2. training/predict.py          -- an earlier/simpler module with
       the same function name and a near-identical body, but WITHOUT
       the API-field-name adapter. It is not imported anywhere in
       app/ (confirmed by inspection: app/api/routes.py imports only
       from repo-root predict.py). This looks like a leftover/
       superseded duplicate rather than a second, intentionally
       maintained interface.

This file tests repo-root predict.py as the primary, locked contract,
since that's what production actually calls. A dedicated test in the
"deprecation flag" section below asserts training/predict.py is not
imported anywhere under app/, so if someone later starts depending on
it, this test fails loudly rather than the duplication silently
persisting or drifting further from the real contract. This is
flagged in docs/qa_findings.md as a question for Latifah/Theresia to
resolve (delete training/predict.py, or clarify its purpose) -- not
resolved unilaterally in this PR.

Structure
---------
    1. UNIT TESTS       (@pytest.mark.unit)
       Model-artifact loading, predict() baseline correctness and
       edge cases, and the training/predict.py deprecation-flag check.
       These need models/best_model.pkl to exist on disk (an artifact
       load, not a network/DB call), which is why they're grouped as
       "unit" here rather than requiring a live service the way the
       API/DB tests do -- consistent with tests/test_etl.py and
       tests/test_api.py's definition of unit vs. integration for
       this repo (see each file's own module docstring).

    2. INTEGRATION TESTS (@pytest.mark.integration)
       Runs the real training/evaluate_models.py pipeline end-to-end
       against the real (test-run) database, then confirms the
       resulting artifact and evaluation report satisfy the same
       checks -- exercising the full training -> artifact ->
       prediction path in one go, not just a pre-existing pickle.
       This is slow (trains 5 real models) and is marked accordingly;
       CI can run `pytest tests/test_models.py -m "not integration"`
       for a fast pass if needed.

Run everything:            pytest tests/test_models.py
Run only unit tests:       pytest tests/test_models.py -m unit
Run only integration:      pytest tests/test_models.py -m integration
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODEL_PATH = REPO_ROOT / "models" / "best_model.pkl"
METRICS_PATH = REPO_ROOT / "evaluation" / "model_comparison.md"
DB_PATH = REPO_ROOT / "database" / "churn.db"


def _tracked_report_sha256() -> str | None:
    """
    SHA-256 of the TRACKED evaluation/model_comparison.md, or None if absent.

    Used to prove that running this test suite does not rewrite a committed
    metrics artifact (NEW-02). Hashed rather than compared byte-for-byte so the
    assertion message stays short.
    """
    if not METRICS_PATH.exists():
        return None
    return hashlib.sha256(METRICS_PATH.read_bytes()).hexdigest()

requires_model_artifact = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason=(
        "models/best_model.pkl does not exist. Run "
        "training/evaluate_models.py first (see README 'Run the "
        "machine learning training pipeline')."
    ),
)

def _db_is_populated() -> bool:
    """
    True only if database/churn.db exists AND the customers table has
    at least one row. File existence alone is not sufficient: another
    test file (e.g. tests/test_etl.py's init_db idempotency tests) may
    have already created an empty schema-only database, which would
    otherwise cause training to be attempted against zero rows and
    fail with a confusing sklearn error rather than skip cleanly.
    """
    if not DB_PATH.exists():
        return False
    try:
        import sqlite3

        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM customers")
            return cursor.fetchone()[0] > 0
        finally:
            conn.close()
    except Exception:
        return False


requires_populated_db = pytest.mark.skipif(
    not _db_is_populated(),
    reason=(
        "database/churn.db does not exist or has no customer rows. Run "
        "the ETL pipeline first: python database/init_db.py && "
        "python etl/load_to_db.py"
    ),
)


def _valid_prediction_payload() -> dict:
    """A single known-valid CustomerPredictionRequest-shaped dict."""
    return {
        "gender": "Female",
        "SeniorCitizen": 0,
        "Partner": "Yes",
        "Dependents": "No",
        "tenure": 12,
        "PhoneService": "Yes",
        "MultipleLines": "No",
        "InternetService": "Fiber optic",
        "OnlineSecurity": "No",
        "OnlineBackup": "Yes",
        "DeviceProtection": "No",
        "TechSupport": "No",
        "StreamingTV": "Yes",
        "StreamingMovies": "No",
        "Contract": "Month-to-month",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check",
        "MonthlyCharges": 70.05,
        "TotalCharges": 840.60,
    }


# ======================================================================
# SECTION 1 -- UNIT TESTS
# ======================================================================


@pytest.mark.unit
@requires_model_artifact
class TestModelArtifactLoading:
    """
    Issue #17 explicit requirement: models/best_model.pkl (or
    equivalent) loads without error, and required preprocessing
    artifacts (encoders/scalers/transformers) load successfully too.
    """

    def test_model_artifact_loads_without_error(self) -> None:
        model = joblib.load(MODEL_PATH)
        assert model is not None

    def test_loaded_artifact_is_a_fitted_sklearn_pipeline(self) -> None:
        """
        Confirms the artifact is a full Pipeline (preprocessor +
        classifier bundled together), not a bare classifier. This
        matters for the next test: it means "the preprocessing
        artifacts required for inference" for THIS project live
        inside best_model.pkl itself, not as separate .pkl files for
        encoders/scalers -- confirmed by inspecting the trained
        object's structure directly, not assumed.
        """
        from sklearn.pipeline import Pipeline

        model = joblib.load(MODEL_PATH)
        assert isinstance(model, Pipeline)
        assert "preprocessor" in model.named_steps
        assert "classifier" in model.named_steps

    def test_preprocessing_transformer_loads_and_has_categorical_encoder(self) -> None:
        """
        The bundled preprocessor is a ColumnTransformer containing a
        OneHotEncoder for categorical columns (training/preprocessing.py
        ::build_preprocessor). Confirms this loads successfully as
        part of the artifact and is fitted (has learned categories_).
        """
        from sklearn.compose import ColumnTransformer
        from sklearn.preprocessing import OneHotEncoder

        model = joblib.load(MODEL_PATH)
        preprocessor = model.named_steps["preprocessor"]
        assert isinstance(preprocessor, ColumnTransformer)

        # transformers_ entries are 3-tuples: (name, transformer, columns).
        categorical_transformer = next(
            transformer
            for name, transformer, _columns in preprocessor.transformers_
            if name == "categorical"
        )
        assert isinstance(categorical_transformer, OneHotEncoder)
        # Fitted encoders expose categories_; this fails if the
        # bundled encoder was somehow saved unfitted.
        assert hasattr(categorical_transformer, "categories_")

    def test_model_exposes_predict_and_predict_proba(self) -> None:
        model = joblib.load(MODEL_PATH)
        assert hasattr(model, "predict")
        assert hasattr(model, "predict_proba")


@pytest.mark.unit
@requires_model_artifact
class TestPredictBaselineCorrectness:
    """
    Issue #17 explicit requirement: predict() executes successfully
    on a valid sample and returns the exact expected shape.
    """

    def test_predict_executes_successfully_on_valid_sample(self) -> None:
        from predict import predict

        result = predict(_valid_prediction_payload())
        assert result is not None

    def test_predict_returns_expected_response_structure(self) -> None:
        from predict import predict

        result = predict(_valid_prediction_payload())
        assert set(result.keys()) == {"churn_probability", "churn_prediction"}
        assert isinstance(result["churn_probability"], float)
        assert isinstance(result["churn_prediction"], bool)

    def test_predict_probability_is_in_valid_range(self) -> None:
        from predict import predict

        result = predict(_valid_prediction_payload())
        assert 0.0 <= result["churn_probability"] <= 1.0

    def test_predict_prediction_flag_is_consistent_with_probability(self) -> None:
        """
        churn_prediction should reflect the model's own decision
        threshold (model.predict), which is not necessarily a naive
        0.5 cutoff on churn_probability for every algorithm -- so this
        checks internal consistency of the *pipeline's own* two calls
        (predict vs predict_proba) rather than asserting a hardcoded
        threshold predict.py doesn't actually use.
        """
        from predict import predict, model as loaded_model, _adapt_api_fields_to_training_schema
        from training.preprocessing import prepare_features

        payload = _valid_prediction_payload()
        result = predict(payload)

        adapted = _adapt_api_fields_to_training_schema(payload)
        X = prepare_features(pd.DataFrame([adapted]))
        expected_prediction = bool(loaded_model.predict(X)[0])

        assert result["churn_prediction"] == expected_prediction


@pytest.mark.unit
@requires_model_artifact
class TestPredictEdgeCases:
    """
    Issue #17 explicit requirement: unseen category values and
    missing/null fields.
    """

    def test_predict_handles_unseen_category_without_raising(self) -> None:
        """
        The trained OneHotEncoder uses handle_unknown="ignore"
        (training/preprocessing.py::build_preprocessor), so a category
        value not present during training must not raise -- confirmed
        directly here, not assumed from reading the encoder config.
        """
        from predict import predict

        payload = _valid_prediction_payload()
        payload["InternetService"] = "Satellite"  # not a real training category
        result = predict(payload)
        assert set(result.keys()) == {"churn_probability", "churn_prediction"}

    def test_predict_handles_unseen_category_on_multiple_fields(self) -> None:
        from predict import predict

        payload = _valid_prediction_payload()
        payload["PaymentMethod"] = "Cryptocurrency"
        payload["Contract"] = "Lifetime"
        result = predict(payload)
        assert 0.0 <= result["churn_probability"] <= 1.0

    def test_predict_with_missing_field_raises_clear_error(self) -> None:
        """
        DOCUMENTED BEHAVIOUR (see docs/qa_findings.md): a customer
        record missing a required field raises KeyError, sourced from
        _adapt_api_fields_to_training_schema()'s dict comprehension
        over _API_FIELD_TO_DB_COLUMN. This is a genuinely clear error
        (KeyError naming the missing field) -- confirmed acceptable
        per the issue's own acceptance criteria ("the function raises
        a clear validation error, or handles missing values per the
        documented strategy"). Asserted explicitly here so any future
        change to silently-default-instead-of-raise is a deliberate,
        visible decision, not an accidental regression.
        """
        from predict import predict

        payload = _valid_prediction_payload()
        del payload["tenure"]

        with pytest.raises(KeyError):
            predict(payload)

    def test_predict_with_null_tenure_raises_rather_than_silently_mispredicting(self) -> None:
        """
        DOCUMENTED GAP (see docs/qa_findings.md): unlike a fully
        MISSING field (previous test -- clear KeyError), a field that
        is PRESENT but explicitly None currently raises a much less
        clear TypeError from deep inside pandas' pd.cut binning logic
        in training/feature_engineering.py::add_tenure_bucket, not a
        validation error naming the field. This test intentionally
        pins the CURRENT behaviour (raises, does not silently
        mispredict) so the important safety property -- "a null
        required field never produces a silent, plausible-looking
        wrong answer" -- is protected by a test even before the error
        message itself is improved. If someone improves this to a
        clearer, explicit validation error, this test still passes
        (any raised exception satisfies pytest.raises(Exception));
        only a regression to *silent success* would break it.
        """
        from predict import predict

        payload = _valid_prediction_payload()
        payload["tenure"] = None

        with pytest.raises(Exception):
            predict(payload)

    def test_predict_with_null_optional_service_field_does_not_silently_mispredict(self) -> None:
        """
        A null value in a categorical service field (not tenure) is
        passed through to the OneHotEncoder as NaN. Confirms this
        currently does not raise and does not silently produce an
        out-of-range or malformed result -- documenting the actual
        current behaviour for a null categorical field, distinct from
        the null-tenure case above (tenure feeds numeric binning
        logic; these fields feed only the categorical encoder).
        """
        from predict import predict

        payload = _valid_prediction_payload()
        payload["OnlineSecurity"] = None

        result = predict(payload)
        assert 0.0 <= result["churn_probability"] <= 1.0


@pytest.mark.unit
@requires_model_artifact
class TestPreprocessingPathConsistency:
    """
    Issue #17 explicit requirement: the prediction pipeline uses the
    same preprocessing path as training -- input transformation works
    before inference, and feature ordering matches what the trained
    model expects.
    """

    def test_predict_uses_prepare_features_before_inference(self) -> None:
        """
        Confirms predict.py actually calls
        training.preprocessing.prepare_features (the same function
        training/train_test_split.py::split_training_data uses via
        prepare_training_data) rather than some separate, potentially
        divergent transformation path.
        """
        import predict as predict_module

        assert predict_module.prepare_features is not None
        import inspect

        source = inspect.getsource(predict_module.predict)
        assert "prepare_features" in source

    def test_feature_columns_match_what_the_trained_transformer_expects(self) -> None:
        """
        Confirms the columns produced by prepare_features() for a
        single prediction request are exactly the columns the trained
        ColumnTransformer was fitted on (categorical transformer
        columns + remainder columns) -- i.e. feature ordering/naming
        did not drift between training and inference. A mismatch here
        would normally surface as either a silent remainder
        misalignment or a ValueError at predict_proba() time; checking
        it directly is more precise than only checking predict()
        doesn't raise.
        """
        from predict import _adapt_api_fields_to_training_schema, model as loaded_model
        from training.preprocessing import prepare_features

        payload = _valid_prediction_payload()
        adapted = _adapt_api_fields_to_training_schema(payload)
        X = prepare_features(pd.DataFrame([adapted]))

        preprocessor = loaded_model.named_steps["preprocessor"]
        # transformers_ entries are 3-tuples: (name, transformer, columns).
        fitted_categorical_columns = next(
            columns
            for name, _transformer, columns in preprocessor.transformers_
            if name == "categorical"
        )

        for column in fitted_categorical_columns:
            assert column in X.columns, (
                f"Column '{column}' expected by the trained preprocessor "
                f"is missing from prepare_features() output at predict time."
            )

    def test_predict_end_to_end_does_not_raise_shape_mismatch(self) -> None:
        """
        The most direct possible confirmation that the inference-time
        preprocessing path matches training: actually call
        predict_proba() through the full pipeline and confirm it
        returns a well-formed probability array, rather than raising
        a sklearn shape/column mismatch error.
        """
        from predict import _adapt_api_fields_to_training_schema, model as loaded_model
        from training.preprocessing import prepare_features

        payload = _valid_prediction_payload()
        adapted = _adapt_api_fields_to_training_schema(payload)
        X = prepare_features(pd.DataFrame([adapted]))

        probabilities = loaded_model.predict_proba(X)
        assert probabilities.shape == (1, 2)
        assert 0.0 <= probabilities[0][1] <= 1.0


@pytest.mark.unit
@requires_model_artifact
class TestTrainingPredictDeprecationFlag:
    """
    QA finding, encoded as a live test rather than only prose (per
    Theresia's explicit request): training/predict.py appears to be a
    superseded duplicate of repo-root predict.py -- same function
    name, near-identical body, but WITHOUT the API-field-name adapter
    layer Issue #14 added. It is not imported anywhere under app/.

    This test asserts that fact directly, so:
      - anyone opening this file immediately sees the duplication
        called out, without needing to dig through git history or
        docs/qa_findings.md, and
      - if someone LATER wires training/predict.py into app/ (instead
        of resolving the duplication some other way), this test fails
        loudly, flagging the drift immediately rather than letting two
        divergent prediction paths silently coexist in production.

    Does not touch training/predict.py or app/ to "fix" this -- that
    decision (delete vs. keep vs. document) belongs to Latifah/
    Theresia, per docs/qa_findings.md.
    """

    def test_app_package_does_not_import_training_predict(self) -> None:
        app_dir = REPO_ROOT / "app"
        offending_files = []

        for py_file in app_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module in ("training.predict", "training predict"):
                        offending_files.append(str(py_file))
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "training.predict":
                            offending_files.append(str(py_file))

        assert offending_files == [], (
            "app/ now imports training/predict.py, which was flagged as a "
            "likely-superseded duplicate of repo-root predict.py (missing "
            "the Issue #14 API-field adapter). Confirm this is intentional "
            "before relying on it -- see docs/qa_findings.md."
        )
# ======================================================================
# SECTION 2 -- INTEGRATION TESTS
# Full real training pipeline, run end-to-end.
# ======================================================================


@pytest.mark.integration
@requires_populated_db
class TestTrainingPipelineEndToEnd:
    """
    Runs the real training pipeline (all 5 models) against the real
    database and confirms the resulting artifacts satisfy the same
    contracts as the unit tests above -- this is the slow, full-fidelity
    counterpart to the pre-existing-artifact unit tests.

    Phase 3 note: `evaluate_all_models()` now runs the baseline + 5-fold
    cross-validated selection + single frozen-holdout evaluation protocol
    (audit item FGA-05), so `results_df` is the *selection* table -- one
    row per candidate plus the naive baseline -- not the old five-row
    holdout table.
    """

    def test_evaluate_all_models_produces_a_usable_artifact(self, tmp_path) -> None:
        """
        Runs the full Phase 3 protocol and checks the artifacts it produces.

        The Markdown report is redirected into `tmp_path` on purpose: it is a
        TRACKED file, and before Phase 2 this test (plus the two logging tests
        below) rewrote `evaluation/model_comparison.md` with whatever the local
        environment produced, so a plain `pytest` run dirtied a committed
        metrics artifact (NEW-02). The final assertion below is the regression
        guard for that: the tracked report must be byte-identical afterwards.

        The model pickle is still written to the repo's `models/` directory --
        it is gitignored, and the next test in this class deliberately reloads
        it to close the training -> prediction loop.
        """
        from training.evaluate_models import (
            BASELINE_MODEL_NAME,
            evaluate_all_models,
        )

        tracked_report_before = _tracked_report_sha256()
        report_dir = tmp_path / "evaluation"

        results_df = evaluate_all_models(report_dir=report_dir)

        # One row per candidate plus the baseline.
        assert len(results_df) == 6
        expected_models = {
            "Logistic Regression",
            "Decision Tree",
            "Random Forest",
            "XGBoost",
            "LightGBM",
        }
        assert set(results_df["model_name"]) == expected_models | {BASELINE_MODEL_NAME}

        for metric in ("accuracy", "precision", "recall", "roc_auc"):
            assert (results_df[metric] >= 0.0).all()
            assert (results_df[metric] <= 1.0).all()

        # Cross-validation bookkeeping: one fold score per fold, per model.
        from training.evaluate_models import CV_N_SPLITS

        assert (results_df["n_folds"] == CV_N_SPLITS).all()
        assert (results_df["fold_roc_auc"].apply(len) == CV_N_SPLITS).all()

        assert MODEL_PATH.exists()
        assert METRICS_PATH.exists()
        # The report this run produced is the redirected one, not the tracked one.
        report_path = report_dir / "model_comparison.md"
        assert report_path.exists()
        report_text = report_path.read_text(encoding="utf-8")
        assert "## Selected Model" in report_text
        assert "## Model selection" in report_text
        assert "DummyClassifier" in report_text
        # ... and the tracked report was left alone.
        assert _tracked_report_sha256() == tracked_report_before, (
            "Running the test suite modified the tracked "
            "evaluation/model_comparison.md. Training output must be redirected "
            "(evaluate_all_models(report_dir=...)) so pytest never rewrites a "
            "committed metrics artifact -- see NEW-02 in "
            "FLAGSHIP_IMPLEMENTATION_PLAN.md."
        )

    def test_freshly_trained_artifact_loads_and_predicts(self) -> None:
        """
        Confirms the artifact this same test run just produced loads
        and predicts successfully -- closing the loop from training
        through to a real prediction, not just checking the file
        exists.
        """
        import importlib
        import predict as predict_module

        importlib.reload(predict_module)  # picks up the freshly-trained artifact
        result = predict_module.predict(_valid_prediction_payload())

        assert set(result.keys()) == {"churn_probability", "churn_prediction"}
        assert 0.0 <= result["churn_probability"] <= 1.0


@pytest.mark.integration
@requires_populated_db
class TestTrainingAndEvaluationLoggingCoverage:
    """
    Issue #17 explicit requirement: confirm meaningful logs exist for
    training progress, evaluation results, and model selection.
    """

    def test_training_logs_progress_for_each_model(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from training.train_models import train_models

        with caplog.at_level(logging.INFO, logger="training.train_models"):
            train_models()

        messages = [record.message for record in caplog.records]
        assert any("Training" in message and "model..." in message for message in messages)
        assert any("training complete" in message for message in messages)

    def test_evaluation_logs_metrics_per_model(
        self, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ) -> None:
        from training.evaluate_models import evaluate_all_models

        with caplog.at_level(logging.INFO, logger="training.evaluate_models"):
            # report_dir keeps this run from rewriting the tracked report (NEW-02).
            evaluate_all_models(report_dir=tmp_path / "evaluation")

        messages = [record.message for record in caplog.records]
        assert any("evaluation complete" in message for message in messages)

    def test_evaluation_logs_best_model_selection(
        self, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ) -> None:
        from training.evaluate_models import evaluate_all_models

        with caplog.at_level(logging.INFO, logger="training.evaluate_models"):
            # report_dir keeps this run from rewriting the tracked report (NEW-02).
            evaluate_all_models(report_dir=tmp_path / "evaluation")

        messages = [record.message for record in caplog.records]
        assert any("Best model" in message for message in messages)

# ======================================================================
# SECTION 3 -- PHASE 3 EVALUATION PROTOCOL (audit item FGA-05)
#
# The protocol is: outer stratified split -> 5-fold stratified cross-validation
# on the TRAINING portion only (candidates + naive baseline) -> freeze the winner
# -> refit it on the full training portion -> evaluate the frozen winner and the
# baseline once on the UNTOUCHED holdout.
#
# These tests pin the properties that make that protocol honest. They do not
# re-assert the metric values (those belong to a reproduction record, not to a
# test), and the expensive selection run is shared per class.
# ======================================================================


@pytest.fixture(scope="module")
def selection_protocol_run():
    """
    Run the training-side half of the protocol once and share it across the
    module: the full 5-fold comparison over five candidates takes ~12 s, which is
    too slow to repeat per test or per class.
    """
    from types import SimpleNamespace

    from training.evaluate_models import select_best_model
    from training.train_test_split import split_training_data

    X_train, X_test, y_train, y_test, _unused = split_training_data()
    best_model_name, selection_results = select_best_model(X_train, y_train)

    return SimpleNamespace(
        best_model_name=best_model_name,
        selection_results=selection_results,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
    )


@pytest.mark.integration
@requires_populated_db
class TestSelectionCannotSeeTheHoldout:
    """
    Acceptance criterion: "The new report contains no selection leakage from the
    final test."

    Two guards: the structural one (the selection function has no parameter that
    could carry holdout rows) and the observable one (the cross-validation
    confusion matrices count exactly the training portion, never the holdout).
    """

    def test_select_best_model_accepts_only_training_data(self) -> None:
        import inspect

        from training.evaluate_models import select_best_model

        parameters = list(inspect.signature(select_best_model).parameters)
        assert parameters == ["X_train", "y_train", "cv"], (
            "select_best_model must be callable with the training portion only. "
            f"Its parameters are {parameters}; if a test/holdout argument was "
            "added, the freeze-before-holdout guarantee is gone."
        )

    def test_cross_validation_covers_the_training_portion_not_the_holdout(
        self, selection_protocol_run
    ) -> None:
        run = selection_protocol_run
        n_train = len(run.X_train)

        assert n_train + len(run.X_test) > n_train  # sanity: the holdout exists
        for _, row in run.selection_results.iterrows():
            fold_total = sum(sum(pair) for pair in row["confusion_matrix"])
            assert fold_total == n_train, (
                f"{row['model_name']} was cross-validated over {fold_total} rows, "
                f"but the training portion has {n_train}. Scoring "
                f"{len(run.X_test)} rows would mean the holdout reached the "
                "selection code."
            )

    def test_outer_split_partitions_the_dataset_without_overlap(self) -> None:
        from training.preprocessing import prepare_training_data
        from training.train_test_split import split_training_data

        X, _y = prepare_training_data()
        X_train, X_test, y_train, y_test, _unused = split_training_data()

        assert len(X_train) + len(X_test) == len(X)
        assert set(X_train.index).isdisjoint(set(X_test.index)), (
            "a row appears in both the training and holdout portions"
        )
        assert len(y_train) == len(X_train) and len(y_test) == len(X_test)
        # The recorded split sizes (docs/reproduction_record.md §4).
        assert len(X_train) == 5634
        assert len(X_test) == 1409


@pytest.mark.integration
@requires_populated_db
class TestSelectionProtocol:
    """
    Acceptance criteria: every candidate and the baseline are measured under the
    same inner folds; the baseline is a reported floor and never selected; the
    winner is the highest mean cross-validated ROC AUC among the candidates.
    """

    CANDIDATES = (
        "Logistic Regression",
        "Decision Tree",
        "Random Forest",
        "XGBoost",
        "LightGBM",
    )

    def test_selection_table_has_every_candidate_plus_the_baseline(
        self, selection_protocol_run
    ) -> None:
        from training.evaluate_models import BASELINE_MODEL_NAME

        run = selection_protocol_run
        assert set(run.selection_results["model_name"]) == set(self.CANDIDATES) | {
            BASELINE_MODEL_NAME
        }

    def test_every_model_uses_the_same_inner_folds(self, selection_protocol_run) -> None:
        from training.evaluate_models import CV_N_SPLITS

        run = selection_protocol_run
        assert (run.selection_results["n_folds"] == CV_N_SPLITS).all()
        # Same fold count for everyone, and each row carries its own fold scores,
        # so the comparison in the report is provably like-for-like.
        for _, row in run.selection_results.iterrows():
            assert len(row["fold_roc_auc"]) == CV_N_SPLITS

    def test_cross_validated_mean_is_the_reported_mean(self, selection_protocol_run) -> None:
        import statistics

        run = selection_protocol_run
        for _, row in run.selection_results.iterrows():
            assert row["roc_auc"] == pytest.approx(
                statistics.fmean(row["fold_roc_auc"]), rel=1e-12
            )
            assert row["roc_auc_std"] == pytest.approx(
                statistics.stdev(row["fold_roc_auc"]), rel=1e-12
            )

    def test_baseline_scores_a_coin_flip_and_is_never_selected(
        self, selection_protocol_run
    ) -> None:
        from training.evaluate_models import BASELINE_MODEL_NAME

        run = selection_protocol_run
        baseline = run.selection_results.loc[
            run.selection_results["model_name"] == BASELINE_MODEL_NAME
        ].iloc[0]

        # DummyClassifier(strategy="prior") ignores the features, so its ROC AUC
        # is 0.5 in every fold by construction and it predicts no positive.
        assert baseline["roc_auc"] == pytest.approx(0.5)
        assert baseline["recall"] == 0.0
        assert baseline["precision"] == 0.0
        assert all(score == pytest.approx(0.5) for score in baseline["fold_roc_auc"])

        assert run.best_model_name != BASELINE_MODEL_NAME, (
            "the naive baseline was selected -- selection must only ever pick one "
            "of the five real candidates"
        )

    def test_winner_is_the_candidate_with_the_highest_mean_cv_roc_auc(
        self, selection_protocol_run
    ) -> None:
        run = selection_protocol_run
        candidates = run.selection_results[
            run.selection_results["model_name"].isin(self.CANDIDATES)
        ]
        expected = candidates.sort_values(
            "roc_auc", ascending=False, kind="stable"
        ).iloc[0]["model_name"]

        assert run.best_model_name == expected
        # And it actually beats the naive floor, which is the only claim the
        # baseline supports.
        winner_auc = candidates.loc[
            candidates["model_name"] == run.best_model_name, "roc_auc"
        ].iloc[0]
        assert winner_auc > 0.5


@pytest.mark.unit
class TestComparisonReportContract:
    """
    The report is a machine-readable artifact as much as a document:
    `app/services/metrics_service.py` takes the first `- Accuracy:`-shaped line
    (the selected model's holdout value) and
    `scripts/generate_model_comparison_csv.py` converts the `## Model selection`
    table. Both couplings are pinned here on synthetic inputs, so a formatting
    change that breaks either reader fails a fast unit test instead of the API.
    """

    @staticmethod
    def _selection_frame() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "model_name": "Logistic Regression",
                    "accuracy": 0.8133,
                    "precision": 0.6746,
                    "recall": 0.5726,
                    "roc_auc": 0.8591,
                    "roc_auc_std": 0.0142,
                    "fold_roc_auc": [0.8615, 0.8386, 0.8517, 0.8707, 0.8732],
                    "n_folds": 5,
                    "confusion_matrix": [[3726, 413], [639, 856]],
                },
                {
                    "model_name": "DummyClassifier (baseline)",
                    "accuracy": 0.7346,
                    "precision": 0.0,
                    "recall": 0.0,
                    "roc_auc": 0.5,
                    "roc_auc_std": 0.0,
                    "fold_roc_auc": [0.5, 0.5, 0.5, 0.5, 0.5],
                    "n_folds": 5,
                    "confusion_matrix": [[4139, 0], [1495, 0]],
                },
            ]
        )

    @staticmethod
    def _holdout_frame() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "model_name": "Logistic Regression",
                    "accuracy": 0.799148,
                    "precision": 0.643533,
                    "recall": 0.545455,
                    "roc_auc": 0.849562,
                    "confusion_matrix": [[922, 113], [170, 204]],
                },
                {
                    "model_name": "DummyClassifier (baseline)",
                    "accuracy": 0.734564,
                    "precision": 0.0,
                    "recall": 0.0,
                    "roc_auc": 0.5,
                    "confusion_matrix": [[1035, 0], [374, 0]],
                },
            ]
        )

    def _write(self, tmp_path: Path) -> str:
        from training.evaluate_models import write_comparison_report

        report_path = tmp_path / "model_comparison.md"
        write_comparison_report(
            report_path, self._selection_frame(), self._holdout_frame()
        )
        return report_path.read_text(encoding="utf-8")

    def test_first_metric_bullets_are_the_selected_models_holdout_values(
        self, tmp_path: Path
    ) -> None:
        report = self._write(tmp_path)

        # Same extraction the API service uses on the real report.
        assert "- Accuracy: 0.7991" in report
        assert "- Precision: 0.6435" in report
        assert "- Recall: 0.5455" in report
        assert "- ROC AUC: 0.8496" in report
        # The cross-validation values must NOT appear in that bullet shape, or
        # the API would report the training-side means as the final result.
        assert "- Accuracy: 0.8133" not in report
        assert "- ROC AUC: 0.8591" not in report

    def test_selection_table_is_convertible_to_the_power_bi_csv(
        self, tmp_path: Path
    ) -> None:
        import importlib.util

        report = self._write(tmp_path)
        script = REPO_ROOT / "scripts" / "generate_model_comparison_csv.py"
        spec = importlib.util.spec_from_file_location(
            "generate_model_comparison_csv", script
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        rows = module.build_csv_rows(module.parse_table(report))
        assert [row["Model"] for row in rows] == [
            "Logistic Regression",
            "DummyClassifier (baseline)",
        ]
        assert rows[0]["ROC_AUC"] == "0.8591"
        assert (
            rows[0]["True_Negatives"],
            rows[0]["False_Positives"],
            rows[0]["False_Negatives"],
            rows[0]["True_Positives"],
        ) == (3726, 413, 639, 856)

    def test_report_labels_the_protocol_baseline_and_limits(self, tmp_path: Path) -> None:
        report = self._write(tmp_path)

        assert "## Model selection" in report
        assert "cross-validation" in report.lower()
        assert "untouched holdout" in report.lower()
        assert "DummyClassifier" in report
        assert "not comparable" in report.lower()  # vs. the archived legacy result
        assert "no time index" in report
        assert "no hyperparameter search" in report.lower()
        # Provenance: an input checksum and the package versions that produced
        # these numbers must be in the report itself.
        assert "SHA-256" in report
        assert "scikit-learn" in report
