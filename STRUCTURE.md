# Repository Structure

This document is the authoritative, complete reference for how this repository is organized. It reflects the actual final state of `main` as of the Issue #20 integration and cleanup pass, verified directly against the repository's real file tree — not the plan, not an earlier draft.

For a shorter, narrative summary of the structure aimed at someone just getting started, see `README.md`'s "Repository Structure" section. This document is the detailed, complete counterpart to that summary.

> **Note:** a few paths below are gitignored and won't appear in a fresh `git clone` until you run the relevant pipeline step — these are marked explicitly. `database/churn.db` and `models/best_model.pkl` fall into this category; see `README.md`'s "Running the Project" section for how to generate them locally.
>
> **Corrected 2026-10-05 (Phase 2 / FGA-07):** this note, the tree entry below and the "Gitignored paths" list all claimed `data/raw/telco_churn_raw.csv` was gitignored. **It is not — it has always been tracked**, and it is present in a fresh clone. The old `.gitignore` rules did list `data/raw/*.csv` and `data/raw/`, but Git ignore rules never apply to files that are already tracked, and the `!data/raw/.gitkeep` negation beneath a whole-directory rule was inert anyway. The rules now read `data/raw/*` plus an explicit `!data/raw/telco_churn_raw.csv`, so the file's tracked status and `.gitignore` agree. Source, checksum and redistribution status: `docs/data_provenance.md`. The remaining inaccuracies in this document — notably `training/predict.py` and `training/scripts/verify_pr.ps1`, neither of which exists anywhere in the tree (both verified absent 2026-10-05) — are tracked as Phase 5 work and were deliberately left alone here.

---

## Full Tree

```text
customer-churn-platform/
│
├── app/                                  # FastAPI application
│   ├── api/
│   │   └── routes.py                     # All 5 endpoint definitions
│   ├── repository/
│   │   └── customer_repository.py        # CustomerRepository — the required DB access layer
│   ├── schemas/
│   │   └── customer_schema.py            # Pydantic request/response models for /predict
│   ├── services/
│   │   ├── auth_service.py               # X-API-Key verification (timing-safe comparison)
│   │   ├── kpi_service.py                # Real KPI computation for /kpis (Issue #14)
│   │   ├── metrics_service.py            # Parses evaluation/model_comparison.md for /model-metrics (Issue #14)
│   │   └── mock_prediction_service.py    # ARCHIVED — Issue #10 scaffold-stage placeholder, retained for reference only, not imported anywhere
│   ├── models/                           # (present in repo scaffold; not used for ORM output today — see database/models.py instead)
│   └── main.py                           # FastAPI app instantiation, router registration, .env loading
│
├── dashboard/
│   ├── business_report.md                # Business-facing findings + 5 recommendations
│   └── churn_dashboard.pbix              # Power BI dashboard, 5 pages, ODBC-connected
│
├── database/
│   ├── db_connection.py                  # get_connection() -> sqlite3.Connection
│   ├── init_db.py                        # Idempotent schema init (CREATE TABLE IF NOT EXISTS)
│   ├── init_views.py                     # Idempotent view init (drop + recreate view_churn_by_contract / view_churn_by_tenure_bucket)
│   ├── models.py                         # SQLAlchemy ORM model (Customer) — additive, not used by the sqlite3-based repository layer
│   └── churn.db                          # ⚠️ Gitignored. Created by running init_db.py + load_to_db.py + init_views.py.
│
├── data/
│   └── raw/
│       └── telco_churn_raw.csv           # ✅ TRACKED (not gitignored). The IBM Telco Cognos CSV the whole pipeline reproduces from — 7,043 rows × 33 cols, SHA-256 recorded in docs/data_provenance.md.
│
├── docs/
│   ├── api_examples.md                   # Request/response examples for all 5 endpoints
│   ├── data_dictionary.md                # Every DB column + engineered ML feature, documented
│   ├── qa_findings.md                    # Full QA findings log across Issues #13/#16/#17/#19 — living reference for known limitations
│   └── sql_analysis_summary.md           # Business questions, views, and validated key findings
│
├── etl/
│   ├── inspect_raw_data.py               # Standalone inspection script (columns, dtypes, nulls, row/col counts)
│   ├── clean_data.py                     # Documented cleaning logic (snake_case columns, total_charges handling, churn_reason fill)
│   └── load_to_db.py                     # Loads cleaned data into the customers table
│
├── evaluation/
│   ├── model_comparison.csv              # Machine-readable version of the model comparison table (generated for Power BI)
│   └── model_comparison.md               # Human-readable comparison across all 5 models + selected-model justification
│
├── models/
│   └── best_model.pkl                    # ⚠️ Gitignored. The persisted, selected model (full sklearn Pipeline: preprocessor + classifier). Created by training/evaluate_models.py.
│
├── schemas/
│   └── .gitkeep                          # Placeholder only — actual Pydantic schemas live in app/schemas/, not here
│
├── scripts/
│   ├── generate_model_comparison_csv.py  # Converts model_comparison.md → model_comparison.csv for Power BI
│   ├── verify_endpoints.sh               # Endpoint verification script (macOS/Linux)
│   └── verify_endpoints.ps1              # Endpoint verification script (Windows PowerShell)
│
├── sql/
│   ├── schema.sql                        # customers table DDL, with NOT NULL / CHECK constraints
│   ├── analysis_queries.sql              # 5 required exploratory business-question queries
│   └── views.sql                         # view_churn_by_contract, view_churn_by_tenure_bucket
│
├── tests/
│   ├── test_etl.py                       # ETL & database tests (Issue #13)
│   ├── test_api.py                       # FastAPI endpoint tests (Issue #16)
│   ├── test_models.py                    # Model training & prediction tests (Issue #17)
│   └── test_sql_views.py                 # SQL view tests (Issue #9, skip-guard added Issue #19)
│
├── training/
│   ├── data_loader.py                    # load_training_data() — reads via SQLite, not raw CSV
│   ├── feature_engineering.py            # TenureBucket, TotalServicesCount, AvgMonthlySpend
│   ├── preprocessing.py                  # prepare_features(), build_preprocessor(), DROP_COLUMNS leakage list
│   ├── train_test_split.py               # split_training_data() — 80/20 split, stratified, seeded
│   ├── train_models.py                   # Trains all 5 models
│   ├── evaluate_models.py                # Evaluates all 5 models, selects best by ROC AUC, writes model_comparison.md
│   ├── README.md                         # Currently empty
│   └── scripts/
│       └── verify_pr.ps1                 # Ad hoc verification script from the Issue #11 review round
│
├── utils/
│   └── .gitkeep                          # Reserved for shared helper functions — currently unused
│
├── predict.py                            # THE real, locked prediction entry point — predict(customer_data: dict) -> dict. Imported by app/api/routes.py. Includes the Issue #14 API-field adapter.
├── requirements.txt                      # Python dependencies
├── pytest.ini                            # pytest markers (unit/integration) + warning filters
├── .env.example                          # Documents API_KEY, DATABASE_PATH, MODEL_PATH, MODEL_METRICS_PATH, etc.
├── .gitignore
├── README.md                             # Setup, architecture, running instructions, API reference, dashboard setup
├── PROCESS.md                            # Git workflow, PR requirements, definition of done, review process (added Issue #20)
├── STRUCTURE.md                          # This file
├── CONTRIBUTORS.md                       # Actual-vs-planned ownership record across the sprint
└── Project Specification.md              # Component-by-component contract used during PR review
```

---

## Notes on Specific Directories

### `schemas/` vs `app/schemas/`
There are two `schemas/` directories in this repo, and this is intentional but worth being explicit about: the root-level `schemas/` contains only a `.gitkeep` placeholder and is not used. The real Pydantic request/response models live in `app/schemas/customer_schema.py`. If you're looking for the API's schema definitions, go to `app/schemas/`, not the root `schemas/` folder.

### `app/models/`
Present in the original scaffold as a placeholder for model-related classes, but the actual persisted model artifact lives at `models/best_model.pkl` (repo root), and the SQLAlchemy ORM model lives at `database/models.py`. `app/models/` is not currently populated.

### Two `predict.py` files
- **`predict.py` (repo root)** is the real, production entry point — this is what `app/api/routes.py` imports and calls. It includes the Issue #14 adapter layer that translates the API's field names (`tenure`, `SeniorCitizen`, etc.) into the training pipeline's column names (`tenure_months`, `senior_citizen`, etc.).
- **`training/predict.py`** is an earlier, superseded version without that adapter layer. It is not imported anywhere under `app/` — confirmed by a live regression test (`tests/test_models.py::TestTrainingPredictDeprecationFlag`) that fails loudly if this ever changes. See `docs/qa_findings.md` Finding 9 for the full history. A team decision on whether to delete this file or formally mark it as reference-only is still open as of this document.

### Gitignored paths you'll need to generate locally
These exist conceptually in the project but are intentionally excluded from version control (see `.gitignore`):
- `database/churn.db` — generated by `python database/init_db.py && python etl/load_to_db.py && python database/init_views.py`.
- `models/best_model.pkl` — generated by `python training/evaluate_models.py`.

`data/raw/telco_churn_raw.csv` is **not** in this list: it is tracked and arrives with the clone (corrected 2026-10-05 — see the note at the top of this document and `docs/data_provenance.md`). Everything *else* placed in `data/raw/` (Kaggle downloads, `.xlsx` workbooks, ad-hoc exports) is ignored.

See `README.md`'s "Running the Project" section for the full, ordered setup sequence.

---

## Source

This document was generated directly from the actual repository file listing as of the Issue #20 integration/cleanup pass, cross-checked against `README.md`, `Project_Specification.md`, and `docs/qa_findings.md`. If the structure changes in future work, update this file alongside the change — it's meant to stay accurate, not become another stale reference document.