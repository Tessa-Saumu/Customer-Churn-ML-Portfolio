# Customer Churn Prediction & Business Intelligence Platform

This is Theresia Saumu's personal portfolio copy of the [original team repository](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform). It preserves the team's Git history and contributor credits. The application documentation changes live on this copy's `main` branch; they do not change the shared project. GitHub does not mark this as a native fork because the shared repository is already owned by the same account.

A mentored team capstone connecting a telecom churn dataset, comparative classification, a local FastAPI service and Power BI reporting.

## Problem and personal contribution

The team built a local workflow over the [IBM Telco dataset](https://www.kaggle.com/datasets/yeanzc/telco-customer-churn-ibm-dataset). As team lead, Theresia Saumu implemented real model/API integration, the training-to-inference field adapter, leakage correction and automated ETL/API/model tests. Evidence: [integration PR #27](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/27), test PRs [#29](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/29), [#30](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/30), [#31](https://github.com/Tessa-Saumu/Customer-Churn-Prediction-BI-Platform/pull/31), and [contribution map](CONTRIBUTORS.md).

ETL, model training, API scaffolding, SQL analysis and dashboard work had other owners. Mentor contributions include scaffolding, pagination, Docker and Streamlit. This is team integration and QA evidence, not sole authorship of the platform.

## Architecture, quickstart and evidence at a glance

The four consumer paths (SQL analytics, model training, the API, and BI) are
distinct, and only the API serves predictions. Nothing here is deployed; every
arrow below is a local file or a documented local step.

```text
                     data/raw/telco_churn_raw.csv
                     (tracked input · 7,043 rows · SHA-256 e984530b…)
                                    │  etl/clean_data.py → etl/load_to_db.py
                                    ▼
                      ┌──────────────────────────────┐
                      │  database/churn.db (SQLite)  │  generated, gitignored
                      │  customers · 7,043 rows      │
                      └──────────────────────────────┘
                       │                      │
        database/init_views.py                 training/data_loader.py
                       │                      │
                       ▼                      ▼
   ┌────────────────────────────┐  ┌───────────────────────────────────┐
   │ SQL layer                  │  │ training/                          │
   │  view_churn_by_contract    │  │ 5 candidates + prior baseline,     │
   │  view_churn_by_tenure_bucket│  │ 5-fold CV on the training 80%,    │
   │  sql/analysis_queries.sql  │  │ freeze winner → 1 holdout eval     │
   └────────────────────────────┘  └───────────────────────────────────┘
                       │                     │                │
                       │                     ▼                ▼
                       │          models/best_model.pkl   evaluation/model_comparison.md
                       │          (generated, gitignored)   (+ model_comparison.csv)
                       │                     │                │
                       │        ┌────────────┴────────────────┴──────────┐
                       │        │ FastAPI · app/main.py · X-API-Key auth │
                       └───────►│  GET  /health            (no auth)     │
                                │  GET  /customers         paginated     │
                                │  GET  /kpis              whole-table   │
                                │  POST /predict           serves pickle │
                                │  GET  /model-metrics     parses report │
                                └────────────────────────────────────────┘
                       │
                       ▼
   ┌────────────────────────────┐    ┌─────────────────────────────┐
   │ Power BI (.pbix)           │    │ streamlit-app.py             │
   │  ODBC DSN → the SQL views  │    │ optional demo — unverified,  │
   │  ProjectPath → the CSV     │    │ exercised by no test         │
   └────────────────────────────┘    └─────────────────────────────┘
```

Five commands reproduce the whole local path (full instructions, env setup and
the macOS/Windows caveat are in [Running the Project](#running-the-project)):

```bash
python -m venv venv && source venv/bin/activate
pip install --upgrade pip wheel && pip install -r requirements.txt
python database/init_db.py && python etl/load_to_db.py && python database/init_views.py
python training/evaluate_models.py
API_KEY=<any-key> uvicorn app.main:app & API_KEY=<any-key> ./scripts/verify_endpoints.sh
```

**Current evidence** — the Churn Drivers page is the one capture that is verifiably
current: every figure it shows (26.54% churn, 1,869 churned, 5,174 active; contract
rates 42.71 / 11.27 / 2.83%; tenure buckets 47 / 26 / 12%) was re-queried from the
live SQL views on 2026-10-06 and matched exactly. The Model Predictions capture is
historical and labelled as such.

![Churn Drivers — verified current capture](dashboard/screenshots/churn_drivers.jpg)

**Status in one line:** reproduced end-to-end in a pinned environment and enforced by
a single CI workflow (`.github/workflows/ci.yml`) that, on a runner, can be green only
with zero test skips — but see [Limitations](#limitations-and-current-status): GitHub
Actions could not start a job for this account, so no green CI run is claimed.

## Evaluation and key finding

Integration exposed an outcome-derived `churn_score` feature unavailable in real prediction requests. It was removed from model inputs and the comparison was rerun. Earlier leakage-affected figures are not valid predictive-performance evidence.

The [current comparison](evaluation/model_comparison.md) uses the Phase 3 protocol (2026-10-06): the five candidates and a `DummyClassifier` prior baseline are scored with 5-fold stratified cross-validation on the 80% **training** portion only, the winner is frozen and refitted, and only then are the winner and the baseline evaluated once on the untouched 20% holdout. Results:

| Model | Setting | Accuracy | Precision | Recall | ROC AUC |
|---|---|---|---|---|---|
| Logistic Regression (**selected**) | untouched holdout, evaluated once | 0.7991 | 0.6435 | 0.5455 | **0.8496** |
| Logistic Regression | 5-fold CV, training portion | 0.8133 | 0.6746 | 0.5726 | 0.8591 (std 0.0142) |
| DummyClassifier (naive baseline) | untouched holdout | 0.7346 | 0.0000 | 0.0000 | 0.5000 |

Logistic Regression still wins under the same criterion as before (mean CV ROC AUC) and clears the naive floor, but the margin over the other candidates is not claimed to be significant, recall remains ~55%, and no hyperparameter search or threshold tuning was done. The dataset has no time index, so no temporal generalization is established.

The **legacy single-split result** (ROC AUC **0.8494**, accuracy **0.8020**) is archived and labelled in [`evaluation/legacy/`](evaluation/legacy/) and must not be read as an untouched final estimate. Audit FGA-09 (a structured metrics artifact for the API) and hyperparameter work remain out of scope; see [`docs/reproduction_record.md`](docs/reproduction_record.md) §12 for the protocol record and provenance.

## Limitations and current status

- **KPI boundary — repaired (post-sprint, Phase 1, 2026-10-05):** `/kpis` used to call `CustomerRepository.get_all()` with its default page size of 100, so it summarized the first 100 rows and presented them as the whole population (on this dataset: `customer_count: 100`, `overall_churn_rate: 100.0`). It now computes a single whole-table SQL aggregate (`CustomerRepository.get_kpi_aggregate()`), so `/kpis` reports the full population — 7,043 customers and a 26.54% churn rate — without materializing customer rows. `/customers` still returns one page by default; that pagination is the mentor's intentional design and was not changed. Regression coverage: `tests/test_kpi_aggregate.py` and the `/kpis` population guards in `tests/test_api.py`.
- Many integration tests skip when generated database/model artifacts are absent, so a historical full-suite pass is not a claim of current correctness. That is now enforced by a single CI workflow, [`.github/workflows/ci.yml`](.github/workflows/ci.yml): it installs the committed pins, builds the artifacts from the tracked CSV, and then requires **zero failures and zero skips** (151 passed / 0 failed / 0 skipped in the pinned environment). **It has not produced a green run, and none is claimed**: GitHub refused to start the job — *"The job is not started because your account is locked due to a billing issue"* — so the job ran zero steps. Every step of the workflow was instead executed locally, in order, and passed (except the PowerShell smoke step, which needs a PowerShell runtime). The clean artifact-present run is recorded in [`docs/reproduction_record.md`](docs/reproduction_record.md).
- **Reproducibility — pinned (Phase 2, 2026-10-05):** one supported runtime (CPython 3.11, `.python-version` = 3.11.2) and one pinned dependency set (`requirements.txt` + `requirements.lock.txt`) now define the environment; a second clean venv built from them froze to exactly the committed lock, and two training runs produced byte-identical reports *and* pickles. Python 3.12 — previously claimed here and in the Dockerfiles — was never run and could not be tested in this environment; the container images were aligned to `python:3.11-slim` but **no Docker build was executed**, so the container path remains documented-not-verified.
- The endpoint verification scripts previously carried stale assertions (including pre-leakage LightGBM metrics in the shell script). They were rewritten against the current contract in Phase 1: `scripts/verify_endpoints.sh` passes **29/29** against a live API in the pinned environment and exits nonzero on a failed or missing check. `scripts/verify_endpoints.ps1` **has still never been executed** — no PowerShell runtime was available in either phase — so it is written and syntax-checked only.
- No cloud deployment is established. The legacy `deploy.yml` workflow — 164 lines of which 132 were comments and 32 blank, so it could never run — was removed on 2026-10-06 (recoverable from Git history at blob `e3847923`); the only workflow now is the test-only `ci.yml`. Docker/Streamlit files exist; their presence does not prove a working deployment (no Docker build was ever run here), and the Streamlit demo is an **optional, unverified** path that no test exercises.
- The committed Power BI screenshots are report captures, not live evidence, and the refresh instructions below describe the intended local setup rather than a verified live ODBC connection. On 2026-10-06 each capture was compared with the live SQL: **`churn_drivers.jpg` is current** (every figure matched) and is featured near the top of this README; **`model_predictions.jpg` is historical** — it shows the legacy single-split five-model table, whose supersession is explained in `dashboard/business_report.md` and [`evaluation/model_comparison.md`](evaluation/model_comparison.md). No Power BI Desktop was available to re-render it, so it is labelled historical rather than refreshed.
- **Evaluation protocol — replaced (Phase 3, 2026-10-06):** the earlier comparison trained all five models on one stratified split and picked the winner on that same holdout, with no baseline. The current protocol cross-validates the candidates plus a naive baseline on the training portion, freezes the winner, and evaluates it once on the untouched holdout. Metrics consequently changed; the legacy values remain archived and labelled. Logistic Regression still does not converge within `max_iter=1000`, which is recorded as an open problem rather than fixed, because fixing it would move the numbers again.
- **Tenure reporting definitions — aligned (Phase 3, 2026-10-06):** `sql/analysis_queries.sql` used four tenure ranges while `view_churn_by_tenure_bucket` (the definition the committed dashboard visual renders) used three, so the same business question had two answers. The query now matches the view; the model's finer four-range `TenureBucket` feature is documented as a separate modelling input.
- Code defects and evaluation protocols were not changed for this documentation pass, with four exceptions: the Phase 1 KPI aggregate (changes `/kpis` only), the optional `report_dir` parameter on `evaluate_all_models()` (so `pytest` cannot rewrite the tracked comparison file), the Phase 3 evaluation protocol (deliberately changes the published metrics, with the previous result archived), and the Phase 3 tenure-bucket alignment (changes the reporting query's grouping, no metric). Phases 4–5 (2026-10-06) add the CI workflow, a `TestLeakageExclusions` regression guard, and documentation corrections; they change no code behaviour beyond that.

**Project work:** July-August 2026. The earlier nine-day figure was a planning target, not demonstrated elapsed delivery time.

---

## Table of Contents

1. [Problem and personal contribution](#problem-and-personal-contribution)
2. [Architecture, quickstart and evidence at a glance](#architecture-quickstart-and-evidence-at-a-glance)
3. [Evaluation and key finding](#evaluation-and-key-finding)
4. [Limitations and current status](#limitations-and-current-status)
5. [Getting Started](#getting-started)
6. [Repository Structure](#repository-structure)
7. [Architecture](#architecture)
8. [Team & Responsibilities](#team--responsibilities)
9. [Milestones](#milestones)
10. [Running the Project](#running-the-project)
11. [Power BI Dashboard Setup](#power-bi-dashboard-setup)
12. [Coding Standards](#coding-standards)
13. [Data Dictionary and SQL Views](#data-dictionary-and-sql-views)
14. [Project Process & Collaboration](#project-process--collaboration)

---

## Getting Started

### Prerequisites

- **Git** — [install instructions](https://git-scm.com/downloads)
- **Python 3.11** — confirm with `python --version`. This is the supported runtime; `.python-version` pins `3.11.2`, the exact patch level the whole pipeline was verified on ([`docs/reproduction_record.md`](docs/reproduction_record.md)). Python 3.12 was claimed by this README and the Dockerfiles until 2026-10-05 but had never been run; it is neither validated nor excluded.
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

# Confirm Python 3.11 is installed (supported runtime — see .python-version)
python --version

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate

# Install dependencies — every direct dependency is pinned in requirements.txt,
# which constrains itself with requirements.lock.txt (the full verified closure),
# so this install is deterministic.
pip install --upgrade pip wheel
pip install -r requirements.txt
```

> **On macOS/Windows:** use `pip install -r requirements.txt` as above. Do **not**
> install `requirements.lock.txt` directly — it is a Linux `pip freeze` and contains
> Linux-only transitive packages (`nvidia-nccl-cu12` via xgboost, `uvloop` via
> `uvicorn[standard]`). Used as the constraints file those entries are inert on other
> platforms. See the header of that file and [`docs/reproduction_record.md`](docs/reproduction_record.md) §2.

### Configure environment variables

Copy the example environment file and fill in real values:

```bash
cp .env.example .env
```

`.env.example` lists **only variables the code actually reads**: `API_KEY` (required for every endpoint except `GET /health`) plus the two optional artifact paths below. **Never commit `.env`** — it's already listed in `.gitignore`, and `tests/test_reproducibility.py` fails if a secret or generated file is ever tracked.

Three settings that used to be documented in `.env.example` were removed on 2026-10-05 because nothing read them: `DATABASE_PATH` (`database/db_connection.py` hardcodes `database/churn.db`, relative to the working directory), `API_HOST` and `API_PORT` (uvicorn owns those through CLI flags: `uvicorn app.main:app --host 0.0.0.0 --port 8000`). They were placeholders that silently did nothing.

As of Issue #14 (real model integration), two additional variables are supported. Both are optional — if unset, they default to the repo-standard paths (`models/best_model.pkl` and `evaluation/model_comparison.md`), so no `.env` change is required to run the project as before. Set them only if your model artifacts live somewhere other than the repo root (e.g. a container image that copies only `app/`, `predict.py`, and `models/`): 

```bash
MODEL_PATH=models/best_model.pkl
MODEL_METRICS_PATH=evaluation/model_comparison.md
```

Both are read at **import** time, so `app/main.py` calls `load_dotenv()` *before* importing the router. Until 2026-10-05 the router was imported first, which meant a `MODEL_METRICS_PATH` written into `.env` was silently ignored — only a real exported variable (such as the `Dockerfile`'s `ENV`) took effect. The ordering is guarded by a structural test and a subprocess test in `tests/test_reproducibility.py`.

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
├── evaluation/      # Current model comparison (Phase 3 protocol), legacy/ (historical archive) and reproduction/ (run logs)
├── schemas/         # Pydantic request/response schemas
├── sql/             # Schema DDL, analysis queries, views
├── tests/
│   ├── test_api.py
│   ├── test_etl.py
│   ├── test_kpi_aggregate.py  # /kpis whole-table aggregate regression
│   ├── test_models.py         # also covers the evaluation protocol
│   ├── test_reproducibility.py
│   └── test_sql_views.py      # SQL views + tenure-bucket definitions
├── training/        # Model training scripts
├── utils/           # Shared helper functions
├── data/
│   └── raw/         # Tracked reproduction input: telco_churn_raw.csv (see docs/data_provenance.md)
├── scripts/
│   ├── generate_model_comparison_csv.py  # Report -> Power BI CSV
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

The component and data-boundary diagram lives at the top of this README under
[Architecture, quickstart and evidence at a glance](#architecture-quickstart-and-evidence-at-a-glance).
The single most important boundary it shows: the API serves predictions from a
persisted artifact and reports from a generated file, Power BI reads the SQL views
and the CSV, and none of them is deployed — there is no live service tying them
together.

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

**Input data — nothing to download.** The pipeline reads one tracked file, `data/raw/telco_churn_raw.csv` (7,043 rows × 33 columns, SHA-256 `e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34`). Its source (the Kaggle IBM Telco listing), version, checksum and **unconfirmed** redistribution status are recorded in [`docs/data_provenance.md`](docs/data_provenance.md). `tests/test_reproducibility.py` re-checks that hash on every run, so you can tell whether your clone holds the exact input the published results came from. (Earlier versions of this README and `STRUCTURE.md` described the file as gitignored; that was false — it is tracked, and `.gitignore` now says so explicitly.)

**Generated files stay out of Git.** `database/churn.db` and `models/best_model.pkl` are gitignored and produced by the steps below, so a clean checkout has neither until you run them.

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

This command runs the evaluation protocol (Phase 3, 2026-10-06):

- Split the data into a stratified 80/20 training/holdout split and **freeze the holdout**.
- Score all five candidates and a `DummyClassifier` prior baseline with 5-fold stratified cross-validation on the **training portion only**:
  - Logistic Regression
  - Decision Tree
  - Random Forest
  - XGBoost
  - LightGBM
- Select the winner by mean cross-validated ROC AUC, refit it on the full training portion.
- Evaluate the frozen winner and the baseline **once** on the untouched holdout, using Accuracy, Precision, Recall, ROC AUC and a Confusion Matrix.
- Save the selected model to `models/best_model.pkl`.
- Generate the evaluation report at `evaluation/model_comparison.md`.

The Power BI CSV is a separate, explicit step: `python scripts/generate_model_comparison_csv.py` converts the report's selection table into `evaluation/model_comparison.csv`.

> **This overwrites a tracked file.** `evaluation/model_comparison.md` is the *current* published result, so running training rewrites it. In the supported environment the rewrite is byte-identical to the committed bytes ([`docs/reproduction_record.md`](docs/reproduction_record.md) §12); if your environment differs, `git diff` shows exactly what changed, and `git checkout -- evaluation/model_comparison.md` restores the committed result.
>
> `pytest` does **not** modify either tracked metrics file — the retraining tests redirect their report into a temporary directory, and tests fail if that ever stops being true.

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

The endpoint verification scripts below check the current API contract — auth, pagination, whole-population KPI semantics and the locked response shapes. Run them against a locally running instance:

**macOS / Linux:**

```bash
API_KEY=<your-key-from-.env> ./scripts/verify_endpoints.sh
```

**Windows (PowerShell):**

```powershell
$env:API_KEY="<your-key-from-.env>"; .\scripts\verify_endpoints.ps1
```

Both scripts check `/health` (no auth), `/customers` (including its paginated default and an explicit page/size request), `/kpis` (whole-population values, not the first page), `/model-metrics`, and `/predict` (with and without the API key where relevant), then print a pass/fail/skip summary and exit nonzero if any check fails. They require `curl` and `jq` (Bash) and an explicit `API_KEY`; a missing tool or key exits with code 2 rather than reporting a misleading all-green run.

Optional settings: `EXPECTED_CUSTOMER_COUNT` (default `7043`, the tracked dataset's row count — set it to your database's row count, or `0` to skip the exact-count check) and `REPORT_PATH` (default `evaluation/model_comparison.md`, used for the API/report consistency check).

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

> **Status (2026-10-06):** these are the documented intended steps, written at sprint
> end and re-verified only by inspection. No Power BI Desktop environment was
> available during this work, so the connection/refresh behaviour below has **not**
> been re-executed; the committed page captures are historical except
> `churn_drivers.jpg`, which was re-verified against the live SQL views.

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
- **Tests required** for every feature — no hard coverage percentage target, but meaningful tests are expected. A single test-only CI workflow (`.github/workflows/ci.yml`) now enforces the artifact-present suite; see [Limitations](#limitations-and-current-status) for the caveat that GitHub Actions has not started a job for this account.
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
