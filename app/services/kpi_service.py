"""
Issue #14 -- Real Integration -- app/services/kpi_service.py

NEW FILE (flagged in PR Notes).

Why this exists / cross-team flag: the issue requires /kpis to be
"connected to the finalized analytics data source." sql/views.sql
(Salome, Issue #9) defines view_churn_by_contract and
view_churn_by_tenure_bucket -- both grouped/bucketed views, neither of
which is a single-row summary matching the KPI shape Issue #10's
placeholder committed to (customer_count, overall_churn_rate,
retention_rate, average_monthly_charges, total_monthly_revenue). No
view in views.sql produces that shape directly.

Rather than block on a new SQL view being added, or reshape the
response (forbidden -- Project_Specification.md section 2.3 explicitly
prohibits changing /kpis' response shape as part of this PR), this
computes the same KPI values from CustomerRepository, which is real,
database-backed data -- satisfying "no placeholder data remains
connected to production endpoints" without touching the public
contract.

Per Project_Specification.md section 4, this is exactly the kind of
mid-sprint interface question that should be flagged to every
downstream owner directly, not just left in a Notes field: recommend
Salome add a dedicated KPI view (e.g. view_executive_kpis) so this
logic can move into SQL. Flagging in PR Notes as a follow-up
suggestion, not blocking this PR on it.


PHASE 1 UPDATE (audit item FGA-01, 2026-10-05) -- the aggregate path
--------------------------------------------------------------------
The Issue #14 implementation computed these values in Python from
CustomerRepository.get_all(). Pagination was added to get_all() later
(stretch commit 806705c, 2026-08-12, mentor) with a default page size
of 100, so /kpis silently began summarizing only the first 100 rows
while still presenting them as the whole population: on the tracked
dataset it returned customer_count=100 and overall_churn_rate=100.0,
contradicting docs/api_examples.md (7043 / 26.54) and both endpoint
verification scripts. No test caught it, because the KPI tests only
asserted the response keys and that churn + retention sums to ~100 --
which 100.0 + 0.0 trivially satisfies.

The values are now computed by a single database-side aggregate,
CustomerRepository.get_kpi_aggregate(), so a population summary is
correct for any table size without materializing customer rows.

Deliberately unchanged:
- get_all() keeps its paginated default (the mentor's intentional
  design). This fix does not remove pagination, and it does not add an
  "all rows" mode to /customers.
- The /kpis response keys, rounding, null semantics and the
  empty-table behaviour are byte-for-byte the same as before; only the
  source of the numbers changed. Regression coverage lives in
  tests/test_kpi_aggregate.py and tests/test_api.py.

Not done here: introducing a dedicated view_executive_kpis SQL view.
The aggregate already lives at the repository boundary this service
depends on, which is the smallest change that makes /kpis correct; a
new view would also require a database rebuild for existing
checkouts, and sql/views.sql is Salome's Issue #9 deliverable.
"""

import logging
from typing import Any

from app.repository.customer_repository import CustomerRepository

logger = logging.getLogger(__name__)


def get_kpis(repository: CustomerRepository | None = None) -> dict[str, Any]:
    """
    Computes executive KPIs from real customer data:
    customer_count, overall_churn_rate, retention_rate,
    average_monthly_charges, total_monthly_revenue.

    Shape matches Issue #10's placeholder exactly, per the "no public
    contract changes" rule for Issue #14.

    The numbers come from one whole-table SQL aggregate
    (CustomerRepository.get_kpi_aggregate), NOT from a page of
    customers -- see the module docstring for why that distinction
    matters.
    """
    repo = repository or CustomerRepository()
    aggregate = repo.get_kpi_aggregate()

    customer_count = int(aggregate.get("customer_count") or 0)
    if customer_count == 0:
        logger.warning("get_kpis: no customers found in database")
        return {
            "customer_count": 0,
            "overall_churn_rate": 0.0,
            "retention_rate": 0.0,
            "average_monthly_charges": 0.0,
            "total_monthly_revenue": 0.0,
        }

    churned = int(aggregate.get("churned_count") or 0)
    total_monthly_charges = float(aggregate.get("total_monthly_charges") or 0.0)
    # The aggregate already divides by COUNT(*) so that rows with a NULL
    # monthly_charges stay in the denominator, exactly as the previous
    # `total / customer_count` did. Guarded here only so a NULL can
    # never reach float().
    average_monthly_charges = float(aggregate.get("average_monthly_charges") or 0.0)

    overall_churn_rate = round(100.0 * churned / customer_count, 2)
    retention_rate = round(100.0 - overall_churn_rate, 2)
    average_monthly_charges = round(average_monthly_charges, 2)
    total_monthly_revenue = round(total_monthly_charges, 2)

    result = {
        "customer_count": customer_count,
        "overall_churn_rate": overall_churn_rate,
        "retention_rate": retention_rate,
        "average_monthly_charges": average_monthly_charges,
        "total_monthly_revenue": total_monthly_revenue,
    }
    logger.info("Computed real KPIs from %d customers: %s", customer_count, result)
    return result