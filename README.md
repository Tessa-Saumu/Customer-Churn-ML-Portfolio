# Customer Churn Prediction & Business Intelligence Platform

This is Theresia Saumu's personal portfolio copy of the [original team repository](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform). It preserves the team's Git history and contributor credits. The application documentation changes live on this copy's `main` branch; they do not change the shared project. GitHub does not mark this as a native fork because the shared repository is already owned by the same account.

A mentored team capstone connecting a telecom churn dataset, comparative classification, a local FastAPI service and Power BI reporting.

## Problem and personal contribution

The team built a local workflow over the [IBM Telco dataset](https://www.kaggle.com/datasets/yeanzc/telco-customer-churn-ibm-dataset). As team lead, Theresia Saumu implemented real model/API integration, the training-to-inference field adapter, leakage correction and automated ETL/API/model tests. Evidence: [integration PR #27](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/27), test PRs [#29](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/29), [#30](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/30), [#31](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/31), and [contribution map](CONTRIBUTORS.md).

ETL, model training, API scaffolding, SQL analysis and dashboard work had other owners. Mentor contributions include scaffolding, pagination, Docker and Streamlit. This is team integration and QA evidence, not sole authorship of the platform.

## Evaluation and key finding

Integration exposed an outcome-derived `churn_score` feature unavailable in real prediction requests. It was removed from model inputs and the comparison was rerun. The [committed comparison](evaluation/model_comparison.md) selects logistic regression with ROC AUC **0.8494**, accuracy **0.8020**, precision **0.6480** and recall **0.5561**. Earlier leakage-affected figures are not valid predictive-performance evidence.

Five candidates were compared on one stratified split, so this holdout also served model selection; it is not an untouched final evaluation. No temporal/geographic generalization, causal impact or production use is established.

## Limitations and current status

- **Known KPI regression:** `kpi_service.get_kpis()` calls `CustomerRepository.get_all()` with its default page size of 100. `/kpis` therefore summarizes the first 100 rows, not all 7,043. Dashboard dataset totals must not be interpreted as evidence that this API endpoint is correct.
- Existing tests do not catch that regression; many integration tests skip when generated database/model artifacts are absent. Historical full-suite success is not a claim of current system correctness.
- Endpoint verification scripts contain stale assertions (including pre-leakage metrics in the shell script) and are not reliable acceptance gates for the current tree.
- No cloud deployment is established. The deployment workflow is disabled, dependencies are unpinned, and no green CI claim is made. Docker/Streamlit files exist; their presence does not prove a working deployment.
- The committed Power BI screenshots are historical report captures. The refresh instructions below describe the intended local setup, not a newly verified live ODBC connection.
- Code defects and evaluation protocols were not changed for this documentation pass.

**Project work:** July-August 2026. The earlier nine-day figure was a planning target, not demonstrated elapsed delivery time.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Repository Structure](#repository-structure)
3. [Architecture](#architecture)
4. [Team & Responsibilities](#team--responsibilities)
5. [Milestones](#milestones)
6. [Running the Project](#running-the-project)
7. [Power BI Dashboard Setup](#power-bi-dashboard-setup)
9. [Coding Standards](#coding-standards)
10. [Data Dictionary and SQL Views](#data-dictionary-and-sql-views)
11. [Project Process & Collaboration](#project-process--collaboration)

---

## Getting Started

### Prerequisites

- **Git** — [install instructions](https://git-scm.com/downloads)
- **Python 3.12** — confirm with `python --version`
- Public read access is sufficient to clone; collaborator access is needed only to push.

### Clone the repository

```bash
git clone https://github.com/Tessa-Saumu/Customer-Churn-ML-Portfolio.git
cd Customer-Churn-ML-Portfolio
```

### Set up your local environment

```bash
# Confirm git is installed
git --version

# Configure your git identity (one-time, if not already done)
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"

# Confirm Python 3.12 is installed
python --version

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure environment variables

Copy the example environment file and fill in real values:

```bash
cp .env.example .env
```

See `.env.example` for the full list of required variables (API key, database path, etc.). **Never commit `.env`** — it's already listed in `.gitignore`. 

As of Issue #14 (real model integration), two additional variables are supported. Both are optional — if unset, they default to the repo-standard paths (`models/best_model.pkl` and `evaluation/model_comparison.md`), so no `.env` change is required to run the project as before. Set them only if your model artifacts live somewhere other than the repo root (e.g. a container image that copies only `app/`, `predict.py`, and `models/`): 

```bash
MODEL_PATH=models/best_model.pkl
MODEL_METRICS_PATH=evaluation/model_comparison.md
```

---

## Repository Structure

```text
customer-churn-platform/
├── app/
│   ├── api/         # FastAPI route definitions
│   ├── models/      # Trained model artifacts / model-related classes
│   ├── repository/  # Data access layer (queries the database)
│   └── services/    # Business logic, auth, prediction services
├── dashboard/
│   ├── churn_dashboard.pbix   # Power BI dashboard file
│   └── business_report.md     # Business-focused report summarising insights
├── database/        # SQLite connection logic, DB init scripts, the .db file (gitignored)
├── docs/
│   └── data_dictionary.md
├── etl/             # Data ingestion and cleaning scripts
├── evaluation/      # Model evaluation scripts and metrics
├── schemas/         # Pydantic request/response schemas
├── sql/             # Schema DDL, analysis queries, views
├── tests/
│   ├── test_api.py
│   ├── test_etl.py
│   ├── test_models.py
│   └── test_sql_views.py      # SQL views tests
├── training/        # Model training scripts
├── utils/           # Shared helper functions
├── data/
│   └── raw/         # Raw dataset CSV (gitignored — see .gitignore)
├── scripts/
│   ├── verify_endpoints.sh    # Endpoint verification script (macOS/Linux)
│   └── verify_endpoints.ps1   # Endpoint verification script (Windows PowerShell)
├── predict.py       # Prediction entry point
├── .env.example
├── .gitignore
├── PROCESS.md       # Internal collaboration & workflow guide
└── README.md
```

This tree reflects the ETL, model training, API, dashboard, tests, and supporting documentation and scripts used in the final project layout. 

---

## Architecture

```text
CSV (raw customer churn dataset)
│
▼
ETL Pipeline
│
▼
Clean Database (SQLite)
│
├─────────────► SQL Analysis (views + queries)
│
▼
Feature Engineering (during preprocessing)
│
▼
Model Training (5 models)
│
▼
Prediction Service
│
▼
FastAPI (5 endpoints, API key auth)
│
▼
Power BI Dashboard (documented local import/refresh setup)
```

### Models

Five models are trained and compared: **Logistic Regression, Decision Tree, Random Forest, XGBoost, LightGBM.** Evaluation metrics include Accuracy, Precision, Recall, ROC AUC, and Confusion Matrix; the best model is selected and used for the `/predict` endpoint. 

### API Endpoints

All endpoints require an `X-API-Key` header except `/health`. 

| Endpoint         | Method | Purpose                                         |
|------------------|--------|-------------------------------------------------|
| `/health`        | GET    | Health check, no auth                           |
| `/customers`     | GET    | Returns customer records                        |
| `/kpis`          | GET    | Returns business KPIs                           |
| `/predict`       | POST   | Returns a churn prediction for a given customer |
| `/model-metrics` | GET    | Returns the best model's evaluation metrics     |


> Full request/response examples for all 5 endpoints are documented in [`docs/api_examples.md`](docs/api_examples.md).
---

## Team & Responsibilities

| Name       | Role                          | Deliverables                                                             |
|-----------|-------------------------------|-------------------------------------------------------------------------|
| **Theresia** | Team Lead / Integration & QA | Technical review, real model/API integration, leakage correction, ETL/API/model tests and final integration |
| **Mercy**    | Lead Data Engineer           | `etl/`, `database/`, `repository/`, `sql/`                              |
| **Latifah**  | Lead ML Engineer             | `models/`, `training/`, `evaluation/`, `predict.py`                     |
| **Praise**   | Backend/API Engineer         | `api/`, `services/`, `schemas/`                                         |
| **Joyce**    | Lead BI & Analytics          | `dashboard/`, `business_report.md`                                      |
| **Pamela** | Planned Testing & QA lead | Automated test implementation ultimately completed by Theresia; see CONTRIBUTORS.md |
| **Salome**   | Lead Data Analyst & Documentation | `README.md`, `docs/`, `data_dictionary.md`                         |

**Coordination note:** Joyce and Salome must stay in sync — the dashboard connects directly to the SQL views Salome produces, so any change to view names or structure should be communicated directly, not left to surface at standup. 

---

## Milestones

| Milestone | Covers                                                                                      |
|----------|----------------------------------------------------------------------------------------------|
| **M0: Sprint Kickoff** | Repository setup & onboarding, all team members                               |
| **M1: Data Foundation** | ETL, database, schema, SQL analysis, views                                   |
| **M2: API Scaffold**    | FastAPI application shell with mocked prediction                             |
| **M3: Model Training**  | 5-model training, evaluation, `predict.py`                                   |
| **M4: Real Integration**| Swap mocked prediction for real model; full test suite against real components |
| **M5: Dashboard**       | Power BI, ODBC connection, all 5 pages                                       |
| **M6: Docs, Testing Polish & Presentation** | Final documentation, full test pass, presentation prep   |
| **M7 (optional): Stretch Goals** | Owned by Michael — only pursued if the core milestones finish early |


---

## Running the Project

This section demonstrates how to run the project end-to-end on your local machine, from ETL to model training, API startup, and tests. 

### 1. Run the ETL pipeline

Initialize and populate the SQLite database with the customer churn data and SQL views: 

```bash
python database/init_db.py
python etl/load_to_db.py
python database/init_views.py
```

After this step, `database/churn.db` should exist and contain all rows from the raw dataset, along with the reusable SQL views used by the dashboard and API. 

### 2. Run the machine learning training pipeline

Once the ETL pipeline has loaded the customer data into the database, install the project dependencies (if you have not already done so): 

```bash
pip install -r requirements.txt
```

Run the complete model training and evaluation pipeline:

```bash
python training/evaluate_models.py
```

This command is intended to:

- Train all five machine learning models:
  - Logistic Regression
  - Decision Tree
  - Random Forest
  - XGBoost
  - LightGBM
- Evaluate each model using Accuracy, Precision, Recall, ROC AUC, and a Confusion Matrix.
- Select the best-performing model based on the evaluation metrics.
- Save the selected model to `models/best_model.pkl`.
- Generate the evaluation report at `evaluation/model_comparison.md`.

### 3. Run the API locally

As of Issue #14, `/predict` and `/model-metrics` now call real artifacts instead of placeholders, so both must exist before starting the API: 

- `models/best_model.pkl` — produced by `training/evaluate_models.py` (see step 2 above). `/predict` will fail to start if this file is missing.
- `evaluation/model_comparison.md` — also produced by `training/evaluate_models.py`. `/model-metrics` returns a 500 with a clear error message if this file is missing, rather than failing silently or falling back to placeholder numbers.

`/customers` and `/kpis` require the database to be initialized and populated first — i.e. the ETL steps in step 1 must have been completed at least once. 

In short, the full local startup order is:

```bash
# 1. ETL — populates database/churn.db
python database/init_db.py
python etl/load_to_db.py
python database/init_views.py

# 2. Training — populates models/best_model.pkl and evaluation/model_comparison.md
python training/evaluate_models.py

# 3. API — now backed entirely by real data/model from steps 1–2
uvicorn app.main:app --reload
```

The historical endpoint scripts can be inspected or run below, but their known stale assertions and the KPI regression mean they are not expected to pass as acceptance checks:

**macOS / Linux:**

```bash
API_KEY=<your-key-from-.env> bash scripts/verify_endpoints.sh
```

**Windows (PowerShell):**

```powershell
$env:API_KEY="<your-key-from-.env>"; ./scripts/verify_endpoints.ps1
```

Both scripts check `/health` (no auth), `/customers`, `/kpis`, `/model-metrics`, and `/predict` (with and without the API key where relevant) and print a pass/fail summary. 

A single manual spot-check, if you want one:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### 4. Run tests

To run the SQL views tests only:

```bash
python -m pytest tests/test_sql_views.py
```

To run the full test suite:

```bash
python -m pytest
```

---

## Power BI Dashboard Setup

This section documents how to set up, open, and refresh `dashboard/churn_dashboard.pbix` locally. 

### Prerequisites

Before opening the dashboard, the database must be initialized and populated: 

```bash
python database/init_db.py
python etl/load_to_db.py
python database/init_views.py
```

Confirm the ETL completed successfully — you should see all rows from the raw dataset (7,043 for the current dataset) inserted into `database/churn.db`. 

### 1. Install a SQLite ODBC driver

Install the **SQLite3 ODBC Driver (64-bit)** on your machine. This is the driver version validated against this dashboard: 

- Driver: SQLite3 ODBC Driver
- Version: 1.34455.00.00 (64-bit)

Installation source and steps will depend on your OS — search for "SQLite ODBC Driver 64-bit" from a trusted driver provider (e.g. ch-werner.de/sqliteodbc) and follow the installer for your platform. 

### 2. Configure an ODBC DSN

Create a **System DSN** pointing at your local `database/churn.db` file. Name the DSN `ChurnDB` (the dashboard's data source expects this name). 

Steps (Windows):

1. Open **ODBC Data Sources (64-bit)** from Windows search.
2. Go to the **System DSN** tab → **Add**.
3. Select the SQLite3 ODBC Driver.
4. Set the DSN name to `ChurnDB` and point the database path at your local `database/churn.db`.
5. Save.

> Do not commit your local DSN configuration or any absolute file paths — these are machine-specific and are already excluded via `.gitignore`. 

### 3. Set the ProjectPath parameter

The Model Predictions page reads `evaluation/model_comparison.csv` via a Power Query parameter called `ProjectPath`, so each person needs to point it at their own local copy of the repo before refreshing: 

1. Open `dashboard/churn_dashboard.pbix` in Power BI Desktop.
2. Go to **Transform Data → Edit Parameters**.
3. Set `ProjectPath` to the full local path of your cloned repo folder. **Do not end the path with a trailing `/` or `\`.**
4. Click **OK**, then refresh (see step 5 below).

This is a one-time local setup step, same as the DSN above — it is not committed with any specific person's path baked in. 

### 4. Connect Power BI to the DSN

1. If prompted for a data source, go to **Get Data → ODBC** and select the `ChurnDB` DSN. 
2. Confirm the following objects are visible and queryable:
   - `customers`
   - `view_churn_by_contract`
   - `view_churn_by_tenure_bucket`
3. If visuals appear empty after connecting, use **Refresh** (Home tab → Refresh) to force Power BI to re-query the live ODBC connection. 

### 5. Refreshing the dashboard

Whenever the underlying data changes (new ETL run, updated views, or a new model evaluation in `evaluation/model_comparison.md`): 

1. Re-run the relevant pipeline step (ETL, views, or model evaluation/CSV regeneration — see `scripts/generate_model_comparison_csv.py`).
2. Open `dashboard/churn_dashboard.pbix` in Power BI Desktop.
3. Click **Refresh** on the Home tab to pull the latest data through the live ODBC connection.
4. Save the file.

No credentials or machine-specific paths (e.g. absolute local file paths, usernames) should ever be committed alongside the `.pbix` file. The DSN name (`ChurnDB`) and the `ProjectPath` parameter are the only environment-specific details the dashboard depends on, and both must be set locally by each team member following the steps above. 

### Business Report

A business-focused interpretation of the dashboard findings, including key insights and actionable recommendations, is available in: 

- **Report location:** `dashboard/business_report.md`
- **GitHub link:** [`dashboard/business_report.md`](dashboard/business_report.md)

Placing this link in the Dashboard section keeps business-facing content close to where stakeholders access the visuals, which is the most natural location for non-technical readers. 

---

## Coding Standards

- **Typing required** on all functions — use the `typing` module or built-in generics.
- **No `print()`** — use the `logging` module for all runtime output.
- **Tests required** for every feature — no hard coverage percentage target, but meaningful tests are expected. This is a project convention; no active CI currently enforces it.
- Pragmatic code is preferred over strict SOLID/clean-architecture adherence — clarity and correctness first.

---

## Data Dictionary and SQL Views

The project includes supporting documentation and reusable SQL views to simplify business analysis and dashboard development.

### Data Dictionary

The data dictionary documents the customer dataset, including each field's business meaning, example values, and intended use in analytics. 

Location:

```text
docs/data_dictionary.md
```

> **Note**
>
> The data dictionary reflects the current SQLite schema (`customers` table) and should be updated if the schema changes in future revisions.

### SQL Views

The following reusable SQL views are available. 

| View                       | Description                                  |
|----------------------------|----------------------------------------------|
| `view_churn_by_contract`   | Churn metrics grouped by contract type       |
| `view_churn_by_tenure_bucket` | Churn metrics grouped by customer tenure |

These views are designed for downstream reporting and Power BI dashboards. 

They are created by running:

```bash
python database/init_views.py
```

They are intended for reuse in Power BI dashboards and SQL analytics. 

## Project Process & Collaboration

Internal collaboration guidelines — including Git workflow, pull request template, definition of done, review process, and sprint board usage — are documented separately to keep the README focused on running and understanding the project.

For full details on how the team works, creates branches, opens PRs, and moves issues across the sprint board, see: 

Added Containerization

- [`PROCESS.md`](PROCESS.md)
