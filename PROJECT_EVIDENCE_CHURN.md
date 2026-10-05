# Project Evidence — Customer Churn Prediction & BI Platform

Repository: `Tessa-Saumu/Customer-Churn-Prediction-BI-Platform` (GitHub)
Evidence gathered: 2026-09-26, from the full GitHub history (91 commits, 21 PRs, 20 issues), the committed tree at `e6e4a0f`, and a full local re-run of the pipeline (ETL → training → API → tests) performed for this document.

---

## Context

**When:**
- Repository created **2026-07-15** (GitHub API `created_at`); first commit `0f6771b` "Initial commit" by Theresia Saumu.
- Core sprint (issues #1–#20, milestones M0–M6) closed with the final integration pass merged **2026-08-06** (PR #34).
- Stretch goals (Docker, CI, Streamlit) added **2026-08-12** (PRs #36, #37, commits `806705c`, `cebf257`); last commit `e6e4a0f` "disable workflow" (Adeyeri Michael, 2026-08-12).
- README states "**Timeline: 9-day target (mentor ceiling: 14 days)**". The observable core-sprint window (first onboarding issues 2026-07-17 → final integration merge 2026-08-06) is ~3 weeks of calendar time; the "9-day" figure is a stated target, not something the Git history lets me reconcile day-by-day.

**Why it existed:**
A team project (structured as a mentored capstone — the repo contains `Project Specification.md`, a per-component contract document, and a named mentor who signs off every PR) whose goal was to build an end-to-end analytics platform for a telecom: ingest the IBM Telco Customer Churn dataset (Cognos Analytics version, 7,043 rows), clean it into SQLite, expose SQL analysis views, train and compare 5 ML models, serve predictions via a FastAPI service, and present findings in a 5-page Power BI dashboard. Dataset source is linked in the README (Kaggle, `yeanzc/telco-customer-churn-ibm-dataset`).

**Solo / team:**
**Team project — 7 named contributors plus a mentor.** Evidence from GitHub commit/PR authorship:
- Theresia Saumu (`Tessa-Saumu`, `theresia.saumu@gmail.com`) — repo owner, Team Lead
- Mercy Mwangi (`myra0i`) — Data Engineering
- Latifah Usaini Bashir (`Lateephah`) — ML Engineering
- Praise (`EloghosaPA`, `praiseagho1@gmail.com`) — Backend/API
- Joyce Ebruphiyo Etata (`joyce-ai4health`) — BI / Power BI
- Salome / Sally Kijo (`KijoSal-dev`, `sallykijo@gmail.com`) — SQL analysis & documentation
- Adeyeri Michael (`Mikehade`) — **mentor** (all merge commits, final sign-off per `PROCESS.md`, stretch-goal work, scaffold code)
- Pamela — named "Lead Testing & QA" in `README.md`/`CONTRIBUTORS.md`, but has **zero commits** in the GitHub history. `CONTRIBUTORS.md` and `docs/qa_findings.md` (Finding 15) state the test suites were ultimately authored by Theresia after "testing responsibilities changed" / Pamela was unavailable.

**My role:**
*The repository does not identify "the user" of this document; my attribution below is evidence-based, not inferred.* The strongest available signal is that the repository is owned by `Tessa-Saumu` (Theresia Saumu), the Team Lead. **If the author of this portfolio is the repo owner (Theresia), the proven role is:**
- Team Lead & Technical Reviewer (first-pass review of all PRs per `PROCESS.md`; 26 of 91 commits authored)
- Implementation owner of **Issue #14 (real model/API integration)** — PR #27: new `app/services/kpi_service.py`, `app/services/metrics_service.py`, the `_adapt_api_fields_to_training_schema()` adapter in `predict.py`, configurable model paths (commits `cbd4994`, `c2ea20e`, `f305458`, `891bc67`, `9ffe7ab`)
- Author of **all three automated test suites** (`tests/test_etl.py`, `tests/test_api.py`, `tests/test_models.py` — PRs #29/#30/#31, commits `3fc44b9`, `4ac1e73`, `c41e36a`) and the skip-guard rewrite of `tests/test_sql_views.py` (Issue #19, commit `8a2ddd3`)
- Author/maintainer of `docs/qa_findings.md` (commits `c880505`, `5f1b689`, `43e504d` era, `5e42ed0` era) and of `PROCESS.md`, `STRUCTURE.md`, `README.md`
- Final integration pass (PR #34, commits `0e6747a`, `02556e5`) — including deleting the superseded `training/predict.py` and completing typing gaps

**Ownership boundaries that cannot be proven from the repository:** who wrote what inside shared files, whether any team member used AI tooling, how much of the mentor's scaffold code (see "What I personally built") each member actually understood vs. was given, and any verbal/contributed work (standups, reviews, presentation) that left no artifact in the repo. The presentation claimed in Issue #20 exists only as checked task boxes — no deck is in the repo.

---

## Problem

**What was actually solved (implemented and verified in this session):**
1. A 7,043-row raw CSV (33 columns) is loaded, cleaned (column normalization, duplicate removal, `total_charges` coercion, `churn_reason` fill, zip-code leading-zero protection), and loaded into a SQLite `customers` table (31 columns) with CHECK constraints — verified: `7043 rows inserted`, both SQL views created.
2. A 5-model classification pipeline (LogReg, Decision Tree, Random Forest, XGBoost, LightGBM) trains on 80/20 stratified splits, evaluates on Accuracy/Precision/Recall/ROC AUC/Confusion Matrix, selects the best model by ROC AUC, and persists it as a joblib pickle — verified by re-run (best model: Logistic Regression, ROC AUC ≈ 0.8496).
3. A FastAPI service with 5 endpoints (1 unauthenticated `/health`, 4 behind `X-API-Key`), backed by the real database and real model — verified live (all 5 endpoints responded correctly, incl. 401/422 behavior).
4. A 5-page Power BI dashboard (654 KB `.pbix`) whose rendered screenshots match the committed dataset and the committed (leakage-free) model metrics — verified by inspection of the 5 screenshots against `evaluation/model_comparison.md` and the DB.
5. A test suite of 87 tests across 4 files — verified: 87/87 pass after the full pipeline; fresh state: 22 pass / 65 skip / 0 fail.

**Aspirational README language not supported by the evidence:**
- "surfaces **actionable recommendations**" — only partially: `dashboard/business_report.md` contains 5 recommendations tied to the data, but there is no system that generates or acts on them.
- "identifies customers likely to churn" — implemented as a probability score endpoint; the model's recall is 55.6% (see ML section), which the business report itself acknowledges.
- "Deployment to cloud" (stretch goal list) — **never achieved**; the only deploy workflow is fully commented out and its 4 historical runs all failed.
- "PostgreSQL instead of SQLite" — listed as stretch goal, never started (still SQLite).
- "SHAP explainability" — listed as stretch goal, never started.
- `README.md` claims the Power BI dashboard is "connected via ODBC" — see Limitations: the `.pbix` contains an in-memory (imported) data model; the ODBC source cannot be confirmed from the file itself.

---

## What I personally built

> See "My role" above for the identity caveat. The table below is the **confirmed ownership map** from GitHub commit/PR evidence, `CONTRIBUTORS.md`, and file docstrings — usable by each member to extract their own claims.

| Component | Confirmed owner (evidence) | Notes |
|---|---|---|
| `etl/` (inspect, clean, load) | Mercy Mwangi (PR #21, commits `fd408ae`, `3d5f642`) | `clean_data.py` docstring: "total_charges handling and the customer_id rename below are Mercy's work, unchanged" |
| `sql/schema.sql`, `database/db_connection.py`, `database/init_db.py`, `database/init_views.py`, `database/models.py` | Mercy Mwangi (PR #21, commits `3d5f642`, `5dac226`) | `db_connection.py` docstring: pattern "given in full" by the mentor except one flagged decision |
| `sql/analysis_queries.sql`, `sql/views.sql`, `docs/data_dictionary.md`, `docs/sql_analysis_summary.md`, `docs/api_examples.md` | Salome (PR #23 commits `2ec4ad5`, `df2b921`, `c400b71`; PR #33; `test_sql_views.py` originally hers) | |
| `training/` (data_loader, feature_engineering, preprocessing, train_test_split, train_models, evaluate_models) | Latifah Usaini Bashir (PR #25, commits `6dc54cb`, `3e79b4d`, `6a69657`) | Her original `preprocessing.py` was missing the `churn_score` leakage exclusion — fixed in Issue #14 (Theresia, `c2ea20e`) |
| `predict.py` (core `predict()`) | Latifah (Issue #11); the Issue #14 field adapter and `MODEL_PATH` env support were added by Theresia (PR #27) | |
| `app/main.py`, `app/api/routes.py`, `app/services/mock_prediction_service.py`, `app/schemas/customer_schema.py` (original) | Praise (PR #26, commit `12df9b7`; PR #22) | `customer_schema.py` docstring: "STATUS: repaired by Theresia" (`risk_level` removed to keep the locked contract) |
| `app/api/routes.py` (real wiring), `app/services/kpi_service.py`, `app/services/metrics_service.py` | Theresia (PR #27) | `kpi_service.py` and `metrics_service.py` are explicitly "NEW FILE (flagged in PR Notes)" |
| `app/repository/customer_repository.py`, `app/services/auth_service.py` | **Mentor-provided scaffolding** | Both docstrings literally say "Given in full … rather than something that depends on judgment calls" / "standard FastAPI auth-dependency pattern" — the team's obligation was to *explain* them, not to author them. `customer_repository.py`'s pagination was added later by the mentor (commit `806705c`) |
| `tests/test_etl.py`, `tests/test_api.py`, `tests/test_models.py`, `docs/qa_findings.md` | Theresia (PRs #29/#30/#31; commits `3fc44b9`, `4ac1e73`, `c41e36a`, `c880505`) | Each file's docstring: "Owner: Theresia … authored entirely from scratch"; Pamela (planned owner) made no commits |
| `tests/test_sql_views.py` | Salome (original, Issue #9); rewritten with skip-guard + idempotency test by Theresia (Issue #19, commit `8a2ddd3`) | File docstring says so explicitly |
| `dashboard/churn_dashboard.pbix`, `dashboard/business_report.md` | Joyce Ebruphiyo Etata (PR #28, commits `9cd450a`, `c355a87`, `751af7e`) | Her PR #35 (doc augmentation) was **closed unmerged**; its content (screenshots) was committed directly to main by Theresia (`8ba0fc3`) — a deviation from the documented no-direct-push rule |
| `README.md`, `PROCESS.md`, `STRUCTURE.md` | Theresia / Salome / KijoSal-dev across commits (`496f568`, `1a22991`, `02556e5`) | |
| `Dockerfile`, `Dockerfile.streamlit`, `docker-compose.yml`, `Makefile`, `.github/workflows/deploy.yml`, `streamlit-app.py` | Adeyeri Michael, mentor (stretch goals, PRs #36/#37, commits `806705c`, `cebf257`) | |

**Unclear ownership:** the `verification scripts` (`scripts/verify_endpoints.sh/.ps1`) were authored on `feature/issue-10-fastapi-scaffold` (Praise's branch, commit `6ab8e8c`) and extended in PR #27 (Theresia, `f305458`) — both touched them; the `.ps1`'s metric updates and the `.sh`'s lack of updates are inconsistent (see Limitations).

---

## Architecture

**Frontend:**
- `dashboard/churn_dashboard.pbix` — 5-page Power BI report (Executive Overview, Customer Demographics, Churn Drivers, Revenue Impact, Model Predictions; page tabs visible in all 5 screenshots). Its data model is **in-memory (imported)** — the `.pbix` contains a 522 KB binary `DataModel` part and no `DataModelSchema` (direct-query) part; the Model Predictions page visuals reference a `model_comparison` table whose columns match `evaluation/model_comparison.csv`. The ODBC/DSN `ChurnDB` configuration the README describes could **not** be confirmed inside the file (strings absent from all parseable parts).
- `streamlit-app.py` (420 lines, added 2026-08-12 by the mentor) — a thin HTTP client over the API with 5 sidebar-navigated pages (Health, Customers, KPIs, Predict, Model Metrics). No logic of its own; `requests` is imported but not declared in `requirements.txt` (it arrives transitively via `streamlit`).

**Backend:**
- FastAPI (`app/main.py`, `app/api/routes.py`) — 5 endpoints. Layering: routes → services (`kpi_service`, `metrics_service`, `auth_service`) → repository (`CustomerRepository`) → raw `sqlite3`. Pydantic request/response schemas in `app/schemas/customer_schema.py`. No dependency-injection container, no ORM in the request path (the SQLAlchemy `Customer` model in `database/models.py` is unused by the running app — `STRUCTURE.md` admits it is "additive, not used").
- `predict.py` (repo root) is the prediction entry point: loads `models/best_model.pkl` **at import time**, adapts API field names to DB column names, runs the same `prepare_features()` as training, returns `{churn_probability, churn_prediction}`.

**Data:**
- `etl/inspect_raw_data.py` (read with `dtype={"Zip Code": str}` to preserve leading zeros) → `etl/clean_data.py` (snake_case normalization, whitespace strip, exact-duplicate removal, `total_charges` → numeric with 0-fill, `churn_reason` NaN → "Not Applicable", drop constant `count` column) → `etl/load_to_db.py` (DELETE-then-append, so re-runs are idempotent).
- Two SQL views for the dashboard: `view_churn_by_contract`, `view_churn_by_tenure_bucket` (`sql/views.sql`, created by `database/init_views.py`).

**ML/AI:**
- `training/data_loader.py` reads from SQLite (not the CSV) → `feature_engineering.py` adds 3 features → `preprocessing.py` drops ID/geo/leakage columns and builds a `ColumnTransformer` (OneHotEncoder, `handle_unknown="ignore"`, numeric passthrough) → `train_test_split.py` (80/20 stratified, `random_state=42`) → `train_models.py` (5 models, all `random_state=42`, wrapped in sklearn `Pipeline`s) → `evaluate_models.py` (metrics, best-by-ROC-AUC selection, joblib dump to `models/best_model.pkl`, writes `evaluation/model_comparison.md`).
- A superseded duplicate `training/predict.py` existed and was **deleted** in commit `0e6747a` (2026-08-02); a regression test (`TestTrainingPredictDeprecationFlag`) still guards that `app/` never imports it.

**Database:**
- SQLite, single table `customers` (31 columns), `customer_id` TEXT PK, `churn_label` NOT NULL, CHECK constraints (non-negative charges, `churn_value IN (0,1)`, `churn_score` 0–100, lat/long bounds). DB file `database/churn.db` is gitignored and generated. Connection: `database/db_connection.py::get_connection()` (raw `sqlite3`, FK pragma on).

**Infrastructure:**
- `Dockerfile` — **two-stage**: stage 1 builds the DB and trains the model inside the image (runs init_db → load_to_db → init_views → evaluate_models, then asserts the artifacts exist); stage 2 is the runtime API image (copies app/, training/, model, DB). This is a genuinely thoughtful build design (artifacts never needed on the host).
- `Dockerfile.streamlit` + `docker-compose.yml` (api + streamlit, healthcheck on `/health`, streamlit waits for healthy api) + `Makefile` (build/run/start/stop/logs/status/test).
- `.github/workflows/deploy.yml` — **entirely commented out** (the repo's final commit is literally "disable workflow"). It was an SSH-based deploy of the Docker image to a server using `secrets.SERVER_SSH_KEY/SERVER_HOST/SERVER_USER`. All 4 historical Actions runs **failed**.
- Nothing is deployed anywhere; there is no live demo URL in the repo.

---

## ML / AI work

**Problem formulation:** Binary classification — will this customer churn? Framed as telecom churn prediction on a snapshot dataset (no temporal dimension in the data; `churn_reason`/`churn_score`/`cltv` are outcome-derived columns).

**Target:** `churn_value` (0/1 integer) from the cleaned DB (`training/preprocessing.py::prepare_training_data`).

**Features:**
- **Implemented and verified:** the 20 business columns from the DB minus `customer_id`, 7 geographic columns (`country`, `state`, `city`, `zip_code`, `lat_long`, `latitude`, `longitude`), `churn_label`, and the 3 leakage columns (`churn_reason`, `churn_score`, `cltv`); plus 3 engineered features (`TenureBucket` — 4 buckets via `pd.cut`, `TotalServicesCount`, `AvgMonthlySpend`); one-hot encoding of categoricals; numeric passthrough. LightGBM's own training log in this session reports **52 used features**.
- **Critical history (verified against Git):** the *first* training run (Latifah, commit `6dc54cb`, 2026-07-22) **did not drop `churn_score`** — an IBM Cognos churn risk score derived from the churn outcome (target leakage). That run produced LightGBM Accuracy 0.9304 / ROC AUC 0.9818 (stale copy still visible at `evaluation/model_comparison.md` as of `6dc54cb`). The leak was discovered during Issue #14 integration testing because real `/predict` requests (which have no `churn_score`) failed with `ValueError: columns are missing: {'churn_score'}`; `churn_score` was added to `DROP_COLUMNS` in `c2ea20e` (2026-07-24) and the evaluation re-run. `dashboard/business_report.md` documents this correction explicitly. **The committed metrics are from the leakage-free pipeline.**

**Baseline:** *Absent.* No persistence/naive baseline is documented or implemented. (Class prior is 26.54% churn; the models' recall of ~50–56% means flagging precision is the trade, but the repo never quantifies a baseline.)

**Models:** Logistic Regression (`max_iter=1000`), Decision Tree, Random Forest, XGBoost, LightGBM — all `random_state=42`, no hyperparameter search of any kind (default parameters except `max_iter`).

**Validation methodology:**
- *Implemented and verified:* single 80/20 **stratified** train/test split, `random_state=42`, metrics on the held-out 1,409-row test set; models compared in one table; best model selected on **ROC AUC** (stated criterion in `evaluate_models.py`).
- *Absent:* no cross-validation, no time-based or out-of-time validation, no statistical significance testing, no calibration check, no per-segment analysis, no baseline comparison. The top-2 models are near-tied (0.8494 vs 0.8484 ROC AUC) and a single split cannot distinguish that gap from noise.
- *Assessment:* the methodology is **adequate for a capstone exercise but does not support strong generalization claims**. What it does support: a reproducible, leakage-controlled comparison of 5 model families on 7k rows, with a documented incident (leak detection → fix → re-evaluation) that is itself solid ML-engineering evidence.

**Metrics:** Accuracy, Precision, Recall, ROC AUC, Confusion Matrix — per model, in `evaluation/model_comparison.md` (and CSV for Power BI via `scripts/generate_model_comparison_csv.py`).

**Final result (committed, `evaluation/model_comparison.md`):**
| Model | Accuracy | Precision | Recall | ROC AUC |
|---|---|---|---|---|
| **Logistic Regression (selected)** | 0.8020 | 0.6480 | 0.5561 | **0.8494** |
| LightGBM | 0.8055 | 0.6582 | 0.5562 | 0.8484 |
| XGBoost | 0.7906 | 0.6201 | 0.5455 | 0.8282 |
| Random Forest | 0.7892 | 0.6222 | 0.5241 | 0.8335 |
| Decision Tree | 0.7317 | 0.4947 | 0.5027 | 0.6583 |

**Reproduced in this session (2026-09-26, unpinned deps, Python 3.11):** Logistic Regression Accuracy 0.7991 / ROC AUC 0.8496 (selected again); XGBoost drifted (0.7842 / 0.8319); DT/RF/LightGBM identical to committed values. So the result **reproduces approximately, not exactly** — `requirements.txt` pins nothing.

Do not call this "successful" beyond: a leakage-free, reproducible-to-within-noise 5-model comparison on a benchmark-quality dataset, with the strongest single-model ROC AUC ≈ 0.849 and a recall gap (55.6%) that the team itself documents as the model's main weakness.

---

## Engineering evidence

**Tests:**
- **87 tests in 4 files** (verified by collection and by run): `tests/test_api.py` (30: 3 "unit" /health + 27 integration over TestClient against the real DB + real model), `tests/test_etl.py` (28: 13 unit on `clean_data()` + 15 integration on real SQLite, repository, schema CHECK constraints, caplog-based logging coverage), `tests/test_models.py` (22: artifact loading, `predict()` contract/edge cases, training↔inference feature-path consistency, an AST-based deprecation guard, and 2 slow end-to-end retraining tests), `tests/test_sql_views.py` (7: view existence, data, schema, idempotency).
- Markers: `unit` / `integration` defined in `pytest.ini`. Skip-guards (`skipif` on missing DB/model/views) make a fresh clone exit 0 — **verified: 22 passed / 65 skipped / 0 failed without artifacts**; with the full pipeline: **87 passed / 0 failed in 10.1s (verified in this session)**.
- What they genuinely test: auth behavior (401s incl. empty header), real-vs-mock regression guards (e.g., "response is not the retired mock's fixed 0.42", "schema field names are snake_case, not the mock's camelCase"), Pydantic 422 validation paths, unseen-category handling end-to-end, SQL CHECK constraint enforcement, `init_db`/`init_views` idempotency, and several tests that deliberately **pin known buggy behavior** so future fixes are noticed (documented in `docs/qa_findings.md`).
- **Gaps found by this review:** no test asserts `/kpis` reflects the *full* dataset (the live `/kpis` regression below slipped through because the KPI tests only check keys and that churn+retention ≈ 100, which 100.0+0.0 trivially satisfies); the "training logs progress" tests assert on log *phrases*, not pipeline correctness; no performance/concurrency tests.
- Evidence they pass: verified this session (see above); `docs/qa_findings.md` documents two independent full runs at Issue #19 time ("87 passed / 0 failed / 0 skipped", twice).

**APIs:**
- 5 endpoints, all **verified live in this session**: `/health` → 200; `/customers` → 401 unauthenticated, 200 + real snake_case rows with `X-API-Key`, `?page=&size=` pagination (added in stretch commit `806705c`); `/kpis` → 200 (but see the bug in Limitations); `/model-metrics` → 200 with values parsed from the evaluation report; `/predict` → 200 with `{churn_probability: 0.711…, churn_prediction: true}` on a valid payload, 422 on malformed input.
- Design: API-key auth via `secrets.compare_digest` (timing-safe, with an explanatory docstring — good security hygiene at this scale); locked public contract enforced by code comments and tests; defensive shape-check on `predict()`'s return; 500s with "see server logs" detail rather than stack traces.

**CI/CD:**
- **No effective CI.** The only workflow, `.github/workflows/deploy.yml`, is 100% commented out (final commit `e6e4a0f` "disable workflow"). GitHub Actions history shows **4 runs, all failed** (the pre-disable attempts, which needed `SERVER_SSH_KEY`/`SERVER_HOST`/`SERVER_USER` secrets that evidently were never provisioned — or the SSH path failed). There is **no workflow that runs pytest or linters**, so the "CI must pass" line in `README.md` Coding Standards has no mechanical enforcement. No lint/type-check tooling is configured at all (no ruff/mypy/black config anywhere).

**Containers:**
- `Dockerfile` (two-stage: in-image ETL + training, then runtime API with a healthcheck), `Dockerfile.streamlit`, `docker-compose.yml` (2 services, `depends_on: service_healthy`), `Makefile`, `.dockerignore` (excludes `.env`, DB, model, `.pbix`). **Not verified in this session** — no Docker daemon available; treat "the images build and run" as *documented, not reproduced here*. The design is sound (build-time artifact generation with explicit `test -f` fail-fast checks).

**Architecture patterns:**
- Layered (routes → services → repository → sqlite3), Pydantic contracts, a repository pattern the spec made mandatory for all DB access, an explicit "locked interface contracts" document (`Project Specification.md` §4) with cross-owner change control, archived-but-not-deleted mock code with a stated reason, and `sys.path.insert(REPO_ROOT)` shims in 5+ files (a pragmatic, repeated hack — a real but minor code smell). Unused scaffolding left in place: root `schemas/`, `app/models/`, `utils/` (`.gitkeep` only), `database/models.py` (ORM, never used in the request path).

**Data validation:**
- Pydantic field-level validation on the request schema (`ge`/`le` constraints — verified to produce 422s); SQL CHECK constraints **verified enforced** by tests (`TestSchemaConstraints`); ETL cleaning rules are documented in-code and pinned by unit tests, including edge cases (blank `total_charges`, literal `""` churn_reason, all-duplicate input); zip-code leading-zero handling at CSV read time. Gaps: `clean_data()` raises raw `KeyError` if the `count` column is missing (Finding 1, pinned by test, never fixed); no schema-validation library (e.g., great_expectations/pandera) — validation is hand-rolled.

**Error handling:**
- Consistent `logging` (no `print()` anywhere — verified by grep); try/except → typed 500s on `/predict` and `/model-metrics` with clear detail messages; explicit file-not-found handling with actionable messages ("Run the training pipeline first"); tests confirm failures are loud rather than silent (a `None` tenure raises rather than silently mispredicting — Finding 7/8). Gap: error quality is uneven (missing field → clear `KeyError`; null tenure → obscure `TypeError` from inside `pandas.cut` — Finding 7, documented, never fixed).

**Monitoring:**
- **None.** No metrics, no APM, no alerting, no structured logs, no request-id correlation. Log output is human-readable stdlib `logging`. The Docker healthcheck is the only automated liveness mechanism.

**Security:**
- API-key auth with constant-time comparison (good); `.env` gitignored with a committed `.env.example` (placeholder key, clearly labeled); `secrets` usage is the only credential handling. Absent: TLS/HTTPS (uvicorn runs plain HTTP), rate limiting, per-key identity/auditing, request logging of authenticated caller. `requests` in the Streamlit app and the whole stack are unpinned — supply-chain exposure is unmanaged (no lockfile, no upper bounds).

---

## Scale

All figures verified against the repository:
- **7,043 customer rows** in `data/raw/telco_churn_raw.csv` (7,044 lines incl. header; 33 columns) — committed to the repo (despite being listed in `.gitignore`).
- **31 columns** in the SQLite `customers` table; 2 SQL views; 5 ad-hoc analysis queries.
- **5 ML models**, 52 features used (per LightGBM training log in this session).
- **5 API endpoints**; **87 tests** (30/28/22/7 across the 4 files).
- **28 Python files, ≈4,028 lines** (verified by `wc -l`).
- **91 commits**, **21 PRs**, **20 issues** on GitHub; 3 branches remain (`main`, `feat-stretch`, `final-integration-pass`); 2 forks.
- **5 Power BI pages**, 5 screenshots, 654 KB `.pbix` (522 KB in-memory data model).
- **No production traffic, users, or deployments** — the scale of *operation* is zero.

---

## Outcome

**What actually worked (verified in this session, 2026-09-26):**
- Full local pipeline end-to-end: ETL → 7,043 rows in SQLite → views → 5-model training → `models/best_model.pkl` + `evaluation/model_comparison.md` regenerated → FastAPI serving real data/model on all 5 endpoints → 87/87 tests passing.
- A leakage detection-and-correction cycle with a paper trail (Git commits `6dc54cb` → `c2ea20e`; `dashboard/business_report.md` note; `docs/qa_findings.md`).
- A real Power BI dashboard whose visuals, screenshots, and a business report are mutually consistent with the committed data (e.g., 1,869 churned / 7,043 = 26.54% everywhere it appears).
- A QA findings culture: 15 documented findings, each with repro steps, severity, owner, and a pinning test where applicable.

**What measurable result exists:**
- Selected model (leakage-free): **Accuracy 80.20%, Precision 64.80%, Recall 55.61%, ROC AUC 84.94%** (committed) / 84.96 (this session's re-run), on a 1,409-row held-out stratified test set.
- Business KPIs from the data: 26.54% churn rate; Month-to-month contract churn 42.71% vs 11.27% (One year) vs 2.63% (Two year) — from `view_churn_by_contract` and the dashboard.
- 87/87 tests green; 16/19 checks green on the (stale) bash verify script — see Limitations.

**Technical output vs product impact:** the technical output is real and reproducible. **There is no evidence of any real-world or product impact** — no deployment, no consumer of the API, no A/B or business outcome, no presentation deck in the repo. The business report's recommendations are plausible but were never executed or measured.

---

## Limitations

**Modelling weaknesses**
1. Single 80/20 split; no cross-validation or out-of-time validation; top-2 models within 0.001 ROC AUC — the "best model" is not statistically distinguishable from the runner-up.
2. No baseline (persistence or naive) ever quantified; recall 55.6% means ~44% of actual churners are missed — acknowledged in `business_report.md`, never improved (no tuning, no threshold work, no SHAP/interpretability despite being a stated stretch goal).
3. `TenureBucket` has an open top bin (`>72` months → silently `NaN`; Finding 6) — latent, never fixed.
4. Unpinned dependencies → metric drift between environments (measured this session: LogReg 0.801987 → 0.799148, XGBoost 0.790632 → 0.784244). No lockfile.

**Architecture weaknesses**
5. **`/kpis` regression (live bug, introduced 2026-08-12 in stretch commit `806705c`):** pagination added to `CustomerRepository.get_all()` (default `size=100`) while `kpi_service.get_kpis()` still calls it with no arguments — so `/kpis` now computes KPIs over **only the first 100 rows** of the table. Verified live: it returned `customer_count: 100, overall_churn_rate: 100.0` (the first 100 rows of this dataset are all churned). This contradicts `docs/api_examples.md` (7043 / 26.54) and both verify scripts, and no test catches it.
6. `predict.py` loads the model at import time → a missing/corrupt model file takes down the *entire* app including `/health` (Finding 4, documented, never fixed).
7. `metrics_service.py` parses a human-readable Markdown report with regex (fragile by the author's own admission; a structured JSON artifact was recommended and never produced).
8. `sys.path.insert(REPO_ROOT)` shims in ≥6 modules; unused ORM (`database/models.py`), unused root `schemas/`, `app/models/`, `utils/`; `training/README.md` is empty (0 bytes).
9. `.env.example` documents `DATABASE_PATH`, which **no code reads** (`database/db_connection.py` hardcodes `database/churn.db`).
10. `streamlit-app.py` imports `requests` without declaring it in `requirements.txt` (works only via streamlit's transitive dep); its Predict page defaults to an empty JSON blob the user must hand-write.

**Reproducibility problems**
11. No dependency pins/lockfile (drift measured); model artifact gitignored (correct practice, but means the committed `evaluation/model_comparison.md` values cannot be re-verified from the repo alone without re-training); Python 3.12 specified in README/Dockerfile but the repo contains no environment metadata (no `pyproject.toml`).
12. `training/predict.py` was deleted on 2026-08-02 (`0e6747a`) but `STRUCTURE.md` (added the same day, same PR) still describes it as present, and `tests/test_models.py`'s module docstring still at length describes the deleted file — stale documentation shipped in the same commit that removed the subject.

**Broken / dead integrations**
13. **`scripts/verify_endpoints.sh` fails 3 checks against the committed app (verified live): 16 passed / 3 failed** — the two model-metrics checks still assert the *pre-leak-fix* LightGBM numbers (~0.9304 / ~0.9818 from the 2026-07-22 run) and the `/kpis` `customer_count == 7043` check fails due to bug #5. The PowerShell twin (`verify_endpoints.ps1`) had its metric checks updated to Logistic Regression but still contains the `customer_count -eq 7043` check (will fail for the same reason; not executed here — no PowerShell in this environment) and a stale header comment still saying "LightGBM".
14. Consequently, `docs/qa_findings.md`'s Issue #19 claim that "**all 19 checks** in `scripts/verify_endpoints.ps1` passed" is **contradicted by the code as committed** (`kpi_service.py` never passed a page/size to `get_all()` in its entire history — the check could only have passed while `get_all()` had no pagination, i.e., before `806705c`; after that commit the scripts were never re-run).
15. The only CI/CD workflow is disabled (100% commented) and all 4 of its historical runs failed; there is no test-enforcing CI at all.
16. `data/raw/telco_churn_raw.csv` is **tracked in Git even though `.gitignore` lists `data/raw/*.csv`** (committed 2026-07-19 in `6f33e31` "safe to commit", re-ignored 4 minutes later in `4e3ae55` without untracking). `STRUCTURE.md` claims the file "won't appear in a fresh `git clone`" — false; it is in the clone.
17. `scripts/verify_endpoints.sh` and `.ps1` are committed without the executable bit (mode 100644) while the README tells users to run `./scripts/verify_endpoints.sh` directly — fails with "Permission denied" on a fresh clone (verified).
18. The Power BI ODBC/`ChurnDB` DSN connection described in README/`Project Specification.md` §2.5 cannot be confirmed inside the committed `.pbix` (in-memory data model; no DSN strings in any parseable part). The dashboard is evidence of *an* ODBC import workflow, not of a live connection.
19. `docs/api_examples.md`'s `/customers` example shows `senior_citizen: 0` and a `tenure` field; the real response has `senior_citizen: "Yes"/"No"` (TEXT) and `tenure_months` — the example doesn't match the actual payload.

**Process / documentation debt**
20. Direct commit to `main` (`8ba0fc3`, 2026-08-09) despite "No direct pushes to `main`. Ever." (`PROCESS.md`); PR #35 (Joyce) closed unmerged with its content committed by someone else.
21. Issue #20 boxes "final presentation" as done, but **no presentation materials exist in the repository**.
22. `README.md` claims 5 endpoints / 5 models / 7,043 rows — all accurate — but the README is 458 lines and now contains at least one stale detail ("As of Issue #14… both must exist before starting the API" is accurate, yet the *verification* scripts it points readers to fail).

---

## Current repository status

**Runs locally: YES — verified in this session (2026-09-26).** `init_db.py` → `load_to_db.py` (7,043 rows) → `init_views.py` → `training/evaluate_models.py` (5 models, artifacts produced) → `uvicorn app.main:app` with all 5 endpoints responding correctly, including auth (401), validation (422), and a real prediction (0.711 probability). No fixes were made to run it; it works as committed, given `pip install -r requirements.txt`.

**Tests pass: YES — verified.** Full pipeline state: **87 passed / 0 failed (10.1s)**. Fresh-clone state (DB + model removed): **22 passed / 65 skipped / 0 failed** (the QA doc claims 21/66/0 — same conclusion, one-test counting difference from the documented cross-file side effect). Caveat: "pass" includes tests that pin known bugs as acceptable current behavior.

**Deployment: NONE.** The only workflow is fully commented out; its 4 historical runs all failed; no cloud resources, no PaaS config, no public URL anywhere in the repo. Docker images are designed but were not built/run in this review.

**README quality: HIGH, with specific inaccuracies.** Setup/run instructions are accurate and were sufficient to reproduce the whole system. Faults: the verify scripts it references fail (13 above); `STRUCTURE.md` (the "authoritative" structure doc) contains 3 verifiable falsehoods (tracked CSV "gitignored", deleted `training/predict.py` "still present", `training/scripts/verify_pr.ps1` referenced but nonexistent); `api_examples.md` `/customers` example doesn't match reality; `DATABASE_PATH` documented but unused.

**Demo available: PARTIAL.** No recorded demo, no live demo. Five dashboard screenshots are genuine Power BI renders consistent with the committed data and metrics, and the Streamlit app + Docker compose provide a runnable (unverified-in-this-session) demo path.

---

## Evidence

**Relevant files:**
- Pipeline: `etl/inspect_raw_data.py`, `etl/clean_data.py`, `etl/load_to_db.py`, `database/init_db.py`, `database/init_views.py`, `database/db_connection.py`, `sql/schema.sql`, `sql/views.sql`, `sql/analysis_queries.sql`
- ML: `training/{data_loader,feature_engineering,preprocessing,train_test_split,train_models,evaluate_models}.py`, `predict.py`, `evaluation/model_comparison.md` (+`.csv`), `scripts/generate_model_comparison_csv.py`
- API: `app/main.py`, `app/api/routes.py`, `app/schemas/customer_schema.py`, `app/repository/customer_repository.py`, `app/services/{auth_service,kpi_service,metrics_service,mock_prediction_service}.py`
- Tests & QA: `tests/{test_api,test_etl,test_models,test_sql_views}.py`, `pytest.ini`, `docs/qa_findings.md`
- Infra: `Dockerfile`, `Dockerfile.streamlit`, `docker-compose.yml`, `Makefile`, `.dockerignore`, `.github/workflows/deploy.yml` (fully commented), `streamlit-app.py`
- Docs: `README.md`, `PROCESS.md`, `STRUCTURE.md`, `CONTRIBUTORS.md`, `Project Specification.md`, `docs/{api_examples,data_dictionary,sql_analysis_summary}.md`, `dashboard/business_report.md`
- Data/artifacts: `data/raw/telco_churn_raw.csv` (7,043 rows, tracked), `dashboard/churn_dashboard.pbix` (654 KB, in-memory model), `models/best_model.pkl` + `database/churn.db` (gitignored, regenerated in this session)

**Key commits (verified via GitHub API):**
- `6dc54cb` (2026-07-22, Latifah) — original ML pipeline; its `model_comparison.md` shows the **leakage-affected** run (LightGBM AUC 0.9818)
- `c2ea20e` (2026-07-24, Theresia) — `churn_score` added to `DROP_COLUMNS`; evaluation re-run → committed metrics (LogReg AUC 0.8494)
- `cbd4994` / `f305458` (2026-07-24, Theresia) — real data/metrics integration; verify-script enhancement
- `8a2ddd3` (2026-07-29, Theresia) — `test_sql_views.py` skip-guard + idempotency test
- `0e6747a` (2026-08-02, Theresia) — deleted `training/predict.py`, typing fixes (same PR added the now-stale `STRUCTURE.md` in `02556e5`)
- `8ba0fc3` (2026-08-09, Theresia) — direct commit to main (process deviation)
- `806705c` (2026-08-12, mentor) — pagination on `get_all()` (**introduced the /kpis regression**), Dockerfile, deploy workflow
- `cebf257` (2026-08-12, mentor) — Streamlit app, `Dockerfile.streamlit`, `docker-compose.yml`
- `e6e4a0f` (2026-08-12, mentor) — "disable workflow" (final commit)

**PRs:** #21 (ETL, Mercy), #22/#26 (FastAPI scaffold, Praise), #23 (SQL analysis, Salome), #25 (ML training, Latifah), #27 (real integration, Theresia), #28 (Power BI, Joyce), #29/#30/#31 (test suites, Theresia), #32 (regression pass, Theresia), #33 (docs, Salome), #34 (final integration, Theresia), #35 (Joyce — **closed unmerged**), #36/#37 (stretch goals, mentor). Merged: 19; closed-unmerged: #24 (revert), #35.

**Issues:** #1–#7 (per-member onboarding), #8 (ETL/DB), #9 (SQL/docs), #10 (API scaffold), #11 (ML), #12 (Power BI), #13/#16/#17 (test suites), #14 (real integration), #15 (stretch goals — Michael), #18 (docs), #19 (regression pass), #20 (final integration). All 20 closed. Issue #20 contains the (unverifiable) "presentation done" checkboxes.

**Screenshots:** `dashboard/screenshots/{executive_overview,customer_demographics,churn_drivers,revenue_impact,model_predictions}.jpg` — all five inspected; all consistent with the committed dataset (7,043 / 1,869 / 26.54%) and the committed leakage-free model metrics (LogReg 80.20% / 84.94%, confusion matrix 922/113/166/208 on the Model Predictions page).

**Demo:** none recorded or hosted.

**Presentation:** none in the repository (claimed complete only in Issue #20 task boxes).

---

## Candidate CV bullets

*(left blank per instructions)*

---

## Work required

**Critical** *(things that currently make the repository a poor or misleading piece of professional evidence)*
1. **Fix the `/kpis` regression** (`app/services/kpi_service.py` → pass explicit full-table parameters, or better, compute KPIs from a dedicated SQL view as the file's own docstring recommends), and **add a test** asserting `/kpis.customer_count` equals the actual `customers` row count. Until then, a reviewer running the app sees a 100% churn rate and a 100-customer count.
2. **Reconcile the verification story:** update `scripts/verify_endpoints.sh` (stale pre-leak-fix LightGBM metric ranges) and `verify_endpoints.ps1` (stale `customer_count -eq 7043` comment/header), re-run both against a live app, and correct or re-baseline the "all 19 checks passed" claim in `docs/qa_findings.md` so the QA record matches the code.
3. **Pin the environment** (`requirements.txt` → exact versions, or a lockfile, plus a Python version pin) so the committed metrics are actually reproducible; document the drift otherwise.
4. **Restore *some* CI** (a minimal GitHub Actions workflow running pytest against a pre-built DB+model, or document why there is none) — currently a "CI must pass" standard with zero enforcement, and the one workflow that exists is disabled after 4 failed runs.

**High value** *(materially strengthens the engineering evidence)*
5. Replace the regex-over-Markdown metrics path with a structured `evaluation/model_comparison.json` (the author of `metrics_service.py` recommended exactly this and it was never done).
6. Lazy-load the model (startup event or first-call load) so `/health` and app import survive a missing artifact (Finding 4).
7. Improve validation rigor for the ML story: add k-fold CV (or at least a second seeded split) and a documented baseline; consider a quick hyperparameter search — the current single-split, default-parameters comparison is the weakest link in an otherwise credible ML section.
8. Fix the tenure-bin open top edge (Finding 6) and add input validation in `predict()` for `None` fields (Finding 7) — both are one-line-class fixes with existing pinned tests to flip.
9. Fix the doc drift: `STRUCTURE.md` (three verified falsehoods), `docs/api_examples.md` `/customers` example, remove or use `DATABASE_PATH`, fill or delete the empty `training/README.md`, and update the `test_models.py` docstring to reflect the deleted `training/predict.py`.

**Optional** *(useful polish)*
10. Migrate deprecated `Field(example=…)` kwargs to `json_schema_extra` (Finding 10) and the pandas 3.x `select_dtypes` selector (Finding 11).
11. Make `scripts/*.sh/.ps1` executable (mode 100755) or document `bash scripts/…` invocation; declare `requests` in `requirements.txt` for the Streamlit app.
12. Resolve `.gitignore` vs. tracked-CSV contradiction (either untrack the CSV or remove the ignore lines, and say which in one sentence of docs).
13. Add a short "Deployment" note stating the real status (Docker-ready, not deployed) instead of leaving a disabled, failed-history workflow in the tree.
14. If the presentation deck exists anywhere, add it (or a link) to the repo; the Issue #20 checkboxes currently assert work that leaves no artifact.

---

## Professional Evidence Assessment

**1. What engineering capability does this project prove best?**
*Coordinated multi-component delivery and integration, with unusually strong testing/QA discipline.* The strongest verifiable engineering evidence is (a) the 87-test suite with skip-guards, regression guards against the retired mocks, pinned known-bug tests, and a 15-finding QA log with repro steps and owner assignments — this is above what most student/team capstones show; and (b) the Issue #14 integration work: discovering a cross-component field-name mismatch (API schema vs DB schema) via a *live* 500, and resolving it with a boundary adapter without breaking a locked public contract. Weaker evidence: the Dockerfile design (two-stage in-image training) is sound but unverified here; there is no CI, no monitoring, no deployment, and the final stretch commit shipped a live regression that the own test suite failed to catch.

**2. What ML/AI capability does it prove best?**
*Leakage awareness and end-to-end reproducibility, not modelling depth.* The best ML evidence is the documented detect→fix→re-evaluate cycle on `churn_score` (commits `6dc54cb` → `c2ea20e`, explicit note in `business_report.md`) — finding that a "feature" is the target in disguise, fixing it, and honestly reporting the drop from AUC 0.98 to 0.85. Equally valuable: the identical preprocessing path for training and inference, proven by tests. What it does *not* prove: hyperparameter tuning, cross-validated or temporally honest evaluation, statistical model selection, calibration, or interpretability. A reviewer should expect to be asked "why no CV?" and the honest answer is "there was no time/scope for it."

**3. What is the strongest verifiable achievement?**
The **full, reproducible end-to-end pipeline** — raw CSV → cleaned SQLite → 5-model comparison (leakage-free) → FastAPI serving the real model → Power BI report consistent with the same data — all of which I re-executed from a clean state in one session with zero modifications (87/87 tests, all endpoints live), *plus* the leakage-correction paper trail. No single file is impressive in isolation; the chain is the achievement.

**4. What is the biggest credibility weakness?**
**The gap between the QA record and the shipped state.** The repo's own final-quality story ("all 19 endpoint checks passed", "87 tests green", "final regression pass done") is contradicted by the code as committed: `/kpis` computes over 100 rows and returns a 100% churn rate; `verify_endpoints.sh` fails 3 checks; the only CI is disabled after 4 failed runs; and the "authoritative" structure doc contains three verifiable falsehoods. The regression landed in the *last* commits (mentor's stretch work), after the regression pass — so the final state is strictly worse than the documented one. A careful reviewer who runs the app for two minutes will find the `/kpis` bug, and it will retroactively undermine the QA claims.

**5. Is there enough here to justify investing additional time in this project?**
*Yes — a bounded amount.* The Critical list above is small (one functional bug + one test, two script/doc reconciliations, dependency pinning, one CI workflow) and each fix converts a credibility liability into a positive signal ("post-sprint maintenance, regression caught and fixed, CI restored"). That narrative — *found a live regression in my own project after the fact, fixed it, and enforced it with a test and CI* — is more valuable to an Applied AI/ML portfolio than any amount of new features. I would not invest in new scope (SHAP, PostgreSQL, cloud deployment) for a portfolio piece at this stage; I would invest only in closing the Critical + a couple of High-value items.

**6. What type of professional role would this project support as evidence?**
*Applied Data Scientist / ML Engineer (early-career) or Data Engineer–adjacent roles* — with honest framing: it demonstrates the full lifecycle (ETL, data-quality, model comparison, API packaging, BI reporting, testing, team process) at a *benchmark-scale, no-production* level. It does **not** currently support claims of production ML engineering (no deployment, no MLOps, no monitoring, no CI enforcement, no statistical validation) or of senior individual-architecture ownership (it was a mentored team project; several core files were mentor-provided scaffolding). For "ML Engineer" titles specifically, pair it with a statement of the validation limits (single split, default hyperparameters) — the leakage story is an asset *only if* the limitations are stated.

**7. What claims should I NOT make publicly based on the current repository?**
- Don't claim "deployed" / "production" / "cloud-hosted" — the only deploy workflow is disabled and has never succeeded.
- Don't cite the 93% accuracy / 98.18 AUC numbers anywhere — those are the *leakage-affected* run; the committed, defensible numbers are 80.2% / 84.94% (and the repo itself says so).
- Don't claim "9 days" as delivered duration without context — the repo's observable window is ~4 weeks including stretch work.
- Don't claim "CI on all PRs" or "all checks pass in CI" — there is no functioning CI.
- Don't claim the `/kpis` endpoint returns dataset-level KPIs, or that `docs/api_examples.md`'s KPI values are what the endpoint returns (it currently returns first-100-rows values).
- Don't claim sole ownership of any component — this was a 7-person + mentor project; the repo's own `CONTRIBUTORS.md` and file docstrings attribute ownership explicitly, and several load-bearing files (repository layer, auth) were mentor-provided.
- Don't claim the Power BI dashboard is "live-connected to ODBC" as a permanent direct-query setup — the committed file is an in-memory (imported) model; the ODBC workflow is documented but not confirmable from the artifact.
- Don't claim "all tests pass on a fresh clone" in the sense of *executing* 87 tests — on a fresh clone 65 of 87 skip by design (that is documented behavior, but "87 tests green" is only true after the pipeline runs).
