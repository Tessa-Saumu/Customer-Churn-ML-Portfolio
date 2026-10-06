#!/usr/bin/env bash
# Local verification script for Issue #14 (Real Integration).
#
# Superset of Issue #10's verify_endpoints.sh: keeps every original
# status-code check (auth still behaves the same -- that's part of
# Issue #14's "no public contract changes" requirement), and adds
# checks that the RESPONSE CONTENT is real, not the old mocked/
# placeholder values. A 200 status code alone doesn't prove the mock
# is gone -- the old mock also returned 200.
#
# Run this against a locally running instance of the API:
#   1. Run the full pipeline first (see README "Before running the
#      API" section added in Issue #14):
#        python database/init_db.py
#        python etl/load_to_db.py
#        python database/init_views.py
#        python training/evaluate_models.py
#   2. In one terminal: uvicorn app.main:app --reload
#   3. In another terminal: ./verify_endpoints.sh
#
# Requires .env to be set up (cp .env.example .env, then fill in a real
# API_KEY) and the server to already be running on localhost:8000.
#
# PHASE 1 (audit item FGA-02, 2026-10-05) -- what changed and why
# --------------------------------------------------------------
# This script had drifted out of sync with the shipped app and could
# not be used as an acceptance gate:
#   * Two checks still asserted the PRE-LEAKAGE LightGBM numbers
#     (accuracy ~0.9304 / ROC AUC ~0.9818, commit 6dc54cb, 2026-07-22)
#     from a run in which churn_score was still a model input. Those
#     values are not valid predictive-performance evidence.
#   * The /kpis customer_count check asserted the full-table row count
#     while /kpis was summarizing only the first 100 rows (FGA-01), so
#     it failed for a real reason that the script could not explain.
#   * A missing `jq` silently turned every content check into a SKIP,
#     which let the script report a misleading all-green run.
#
# The script now:
#   * Requires `curl` and `jq` and exits nonzero if either is missing,
#     so a green run always means every check actually executed.
#   * Asserts response keys, value ranges and the pagination/aggregate
#     semantics of the current contract, instead of pinning exact model
#     numbers that drift between environments.
#   * Keeps one configurable exact-count check for the KPI population
#     (EXPECTED_CUSTOMER_COUNT, default 7043 for the tracked dataset)
#     plus a self-configuring cross-check that /kpis is larger than a
#     full /customers page.
#
# Exit codes:
#   0  every check passed
#   1  at least one check failed (the API regressed)
#   2  the script could not run (missing tool, unset API_KEY, bad
#      EXPECTED_CUSTOMER_COUNT, or no server reachable)

set -u

API_KEY="${API_KEY:-}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
# The tracked Telco dataset loads 7,043 rows. Override this to match a
# different database, or set it to 0 to skip the exact-count check.
EXPECTED_CUSTOMER_COUNT="${EXPECTED_CUSTOMER_COUNT:-7043}"
REPORT_PATH="${REPORT_PATH:-evaluation/model_comparison.md}"

# ---------------------------------------------------------------------
# Preflight: fail loudly rather than reporting a partial run as green.
# ---------------------------------------------------------------------

missing=0
for tool in curl jq; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: required tool '$tool' is not installed or not on PATH."
        missing=1
    fi
done
if [ "$missing" -ne 0 ]; then
    echo "       Install the missing tool(s) and re-run; this script no longer"
    echo "       skips content checks, because a skipped check is not a pass."
    exit 2
fi

if [ -z "$API_KEY" ]; then
    echo "Set API_KEY before running, matching the value in your .env file."
    echo "Example: API_KEY=local-dev-key-123 ./verify_endpoints.sh"
    exit 2
fi

case "$EXPECTED_CUSTOMER_COUNT" in
    '' | *[!0-9]*)
        echo "ERROR: EXPECTED_CUSTOMER_COUNT must be a non-negative integer."
        echo "       Got: '$EXPECTED_CUSTOMER_COUNT'"
        echo "       Set it to your database's customer row count, or 0 to skip"
        echo "       the exact-count check."
        exit 2
        ;;
esac

BODY_FILE="$(mktemp "${TMPDIR:-/tmp}/verify_body.XXXXXX")"
cleanup() { rm -f "$BODY_FILE"; }
trap cleanup EXIT

pass=0
fail=0
skip=0

check() {
    local description="$1"
    local expected_status="$2"
    shift 2
    local response
    response=$(curl -s -o "$BODY_FILE" -w "%{http_code}" "$@")

    if [ "$response" = "$expected_status" ]; then
        echo "PASS  [$response]  $description"
        pass=$((pass + 1))
    else
        echo "FAIL  [$response, expected $expected_status]  $description"
        echo "      Body: $(cat "$BODY_FILE")"
        fail=$((fail + 1))
    fi
}

# Like check(), but for asserting something about the response BODY
# rather than just the status code. `condition_desc` is a jq boolean
# expression evaluated against the last response body in $BODY_FILE.
# Only meaningful after a check() call that hit the same endpoint
# immediately before it (reuses $BODY_FILE).
check_content() {
    local description="$1"
    local jq_filter="$2"

    if jq -e "$jq_filter" "$BODY_FILE" >/dev/null 2>&1; then
        echo "PASS  [content]  $description"
        pass=$((pass + 1))
    else
        echo "FAIL  [content]  $description"
        echo "      Body: $(cat "$BODY_FILE")"
        fail=$((fail + 1))
    fi
}

skip_check() {
    echo "SKIP  $1"
    skip=$((skip + 1))
}

echo "Verifying against $BASE_URL"
echo "----------------------------------------"

check "GET /health (no auth)" 200 \
    "$BASE_URL/health"

check "GET /customers without API key -> 401" 401 \
    "$BASE_URL/customers"

check "GET /customers with API key -> 200" 200 \
    -H "X-API-Key: $API_KEY" "$BASE_URL/customers"

# Issue #14: /customers must be real CustomerRepository data, not
# Issue #10's two hardcoded records (customerID "C001"/"C002" with
# camelCase field names). Real schema uses snake_case customer_id.
check_content "GET /customers returns real schema field names (not mock's camelCase)" \
    '(.[0] | has("customer_id")) and ((.[0] | has("customerID")) | not)'

check_content "GET /customers row count is not the Issue #10 mock's fixed 2 records" \
    'length != 2'

# Mentor-added pagination (commit 806705c) is intentional and must stay:
# the default /customers response is bounded to one page.
check_content "GET /customers default response stays within one page (<= 100 rows)" \
    'length <= 100'

default_page_length=$(jq 'length' "$BODY_FILE" 2>/dev/null || echo 0)

# Explicit page/size requests keep their existing behaviour.
check "GET /customers?page=1&size=5 with API key -> 200" 200 \
    -H "X-API-Key: $API_KEY" "$BASE_URL/customers?page=1&size=5"

check_content "GET /customers honours the requested page size (<= 5 rows)" \
    'length <= 5'

check "GET /kpis without API key -> 401" 401 \
    "$BASE_URL/kpis"

check "GET /kpis with API key -> 200" 200 \
    -H "X-API-Key: $API_KEY" "$BASE_URL/kpis"

# FGA-01: /kpis is a whole-population summary. Issue #10's mock always
# returned exactly customer_count: 7043; the real database also loads
# 7043 rows, so that number is no longer a reliable "is it real" signal
# on its own. What is checked here is the SEMANTICS: the five locked
# keys, internally consistent rates, and a population that is not the
# /customers page.
check_content "GET /kpis has exactly the five locked response keys" \
    '(keys | sort) == ["average_monthly_charges", "customer_count", "overall_churn_rate", "retention_rate", "total_monthly_revenue"]'

check_content "GET /kpis: overall_churn_rate + retention_rate ~= 100" \
    '(.overall_churn_rate + .retention_rate) > 99.9 and (.overall_churn_rate + .retention_rate) < 100.1'

check_content "GET /kpis: rates are percentages within [0, 100]" \
    '(.overall_churn_rate >= 0) and (.overall_churn_rate <= 100) and (.retention_rate >= 0) and (.retention_rate <= 100)'

check_content "GET /kpis: customer_count is a positive integer and charges are non-negative" \
    '(.customer_count > 0) and (.average_monthly_charges >= 0) and (.total_monthly_revenue >= 0)'

# The core FGA-01 regression check. /kpis used to call the paginated
# get_all(), so it summarized the first 100 rows and reported them as
# the whole population (on the tracked dataset: customer_count 100,
# overall_churn_rate 100.0).
if [ "$EXPECTED_CUSTOMER_COUNT" -gt 0 ]; then
    check_content "GET /kpis: customer_count is the full table ($EXPECTED_CUSTOMER_COUNT rows), not the 100-row default page" \
        ".customer_count == $EXPECTED_CUSTOMER_COUNT"
else
    skip_check "exact /kpis customer_count check (EXPECTED_CUSTOMER_COUNT=0)"
fi

# Same regression, without any configuration: when the default
# /customers page came back full there is more than one page in the
# table, so the KPI population must be strictly larger than that page.
if [ "$default_page_length" -eq 100 ]; then
    check_content "GET /kpis: customer_count is larger than a full /customers default page" \
        '.customer_count > 100'
else
    skip_check "/kpis vs. full-page cross-check (default page returned $default_page_length rows, not 100)"
fi

check "GET /model-metrics with API key -> 200" 200 \
    -H "X-API-Key: $API_KEY" "$BASE_URL/model-metrics"

# Issue #14: /model-metrics must be real values parsed from
# evaluation/model_comparison.md's Selected Model block, not Issue
# #10's fixed placeholder {0.89, 0.86, 0.81, 0.91}. Exact numbers are
# deliberately NOT pinned here -- the report is regenerated whenever
# the protocol or the environment changes (Phase 3, 2026-10-06,
# replaced the single-split selection with cross-validation plus one
# frozen holdout evaluation). What is asserted is the contract, the
# value ranges, the absence of the two known-invalid result sets, and
# agreement with whatever the report currently says.
check_content "GET /model-metrics has exactly the four locked keys" \
    '(keys | sort) == ["accuracy", "precision", "recall", "roc_auc"]'

check_content "GET /model-metrics values are all within [0, 1]" \
    '([.accuracy, .precision, .recall, .roc_auc] | map(. >= 0 and . <= 1) | all)'

check_content "GET /model-metrics does not match the Issue #10 placeholder values" \
    '[.accuracy, .precision, .recall, .roc_auc] != [0.89, 0.86, 0.81, 0.91]'

# The pre-leakage run (commit 6dc54cb, 2026-07-22) trained with
# churn_score still in the feature set and reported LightGBM accuracy
# ~0.9304 / ROC AUC ~0.9818. Those figures are target leakage and must
# never reappear.
check_content "GET /model-metrics accuracy is not the pre-leakage LightGBM result (~0.9304)" \
    '((.accuracy > 0.929) and (.accuracy < 0.932)) | not'

check_content "GET /model-metrics roc_auc is not the pre-leakage LightGBM result (~0.9818)" \
    '((.roc_auc > 0.981) and (.roc_auc < 0.983)) | not'

# The endpoint must stay consistent with the report it parses.
if [ -f "$REPORT_PATH" ]; then
    report_accuracy=$(sed -n 's/^- *Accuracy: *//p' "$REPORT_PATH" | head -n 1)
    report_roc_auc=$(sed -n 's/^- *ROC AUC: *//p' "$REPORT_PATH" | head -n 1)
    if [ -n "$report_accuracy" ] && [ -n "$report_roc_auc" ]; then
        check_content "GET /model-metrics agrees with the selected model in $REPORT_PATH" \
            "(.accuracy == $report_accuracy) and (.roc_auc == $report_roc_auc)"
    else
        skip_check "report/metrics consistency check ($REPORT_PATH has no parseable selected-model block)"
    fi
else
    skip_check "report/metrics consistency check ($REPORT_PATH not found)"
fi

check "POST /predict without API key -> 401" 401 \
    -X POST -H "Content-Type: application/json" \
    -d '{}' \
    "$BASE_URL/predict"

check "POST /predict with API key -> 200" 200 \
    -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
    -d '{
        "gender": "Female", "SeniorCitizen": 0, "Partner": "Yes", "Dependents": "No",
        "tenure": 12, "PhoneService": "Yes", "MultipleLines": "No",
        "InternetService": "Fiber optic", "OnlineSecurity": "No", "OnlineBackup": "Yes",
        "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "Yes",
        "StreamingMovies": "No", "Contract": "Month-to-month", "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check", "MonthlyCharges": 70.05, "TotalCharges": 840.60
    }' \
    "$BASE_URL/predict"

# Issue #14: response shape is locked (churn_probability, churn_prediction
# only) -- same check as Issue #10 would have made, re-verified here
# since #14 touches this endpoint's internals.
check_content "POST /predict response has exactly the locked two keys" \
    '(keys | sort) == ["churn_prediction", "churn_probability"]'

check_content "POST /predict churn_probability is in valid [0,1] range" \
    '(.churn_probability >= 0) and (.churn_probability <= 1)'

# Issue #14: the old mock ALWAYS returned exactly 0.42 regardless of
# input. This doesn't prove the model is "correct" -- only that it's
# not the fixed mock constant.
check_content "POST /predict churn_probability is not the Issue #10 mock's fixed 0.42" \
    '.churn_probability != 0.42'

# Malformed-input edge case (mock had no validation-failure path worth
# checking since it never called a real model that could reject
# unseen categories/shapes -- this endpoint's error handling is new
# in Issue #14, see routes.py's try/except around real_predict()).
check "POST /predict with missing required field -> 422" 422 \
    -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
    -d '{"gender": "Female"}' \
    "$BASE_URL/predict"

echo "----------------------------------------"
echo "Results: $pass passed, $fail failed, $skip skipped"

if [ "$fail" -gt 0 ]; then
    exit 1
fi

if [ "$skip" -gt 0 ]; then
    echo "NOTE: $skip check(s) were skipped. A run with skips is not a full pass."
fi
