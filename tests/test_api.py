"""
Issue #16 -- FastAPI Testing -- tests/test_api.py

Owner: Theresia, no content carried over from Praise's
(#10/#14) implementation.

Structure
---------
    1. UNIT TESTS       (@pytest.mark.unit)
       /health only -- the one endpoint with genuinely no external
       dependency (no auth, no DB, no model). Everything else this
       app does touches a real database and/or a real model artifact
       at import time (see note below), so a "pure" unit test of
       /customers, /kpis, /predict, or /model-metrics that mocks all
       of that away would mostly be testing the mocks, not the app.

    2. INTEGRATION TESTS (@pytest.mark.integration)
       Uses FastAPI's TestClient against the real `app` object, the
       real database, and the real trained model. This matches how
       Issue #14 actually wired the app -- there is no mocked
       prediction path left to test in isolation (mock_predict() is
       archived and unreachable, per
       app/services/mock_prediction_service.py's own docstring).

Run everything:            pytest tests/test_api.py
Run only unit tests:       pytest tests/test_api.py -m unit
Run only integration:      pytest tests/test_api.py -m integration

IMPORTANT ordering/import note
-------------------------------
app/api/routes.py imports `predict` from the repo-root predict.py at
MODULE level, and predict.py loads models/best_model.pkl via
joblib.load(...) at ITS module level too (not lazily, not inside a
function). This means simply *importing* app.main -- which every test
in this file does, even the /health-only ones -- requires
models/best_model.pkl to already exist on disk. There is no way to
test /health in true isolation from the model artifact under the
current import structure. This is flagged in PR Notes as a
follow-up-worthy coupling (a broken/missing model file currently
prevents the app from starting at all, including /health, which is a
stronger failure mode than "the /predict endpoint doesn't work") --
not fixed here, since changing import-time loading to lazy loading is
an app/api-owned implementation change, not a testing change.

Because of this, these tests skip clearly (not fail confusingly) if
models/best_model.pkl or database/churn.db are absent, same pattern as
tests/test_etl.py.

Auth setup
----------
API_KEY is read from the environment by app/services/auth_service.py
at request time (not at import time), so tests set it via
monkeypatch.setenv rather than depending on a real .env file being
present -- this makes the suite runnable in CI without secrets.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    # Type-only import: `from __future__ import annotations` (above)
    # means annotations are never evaluated at runtime, so this does
    # NOT reintroduce the model-loading import at collection time --
    # the real, lazy `from fastapi.testclient import TestClient` inside
    # the `client` fixture below is unchanged and still what actually
    # runs.
    from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODEL_PATH = REPO_ROOT / "models" / "best_model.pkl"
DB_PATH = REPO_ROOT / "database" / "churn.db"
METRICS_PATH = REPO_ROOT / "evaluation" / "model_comparison.md"

TEST_API_KEY = "test-api-key-for-pytest-only"

requires_app_dependencies = pytest.mark.skipif(
    not MODEL_PATH.exists() or not DB_PATH.exists(),
    reason=(
        "models/best_model.pkl and/or database/churn.db are missing. "
        "The app imports and loads the real model at module load time, "
        "so run the full pipeline first (see README 'Running the "
        "Project'): database/init_db.py, etl/load_to_db.py, "
        "training/evaluate_models.py."
    ),
)


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures every test in this file runs against a known, fixed API key."""
    monkeypatch.setenv("API_KEY", TEST_API_KEY)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> "TestClient":
    """
    Real TestClient against the real app. Imported lazily inside the
    fixture (not at module top-level) so that a skip via
    requires_app_dependencies happens BEFORE the model-loading import
    is attempted, rather than the whole file failing to collect.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _valid_prediction_payload() -> dict:
    """A single known-valid CustomerPredictionRequest body."""
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
# /health only -- see module docstring for why this is the only
# endpoint that can be meaningfully isolated under the current app
# structure.
# ======================================================================


@pytest.mark.unit
@requires_app_dependencies
class TestHealthEndpoint:
    def test_health_returns_200(self, client: "TestClient") -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_does_not_require_authentication(self, client: "TestClient") -> None:
        response = client.get("/health")  # deliberately no X-API-Key header
        assert response.status_code == 200

    def test_health_response_shape(self, client: "TestClient") -> None:
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# ======================================================================
# SECTION 2 -- INTEGRATION TESTS
# Real TestClient, real database, real model.
# ======================================================================


@pytest.mark.integration
@requires_app_dependencies
class TestAuthentication:
    """Issue #16 explicit requirement: authentication behaviour."""

    def test_customers_without_api_key_returns_401(self, client: "TestClient") -> None:
        response = client.get("/customers")
        assert response.status_code == 401

    def test_customers_with_valid_api_key_returns_200(self, client: "TestClient") -> None:
        response = client.get("/customers", headers={"X-API-Key": TEST_API_KEY})
        assert response.status_code == 200

    def test_customers_with_empty_api_key_header_returns_401(self, client: "TestClient") -> None:
        response = client.get("/customers", headers={"X-API-Key": ""})
        assert response.status_code == 401

    def test_customers_with_incorrect_api_key_format_returns_401(self, client: "TestClient") -> None:
        response = client.get(
            "/customers", headers={"X-API-Key": "not-even-close-to-the-real-key!!"}
        )
        assert response.status_code == 401

    def test_kpis_without_api_key_returns_401(self, client: "TestClient") -> None:
        response = client.get("/kpis")
        assert response.status_code == 401

    def test_model_metrics_without_api_key_returns_401(self, client: "TestClient") -> None:
        response = client.get("/model-metrics")
        assert response.status_code == 401

    def test_predict_without_api_key_returns_401(self, client: "TestClient") -> None:
        response = client.post("/predict", json=_valid_prediction_payload())
        assert response.status_code == 401


@pytest.mark.integration
@requires_app_dependencies
class TestCustomersEndpoint:
    def test_customers_returns_a_list(self, client: "TestClient") -> None:
        response = client.get("/customers", headers={"X-API-Key": TEST_API_KEY})
        assert isinstance(response.json(), list)

    def test_customers_returns_real_schema_field_names(self, client: "TestClient") -> None:
        """
        Confirms this endpoint returns real, snake_case DB column
        names (e.g. customer_id) -- not Issue #10's original mock,
        which used camelCase (customerID). Regression guard for the
        Issue #14 real-integration swap.
        """
        response = client.get("/customers", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()
        assert len(body) > 0
        assert "customer_id" in body[0]
        assert "customerID" not in body[0]


@pytest.mark.integration
@requires_app_dependencies
class TestKpisEndpoint:
    def test_kpis_returns_200(self, client: "TestClient") -> None:
        response = client.get("/kpis", headers={"X-API-Key": TEST_API_KEY})
        assert response.status_code == 200

    def test_kpis_response_has_expected_keys(self, client: "TestClient") -> None:
        response = client.get("/kpis", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()
        for key in (
            "customer_count",
            "overall_churn_rate",
            "retention_rate",
            "average_monthly_charges",
            "total_monthly_revenue",
        ):
            assert key in body

    def test_kpis_churn_and_retention_rates_sum_to_100(self, client: "TestClient") -> None:
        response = client.get("/kpis", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()
        assert body["overall_churn_rate"] + body["retention_rate"] == pytest.approx(
            100.0, abs=0.1
        )

    def test_kpis_customer_count_matches_the_whole_database(
        self, client: "TestClient"
    ) -> None:
        """
        FGA-01 regression guard (Phase 1).

        /kpis used to be computed from CustomerRepository.get_all(),
        which returns one page (default 100 rows), so the endpoint
        reported a page as if it were the population. The check above
        could not catch that: 100.0 + 0.0 sums to 100 just fine.

        This asserts the endpoint's customer_count equals the actual
        row count in database/churn.db, computed here with direct SQL
        rather than through the service under test. On the tracked
        dataset that is 7,043; any page-scoped implementation reports
        100 and fails.
        """
        response = client.get("/kpis", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()

        connection = sqlite3.connect(DB_PATH)
        try:
            expected_count = connection.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0]
        finally:
            connection.close()

        assert body["customer_count"] == expected_count
        assert expected_count > 100, (
            "This guard only means something with more than 100 rows in the "
            "database; run the ETL pipeline (python etl/load_to_db.py)."
        )

    def test_kpis_churn_rate_matches_the_whole_database(
        self, client: "TestClient"
    ) -> None:
        """
        Companion to the count check above: the churn rate must be the
        population rate, not the first page's. On the tracked dataset
        the first 100 rows are all churned, so a page-scoped
        implementation reports 100.0 instead of 26.54.
        """
        response = client.get("/kpis", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()

        connection = sqlite3.connect(DB_PATH)
        try:
            churned, total = connection.execute(
                """
                SELECT SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END),
                       COUNT(*)
                FROM customers
                """
            ).fetchone()
        finally:
            connection.close()

        assert body["overall_churn_rate"] == pytest.approx(
            round(100.0 * churned / total, 2)
        )
        assert body["retention_rate"] == pytest.approx(
            round(100.0 - round(100.0 * churned / total, 2), 2)
        )

    def test_kpis_totals_match_the_whole_database(self, client: "TestClient") -> None:
        """Same whole-table reference for the charge aggregates."""
        response = client.get("/kpis", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()

        connection = sqlite3.connect(DB_PATH)
        try:
            total_charges, avg_charges = connection.execute(
                """
                SELECT SUM(monthly_charges),
                       SUM(monthly_charges) / COUNT(*)
                FROM customers
                """
            ).fetchone()
        finally:
            connection.close()

        assert body["total_monthly_revenue"] == pytest.approx(round(total_charges, 2))
        assert body["average_monthly_charges"] == pytest.approx(round(avg_charges, 2))

    def test_kpis_is_not_scoped_to_the_customers_page(self, client: "TestClient") -> None:
        """
        The KPI population must not be bounded by the /customers page.
        With more than 100 rows in the table, a summary that equals
        the default page size is the bug this guards against.
        """
        customers = client.get(
            "/customers", headers={"X-API-Key": TEST_API_KEY}
        ).json()
        kpis = client.get("/kpis", headers={"X-API-Key": TEST_API_KEY}).json()

        assert len(customers) <= 100  # pagination still bounds /customers
        assert kpis["customer_count"] >= len(customers)
        if kpis["customer_count"] > 100:
            assert kpis["customer_count"] > len(customers)


@pytest.mark.integration
@requires_app_dependencies
class TestModelMetricsEndpoint:
    def test_model_metrics_returns_200(self, client: "TestClient") -> None:
        response = client.get("/model-metrics", headers={"X-API-Key": TEST_API_KEY})
        assert response.status_code == 200

    def test_model_metrics_response_has_expected_keys(self, client: "TestClient") -> None:
        response = client.get("/model-metrics", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()
        for key in ("accuracy", "precision", "recall", "roc_auc"):
            assert key in body

    def test_model_metrics_values_are_valid_probabilities(self, client: "TestClient") -> None:
        response = client.get("/model-metrics", headers={"X-API-Key": TEST_API_KEY})
        body = response.json()
        for key in ("accuracy", "precision", "recall", "roc_auc"):
            assert 0.0 <= body[key] <= 1.0


@pytest.mark.integration
@requires_app_dependencies
class TestPredictEndpointBaseline:
    """Issue #16 explicit requirement: /predict happy-path + schema."""

    def test_predict_with_valid_payload_returns_200(self, client: "TestClient") -> None:
        response = client.post(
            "/predict",
            json=_valid_prediction_payload(),
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert response.status_code == 200

    def test_predict_response_matches_locked_schema(self, client: "TestClient") -> None:
        response = client.post(
            "/predict",
            json=_valid_prediction_payload(),
            headers={"X-API-Key": TEST_API_KEY},
        )
        body = response.json()
        assert set(body.keys()) == {"churn_probability", "churn_prediction"}
        assert isinstance(body["churn_probability"], float)
        assert isinstance(body["churn_prediction"], bool)

    def test_predict_probability_is_within_valid_range(self, client: "TestClient") -> None:
        response = client.post(
            "/predict",
            json=_valid_prediction_payload(),
            headers={"X-API-Key": TEST_API_KEY},
        )
        probability = response.json()["churn_probability"]
        assert 0.0 <= probability <= 1.0

    def test_predict_is_not_the_retired_mock_constant(self, client: "TestClient") -> None:
        """
        Regression guard: Issue #10's mock always returned exactly
        0.42 regardless of input. This alone doesn't prove the real
        model is "correct," only that the retired mock constant is not
        silently still wired in.
        """
        response = client.post(
            "/predict",
            json=_valid_prediction_payload(),
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert response.json()["churn_probability"] != 0.42


@pytest.mark.integration
@requires_app_dependencies
class TestPredictEndpointEdgeCases:
    """Issue #16 explicit requirement: malformed data, invalid values."""

    def test_predict_with_missing_required_field_returns_422_not_500(self, client: "TestClient") -> None:
        response = client.post(
            "/predict",
            json={"gender": "Female"},
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert response.status_code == 422

    def test_predict_with_wrong_types_returns_422(self, client: "TestClient") -> None:
        payload = _valid_prediction_payload()
        payload["tenure"] = "not-a-number"
        response = client.post(
            "/predict", json=payload, headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 422

    def test_predict_with_negative_tenure_returns_422(self, client: "TestClient") -> None:
        """
        CustomerPredictionRequest.tenure has ge=0. Negative tenure is
        a physically impossible value and must be rejected by
        validation before it ever reaches the model.
        """
        payload = _valid_prediction_payload()
        payload["tenure"] = -5
        response = client.post(
            "/predict", json=payload, headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 422

    def test_predict_with_out_of_range_senior_citizen_returns_422(self, client: "TestClient") -> None:
        """
        CustomerPredictionRequest.SeniorCitizen has ge=0, le=1 (must
        be exactly 0 or 1). An impossible value like 5 must be
        rejected by validation.
        """
        payload = _valid_prediction_payload()
        payload["SeniorCitizen"] = 5
        response = client.post(
            "/predict", json=payload, headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 422

    def test_predict_with_negative_monthly_charges_returns_422(self, client: "TestClient") -> None:
        payload = _valid_prediction_payload()
        payload["MonthlyCharges"] = -70.05
        response = client.post(
            "/predict", json=payload, headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 422

    def test_predict_with_empty_json_body_returns_422(self, client: "TestClient") -> None:
        response = client.post(
            "/predict", json={}, headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 422

    def test_predict_error_response_has_detail_field(self, client: "TestClient") -> None:
        """
        FastAPI's standard validation error shape includes a "detail"
        key describing what failed -- confirms /predict's 422s are
        genuinely informative validation errors, not bare status codes
        with no explanation.
        """
        response = client.post(
            "/predict",
            json={"gender": "Female"},
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert "detail" in response.json()

    def test_predict_with_unseen_category_does_not_return_500(self, client: "TestClient") -> None:
        """
        A category value that plausibly never appeared during
        training (the trained OneHotEncoder uses
        handle_unknown="ignore") must not crash the endpoint with a
        500 -- confirmed at the predict.py level directly during test
        authorship; this test re-confirms it holds through the full
        HTTP layer too.
        """
        payload = _valid_prediction_payload()
        payload["InternetService"] = "Satellite"
        response = client.post(
            "/predict", json=payload, headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 200
        assert set(response.json().keys()) == {"churn_probability", "churn_prediction"}