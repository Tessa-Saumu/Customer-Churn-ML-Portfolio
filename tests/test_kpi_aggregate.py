"""
Phase 1 (audit item FGA-01) -- tests/test_kpi_aggregate.py

Regression coverage for the /kpis population aggregate.

Why this file exists
--------------------
`app/services/kpi_service.py` originally computed the executive KPIs
in Python from `CustomerRepository.get_all()`. Pagination was later
added to `get_all()` with a default page size of 100, so /kpis began
summarizing only the first page while still presenting it as the whole
population. On the tracked dataset the first 100 rows happen to be all
churned, so the endpoint returned:

    customer_count: 100, overall_churn_rate: 100.0, retention_rate: 0.0

which contradicted docs/api_examples.md (7043 / 26.54) and both
endpoint verification scripts. Nothing caught it, because the KPI
tests only asserted the response keys and that churn + retention sums
to ~100 -- a check that 100.0 + 0.0 trivially satisfies.

These tests run against a purpose-built temporary SQLite database, so
they do NOT require the repository's generated `database/churn.db` or
`models/best_model.pkl`: the regression must be catchable on a fresh
clone, not only after the full pipeline has run. They are marked
`integration` because they exercise a real SQLite database and the
real repository/service code.

Deliberately >100 rows, with the first 100 all churned
------------------------------------------------------
The fixture mirrors the real dataset's failure signature (first page
100% churned, population ~67% churned) so that any implementation
which reads only the default page fails loudly instead of passing by
coincidence.

How the temporary database is wired in
--------------------------------------
`database/db_connection.py` resolves `database/churn.db` relative to
the current working directory, so the fixture creates
`<tmp>/database/churn.db` and uses `monkeypatch.chdir` to point the
real `get_connection()` at it. This exercises the production
connection path (including its directory creation and PRAGMA) rather
than stubbing it out.
"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.repository.customer_repository import CustomerRepository
from app.services.kpi_service import get_kpis

SCHEMA_PATH = REPO_ROOT / "sql" / "schema.sql"

# Must exceed the /customers default page size (100) for the
# "is this page-scoped?" assertions below to mean anything.
POPULATION = 150
# The first 100 rows -- exactly one default page -- are all churned.
FIRST_PAGE_CHURNED = 100
CHURNED = 100
RETAINED = POPULATION - CHURNED


def _insert_customer(
    connection: sqlite3.Connection,
    index: int,
    *,
    churn_label: str,
    monthly_charges: float | None,
) -> None:
    """Inserts one row that satisfies every CHECK constraint in schema.sql."""
    connection.execute(
        """
        INSERT INTO customers (
            customer_id, gender, senior_citizen, tenure_months,
            monthly_charges, total_charges, churn_label, churn_value,
            latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"KPI-TEST-{index:04d}",
            "Female" if index % 2 == 0 else "Male",
            "Yes" if index % 3 == 0 else "No",
            index,
            monthly_charges,
            None if monthly_charges is None else monthly_charges * index,
            churn_label,
            1 if churn_label == "Yes" else 0,
            34.05,
            -118.24,
        ),
    )


@pytest.fixture()
def populated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    A temporary `database/churn.db` holding POPULATION deliberately
    mixed customers: the first FIRST_PAGE_CHURNED rows (exactly one
    default /customers page) are all churned, the rest are retained.

    Yields the path to the temporary database file.
    """
    db_path = tmp_path / "database" / "churn.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for index in range(POPULATION):
            _insert_customer(
                connection,
                index,
                churn_label="Yes" if index < CHURNED else "No",
                # Distinct, non-integer monthly charges so a whole-table
                # SUM/AVG cannot be reproduced by counting rows alone.
                monthly_charges=20.0 + index * 0.25,
            )
        connection.commit()
    finally:
        connection.close()

    # Points the real get_connection() at the temporary database.
    monkeypatch.chdir(tmp_path)

    yield db_path


def _reference_totals(db_path: Path) -> dict[str, float]:
    """
    Independently computed whole-table reference values, written as
    plain SQL against the same file -- deliberately not reusing the
    repository's aggregate query, so the test is not comparing the
    implementation with itself.
    """
    connection = sqlite3.connect(db_path)
    try:
        count, churned, total_charges, avg_charges = connection.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END),
                   SUM(monthly_charges),
                   SUM(monthly_charges) / COUNT(*)
            FROM customers
            """
        ).fetchone()
    finally:
        connection.close()

    churn_rate = round(100.0 * churned / count, 2)
    return {
        "customer_count": float(count),
        "churned_count": float(churned),
        "overall_churn_rate": churn_rate,
        "retention_rate": round(100.0 - churn_rate, 2),
        "average_monthly_charges": round(avg_charges, 2),
        "total_monthly_revenue": round(total_charges, 2),
    }


@pytest.mark.integration
class TestKpiAggregateIsWholeTable:
    """The core FGA-01 regression: /kpis must see every row."""

    def test_kpis_match_independent_whole_table_sql_totals(
        self, populated_db: Path
    ) -> None:
        expected = _reference_totals(populated_db)
        actual = get_kpis()

        assert actual["customer_count"] == int(expected["customer_count"])
        assert actual["overall_churn_rate"] == pytest.approx(
            expected["overall_churn_rate"]
        )
        assert actual["retention_rate"] == pytest.approx(expected["retention_rate"])
        assert actual["average_monthly_charges"] == pytest.approx(
            expected["average_monthly_charges"]
        )
        assert actual["total_monthly_revenue"] == pytest.approx(
            expected["total_monthly_revenue"]
        )

    def test_kpis_are_not_scoped_to_the_default_page(
        self, populated_db: Path
    ) -> None:
        """
        The sharp version of the regression: the first 100 rows of the
        fixture are ALL churned, so a page-scoped implementation
        reports customer_count=100 / churn rate=100.0. The whole-table
        truth is 150 customers and a 66.67% churn rate.
        """
        result = get_kpis()

        assert result["customer_count"] == POPULATION
        assert result["overall_churn_rate"] == pytest.approx(66.67)
        assert result["retention_rate"] == pytest.approx(33.33)

    def test_kpis_response_shape_is_unchanged(self, populated_db: Path) -> None:
        """
        Phase 1 must not touch the public contract: exactly the five
        Issue #10 keys, in the same types, with the same rounding.
        """
        result = get_kpis()

        assert set(result.keys()) == {
            "customer_count",
            "overall_churn_rate",
            "retention_rate",
            "average_monthly_charges",
            "total_monthly_revenue",
        }
        assert isinstance(result["customer_count"], int)
        for key in (
            "overall_churn_rate",
            "retention_rate",
            "average_monthly_charges",
            "total_monthly_revenue",
        ):
            assert isinstance(result[key], float)
        # Two-decimal rounding, as before.
        for key in (
            "overall_churn_rate",
            "retention_rate",
            "average_monthly_charges",
            "total_monthly_revenue",
        ):
            assert result[key] == round(result[key], 2)

    def test_churn_and_retention_rates_still_sum_to_100(
        self, populated_db: Path
    ) -> None:
        """Pre-existing invariant, kept so the old check is not weakened."""
        result = get_kpis()
        assert result["overall_churn_rate"] + result["retention_rate"] == pytest.approx(
            100.0, abs=0.1
        )


@pytest.mark.integration
class TestKpiAggregateDoesNotFetchCustomerRows:
    """
    The aggregate must be a database-side summary. Fetching customer
    rows to summarize them is what made the endpoint wrong (and is
    what would make it expensive on a large table), so get_kpis must
    never call get_all().
    """

    def test_get_kpis_never_calls_get_all(self, populated_db: Path) -> None:
        class ExplodingRepository(CustomerRepository):
            def get_all(self, page: int = 0, size: int = 100) -> list[dict[str, Any]]:
                raise AssertionError(
                    "get_kpis() must not read customer rows; it must use the "
                    "database-side aggregate (see FGA-01)"
                )

        # Sanity: the subclass really is in play.
        with pytest.raises(AssertionError):
            ExplodingRepository().get_all()

        result = get_kpis(ExplodingRepository())
        assert result["customer_count"] == POPULATION


@pytest.mark.integration
class TestPaginationIsPreserved:
    """
    FGA-01 must not be fixed by weakening the mentor's pagination.
    /customers keeps returning one page by default.
    """

    def test_default_get_all_returns_at_most_one_page(
        self, populated_db: Path
    ) -> None:
        customers = CustomerRepository().get_all()
        assert len(customers) == 100
        assert len(customers) < POPULATION

    def test_explicit_page_and_size_are_unchanged(self, populated_db: Path) -> None:
        repository = CustomerRepository()

        first_page = repository.get_all(page=0, size=100)
        second_page = repository.get_all(page=1, size=100)

        assert len(first_page) == 100
        assert len(second_page) == POPULATION - 100
        assert first_page[0]["customer_id"] != second_page[0]["customer_id"]

    def test_small_page_size_is_respected(self, populated_db: Path) -> None:
        assert len(CustomerRepository().get_all(page=0, size=5)) == 5

    def test_page_beyond_the_end_returns_no_rows(self, populated_db: Path) -> None:
        assert CustomerRepository().get_all(page=99, size=100) == []

    def test_invalid_page_and_size_still_raise_value_error(
        self, populated_db: Path
    ) -> None:
        repository = CustomerRepository()
        with pytest.raises(ValueError):
            repository.get_all(page=-1)
        with pytest.raises(ValueError):
            repository.get_all(size=0)


@pytest.mark.integration
class TestKpiAggregateNullAndEmptySemantics:
    """
    The aggregate must preserve the previous null/empty behaviour
    rather than quietly redefining it.
    """

    def test_empty_table_returns_zeroed_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "database" / "churn.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        try:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            connection.commit()
        finally:
            connection.close()
        monkeypatch.chdir(tmp_path)

        assert get_kpis() == {
            "customer_count": 0,
            "overall_churn_rate": 0.0,
            "retention_rate": 0.0,
            "average_monthly_charges": 0.0,
            "total_monthly_revenue": 0.0,
        }

    def test_null_monthly_charges_count_as_zero_and_stay_in_the_denominator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Previous behaviour: `float(c.get("monthly_charges") or 0.0)` --
        a NULL charge contributed 0 to the total and still counted as a
        customer. The aggregate reproduces that (SUM ignores NULLs,
        and the divisor is COUNT(*), not SQL AVG()).
        """
        db_path = tmp_path / "database" / "churn.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        try:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            _insert_customer(connection, 0, churn_label="No", monthly_charges=100.0)
            _insert_customer(connection, 1, churn_label="Yes", monthly_charges=None)
            _insert_customer(connection, 2, churn_label="No", monthly_charges=200.0)
            connection.commit()
        finally:
            connection.close()
        monkeypatch.chdir(tmp_path)

        result = get_kpis()

        assert result["customer_count"] == 3
        assert result["overall_churn_rate"] == pytest.approx(33.33)
        assert result["total_monthly_revenue"] == pytest.approx(300.0)
        # 300 / 3, NOT 300 / 2 -- the NULL row stays in the denominator.
        assert result["average_monthly_charges"] == pytest.approx(100.0)
