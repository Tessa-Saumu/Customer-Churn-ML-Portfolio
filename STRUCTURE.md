# Repository Structure

This document is the authoritative, complete reference for how this repository is organized. It is verified directly against the repository's real file tree — not the plan, not an earlier draft.

For a shorter, narrative summary of the structure aimed at someone just getting started, see `README.md`'s "Repository Structure" section. This document is the detailed, complete counterpart to that summary.

> **Note:** a few paths below are gitignored and won't appear in a fresh `git clone` until you run the relevant pipeline step — these are marked explicitly. `database/churn.db` and `models/best_model.pkl` fall into this category; see `README.md`'s "Running the Project" section for how to generate them locally.

> **Re-verified 2026-10-06 (Phase 5 / audit item FGA-08) against `git ls-files` (85 tracked files).** The previous version of this document was generated at the Issue #20 cleanup pass and had drifted. What was corrected now:
>
> - **`training/predict.py` does not exist.** It was described here as a second, superseded prediction module. There is exactly one `predict.py`, at the repo root. The regression test that was said to guard the duplication (`TestTrainingPredictDeprecationFlag`) still exists and still passes, but it asserts only that nothing under `app/` imports `training.predict` — which is trivially true of a file that is not there. See the corrected note below.
> - **`training/scripts/verify_pr.ps1` does not exist**, and neither does the `training/scripts/` directory.
> - Added everything the flagship consolidation introduced and the earlier tree predated: `tests/test_kpi_aggregate.py`, `tests/test_reproducibility.py`, `docs/data_provenance.md`, `docs/reproduction_record.md`, `evaluation/legacy/`, `evaluation/reproduction/`, `dashboard/screenshots/`, `.python-version`, `requirements.lock.txt`, `.github/workflows/ci.yml`, and the Docker/Compose/Makefile/Streamlit files.
> - The `.env.example` description no longer lists `DATABASE_PATH` (removed in Phase 2 — nothing read it).
> - The `data/raw/telco_churn_raw.csv` "gitignored" claim was already corrected on 2026-10-05 (Phase 2 / FGA-07); that correction stands. Source, checksum and redistribution status: `docs/data_provenance.md`.

---

## Full Tree

```text
customer-churn-platform/
│
├── .github/
│   └── workflows/
│       └── ci.yml                          # The single enforced check: pinned install -> artifacts -> full suite (zero skips) -> endpoint smoke checks
│
├── app/                                    # FastAPI application
│   ├── api/
│   │   └── routes.py                       # All 5 endpoint definitions
│   ├── repository/
│   │   └── customer_repository.py          # CustomerRepository — DB access layer: paginated get_all() plus the whole-table get_kpi_aggregate()
│   ├── schemas/
│   │   └── customer_schema.py              # Pydantic request/response models for /predict
│   ├── services/
│   │   ├── auth_service.py                 # X-API-Key verification (timing-safe comparison)
│   │   ├── kpi_service.py                  # Whole-population KPI computation for /kpis
│   │   ├── metrics_service.py              # Parses evaluation/model_comparison.md for /model-metrics
│   │   └── mock_prediction_service.py      # ARCHIVED — Issue #10 scaffold-stage placeholder, retained for reference only, not imported anywhere
│   ├── models/
│   │   └── .gitkeep                        # Scaffold placeholder; not used for ORM output (see database/models.py)
│   └── main.py                             # FastAPI app instantiation, router registration, .env loading (load_dotenv runs BEFORE the router import)
│
├── dashboard/
│   ├── business_report.md                  # Business-facing findings + 5 recommendations
│   ├── churn_dashboard.pbix                # Power BI dashboard, 5 pages, SQLite-over-ODBC data source
│   └── screenshots/                        # 5 committed report captures (one per page)
│       ├── executive_overview.jpg
│       ├── customer_demographics.jpg
│       ├── churn_drivers.jpg
│       ├── revenue_impact.jpg
│       └── model_predictions.jpg           # ⚠️ HISTORICAL CAPTURE — shows the legacy single-split metrics; not refreshed
│
├── database/
│   ├── db_connection.py                    # get_connection() -> sqlite3.Connection (DB path is hardcoded to database/churn.db)
│   ├── init_db.py                          # Idempotent schema init (CREATE TABLE IF NOT EXISTS)
│   ├── init_views.py                       # Idempotent view init (drop + recreate view_churn_by_contract / view_churn_by_tenure_bucket)
│   ├── models.py                           # SQLAlchemy ORM model (Customer) — additive, not used by the sqlite3-based repository layer
│   └── churn.db                            # ⚠️ Gitignored. Created by running init_db.py + load_to_db.py + init_views.py.
│
├── data/
│   └── raw/
│       └── telco_churn_raw.csv             # ✅ TRACKED (not gitignored). The IBM Telco Cognos CSV the whole pipeline reproduces from — 7,043 rows × 33 cols, SHA-256 recorded in docs/data_provenance.md.
│
├── docs/
│   ├── api_examples.md                     # Request/response examples for all 5 endpoints (regenerated against live output 2026-10-06)
│   ├── data_dictionary.md                  # Every DB column + engineered ML feature, documented
│   ├── data_provenance.md                  # Input identity/checksum, upstream source, rights analysis and retention decision
│   ├── qa_findings.md                      # Full QA findings log across Issues #13/#16/#17/#19 — living reference for known limitations
│   ├── reproduction_record.md              # The authoritative runtime/pins/commands/results record for the published metrics
│   └── sql_analysis_summary.md             # Business questions, views, and validated key findings
│
├── etl/
│   ├── inspect_raw_data.py                 # Standalone inspection script (columns, dtypes, nulls, row/col counts)
│   ├── clean_data.py                       # Documented cleaning logic (snake_case columns, total_charges handling, churn_reason fill)
│   └── load_to_db.py                       # Loads cleaned data into the customers table
│
├── evaluation/
│   ├── model_comparison.md                 # CURRENT report: CV selection table + one frozen-holdout evaluation, with protocol and provenance
│   ├── model_comparison.csv                # Machine-readable selection table (generated for Power BI; LF line endings)
│   ├── legacy/                             # Archived predecessor result, labelled historical and frozen by hash
│   │   ├── README.md
│   │   ├── model_comparison_single_split.md
│   │   └── model_comparison_single_split.csv
│   └── reproduction/                       # Raw run logs per reproduction, each with a label saying what it is
│       ├── 2026-10-05-pinned-single-split/ # README.md, model_comparison.{md,csv}, training.log
│       └── 2026-10-06-phase3-cv-holdout/   # README.md, training.log (the tracked report IS this run's output)
│
├── models/
│   └── best_model.pkl                      # ⚠️ Gitignored. The persisted, selected model (full sklearn Pipeline: preprocessor + classifier). Created by training/evaluate_models.py.
│
├── schemas/
│   └── .gitkeep                            # Placeholder only — actual Pydantic schemas live in app/schemas/, not here
│
├── scripts/
│   ├── generate_model_comparison_csv.py    # Converts model_comparison.md → model_comparison.csv for Power BI
│   ├── verify_endpoints.sh                 # Endpoint verification script (macOS/Linux): 29 checks, exits nonzero on failure
│   └── verify_endpoints.ps1                # Endpoint verification script (Windows PowerShell): mirrors the Bash checks
│
├── sql/
│   ├── schema.sql                          # customers table DDL, with NOT NULL / CHECK constraints
│   ├── analysis_queries.sql                # 5 required exploratory business-question queries
│   └── views.sql                           # view_churn_by_contract, view_churn_by_tenure_bucket
│
├── tests/
│   ├── test_etl.py                         # ETL & database tests (Issue #13)
│   ├── test_api.py                         # FastAPI endpoint tests (Issue #16) + whole-population /kpis guards
│   ├── test_kpi_aggregate.py               # /kpis whole-table aggregate regression + pagination preservation (runs with no artifacts)
│   ├── test_models.py                      # Model training & prediction tests (Issue #17) + evaluation-protocol and leakage-exclusion tests
│   ├── test_reproducibility.py             # Input provenance, pinned runtime, artifact/secret hygiene, metrics immutability
│   └── test_sql_views.py                   # SQL view tests (Issue #9) + tenure-bucket boundary/definition tests
│
├── training/
│   ├── data_loader.py                      # load_training_data() — reads via SQLite, not raw CSV
│   ├── feature_engineering.py              # TenureBucket, TotalServicesCount, AvgMonthlySpend
│   ├── preprocessing.py                    # prepare_features(), build_preprocessor(), DROP_COLUMNS leakage list
│   ├── train_test_split.py                 # split_training_data() — 80/20 split, stratified, seeded
│   ├── train_models.py                     # Candidate/baseline builders, build_pipeline(), train_single_model()
│   ├── evaluate_models.py                  # Evaluation protocol: 5-fold CV selection on the training portion + baseline, then one frozen-holdout evaluation; writes model_comparison.md
│   ├── README.md                           # Present but empty (0 bytes)
│   └── .gitkeep
│
├── utils/
│   └── .gitkeep                            # Reserved for shared helper functions — currently unused
│
├── predict.py                              # THE real, locked prediction entry point — predict(customer_data: dict) -> dict. Imported by app/api/routes.py. Includes the Issue #14 API-field adapter.
├── streamlit-app.py                        # Optional local demo UI — not part of the verified path and not exercised by any test
├── requirements.txt                        # Python dependencies — every direct dependency pinned
├── requirements.lock.txt                   # Full verified transitive closure (Linux pip freeze), used as requirements.txt's constraints file
├── pytest.ini                              # pytest markers (unit/integration) + warning filters
├── .python-version                         # 3.11.2 — the supported runtime
├── .env.example                            # Documents API_KEY, MODEL_PATH, MODEL_METRICS_PATH (and names the settings that are NOT env-configurable)
├── .gitignore
├── .dockerignore
├── Dockerfile                              # Two-stage API image (python:3.11-slim) — never built in this environment
├── Dockerfile.streamlit                    # Streamlit demo image — never built in this environment
├── docker-compose.yml                      # Local api + streamlit services
├── Makefile                                # Docker/Compose and test shortcuts
├── README.md                               # Setup, architecture, running instructions, API reference, dashboard setup
├── PROCESS.md                              # Git workflow, PR requirements, definition of done, review process (added Issue #20)
├── STRUCTURE.md                            # This file
├── CONTRIBUTORS.md                         # Actual-vs-planned ownership record across the sprint
├── Project Specification.md                # Component-by-component contract used during PR review
├── PROJECT_EVIDENCE_CHURN.md               # Dated (2026-09-26) evidence record about the ORIGINAL team repository
├── FLAGSHIP_GAP_AUDIT.md                   # The audit this consolidation works from
└── FLAGSHIP_IMPLEMENTATION_PLAN.md         # The phase plan and its implementation records
```

---

## Notes on Specific Directories

### `schemas/` vs `app/schemas/`
There are two `schemas/` directories in this repo, and this is intentional but worth being explicit about: the root-level `schemas/` contains only a `.gitkeep` placeholder and is not used. The real Pydantic request/response models live in `app/schemas/customer_schema.py`. If you're looking for the API's schema definitions, go to `app/schemas/`, not the root `schemas/` folder.

### `app/models/`
Present in the original scaffold as a placeholder for model-related classes, but the actual persisted model artifact lives at `models/best_model.pkl` (repo root), and the SQLAlchemy ORM model lives at `database/models.py`. `app/models/` contains only a `.gitkeep`.

### There is one `predict.py`
**`predict.py` at the repo root is the only prediction entry point.** It is what `app/api/routes.py` imports and calls, and it includes the Issue #14 adapter layer that translates the API's field names (`tenure`, `SeniorCitizen`, etc.) into the training pipeline's column names (`tenure_months`, `senior_citizen`, etc.).

This document previously described a second, superseded `training/predict.py`. **No such file exists** — verified absent on 2026-10-06, as it was on 2026-10-05. `docs/qa_findings.md` Finding 9 records the history behind that description. `tests/test_models.py::TestTrainingPredictDeprecationFlag` remains and passes, but be precise about what it proves: it asserts that no module under `app/` imports `training.predict`. That is a guard against the duplication *returning*, not evidence that the file is present.

### `.github/workflows/`
Contains exactly one workflow, `ci.yml`: install the pinned environment → build the database and model from the tracked CSV → run the full suite requiring **zero failures and zero skips** → run both endpoint smoke scripts against a live API. It has read-only repository permissions, needs no secrets, and cannot deploy anything.

A `deploy.yml` also lived here until 2026-10-06. It was 164 lines of which 132 were comments and the remaining 32 blank — it could never have run — yet GitHub still listed it as an active workflow and recorded a "failure" for every push. It was removed; the repository is and remains undeployed. The file is recoverable from Git history at blob `e3847923`.

### Gitignored paths you'll need to generate locally
These exist conceptually in the project but are intentionally excluded from version control (see `.gitignore`):
- `database/churn.db` — generated by `python database/init_db.py && python etl/load_to_db.py && python database/init_views.py`.
- `models/best_model.pkl` — generated by `python training/evaluate_models.py`.

`data/raw/telco_churn_raw.csv` is **not** in this list: it is tracked and arrives with the clone (corrected 2026-10-05 — see the note at the top of this document and `docs/data_provenance.md`). Everything *else* placed in `data/raw/` (Kaggle downloads, `.xlsx` workbooks, ad-hoc exports) is ignored.

See `README.md`'s "Running the Project" section for the full, ordered setup sequence.

---

## Source

This document was regenerated from the actual repository file listing (`git ls-files`, 85 tracked files) on 2026-10-06, cross-checked against `README.md`, `Project Specification.md` and `docs/qa_findings.md`. If the structure changes in future work, update this file alongside the change — it's meant to stay accurate, not become another stale reference document.
