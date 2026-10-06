# Customer Churn Dashboard Business Report

> **Post-sprint note (2026-10-06, portfolio owner — not part of Joyce's original report).**
> The model figures in section 5 are the **legacy single-split** result and are kept
> as the historical record of the leakage-corrected evaluation this report announced.
> Phase 3 replaced the evaluation protocol (training-side cross-validation for
> selection, one frozen holdout evaluation, plus a naive baseline), so the current
> numbers differ: Logistic Regression on the untouched holdout is accuracy 0.7991 /
> precision 0.6435 / recall 0.5455 / ROC AUC 0.8496, against a prior baseline whose
> ROC AUC is 0.5. See [`evaluation/model_comparison.md`](../evaluation/model_comparison.md)
> and [`docs/reproduction_record.md`](../docs/reproduction_record.md) §12. The
> recommendations below are unaffected — the recall caveat still applies. The
> committed Power BI screenshot of the Model Predictions page shows the legacy
> values; it has not been refreshed (no Power BI Desktop here) and is labelled
> historical in `README.md`.

## Project Overview

This report summarizes the key findings from the Customer Churn Power BI Dashboard developed as part of the Customer Churn Prediction BI Platform project.

The dashboard connects to the project's SQLite database (`churn.db`) through an ODBC connection and provides interactive insights into customer demographics, churn behavior, revenue impact, and machine learning model performance.

The dashboard contains five pages:

1. Executive Overview
2. Customer Demographics
3. Churn Drivers
4. Revenue Impact
5. Model Predictions

---

# Executive Summary

The analysis shows that customer churn remains a significant business challenge.

Out of **7,043 customers**, **1,869 customers** have churned, resulting in an overall **churn rate of 26.54%**.

The dashboard identifies the customer groups most likely to churn, highlights the financial impact of churn, and presents a predictive machine learning model that can help identify customers at risk before they leave.

---

# Dashboard Findings

## 1. Executive Overview

The Executive Overview page provides a high-level summary of customer churn.

### Key Metrics

- Total Customers: **7,043**
- Active Customers: **5,174**
- Churned Customers: **1,869**
- Overall Churn Rate: **26.54%**

### Key Insights

- Approximately one in every four customers has churned.
- Month-to-Month contracts experience substantially higher churn than One-Year and Two-Year contracts.
- Customers with shorter tenure are significantly more likely to churn.
- The dashboard highlights the Top 5 churn reasons to support targeted retention initiatives.

---

## 2. Customer Demographics

This page explores how customer characteristics relate to churn.

### Key Insights

- Senior citizens experience a higher churn rate than non-senior customers.
- Customers without partners or dependents are more likely to churn.
- Churn differs across gender and demographic groups.
- Internet service adoption and phone service usage vary across the customer base.

Understanding these demographic patterns enables more targeted customer retention strategies.

---

## 3. Churn Drivers

The Churn Drivers page identifies the factors most strongly associated with customer churn.

### Key Insights

- Month-to-Month contract customers are the highest-risk customer segment.
- Customers with shorter tenure exhibit the greatest likelihood of churning.
- Internet service type influences churn behavior.
- Payment method also affects customer retention.
- The Top 5 churn reasons provide actionable insight into customer dissatisfaction.

These findings help identify where retention efforts will have the greatest impact.

---

## 4. Revenue Impact

Customer churn has a measurable financial impact on the business.

The dashboard compares:

- Revenue from Active Customers
- Revenue from Churned Customers
- Average Monthly Charges
- Average Total Charges
- Average Customer Lifetime Value (CLTV)

### Key Insights

- Churned customers represent a substantial loss in recurring revenue.
- Higher-value customers contribute significantly to revenue and should be prioritised for retention.
- CLTV provides an effective measure for identifying customers deserving proactive engagement.

---

## 5. Model Predictions

Five machine learning models were evaluated for customer churn prediction.

### Models Evaluated

- Logistic Regression
- Decision Tree
- Random Forest
- XGBoost
- LightGBM

Following the corrected model evaluation (produced after a data leakage issue in the training pipeline was identified and fixed during API integration), **Logistic Regression** was selected as the report's model.

> **Post-sprint note:** "was selected as the production model" described a locally
> served artifact, not a deployment — the project was never deployed. The figures in
> the table below are the legacy single-split evaluation; see the note at the top of
> this report.

### Selected Model Performance

| Metric | Value |
|---------|------:|
| Accuracy | **80.20%** |
| Precision | **64.80%** |
| Recall | **55.62%** |
| ROC AUC | **84.94%** |

> **Note on this update:** an earlier version of this report cited a Logistic Regression evaluation of 91.77% accuracy / 97.43% ROC AUC. Those figures came from a stale evaluation run affected by data leakage in the training pipeline, discovered during real model integration (Issue #14). **Historically**, the figures above reflected the corrected evaluation; since Phase 3 (2026-10-06) they are the legacy single-split figures, and the current protocol's untouched-holdout values are in [`evaluation/model_comparison.md`](../evaluation/model_comparison.md).

The selected model's predictive performance is more modest than the pre-correction figures suggested, particularly on recall (55.62%), meaning a meaningful share of customers who do churn will not be flagged by the model. It should be used as one input among several for identifying at-risk customers, not as a sole determinant, until further tuning or feature work improves recall.

---

# Business Recommendations

## Recommendation 1

Develop targeted retention campaigns for customers on Month-to-Month contracts by offering incentives to migrate to longer-term contracts.

---

## Recommendation 2

Use the Logistic Regression model's churn predictions as one input for prioritizing outreach to at-risk customers, alongside the dashboard's descriptive churn drivers (contract type, tenure, service usage). Given the model's current recall of 55.62%, do not rely on it as the sole method for identifying at-risk customers — combine it with the tenure and contract-type segments identified in the Churn Drivers page.

---

## Recommendation 3

Prioritize customers with high Customer Lifetime Value (CLTV) by offering personalized retention strategies and loyalty incentives.

---

## Recommendation 4

Address the leading churn reasons identified in the dashboard through improvements in pricing, customer support, and service quality.

---

## Recommendation 5

Monitor customer churn continuously using the Power BI dashboard to evaluate the effectiveness of retention initiatives and support data-driven decision-making. As the model is retrained or tuned to improve recall, refresh this dashboard's Model Predictions page to reflect updated evaluation metrics.

---

# Conclusion

The Customer Churn Dashboard provides a comprehensive view of customer behavior, churn trends, revenue impact, and predictive analytics.

By combining descriptive analytics with machine learning insights, the dashboard enables stakeholders to identify at-risk customers, understand the primary causes of churn, and implement effective retention strategies that improve customer satisfaction and long-term business performance.