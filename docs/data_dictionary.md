# Data Dictionary

> **Status:** Final documentation for the Customer Churn Prediction & BI Platform. This document describes the SQLite database schema, machine learning engineered features, preprocessing pipeline, and analytical SQL views used throughout the project.

---

# Overview

The Customer Churn dataset contains demographic, geographic, service subscription, billing, and churn information for customers. These fields support the ETL pipeline, SQL analytics, business intelligence dashboards, and customer churn prediction.

**Dataset**

IBM Telco Customer Churn Dataset

**Primary Table**

`customers`

---

# Database Fields

| Column | SQLite Type | Description | Example | Why it may relate to churn |
|---------|-------------|-------------|---------|----------------------------|
| customer_id | TEXT | Unique identifier for each customer. Primary key. | 7590-VHVEG | Used to uniquely identify each customer record. |
| country | TEXT | Country where the customer resides. | United States | Customer behavior may differ by country. |
| state | TEXT | State of residence. | California | Regional differences may influence churn patterns. |
| city | TEXT | Customer city. | Los Angeles | Enables geographic churn analysis. |
| zip_code | TEXT | Postal/ZIP code. | 90001 | Supports regional segmentation. |
| lat_long | TEXT | Combined latitude and longitude coordinates. | 34.05,-118.24 | Supports geographic visualization. |
| latitude | REAL | Latitude coordinate. | 34.05 | Used for geographic analysis. |
| longitude | REAL | Longitude coordinate. | -118.24 | Used for geographic analysis. |
| gender | TEXT | Customer gender. | Male | Demographic feature for segmentation. |
| senior_citizen | TEXT | Indicates whether the customer is a senior citizen. | Yes | Senior customers may have different retention behavior. |
| partner | TEXT | Indicates whether the customer has a partner. | Yes | Household composition may influence retention. |
| dependents | TEXT | Indicates whether the customer has dependents. | No | Family responsibilities may affect customer loyalty. |
| tenure_months | INTEGER | Number of months the customer has remained with the company. | 24 | One of the strongest predictors of churn. |
| phone_service | TEXT | Indicates whether phone service is subscribed. | Yes | Service adoption may influence churn. |
| multiple_lines | TEXT | Indicates whether multiple phone lines are subscribed. | No | Reflects service usage complexity. |
| internet_service | TEXT | Type of internet service. | Fiber optic | Internet technology often correlates with churn. |
| online_security | TEXT | Indicates whether online security service is subscribed. | Yes | Value-added services may improve customer retention. |
| online_backup | TEXT | Indicates whether online backup service is subscribed. | No | Additional services may reduce churn. |
| device_protection | TEXT | Indicates whether device protection is subscribed. | Yes | Customers using more services often remain longer. |
| tech_support | TEXT | Indicates whether technical support is subscribed. | Yes | Better support can reduce customer dissatisfaction. |
| streaming_tv | TEXT | Indicates whether streaming TV is subscribed. | Yes | Entertainment services may increase engagement. |
| streaming_movies | TEXT | Indicates whether streaming movies are subscribed. | No | Higher service adoption may improve retention. |
| contract | TEXT | Customer contract type. | Month-to-month | One of the strongest churn indicators. |
| paperless_billing | TEXT | Indicates whether paperless billing is enabled. | Yes | Billing preferences may relate to customer behavior. |
| payment_method | TEXT | Customer payment method. | Electronic check | Certain payment methods show higher churn rates. |
| monthly_charges | REAL | Monthly service charges. | 75.30 | Higher monthly charges may increase churn risk. |
| total_charges | REAL | Total amount paid by the customer. | 2045.60 | Indicates long-term customer value. |
| churn_label | TEXT | Indicates whether the customer churned. | Yes | Human-readable target variable. |
| churn_value | INTEGER | Binary churn indicator (0 = No, 1 = Yes). | 1 | Target variable used for machine learning. |
| churn_score | INTEGER | IBM-provided churn risk score. | 82 | Stored in the dataset but excluded from model training to prevent data leakage. |
| cltv | INTEGER | Customer Lifetime Value. | 4500 | Used for business reporting but excluded from model training. |
| churn_reason | TEXT | Reported reason for customer churn. | Competitor offered better service | Used for business analysis but excluded from model training because it is only known after churn occurs. |

---

# Engineered Machine Learning Features

The following features are created dynamically during the machine learning pipeline (`training/feature_engineering.py`). They are **not stored in the SQLite database** but are generated during training and prediction.

| Feature | Derived From | Description | Purpose |
|---------|--------------|-------------|---------|
| TenureBucket | tenure_months | Model-input grouping with four ranges: 0–12, 13–24, 25–48 and 49–72 months (`bins = [-1, 12, 24, 48, 72]`). Values greater than 72 months are not assigned to a bucket and currently become `NaN`, which is a documented known limitation (see `docs/qa_findings.md`, Finding 6). This is **not** the reporting definition: the SQL view and the dashboard use 0–12 / 13–36 / 37+ months (see `docs/sql_analysis_summary.md`). The two groupings are intentionally separate — the feature exists to give the model finer tenure resolution — and their counts must not be compared. | Helps the model capture non-linear relationships between customer tenure and churn. |
| TotalServicesCount | Service subscription columns | Counts the number of subscribed services (`Yes` values) across phone, internet support and streaming services. | Represents overall customer engagement and service adoption. |
| AvgMonthlySpend | total_charges, tenure_months | Calculates average spend over the customer's lifetime (`total_charges ÷ tenure_months`), replacing zero tenure with one to avoid division by zero. | Provides a normalized spending metric for modeling customer value. |

---

# Machine Learning Preprocessing

Before model training, the dataset undergoes preprocessing to produce model-ready inputs.

The preprocessing pipeline performs the following steps:

- Applies engineered machine learning features.
- Removes identifier fields that do not contribute to prediction (for example `customer_id`).
- Removes variables that would introduce data leakage (`churn_reason`, `churn_score`, and `cltv`).
- Removes geographic fields that provide limited predictive value for this dataset.
- Applies one-hot encoding to categorical variables using scikit-learn's `OneHotEncoder`.
- Preserves numerical features using a reusable `ColumnTransformer` so the same preprocessing is applied during both training and prediction.

---

# Data Validation Rules

The SQLite schema enforces several integrity constraints:

- `customer_id` is the primary key.
- `churn_label` cannot be NULL.
- `churn_value` must be either `0` or `1`.
- `churn_score` must be between `0` and `100`.
- `monthly_charges` and `total_charges` must be non-negative.
- `latitude` must be between `-90` and `90`.
- `longitude` must be between `-180` and `180`.

---

# SQL Views

## view_churn_by_contract

### Purpose

Provides reusable contract-level churn metrics for reporting and Power BI dashboards.

### Metrics

- Total customers
- Churned customers
- Churn rate (%)

---

## view_churn_by_tenure_bucket

### Purpose

Provides reusable tenure-based churn metrics for reporting and dashboard visualizations.

### Tenure buckets

- `0-12 Months` — `tenure_months` between 0 and 12
- `13-36 Months` — `tenure_months` between 13 and 36
- `37+ Months` — `tenure_months` of 37 or more

These are the reporting-facing boundaries. They match Business Question 3 in `sql/analysis_queries.sql` (aligned 2026-10-06, audit item FGA-06) and the committed Power BI "Churn Rate by Tenure" visual. The machine-learning `TenureBucket` feature uses different, finer ranges and is not comparable.

### Metrics

- Total customers
- Churned customers
- Churn rate (%)

---

# Notes

- This document reflects the final SQLite schema implemented in `sql/schema.sql`.
- Database fields are documented separately from engineered machine learning features.
- Engineered features are generated dynamically during preprocessing and are not persisted in the database.
- SQL views support downstream analytics, reporting and business intelligence dashboards.