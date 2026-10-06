# API Examples

This document provides example requests and responses for the Customer Churn Prediction & BI Platform API.

> **Regenerated 2026-10-06 (Phase 5 / audit item FGA-08).** Every request and
> response below was captured from a live `uvicorn app.main:app` in the pinned
> environment (CPython 3.11.2, `requirements.txt` + `requirements.lock.txt`)
> against a database built from the tracked `data/raw/telco_churn_raw.csv`, and
> then checked against direct SQL. Two things in the previous version of this
> file were wrong and are corrected here:
>
> - The `/customers` example used field names the endpoint does not return
>   (`senior_citizen: 0`, `tenure`). The real response returns `"Yes"`/`"No"`
>   text for `senior_citizen` and `tenure_months`, and it returns **all 33**
>   columns, not a subset.
> - The `/model-metrics` example showed `0.84 / 0.79 / 0.73 / 0.88`, which
>   matched no run of this project. It now shows the values
>   `evaluation/model_comparison.md` actually contains.

## Authentication

All endpoints except `/health` require API key authentication.

Include the following header in authenticated requests:

```http
X-API-Key: $API_KEY
```

Replace `$API_KEY` with your configured API key.

A request with a missing or invalid key returns **401** with:

```json
{
  "detail": "Missing or invalid API key"
}
```

If the server itself has no `API_KEY` configured, the same 401 is returned with
`"detail": "Server misconfigured: API_KEY not set"`.

---

## GET /health

Returns the health status of the API.

### Example Request

```bash
curl http://localhost:8000/health
```

### Example Response

```json
{
  "status": "ok"
}
```

---

## GET /customers

Returns customer records from the SQLite database, **one page at a time**.

Pagination is intentional: the endpoint never returns the whole table. The
default page size is 100 and page numbering starts at 0.

| Query parameter | Default | Meaning |
|---|---|---|
| `page` | `0` | Zero-based page index |
| `size` | `100` | Rows per page |

### Example Request

```bash
# First 100 customers (the defaults)
curl -X GET "http://localhost:8000/customers" \
  -H "X-API-Key: $API_KEY"

# Second page of five
curl -X GET "http://localhost:8000/customers?page=1&size=5" \
  -H "X-API-Key: $API_KEY"
```

### Example Response

The response is a JSON array of customer objects. Each object carries all 33
columns of the `customers` table — this is the first record returned for the
tracked dataset, reproduced in full:

```json
[
  {
    "customer_id": "3668-QPYBK",
    "country": "United States",
    "state": "California",
    "city": "Los Angeles",
    "zip_code": "90003",
    "lat_long": "33.964131, -118.272783",
    "latitude": 33.964131,
    "longitude": -118.272783,
    "gender": "Male",
    "senior_citizen": "No",
    "partner": "No",
    "dependents": "No",
    "tenure_months": 2,
    "phone_service": "Yes",
    "multiple_lines": "No",
    "internet_service": "DSL",
    "online_security": "Yes",
    "online_backup": "Yes",
    "device_protection": "No",
    "tech_support": "No",
    "streaming_tv": "No",
    "streaming_movies": "No",
    "contract": "Month-to-month",
    "paperless_billing": "Yes",
    "payment_method": "Mailed check",
    "monthly_charges": 53.85,
    "total_charges": 108.15,
    "churn_label": "Yes",
    "churn_value": 1,
    "churn_score": 86,
    "cltv": 3239,
    "churn_reason": "Competitor made better offer"
  }
]
```

> **Notes:**
> - `senior_citizen` is `"Yes"`/`"No"` text (`senior_citizen TEXT` in
>   `sql/schema.sql`), not `0`/`1`. The `0`/`1` integer form appears only in the
>   `POST /predict` request schema, where the field is named `SeniorCitizen`.
> - Tenure is `tenure_months`, not `tenure`. (`tenure` is the field name used by
>   `POST /predict`, whose request schema deliberately differs — see below.)
> - `churn_score`, `churn_reason` and `cltv` are returned here because this
>   endpoint is a data-listing endpoint over the stored table. They are
>   **excluded from model inputs** (`training/preprocessing.py`'s
>   `DROP_COLUMNS`) precisely because `churn_score` is outcome-derived. See
>   `README.md`'s evaluation section.

---

## GET /kpis

Returns executive KPI metrics computed over the **whole** customer population as
a single SQL aggregate (`CustomerRepository.get_kpi_aggregate()`), not over one
`/customers` page.

### Example Request

```bash
curl -X GET http://localhost:8000/kpis \
  -H "X-API-Key: $API_KEY"
```

### Example Response

```json
{
  "customer_count": 7043,
  "overall_churn_rate": 26.54,
  "retention_rate": 73.46,
  "average_monthly_charges": 64.76,
  "total_monthly_revenue": 456116.6
}
```

> **Note:** these are the actual values for the tracked dataset, verified
> against direct SQL:
> `SELECT COUNT(*), SUM(churn_value), AVG(monthly_charges), SUM(monthly_charges) FROM customers`
> → 7,043 customers, 1,869 churned (26.54%), average 64.76, total 456,116.6.
> Values are rounded to two decimals by the service, so
> `total_monthly_revenue` is `456116.6` rather than `456116.60`.

---

## POST /predict

Generates a churn prediction using the trained machine learning model.

The request body is `CustomerPredictionRequest`
(`app/schemas/customer_schema.py`), whose field names intentionally follow the
public Telco dataset rather than the database's snake_case columns — `predict.py`
adapts them. That is why `tenure` and `SeniorCitizen` appear here while
`/customers` returns `tenure_months` and `senior_citizen`.

### Example Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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
    "TotalCharges": 840.60
  }'
```

### Example Response

```json
{
  "churn_probability": 0.7113677247256835,
  "churn_prediction": true
}
```

> The probability is unrounded by design; `churn_prediction` is
> `churn_probability >= 0.5`.

### Possible Error Responses

A body that fails schema validation returns **422** with FastAPI's standard
array-of-errors shape (18 errors for the single-field body below, one per
missing required field):

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "SeniorCitizen"],
      "msg": "Field required",
      "input": {"gender": "Female"}
    }
  ]
}
```

A prediction that fails inside the model returns **500**:

```json
{
  "detail": "Prediction failed. See server logs for details."
}
```

A model that returns an unexpected shape returns **500**:

```json
{
  "detail": "Prediction service returned an unexpected response shape."
}
```

---

## GET /model-metrics

Returns evaluation metrics for the selected model. The endpoint parses the
"Selected Model" block of `evaluation/model_comparison.md`, so these numbers are
always the ones in the committed report.

### Example Request

```bash
curl -X GET http://localhost:8000/model-metrics \
  -H "X-API-Key: $API_KEY"
```

### Example Response

```json
{
  "accuracy": 0.7991,
  "precision": 0.6435,
  "recall": 0.5455,
  "roc_auc": 0.8496
}
```

> **Note:** these are the **untouched-holdout** values for the model selected by
> the current protocol (5-fold stratified cross-validation on the training
> portion, then one frozen-holdout evaluation). The selection table's
> cross-validated means are higher (ROC AUC 0.8591) and are *not* what this
> endpoint serves — the CV figure is a selection score, not an estimate of
> unseen performance. Protocol and provenance: `evaluation/model_comparison.md`
> and `docs/reproduction_record.md` §12. The archived legacy single-split result
> (accuracy 0.8020, ROC AUC 0.8494) is in `evaluation/legacy/`.

### Possible Error Response

```json
{
  "detail": "Model metrics are unavailable. Run the training pipeline first."
}
```

---

## Endpoint Summary

| Endpoint | Method | Authentication | Description |
|----------|--------|----------------|-------------|
| `/health` | GET | No | Returns API health status. |
| `/customers` | GET | Yes (`X-API-Key`) | Returns one page of customer records (`page`, `size`; defaults `0` / `100`). |
| `/kpis` | GET | Yes (`X-API-Key`) | Returns executive KPIs aggregated over the whole customer table. |
| `/predict` | POST | Yes (`X-API-Key`) | Predicts customer churn using the trained machine learning model. |
| `/model-metrics` | GET | Yes (`X-API-Key`) | Returns the selected model's evaluation metrics. |

## Notes

- All authenticated endpoints require an API key supplied in the `X-API-Key` request header.
- The `/predict` endpoint accepts the `CustomerPredictionRequest` schema defined in `app/schemas/customer_schema.py`.
- The `/predict` endpoint returns the `CustomerPredictionResponse` schema containing:
  - `churn_probability` (float)
  - `churn_prediction` (boolean)
- `scripts/verify_endpoints.sh` (and its PowerShell twin) assert every contract
  above against a live server and exit nonzero on any mismatch.
