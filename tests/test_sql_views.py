"""
Issue #19 -- Full Regression Pass -- tests/test_sql_views.py

Owner: Salome, edited by Theresia, added during the Issue #19 full regression pass.
This file predates Issue #19.
(it already existed and passed once the full pipeline had been run
locally), but had no skip-guard, so it hard-FAILED rather than
SKIPPED on a fresh clone -- the only one of the four test files in
tests/ that behaved this way. See docs/qa_findings.md's Issue #19
section for the full writeup of this finding.

Prerequisites
-------------
These tests assume sql/views.sql has already been applied to
database/churn.db via:

    python database/init_db.py
    python etl/load_to_db.py
    python database/init_views.py

If database/churn.db does not exist, or either view is missing (e.g.
init_views.py has not been run yet), these tests SKIP with a clear
reason -- matching the pattern already used by
tests/test_etl.py::requires_populated_db and
tests/test_models.py::requires_populated_db/requires_model_artifact --
rather than failing with a confusing sqlite3.OperationalError.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database.db_connection import get_connection

DB_PATH = REPO_ROOT / "database" / "churn.db"

REQUIRED_VIEWS = ("view_churn_by_contract", "view_churn_by_tenure_bucket")


def _views_exist() -> bool:
    """
    True if database/churn.db exists AND both required views have
    been created in it. Used to skip gracefully on a fresh clone, or
    after the ETL pipeline has run but before database/init_views.py
    has -- both are legitimate pre-pipeline states, not bugs.
    """
    if not DB_PATH.exists():
        return False
    try:
        conn = get_connection()
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            )
            existing = {row[0] for row in cursor.fetchall()}
            return all(view in existing for view in REQUIRED_VIEWS)
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return False


requires_views = pytest.mark.skipif(
    not _views_exist(),
    reason=(
        "database/churn.db is missing, or view_churn_by_contract / "
        "view_churn_by_tenure_bucket have not been created yet. Run "
        "the full pipeline first (see README 'Run the ETL pipeline'): "
        "python database/init_db.py && python etl/load_to_db.py && "
        "python database/init_views.py"
    ),
)


@pytest.mark.integration
@requires_views
class TestViewsExist:
    """Verify both required analytical views exist in the schema."""

    def test_view_churn_by_contract_exists(self) -> None:
        """Verify the contract churn view exists."""
        conn = get_connection()

        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='view'
            AND name='view_churn_by_contract'
            """
        )

        assert cursor.fetchone() is not None

        conn.close()

    def test_view_churn_by_tenure_bucket_exists(self) -> None:
        """Verify the tenure bucket churn view exists."""
        conn = get_connection()

        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='view'
            AND name='view_churn_by_tenure_bucket'
            """
        )

        assert cursor.fetchone() is not None

        conn.close()


@pytest.mark.integration
@requires_views
class TestViewsReturnData:
    """Verify both views return rows once the pipeline has populated the database."""

    def test_contract_view_returns_data(self) -> None:
        """Verify the contract churn view returns rows."""
        conn = get_connection()

        cursor = conn.execute(
            """
            SELECT COUNT(*)
            FROM view_churn_by_contract
            """
        )

        assert cursor.fetchone()[0] > 0

        conn.close()

    def test_tenure_view_returns_data(self) -> None:
        """Verify the tenure bucket churn view returns rows."""
        conn = get_connection()

        cursor = conn.execute(
            """
            SELECT COUNT(*)
            FROM view_churn_by_tenure_bucket
            """
        )

        assert cursor.fetchone()[0] > 0

        conn.close()


@pytest.mark.integration
@requires_views
class TestViewSchemas:
    """Verify both views expose the exact columns the dashboard depends on."""

    def test_contract_view_contains_expected_columns(self) -> None:
        """Verify the contract churn view exposes the expected columns."""
        conn = get_connection()

        cursor = conn.execute(
            """
            SELECT *
            FROM view_churn_by_contract
            LIMIT 1
            """
        )

        columns = [column[0] for column in cursor.description]

        expected = [
            "contract",
            "total_customers",
            "churned_customers",
            "churn_rate_percentage",
        ]

        assert columns == expected

        conn.close()

    def test_tenure_view_contains_expected_columns(self) -> None:
        """Verify the tenure bucket churn view exposes the expected columns."""
        conn = get_connection()

        cursor = conn.execute(
            """
            SELECT *
            FROM view_churn_by_tenure_bucket
            LIMIT 1
            """
        )

        columns = [column[0] for column in cursor.description]

        expected = [
            "tenure_bucket",
            "total_customers",
            "churned_customers",
            "churn_rate_percentage",
        ]

        assert columns == expected

        conn.close()


@pytest.mark.integration
class TestViewsIdempotency:
    """
    Confirms database/init_views.py itself is safe to run repeatedly --
    a gap identified during the Issue #19 walkthrough:
    database/init_db.py has dedicated idempotency coverage in
    tests/test_etl.py::TestDatabaseIdempotency, but init_views.py had
    no equivalent test anywhere despite following the same
    drop-and-recreate pattern (see its own docstring).
    """

    def test_init_views_can_run_twice_without_error(self) -> None:
        if not DB_PATH.exists():
            pytest.skip(
                "database/churn.db is missing. Run python "
                "database/init_db.py first."
            )

        from database.init_views import init_views

        # Running twice back-to-back must not raise, and must leave
        # both views queryable afterward -- mirrors
        # TestDatabaseIdempotency's pattern for init_db() in
        # tests/test_etl.py.
        init_views()
        init_views()

        conn = get_connection()
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            )
            existing = {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

        for view in REQUIRED_VIEWS:
            assert view in existing

# ======================================================================
# Tenure-bucket definitions (Phase 3, 2026-10-06 -- audit item FGA-06)
#
# Before this, the same business question ("which tenure group churns most?")
# had two answers: `sql/analysis_queries.sql` used four ranges (0-12, 13-24,
# 25-48, 49-72) while `view_churn_by_tenure_bucket` used three (0-12, 13-36,
# 37+). The view's grouping is the one the committed Power BI "Churn Rate by
# Tenure" visual renders, so the *reporting* query was aligned to the view and
# both definitions were named in the docs. The model's engineered TenureBucket
# feature stays four-range and is documented as a separate modelling input.
#
# TestTenureBucketBoundaries runs without any generated artifact (it builds its
# own throwaway database from sql/schema.sql + sql/views.sql).
# ======================================================================

BOUNDARY_QUERY = (
    REPO_ROOT / "sql" / "analysis_queries.sql"
)


def _business_question_tenure_statement() -> str:
    """
    The tenure-bucket statement from sql/analysis_queries.sql, comments stripped.

    Extracting it from the file (rather than restating the CASE in the test)
    is the point: the test fails if the query file drifts from the view again.
    """
    text = BOUNDARY_QUERY.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("--")
    )
    statements = [s.strip() for s in without_comments.split(";") if s.strip()]
    matches = [s for s in statements if "tenure_bucket" in s and "CASE" in s.upper()]
    assert len(matches) == 1, (
        f"expected exactly one tenure-bucket CASE statement in "
        f"sql/analysis_queries.sql, found {len(matches)}"
    )
    return matches[0]


def _build_boundary_database(path: Path, tenures: list[int]) -> None:
    """A throwaway customers table + the real views, from the real SQL files."""
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            (REPO_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
        )
        connection.executescript(
            (REPO_ROOT / "sql" / "views.sql").read_text(encoding="utf-8")
        )
        for index, tenure in enumerate(tenures):
            connection.execute(
                "INSERT INTO customers (customer_id, tenure_months, monthly_charges, "
                "churn_label, churn_value) VALUES (?, ?, ?, ?, ?)",
                (f"T-{index:03d}", tenure, 50.0, "Yes" if index % 2 else "No", index % 2),
            )
        connection.commit()
    finally:
        connection.close()


@pytest.mark.unit
class TestTenureBucketBoundaries:
    """Boundary behaviour of the reporting view, on a purpose-built database."""

    # 0 / 12 / 13 / 36 flip at the documented edges; 37 starts the open bucket;
    # 72 and 75 are the values the *model* feature cannot bin (>72 -> NaN) --
    # they must still land in the reporting view's 37+ bucket.
    BOUNDARY_TENURES = (0, 12, 13, 36, 37, 72, 75)

    def test_view_buckets_every_boundary_value_exactly_once(self, tmp_path: Path) -> None:
        db_path = tmp_path / "boundary.db"
        _build_boundary_database(db_path, self.BOUNDARY_TENURES)

        connection = sqlite3.connect(db_path)
        try:
            rows = connection.execute(
                "SELECT tenure_bucket, total_customers FROM view_churn_by_tenure_bucket"
            ).fetchall()
        finally:
            connection.close()

        assert dict(rows) == {
            "0-12 Months": 2,   # tenure 0, 12
            "13-36 Months": 2,  # tenure 13, 36
            "37+ Months": 3,    # tenure 37, 72, 75
        }
        assert sum(count for _bucket, count in rows) == len(self.BOUNDARY_TENURES), (
            "every customer must fall into exactly one bucket"
        )

    def test_view_uses_the_documented_three_range_definition(self, tmp_path: Path) -> None:
        db_path = tmp_path / "labels.db"
        _build_boundary_database(db_path, self.BOUNDARY_TENURES)

        connection = sqlite3.connect(db_path)
        try:
            labels = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT tenure_bucket FROM view_churn_by_tenure_bucket"
                )
            }
        finally:
            connection.close()

        assert labels == {"0-12 Months", "13-36 Months", "37+ Months"}, (
            "the reporting view's grouping changed. It is what the committed "
            "Power BI 'Churn Rate by Tenure' visual renders and what "
            "docs/data_dictionary.md / docs/sql_analysis_summary.md document."
        )


@pytest.mark.integration
@requires_views
class TestTenureBucketDefinitionsAgree:
    """
    The reporting query and the reusable view must answer the same question the
    same way (audit FGA-06). These compare real outputs on the real database.
    """

    def _query_buckets(self) -> dict[str, tuple[int, int]]:
        conn = get_connection()
        try:
            cur = conn.execute(_business_question_tenure_statement())
            return {
                row[0]: (row[1], row[2])
                for row in cur.fetchall()
            }
        finally:
            conn.close()

    def _view_buckets(self) -> dict[str, tuple[int, int]]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT tenure_bucket, total_customers, churned_customers "
                "FROM view_churn_by_tenure_bucket"
            )
            return {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        finally:
            conn.close()

    def test_analysis_query_and_view_return_identical_buckets(self) -> None:
        assert self._query_buckets() == self._view_buckets(), (
            "sql/analysis_queries.sql's tenure statement and "
            "view_churn_by_tenure_bucket disagree. They are two published answers "
            "to the same business question and must use the same definition -- see "
            "docs/sql_analysis_summary.md."
        )

    def test_view_covers_every_customer_exactly_once(self) -> None:
        conn = get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            bucket_total = conn.execute(
                "SELECT SUM(total_customers) FROM view_churn_by_tenure_bucket"
            ).fetchone()[0]
        finally:
            conn.close()

        assert bucket_total == total

    def test_model_feature_grouping_is_documented_as_a_separate_definition(self) -> None:
        """
        The four-range modelling feature (0-12, 13-24, 25-48, 49-72) is
        intentionally different from the three-range reporting grouping. If that
        is true, the data dictionary must say so -- otherwise a comparison of
        the two sets of counts looks like a bug.
        """
        data_dictionary = (REPO_ROOT / "docs" / "data_dictionary.md").read_text(
            encoding="utf-8"
        )
        assert "13–36" in data_dictionary or "13-36" in data_dictionary, (
            "docs/data_dictionary.md must document the reporting view's three-range "
            "grouping"
        )
        assert "not** the reporting definition" in data_dictionary or (
            "not the reporting definition" in data_dictionary
        ), (
            "docs/data_dictionary.md must state that the ML TenureBucket feature is "
            "not the reporting definition"
        )

        summary = (REPO_ROOT / "docs" / "sql_analysis_summary.md").read_text(
            encoding="utf-8"
        )
        assert "13–36 Months" in summary or "13-36 Months" in summary
        assert "different, deliberately finer grouping" in summary or (
            "different" in summary and "modelling input" in summary
        )
