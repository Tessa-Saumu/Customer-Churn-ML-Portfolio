"""
Issue #8 -- ETL & Database -- app/repository/customer_repository.py

This is the layer everyone else's code is required to go through --
per the spec, Praise's API or Latifah's training code querying the raw
CSV or raw SQL directly instead of this class is an explicit reject
condition. Get the two methods below right and this file is done.

Given in full since this is a standard, well-known pattern (a typed
repository over a DB connection) rather than something that depends on
judgment calls about your specific data. The requirement here isn't
that you write this from scratch -- it's that you can explain every
line of it before it goes up. Once you can, move on to running the
full pipeline end-to-end as your final check for today.
"""

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database.db_connection import get_connection

logger = logging.getLogger(__name__)


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


class CustomerRepository:
    def get_all(
        self,
        page: int = 0,
        size: int = 100,
    ) -> list[dict[str, Any]]:
        if page < 0:
            raise ValueError("page must be >= 0")
        if size <= 0:
            raise ValueError("size must be > 0")

        limit = size
        offset = page * size

        connection = get_connection()
        try:
            cursor = connection.execute(
                "SELECT * FROM customers LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cursor.fetchall()
            result = [_row_to_dict(cursor, row) for row in rows]
            logger.info(
                "get_all returned %d customers (page=%d, size=%d)",
                len(result),
                page,
                size,
            )
            return result
        finally:
            connection.close()

    def get_by_id(self, customer_id: str) -> dict[str, Any] | None:
        connection = get_connection()
        try:
            cursor = connection.execute(
                "SELECT * FROM customers WHERE customer_id = ?",
                (customer_id,),
            )
            row = cursor.fetchone()
            if row is None:
                logger.info("get_by_id: no customer found for id=%s", customer_id)
                return None
            return _row_to_dict(cursor, row)
        finally:
            connection.close()

    def get_kpi_aggregate(self) -> dict[str, Any]:
        """
        Single-row SQL aggregate over the WHOLE customers table, for
        population-level summaries such as app/services/kpi_service.py.

        Why this exists (Phase 1 / audit item FGA-01): /kpis used to be
        computed by calling get_all(), which returns one *page* of
        customers (default size 100, mentor-added pagination). The KPI
        service therefore summarized the first 100 rows and reported
        them as the whole population -- on the tracked dataset that
        produced customer_count=100 and a 100% churn rate.

        This keeps the population math in the database so a summary
        never has to materialize customer rows, and so it stays correct
        as the table grows. It does NOT change get_all(): /customers
        remains paginated by default, which is intentional.

        Returned keys (raw, unrounded -- rounding is the caller's
        presentation decision):
            customer_count          COUNT(*) over the whole table
            churned_count           rows with churn_label = 'Yes'
            total_monthly_charges   SUM(monthly_charges); NULL charges
                                   contribute 0, matching the previous
                                   Python `float(x or 0.0)` handling
            average_monthly_charges SUM(monthly_charges) / COUNT(*) --
                                   deliberately NOT SQL AVG(), because
                                   AVG() would divide by the number of
                                   NON-NULL charges and silently change
                                   the previous semantics

        churn is counted on churn_label (not churn_value) to preserve
        the exact behaviour the service had before this method existed.
        """
        connection = get_connection()
        try:
            cursor = connection.execute(
                """
                SELECT
                    COUNT(*) AS customer_count,
                    COALESCE(
                        SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END), 0
                    ) AS churned_count,
                    COALESCE(SUM(monthly_charges), 0.0) AS total_monthly_charges,
                    COALESCE(SUM(monthly_charges), 0.0) / COUNT(*)
                        AS average_monthly_charges
                FROM customers
                """
            )
            row = cursor.fetchone()
            result = _row_to_dict(cursor, row)
            logger.info(
                "get_kpi_aggregate over the whole customers table: %s", result
            )
            return result
        finally:
            connection.close()