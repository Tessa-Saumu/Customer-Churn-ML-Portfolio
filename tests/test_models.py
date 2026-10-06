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
    """

    def test_evaluate_all_models_produces_a_usable_artifact(self, tmp_path) -> None:
        """
        Trains all five models and checks the artifacts it produces.

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
        from training.evaluate_models import evaluate_all_models

        tracked_report_before = _tracked_report_sha256()
        report_dir = tmp_path / "evaluation"

        results_df = evaluate_all_models(report_dir=report_dir)

        assert len(results_df) == 5
        expected_models = {
            "Logistic Regression",
            "Decision Tree",
            "Random Forest",
            "XGBoost",
            "LightGBM",
        }
        assert set(results_df["model_name"]) == expected_models

        for metric in ("accuracy", "precision", "recall", "roc_auc"):
            assert (results_df[metric] >= 0.0).all()
            assert (results_df[metric] <= 1.0).all()

        assert MODEL_PATH.exists()
        assert METRICS_PATH.exists()
        # The report this run produced is the redirected one, not the tracked one.
        assert (report_dir / "model_comparison.md").exists()
        assert (
            "## Selected Model"
            in (report_dir / "model_comparison.md").read_text(encoding="utf-8")
        )
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