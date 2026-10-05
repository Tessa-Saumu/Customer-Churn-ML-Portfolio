# Local verification script for Issue #14 (Real Integration).
#
# Superset of Issue #10's verify_endpoints.ps1: keeps every original
# status-code check (auth still behaves the same -- part of Issue
# #14's "no public contract changes" requirement), and adds checks
# that RESPONSE CONTENT is real, not the old mocked/placeholder
# values. A 200 status code alone doesn't prove the mock is gone --
# the old mock also returned 200.
#
# Run this against a locally running instance of the API:
#   1. Run the full pipeline first (see README "Before running the
#      API" section added in Issue #14):
#        python database/init_db.py
#        python etl/load_to_db.py
#        python database/init_views.py
#        python training/evaluate_models.py
#   2. In one terminal:
#        uvicorn app.main:app --reload
#   3. In another terminal:
#        .\verify_endpoints.ps1
#
# Requires the API_KEY environment variable to be set to the same key
# the API is running with (matching your .env file). Unlike the
# previous version of this script there is no silent default key: an
# unset API_KEY now fails immediately rather than producing a run
# whose results cannot be trusted.
#
# Optional environment variables:
#   API_KEY                 - API key to send in the X-API-Key header. REQUIRED.
#   BASE_URL                - Base URL of the running API (default: http://localhost:8000).
#   EXPECTED_CUSTOMER_COUNT - Customer row count in the database the API is
#                             serving (default: 7043, the tracked Telco
#                             dataset). Set to 0 to skip the exact-count check.
#   REPORT_PATH             - Path to evaluation/model_comparison.md, used for
#                             the report/metrics consistency check
#                             (default: evaluation/model_comparison.md).
#
# PHASE 1 (audit item FGA-02, 2026-10-05) -- what changed and why
# --------------------------------------------------------------
# This script had drifted out of sync with the shipped app and could
# not be used as an acceptance gate:
#   * It still pinned the Logistic Regression numbers
#     (accuracy ~0.8020 / ROC AUC ~0.8494) as if they were contract,
#     even though unpinned dependencies move them between
#     environments, and its header comment still described the
#     selected model as LightGBM.
#   * Its /kpis customer_count check asserted the full-table row count
#     while /kpis was summarizing only the first 100 rows (FGA-01), so
#     it failed for a real reason the script could not explain.
#   * Check-Endpoint treated any 2xx response as 200, so it could not
#     actually assert a status code.
#
# It now asserts the same semantics as scripts/verify_endpoints.sh:
# response keys, value ranges, pagination behaviour, whole-population
# KPI semantics, and the absence of the two known-invalid result sets
# (Issue #10's placeholder and the pre-leakage LightGBM run). Exact
# model numbers are deliberately not pinned.
#
# Exit codes:
#   0 = All endpoint checks passed (skips, if any, are reported).
#   1 = One or more endpoint checks failed.
#   2 = The script could not run (missing API_KEY, bad
#       EXPECTED_CUSTOMER_COUNT, or no server reachable).

$ErrorActionPreference = "Stop"

$API_KEY = $env:API_KEY
$BASE_URL = if ($env:BASE_URL) { $env:BASE_URL } else { "http://localhost:8000" }
$EXPECTED_CUSTOMER_COUNT = if ($env:EXPECTED_CUSTOMER_COUNT) { $env:EXPECTED_CUSTOMER_COUNT } else { "7043" }
$REPORT_PATH = if ($env:REPORT_PATH) { $env:REPORT_PATH } else { "evaluation/model_comparison.md" }

$pass = 0
$fail = 0
$skip = 0

# ---------------------------------------------------------------------
# Preflight: fail loudly rather than reporting a partial run as green.
# ---------------------------------------------------------------------

if ([string]::IsNullOrWhiteSpace($API_KEY)) {
    Write-Host "ERROR: API_KEY is not set."
    Write-Host "       Set it to the key the API is running with, e.g."
    Write-Host "       `$env:API_KEY='local-dev-key-123'; .\verify_endpoints.ps1"
    exit 2
}

if ($EXPECTED_CUSTOMER_COUNT -notmatch '^\d+$') {
    Write-Host "ERROR: EXPECTED_CUSTOMER_COUNT must be a non-negative integer."
    Write-Host "       Got: '$EXPECTED_CUSTOMER_COUNT'"
    Write-Host "       Set it to your database's customer row count, or 0 to skip"
    Write-Host "       the exact-count check."
    exit 2
}

function Skip-Check {
    param([string]$Description)
    Write-Host "SKIP $Description" -ForegroundColor Yellow
    $script:skip++
}

function Check-Endpoint {
    param(
        [string]$Description,
        [string]$Method = "GET",
        [string]$Uri,
        [int]$ExpectedStatus,
        [hashtable]$Headers = $null,
        [string]$Body = $null
    )

    # $script:lastResponseContent holds the parsed body of the most
    # recent successful (2xx) call, for Check-Content to inspect.
    $script:lastResponseContent = $null

    try {
        if ($Body) {
            $response = Invoke-WebRequest `
                -Uri $Uri `
                -Method $Method `
                -Headers $Headers `
                -ContentType "application/json" `
                -Body $Body

        }
        else {
            $response = Invoke-WebRequest `
                -Uri $Uri `
                -Method $Method `
                -Headers $Headers
        }

        # FGA-02: assert the ACTUAL status code. The previous version
        # hardcoded 200 on the success path, which meant any 2xx
        # (201, 204, ...) was reported as the expected 200.
        $status = [int]$response.StatusCode
        $script:lastResponseContent = $response.Content | ConvertFrom-Json
    }
    catch {
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        else {
            Write-Host "FAIL [No Response] $Description" -ForegroundColor Red
            Write-Host "      Is the API running at $Uri ?"
            $script:fail++
            return
        }
    }

    if ($status -eq $ExpectedStatus) {
        Write-Host "PASS [$status] $Description" -ForegroundColor Green
        $script:pass++
    }
    else {
        Write-Host "FAIL [$status expected $ExpectedStatus] $Description" -ForegroundColor Red
        $script:fail++
    }
}

# Evaluates a scriptblock against $script:lastResponseContent (set by
# the most recent Check-Endpoint call). Only meaningful immediately
# after a Check-Endpoint call that hit the same endpoint and returned
# 2xx -- if that call failed, $lastResponseContent is $null and this
# check reports FAIL rather than silently passing.
function Check-Content {
    param(
        [string]$Description,
        [scriptblock]$Condition
    )

    if ($null -eq $script:lastResponseContent) {
        Write-Host "FAIL [content, no response body] $Description" -ForegroundColor Red
        $script:fail++
        return
    }

    $result = & $Condition $script:lastResponseContent

    if ($result) {
        Write-Host "PASS [content] $Description" -ForegroundColor Green
        $script:pass++
    }
    else {
        Write-Host "FAIL [content] $Description" -ForegroundColor Red
        Write-Host "      Body: $($script:lastResponseContent | ConvertTo-Json -Compress)"
        $script:fail++
    }
}

Write-Host "Verifying against $BASE_URL"
Write-Host "----------------------------------------"

# Fail fast (exit 2) if nothing is listening, instead of reporting a
# pile of connection failures as endpoint regressions.
Check-Endpoint `
    -Description "GET /health" `
    -Uri "$BASE_URL/health" `
    -ExpectedStatus 200

if ($fail -gt 0) {
    Write-Host "ERROR: could not reach the API at $BASE_URL."
    Write-Host "       Start it with: uvicorn app.main:app --reload"
    exit 2
}

$headers = @{
    "X-API-Key" = $API_KEY
}

Check-Endpoint `
    -Description "GET /customers without API key" `
    -Uri "$BASE_URL/customers" `
    -ExpectedStatus 401

Check-Endpoint `
    -Description "GET /customers with API key" `
    -Headers $headers `
    -ExpectedStatus 200

# Issue #14: /customers must be real CustomerRepository data, not
# Issue #10's two hardcoded records (customerID "C001"/"C002" with
# camelCase field names). Real schema uses snake_case customer_id.
Check-Content `
    -Description "GET /customers returns real schema field names (not mock's camelCase)" `
    -Condition { param($c) ($null -ne $c[0].customer_id) -and ($null -eq $c[0].customerID) }

Check-Content `
    -Description "GET /customers row count is not the Issue #10 mock's fixed 2 records" `
    -Condition { param($c) $c.Count -ne 2 }

# Mentor-added pagination (commit 806705c) is intentional and must stay:
# the default /customers response is bounded to one page.
Check-Content `
    -Description "GET /customers default response stays within one page (<= 100 rows)" `
    -Condition { param($c) $c.Count -le 100 }

$defaultPageLength = @($script:lastResponseContent).Count

# Explicit page/size requests keep their existing behaviour.
Check-Endpoint `
    -Description "GET /customers?page=1&size=5 with API key" `
    -Headers $headers `
    -Uri "$BASE_URL/customers?page=1&size=5" `
    -ExpectedStatus 200

Check-Content `
    -Description "GET /customers honours the requested page size (<= 5 rows)" `
    -Condition { param($c) $c.Count -le 5 }

Check-Endpoint `
    -Description "GET /kpis without API key" `
    -Uri "$BASE_URL/kpis" `
    -ExpectedStatus 401

Check-Endpoint `
    -Description "GET /kpis with API key" `
    -Headers $headers `
    -ExpectedStatus 200

# FGA-01: /kpis is a whole-population summary. Issue #10's mock always
# returned exactly customer_count: 7043, and the real database also
# loads 7043 rows, so that number is no longer a reliable "is it real"
# signal on its own. What is checked here is the SEMANTICS: the five
# locked keys, internally consistent rates, and a population that is
# not the /customers page.
Check-Content `
    -Description "GET /kpis has exactly the five locked response keys" `
    -Condition {
        param($k)
        $keys = $k.PSObject.Properties.Name | Sort-Object
        ($keys -join ",") -eq "average_monthly_charges,customer_count,overall_churn_rate,retention_rate,total_monthly_revenue"
    }

Check-Content `
    -Description "GET /kpis: overall_churn_rate + retention_rate ~= 100" `
    -Condition { param($k) [math]::Abs(($k.overall_churn_rate + $k.retention_rate) - 100) -lt 0.1 }

Check-Content `
    -Description "GET /kpis: rates are percentages within [0, 100]" `
    -Condition {
        param($k)
        ($k.overall_churn_rate -ge 0) -and ($k.overall_churn_rate -le 100) -and
        ($k.retention_rate -ge 0) -and ($k.retention_rate -le 100)
    }

Check-Content `
    -Description "GET /kpis: customer_count is a positive integer and charges are non-negative" `
    -Condition {
        param($k)
        ($k.customer_count -gt 0) -and ($k.average_monthly_charges -ge 0) -and ($k.total_monthly_revenue -ge 0)
    }

# The core FGA-01 regression check. /kpis used to call the paginated
# get_all(), so it summarized the first 100 rows and reported them as
# the whole population (on the tracked dataset: customer_count 100,
# overall_churn_rate 100.0).
if ([int]$EXPECTED_CUSTOMER_COUNT -gt 0) {
    Check-Content `
        -Description "GET /kpis: customer_count is the full table ($EXPECTED_CUSTOMER_COUNT rows), not the 100-row default page" `
        -Condition { param($k) $k.customer_count -eq [int]$EXPECTED_CUSTOMER_COUNT }
}
else {
    Skip-Check "exact /kpis customer_count check (EXPECTED_CUSTOMER_COUNT=0)"
}

# Same regression, without any configuration: when the default
# /customers page came back full there is more than one page in the
# table, so the KPI population must be strictly larger than that page.
if ($defaultPageLength -eq 100) {
    Check-Content `
        -Description "GET /kpis: customer_count is larger than a full /customers default page" `
        -Condition { param($k) $k.customer_count -gt 100 }
}
else {
    Skip-Check "/kpis vs. full-page cross-check (default page returned $defaultPageLength rows, not 100)"
}

Check-Endpoint `
    -Description "GET /model-metrics with API key" `
    -Headers $headers `
    -ExpectedStatus 200

# Issue #14: /model-metrics must be real values parsed from
# evaluation/model_comparison.md's Selected Model block, not Issue
# #10's fixed placeholder {0.89, 0.86, 0.81, 0.91}. Exact numbers are
# deliberately NOT pinned here -- unpinned dependencies move them
# between environments (measured drift: Logistic Regression ROC AUC
# 0.8494 -> 0.8496). What is asserted is the contract, the value
# ranges, and the absence of the two known-invalid result sets.
Check-Content `
    -Description "GET /model-metrics has exactly the four locked keys" `
    -Condition {
        param($m)
        $keys = $m.PSObject.Properties.Name | Sort-Object
        ($keys -join ",") -eq "accuracy,precision,recall,roc_auc"
    }

Check-Content `
    -Description "GET /model-metrics values are all within [0, 1]" `
    -Condition {
        param($m)
        ($m.accuracy -ge 0) -and ($m.accuracy -le 1) -and
        ($m.precision -ge 0) -and ($m.precision -le 1) -and
        ($m.recall -ge 0) -and ($m.recall -le 1) -and
        ($m.roc_auc -ge 0) -and ($m.roc_auc -le 1)
    }

Check-Content `
    -Description "GET /model-metrics does not match the Issue #10 placeholder values" `
    -Condition {
        param($m)
        -not (
            ($m.accuracy -eq 0.89) -and
            ($m.precision -eq 0.86) -and
            ($m.recall -eq 0.81) -and
            ($m.roc_auc -eq 0.91)
        )
    }

# The pre-leakage run (commit 6dc54cb, 2026-07-22) trained with
# churn_score still in the feature set and reported LightGBM accuracy
# ~0.9304 / ROC AUC ~0.9818. Those figures are target leakage and must
# never reappear.
Check-Content `
    -Description "GET /model-metrics accuracy is not the pre-leakage LightGBM result (~0.9304)" `
    -Condition { param($m) -not (($m.accuracy -gt 0.929) -and ($m.accuracy -lt 0.932)) }

Check-Content `
    -Description "GET /model-metrics roc_auc is not the pre-leakage LightGBM result (~0.9818)" `
    -Condition { param($m) -not (($m.roc_auc -gt 0.981) -and ($m.roc_auc -lt 0.983)) }

# The endpoint must stay consistent with the report it parses.
if (Test-Path $REPORT_PATH) {
    $reportText = Get-Content -Path $REPORT_PATH -Raw
    $accuracyMatch = [regex]::Match($reportText, '(?m)^-\s*Accuracy:\s*([0-9.]+)')
    $rocAucMatch = [regex]::Match($reportText, '(?m)^-\s*ROC AUC:\s*([0-9.]+)')
    if ($accuracyMatch.Success -and $rocAucMatch.Success) {
        $reportAccuracy = [double]$accuracyMatch.Groups[1].Value
        $reportRocAuc = [double]$rocAucMatch.Groups[1].Value
        Check-Content `
            -Description "GET /model-metrics agrees with the selected model in $REPORT_PATH" `
            -Condition { param($m) ([double]$m.accuracy -eq $reportAccuracy) -and ([double]$m.roc_auc -eq $reportRocAuc) }
    }
    else {
        Skip-Check "report/metrics consistency check ($REPORT_PATH has no parseable selected-model block)"
    }
}
else {
    Skip-Check "report/metrics consistency check ($REPORT_PATH not found)"
}

Check-Endpoint `
    -Description "POST /predict without API key" `
    -Method POST `
    -Uri "$BASE_URL/predict" `
    -Body (@{} | ConvertTo-Json) `
    -ExpectedStatus 401

$body = @{
    gender = "Female"
    SeniorCitizen = 0
    Partner = "Yes"
    Dependents = "No"
    tenure = 12
    PhoneService = "Yes"
    MultipleLines = "No"
    InternetService = "Fiber optic"
    OnlineSecurity = "No"
    OnlineBackup = "Yes"
    DeviceProtection = "No"
    TechSupport = "No"
    StreamingTV = "Yes"
    StreamingMovies = "No"
    Contract = "Month-to-month"
    PaperlessBilling = "Yes"
    PaymentMethod = "Electronic check"
    MonthlyCharges = 70.05
    TotalCharges = 840.60
} | ConvertTo-Json

Check-Endpoint `
    -Description "POST /predict with API key" `
    -Method POST `
    -Uri "$BASE_URL/predict" `
    -Headers $headers `
    -Body $body `
    -ExpectedStatus 200

# Issue #14: response shape is locked (churn_probability, churn_prediction
# only) -- same check as Issue #10 would have made, re-verified here
# since #14 touches this endpoint's internals.
Check-Content `
    -Description "POST /predict response has exactly the locked two keys" `
    -Condition {
        param($p)
        $keys = $p.PSObject.Properties.Name | Sort-Object
        ($keys -join ",") -eq "churn_prediction,churn_probability"
    }

Check-Content `
    -Description "POST /predict churn_probability is in valid [0,1] range" `
    -Condition { param($p) ($p.churn_probability -ge 0) -and ($p.churn_probability -le 1) }

# Issue #14: the old mock ALWAYS returned exactly 0.42 regardless of
# input. This doesn't prove the model is "correct" -- only that it's
# not the fixed mock constant.
Check-Content `
    -Description "POST /predict churn_probability is not the Issue #10 mock's fixed 0.42" `
    -Condition { param($p) $p.churn_probability -ne 0.42 }

# Malformed-input edge case (mock had no validation-failure path worth
# checking since it never called a real model that could reject
# unseen categories/shapes -- this endpoint's error handling is new
# in Issue #14, see routes.py's try/except around real_predict()).
Check-Endpoint `
    -Description "POST /predict with missing required field" `
    -Method POST `
    -Uri "$BASE_URL/predict" `
    -Headers $headers `
    -Body (@{ gender = "Female" } | ConvertTo-Json) `
    -ExpectedStatus 422

Write-Host "----------------------------------------"
Write-Host "Results: $pass passed, $fail failed, $skip skipped"

if ($fail -gt 0) {
    exit 1
}

if ($skip -gt 0) {
    Write-Host "NOTE: $skip check(s) were skipped. A run with skips is not a full pass."
}
