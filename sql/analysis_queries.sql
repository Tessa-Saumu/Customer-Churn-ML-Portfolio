-- ==========================================================
-- Customer Churn Analysis Queries
-- Final SQLite Database: database/churn.db
-- Table: customers
-- ==========================================================

-- ==========================================================
-- Business Question 1:
-- What percentage of customers have churned?
-- ==========================================================

SELECT ROUND(100.0 * SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_percentage
FROM customers;

-- ==========================================================
-- Business Question 2:
-- How does churn rate differ across customer contract types?
-- ==========================================================

SELECT contract,
COUNT(*) AS total_customers,
SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END) AS churned_customers,
ROUND(100.0 * SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_percentage
FROM customers
GROUP BY contract
ORDER BY churn_rate_percentage DESC;

-- ==========================================================
-- Business Question 3:
-- Which customer tenure group has the highest churn rate?
--
-- Grouping aligned to view_churn_by_tenure_bucket (sql/views.sql)
-- on 2026-10-06 (Phase 3, audit item FGA-06). This query previously
-- used four ranges (0-12 / 13-24 / 25-48 / 49-72) while the view --
-- the definition the committed Power BI "Churn Rate by Tenure"
-- visual renders -- used three. Two different answers to the same
-- business question is a consistency defect, not a feature, so the
-- reporting-facing query now matches the view. The model's
-- engineered TenureBucket feature is a separate, deliberately finer
-- modelling input and is documented as such in
-- docs/data_dictionary.md. Boundaries are pinned by
-- tests/test_sql_views.py::TestTenureBucketDefinitions.
-- ==========================================================

SELECT
CASE
WHEN tenure_months BETWEEN 0 AND 12 THEN '0-12 Months'
WHEN tenure_months BETWEEN 13 AND 36 THEN '13-36 Months'
ELSE '37+ Months'
END AS tenure_bucket,
COUNT(*) AS total_customers,
SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END) AS churned_customers,
ROUND(100.0 * SUM(CASE WHEN churn_label = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_percentage
FROM customers
GROUP BY tenure_bucket
ORDER BY churn_rate_percentage DESC;

-- ==========================================================
-- Business Question 4:
-- Do churned customers have different average monthly charges
-- compared with retained customers?
-- ==========================================================

SELECT churn_label,
ROUND(AVG(monthly_charges), 2) AS average_monthly_charges
FROM customers
GROUP BY churn_label;

-- ==========================================================
-- Business Question 5:
-- Which services have the largest difference in churn rate
-- between users and non-users?
-- ==========================================================

WITH feature_churn AS (

SELECT
    'Online Security' AS feature,
    ROUND(100.0 * SUM(CASE WHEN online_security = 'Yes' AND churn_label = 'Yes' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN online_security = 'Yes' THEN 1 ELSE 0 END), 0), 2) AS users_churn_rate,
    ROUND(100.0 * SUM(CASE WHEN online_security = 'No' AND churn_label = 'Yes' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN online_security = 'No' THEN 1 ELSE 0 END), 0), 2) AS non_users_churn_rate
FROM customers

UNION ALL

SELECT
    'Tech Support',
    ROUND(100.0 * SUM(CASE WHEN tech_support = 'Yes' AND churn_label = 'Yes' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN tech_support = 'Yes' THEN 1 ELSE 0 END), 0), 2),
    ROUND(100.0 * SUM(CASE WHEN tech_support = 'No' AND churn_label = 'Yes' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN tech_support = 'No' THEN 1 ELSE 0 END), 0), 2)
FROM customers

UNION ALL

SELECT
    'Online Backup',
    ROUND(100.0 * SUM(CASE WHEN online_backup = 'Yes' AND churn_label = 'Yes' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN online_backup = 'Yes' THEN 1 ELSE 0 END), 0), 2),
    ROUND(100.0 * SUM(CASE WHEN online_backup = 'No' AND churn_label = 'Yes' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN online_backup = 'No' THEN 1 ELSE 0 END), 0), 2)
FROM customers

)

SELECT feature,
users_churn_rate AS users_churn_percentage,
non_users_churn_rate AS non_users_churn_percentage,
ROUND(ABS(users_churn_rate - non_users_churn_rate), 2) AS churn_difference
FROM feature_churn
ORDER BY churn_difference DESC
LIMIT 3;
