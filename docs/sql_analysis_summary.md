# SQL Analysis Summary

## Overview

This document summarizes the SQL analytics developed for **Issue #9** using the customer churn database created in **Issue #8**.

The analysis is based on the `customers` table in the SQLite database and includes exploratory SQL queries together with reusable analytical views for reporting and dashboard development.

---

# Analysis Queries

## 1. Overall Churn Rate

### Business Question

What percentage of customers have churned?

### Purpose

Calculates the overall customer churn rate to establish a baseline retention metric.

---

## 2. Churn Rate by Contract Type

### Business Question

How does churn differ across customer contract types?

### Purpose

Measures churn across Month-to-month, One year, and Two year contracts to understand the relationship between contract length and customer retention.

---

## 3. Churn Rate by Tenure Bucket

### Business Question

Which customer tenure group experiences the highest churn?

### Tenure Buckets

- 0–12 Months
- 13–36 Months
- 37+ Months

These are the same boundaries and labels as `view_churn_by_tenure_bucket` (`sql/views.sql`), which the committed Power BI "Churn Rate by Tenure" visual renders. Before 2026-10-06 this query used four ranges (0–12, 13–24, 25–48, 49–72) while the view used three, so the same business question had two different answers (audit item FGA-06). The query now matches the view; `tests/test_sql_views.py::TestTenureBucketDefinitions` pins the boundaries and compares the two outputs.

The model's engineered `TenureBucket` feature (`training/feature_engineering.py`) is a **different, deliberately finer grouping** (0–12, 13–24, 25–48, 49–72 months) used only as a model input; it is not a reporting definition and its counts should not be compared with this table. See `docs/data_dictionary.md`.

### Purpose

Segments customers by tenure to identify which lifecycle stages are most vulnerable to churn.

---

## 4. Average Monthly Charges

### Business Question

Do churned customers have different monthly charges compared with retained customers?

### Purpose

Compares average monthly charges for churned and retained customers to determine whether pricing is associated with customer attrition.

---

## 5. Feature Impact Analysis

### Business Question

Which service features have the greatest difference in churn rates between users and non-users?

### Purpose

Compares churn rates within customer subgroups using conditional aggregation to identify services associated with stronger customer retention.

---

# SQL Views

## view_churn_by_contract

### Purpose

Provides reusable contract-level churn metrics for reporting tools such as Power BI and Tableau.

### Metrics

- Total customers
- Churned customers
- Churn rate (%)

---

## view_churn_by_tenure_bucket

### Purpose

Provides reusable tenure-based churn metrics for dashboards and business reporting.

### Metrics

- Total customers
- Churned customers
- Churn rate (%)

---

# Validation

The SQL analysis was revalidated against the final SQLite database (`database/churn.db`) after completion of the ETL pipeline, schema updates, and feature engineering.

Validation included:

- Successfully re-running all analytical SQL queries against the final `customers` table.
- Verifying that the SQL views execute correctly and return expected results.
- Confirming that the reported churn metrics remain consistent with the current database.
- Revalidating feature-impact calculations using the final production dataset.

---

# Key Findings

The SQL analysis was revalidated against the final SQLite database (`database/churn.db`).

The verified results indicate:

- Overall customer churn rate is **26.54%**.
- Month-to-month contracts continue to experience the highest churn rates.
- Customers with shorter tenure remain significantly more likely to churn than longer-tenured customers.
- Churned customers have higher average monthly charges than retained customers.
- Service features including **Online Security**, **Tech Support**, and **Online Backup** continue to show lower churn rates among subscribers than non-subscribers.

> **Note:** These findings were verified against the final project database. If the ETL pipeline or source dataset changes in future, the SQL queries should be re-run and the documented metrics updated accordingly.