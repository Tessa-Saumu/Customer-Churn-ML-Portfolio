# Flagship Implementation Plan — Customer Churn Prediction & BI Platform

**Source of scope:** [`FLAGSHIP_GAP_AUDIT.md`](FLAGSHIP_GAP_AUDIT.md)
**Plan type:** minimum consolidation needed for the audit's Flagship Definition of Done
**Implementation status:** **Phase 1 complete (2026-10-05). Phases 2–5 not started.** See [Phase 1 implementation record](#phase-1-implementation-record) below.

## Scope and guardrails

This plan uses five phases. Each planned change maps to an audit backlog item:

| Phase | Audit gaps addressed |
|---|---|
| 1. KPI correctness and acceptance checks | FGA-01, FGA-02 |
| 2. Reproduction and input provenance | FGA-03, FGA-07; configuration cleanup only from FGA-10 |
| 3. Evaluation and analytics consistency | FGA-05, FGA-06 |
| 4. Minimal CI | FGA-04 |
| 5. Professional packaging and final verification | FGA-08; final verification of all required items |

FGA-09 (replacing the working Markdown metrics parser with a structured artifact) and the remaining FGA-10 hardening are P2 items and are **not required** for this plan's finish line. Do not expand the work to include them unless the project later makes a claim that depends on them.

**Pagination is preserved.** `/customers` remains paginated by default. `/kpis` will use a bounded database aggregate, not an unbounded customer-list request. The original pagination work remains attributed to the mentor; a later KPI aggregate fix is separate maintenance work.

**Metric preservation rule.** Before changing any training or evaluation output, preserve the current committed `evaluation/model_comparison.md` and `.csv` exactly as the legacy single-split result, with its source revision and protocol labelled. Do not replace those values silently. The new protocol's output is reported separately and becomes current only after it passes the acceptance checks below. The old 0.8494 ROC AUC is not an untouched final estimate and must not be compared as if it came from the new protocol.

---

## Phase 1 — Correct the KPI boundary and restore trustworthy API checks

**Audit mapping:** FGA-01, FGA-02
**Objective:** Make population KPIs correct without weakening customer pagination, then ensure the API verification path describes the current implementation.

### Files/components affected

- `app/services/kpi_service.py`
- `app/repository/customer_repository.py` and, only if needed, `sql/` for a single-row aggregate query
- `tests/test_api.py` and/or a focused repository/service test
- `scripts/verify_endpoints.sh`, `scripts/verify_endpoints.ps1`
- `docs/qa_findings.md` (historical status wording only; final run counts are updated in Phase 5)

### Exact changes

1. Add a dedicated aggregate operation at the existing repository/service boundary. Calculate customer count, churn count/rate, retention, average monthly charges, and total monthly charges in SQLite (using `COALESCE` or equivalent where needed to preserve current null semantics). Keep the `/kpis` response keys, rounding, authentication, and `/customers` default page size unchanged.
2. Add a regression test with more than 100 deliberately mixed rows. It must prove that `/customers` still returns only the requested page while `/kpis` matches the full table's independently computed SQL totals. Include an empty-table case if the current service contract supports it.
3. Update the Bash and PowerShell smoke scripts to test the live contract and current KPI semantics. Remove hard-coded leakage-era LightGBM values. Assert response keys, numeric ranges and the relevant page/aggregate behavior; don't pin the new model result to stale constants. Make a missing required check tool fail clearly rather than report a misleading all-green run.
4. Reword the old Issue #19 “all checks passed/no blockers” language as a dated historical result and note that a later pagination change exposed an aggregate-path regression. Do not state final pass/skip counts until the clean run in Phase 4.

### Tests/checks

- Run the new isolated aggregate test against a temporary SQLite database with more than 100 rows.
- Run API tests for `/kpis`, `/customers` pagination, API-key rejection, malformed `/predict` input and `/model-metrics` response shape.
- Run the Bash smoke script against the local API. Run the PowerShell script on a PowerShell-capable environment; if unavailable, record that rather than claiming it was executed.
- Verify that the current full-dataset KPI result agrees with direct SQL for the committed dataset. The expected customer count and churn rate are 7,043 and 26.54%; derive the remaining values from the query rather than copying example values blindly.

### Expected output

`/customers` remains bounded and paginated. `/kpis` returns a single correct full-population summary without materializing all customer records. The current API checks no longer expect the pre-leakage model metrics, and the QA document no longer presents an old run as current acceptance evidence.

### Acceptance criteria

- A test that would fail if the service reads only the first 100 rows passes.
- The default `/customers` request still returns no more than 100 rows, and explicit page/size requests retain existing behavior.
- Both maintained smoke scripts assert the same API semantics and exit nonzero on a failed assertion.
- The public API response shapes and auth behavior do not change.

### Rollback/risk considerations

The mentor's pagination implementation is intentional; do not revert it or change its default to “all rows.” If aggregate rounding/null handling differs, compare it with a direct whole-table reference query and adjust the aggregate, not the API contract. Keep the legacy model metrics untouched in this phase.

---

## Phase 1 implementation record

**Completed:** 2026-10-05. **Status: all four Phase 1 acceptance criteria met** (evidence below). Phases 2–5 were not started.

### Pre-implementation verification

The plan was checked against the tree before any edit. All assumptions held:

| Plan assumption | Verified in tree | Result |
|---|---|---|
| `kpi_service.get_kpis()` calls `repo.get_all()` with no arguments | `app/services/kpi_service.py:49` | Confirmed — reproduced live: `/kpis` returned `customer_count: 100`, `overall_churn_rate: 100.0` (the first 100 rows of the tracked dataset are all churned) |
| `CustomerRepository.get_all(page=0, size=100)` is paginated | `app/repository/customer_repository.py` | Confirmed |
| `scripts/verify_endpoints.sh` carries pre-leakage LightGBM assertions and an incompatible `/kpis` count check | `scripts/verify_endpoints.sh` | Confirmed — executed against a live API: **16 passed / 3 failed** (stale `~0.9304` accuracy, stale `~0.9818` ROC AUC, and `customer_count == 7043`) |
| `scripts/verify_endpoints.ps1` carries the same shape of staleness plus a stale “LightGBM” header comment | `scripts/verify_endpoints.ps1` | Confirmed by inspection |
| `docs/qa_findings.md` presents the Issue #19 run as current acceptance evidence | `docs/qa_findings.md` | Confirmed |
| No test asserts `/kpis` reflects the full dataset | `tests/test_api.py` | Confirmed — the KPI tests only asserted keys and `churn + retention ≈ 100`, which `100.0 + 0.0` satisfies |
| Baseline suite is green with artifacts present | `pytest` | Confirmed — **87 passed / 0 failed** before any change |

**One assumption needed qualifying.** The plan's Phase 1 test section says to verify the full-dataset KPI result “agrees with direct SQL … the expected customer count and churn rate are 7,043 and 26.54%.” Those values are correct for the tracked dataset, but `evaluation/model_comparison.md` is regenerated on every pipeline/test run, and in this sandbox's unpinned environment the rerun drifts (see “Environment findings” below). The KPI values themselves did **not** drift — they are properties of the data, not of a package version.

### Files changed

| File | Change |
|---|---|
| `app/repository/customer_repository.py` | **Added `get_kpi_aggregate()`** — one whole-table SQL aggregate returning `customer_count`, `churned_count`, `total_monthly_charges`, `average_monthly_charges`. No existing method, signature or behaviour was modified. |
| `app/services/kpi_service.py` | `get_kpis()` now reads the aggregate instead of `repo.get_all()`. Response keys, types, two-decimal rounding, empty-table behaviour and null semantics are unchanged; only the source of the numbers changed. Module docstring records the regression and the fix. |
| `tests/test_kpi_aggregate.py` | **New file, 12 tests.** Whole-table regression coverage on a purpose-built temporary SQLite database with 150 mixed rows (first 100 all churned, mirroring the real failure signature), plus pagination-preservation, empty-table and NULL-charge tests. Runs without `database/churn.db` or `models/best_model.pkl`. |
| `tests/test_api.py` | Added 4 integration tests to `TestKpisEndpoint`: `/kpis` count, churn/retention rate and charge totals must equal independently computed whole-table SQL, and the KPI population must not be bounded by the `/customers` page. |
| `scripts/verify_endpoints.sh` | Rewritten against the current contract: 29 checks, `curl`/`jq`/`API_KEY` now hard preflight requirements (exit 2), pre-leakage and Issue #10 placeholder values excluded rather than pinned, pagination and whole-population KPI semantics asserted, `EXPECTED_CUSTOMER_COUNT` (default 7043) configurable, API/report consistency check added, temp file via `mktemp`. **Mode changed 100644 → 100755** (see Deviations). |
| `scripts/verify_endpoints.ps1` | Mirrors the Bash script's 29 checks and exit codes. Also fixes a latent bug: `Check-Endpoint` hardcoded `$status = 200` on the success path, so any 2xx was reported as the expected 200. |
| `docs/qa_findings.md` | Issue #19 section is now explicitly labelled a dated historical record (2026-07-29) with a note that commit `806705c` (2026-08-12) later introduced the aggregate regression; the “all 19 checks passed” and “No blocking issues remain” statements are qualified; Finding 16 added to the summary table. Final pass/skip counts deliberately **not** restated. |
| `README.md` | The “Known KPI regression” limitation bullet now records the repair; the verify-script paragraph no longer describes the scripts as expected-to-fail and documents their exit codes and optional settings. Minimal, surgical edits only — the Phase 5 restructure is untouched. |

### Test results

Run with Python 3.11.2 in a fresh virtualenv from `requirements.txt` (pandas 3.0.6, scikit-learn 1.9.1, fastapi 0.142.2, pydantic 2.13.5, pytest 9.1.1 — unpinned, see below).

| Run | Result |
|---|---|
| Full suite, artifacts present (baseline, before changes) | **87 passed / 0 failed** |
| Full suite, artifacts present (after changes) | **103 passed / 0 failed** (87 + 12 new KPI-aggregate + 4 new API KPI guards) |
| Per file after changes | `test_api.py` 34, `test_etl.py` 28, `test_kpi_aggregate.py` 12, `test_models.py` 22, `test_sql_views.py` 7 |
| Markers | `-m unit` → 33 passed; `-m integration` → 70 passed |
| Full suite, fresh state (DB + model removed) | 34 passed / 69 skipped / **0 failed**. The 12 new KPI-aggregate tests run and pass in this state, which is the point: the regression is catchable on a fresh clone. Fresh-state counts are **not** being published as final; a clean artifact-present run belongs to Phase 4. |
| `ruff check` (ad-hoc, not added to the repo) | No new findings in `tests/test_kpi_aggregate.py`, `app/services/kpi_service.py`. The 36 findings in the touched files are pre-existing style (`UP037` quoted `"TestClient"` annotations, which are the deliberate `TYPE_CHECKING` pattern documented in QA Finding 15) and repo-wide patterns (64 findings across the tree). Not fixed — out of Phase 1 scope. |
| `python -m compileall` | Clean |

**Regression proof.** The new tests were run against the *pre-fix* implementation to confirm they actually catch the bug. Result: `tests/test_kpi_aggregate.py` → **3 failed** (`test_kpis_match_independent_whole_table_sql_totals`, `test_kpis_are_not_scoped_to_the_default_page`, `test_get_kpis_never_calls_get_all`); `tests/test_api.py -k Kpis` → **3 failed** (count, churn-rate and totals vs. whole-table SQL). Both files pass with the fix in place.

### End-to-end workflow run

Full clean rebuild of the affected path, from a deleted `database/churn.db`, `models/best_model.pkl` and `evaluation/model_comparison.md`:

```
python database/init_db.py      → Database initialized from sql/schema.sql
python etl/load_to_db.py        → Rows inserted: 7043
python database/init_views.py   → Views initialized from sql/views.sql
python training/evaluate_models.py → Best model: Logistic Regression, saved
uvicorn app.main:app            → all 5 endpoints live
```

Live endpoint results after the rebuild:

| Endpoint | Result |
|---|---|
| `GET /health` | `{"status":"ok"}` (no auth) |
| `GET /customers` (default) | 100 rows — **pagination unchanged** |
| `GET /customers?page=1&size=5` | 5 rows |
| `GET /kpis` | `{"customer_count":7043,"overall_churn_rate":26.54,"retention_rate":73.46,"average_monthly_charges":64.76,"total_monthly_revenue":456116.6}` — **matches direct SQL exactly** and matches `docs/api_examples.md` |
| `GET /model-metrics` | 200, four locked keys |
| `POST /predict` | 200 on a valid payload; 422 on malformed input |
| auth | 401 on all four protected endpoints without a key |

`./scripts/verify_endpoints.sh` against that live API: **29 passed / 0 failed / 0 skipped, exit 0**.

Failure paths were exercised explicitly:

| Scenario | Result |
|---|---|
| `EXPECTED_CUSTOMER_COUNT=999` | 1 FAIL, **exit 1** |
| `API_KEY` unset | clear message, **exit 2** |
| `EXPECTED_CUSTOMER_COUNT=abc` | clear message, **exit 2** |
| `jq` not on `PATH` | clear message, **exit 2** (previously: silent SKIP and a misleading green run) |

**Not executed:** `scripts/verify_endpoints.ps1`. No PowerShell runtime exists in this environment (`pwsh`/`powershell` absent). The script was written to mirror the Bash checks one-for-one and was syntax-checked for balanced blocks, but it has **not** been run and is not claimed as executed. It needs a Windows/PowerShell machine before Phase 4 can treat it as verified.

### Deviations from plan

1. **`README.md` was edited (not in Phase 1's listed files).** The Phase 1 file list covers code, tests, scripts and `docs/qa_findings.md`. Leaving the README's “Known KPI regression … `/kpis` therefore summarizes the first 100 rows” bullet and its “the endpoint scripts … are not expected to pass as acceptance checks” paragraph in place would have created a *new* contradiction between the docs and the fixed code. Only those two passages were changed; the Phase 5 restructure was not started.
2. **`scripts/verify_endpoints.sh` mode changed 100644 → 100755.** The README documents `./scripts/verify_endpoints.sh`, and the file was committed without the executable bit (a “Permission denied” on a fresh clone). The bit is required for the Phase 1 acceptance criterion that the script be runnable and fail nonzero. No `.ps1` equivalent exists (PowerShell does not use the exec bit).
3. **The `/kpis` aggregate lives in the repository, not in a new SQL view.** `kpi_service.py`'s own docstring recommends a `view_executive_kpis` view. A new view in `sql/views.sql` (Salome's Issue #9 deliverable) would also require a database rebuild for existing checkouts and would add a `test_sql_views.py` surface. The aggregate already sits at the repository boundary the service depends on, which is the smallest change that makes the endpoint correct. Recorded here rather than deferred silently.
4. **The smoke scripts no longer pin exact `/model-metrics` values.** The plan said to remove the leakage-era constants and not “pin the new model result to stale constants,” so both scripts assert keys, `[0,1]` ranges, and the *absence* of the two known-invalid result sets (Issue #10's `{0.89, 0.86, 0.81, 0.91}` and the pre-leakage LightGBM `~0.9304` / `~0.9818`). One new check compares the endpoint against `evaluation/model_comparison.md` instead of a literal, so the scripts stay valid under dependency drift.
5. **`EXPECTED_CUSTOMER_COUNT` is configurable with a default of 7043.** The original script hardcoded `7043`. The default keeps the original intent for the tracked dataset; the override (or `0` to skip) makes the script usable against any database instead of failing for an unrelated reason.
6. **`scripts/verify_endpoints.ps1` no longer defaults `API_KEY` to `local-dev-key-123`.** It now requires the variable, matching the Bash script. This is a script behaviour change made so that both maintained scripts assert the same semantics.
7. **`Check-Endpoint` in the `.ps1` no longer hardcodes `$status = 200`.** Any 2xx was previously reported as the expected 200, so the script could not actually assert a status code. Needed for “exit nonzero on a failed assertion” to mean anything.

### Newly discovered problems (backlog — not fixed in Phase 1)

These were found while implementing Phase 1. None blocks this phase, so none was fixed.

| ID | Problem | Where | Suggested phase |
|---|---|---|---|
| NEW-01 | **Unpinned dependencies move the metrics.** A clean rerun in this environment produced Logistic Regression accuracy 0.7991 / ROC AUC 0.8496 (vs. the committed 0.801987 / 0.849448) and XGBoost 0.784244 / 0.831920 (vs. 0.790632 / 0.828214). Decision Tree, Random Forest and LightGBM were identical. This is the drift the audit already records; it is now re-measured here. Environment: Python 3.11.2, pandas 3.0.6, numpy 2.4.6, scikit-learn 1.9.1, xgboost 3.2.0, lightgbm 4.7.0 — while `README.md` documents Python 3.12. | `requirements.txt`, `README.md` | **Phase 2** (FGA-03) |
| NEW-02 | **`evaluation/model_comparison.md` is rewritten by the test suite.** `tests/test_models.py`'s end-to-end retraining tests call `evaluate_all_models()`, which overwrites the tracked report. So `pytest` alone changes a tracked metrics file. The committed file was restored after every run in this phase; a reviewer running `pytest` will see the same drift appear. | `tests/test_models.py`, `training/evaluate_models.py` | **Phase 2** — needs a decision (pin deps, or write retraining output to a temp path) |
| NEW-03 | **The served model can disagree with the report it is judged by.** `/model-metrics` parses `evaluation/model_comparison.md`, while `/predict` serves `models/best_model.pkl`. After a drifted retrain the pickle scores 0.7991 while the report can still say 0.8020. Nothing asserts the two agree. | `app/services/metrics_service.py` | **Phase 2/3**; also relevant to FGA-09 |
| NEW-04 | **`docs/api_examples.md`'s `/customers` example is still wrong** (`senior_citizen: 0` and `tenure` — the real response has `"Yes"/"No"` TEXT and `tenure_months`). Pre-existing, documented in the evidence; not touched here. | `docs/api_examples.md` | **Phase 5** (FGA-08) |
| NEW-05 | **`docs/api_examples.md`'s `/model-metrics` example values are stale** (`0.84 / 0.79 / 0.73 / 0.88`), and its `/kpis` example happens to match the now-correct output. Both need regenerating against real output. | `docs/api_examples.md` | **Phase 5** |
| NEW-06 | **`scripts/verify_endpoints.ps1` has never been executed in this environment.** No PowerShell runtime is available. It is written but unverified. | `scripts/verify_endpoints.ps1` | **Phase 4** |
| NEW-07 | `pytest.ini` ends without a trailing newline after `ignore::UserWarning`, so the last filter line and the next file's content are adjacent. Cosmetic, no behavioural effect. | `pytest.ini` | Optional |
| NEW-08 | `B905` (`zip()` without `strict=`) in `_row_to_dict` and 64 other advisory `ruff` findings across the tree. No linter is configured for this repo, so nothing enforces or surfaces them. | repo-wide | Optional; not Phase 1 |

### Environment findings (recorded, not acted on)

- Python 3.11.2 was the only interpreter available; `README.md` documents Python 3.12. Phase 2 must pick one and state it.
- `requirements.txt` pins nothing. A fresh `pip install -r requirements.txt` resolved to the versions listed under NEW-01.
- No `.env` file exists in the checkout; `predict.py`'s `load_dotenv()` is a no-op, which is fine for the runs above.
- All numbers above were produced in this sandbox. Nothing here should be read as a claim about the original team repository.


---

## Phase 2 — Freeze the reproducible input and runtime

**Audit mapping:** FGA-03, FGA-07; configuration cleanup from FGA-10 only where needed for an accurate setup path.
**Objective:** Establish one truthful, clean local reproduction path before changing the model protocol or declaring new metrics.

### Files/components affected

- `requirements.txt` and a small lock/constraints file if required by the chosen pip workflow
- A Python-version marker such as `.python-version`, if useful for the selected runtime
- `.env.example`, `.gitignore`, and a short data-provenance note in `README.md` or `docs/`
- `README.md` run instructions
- Existing generated-result files under `evaluation/` (preserved before any rerun)

### Exact changes

1. Confirm the source, version and redistribution terms for `data/raw/telco_churn_raw.csv`; record its SHA-256. If redistribution is permitted, keep the file tracked and remove the contradictory ignore/documentation claims. If it is not permitted or cannot be established, stop publishing the file, document the permitted download/setup path and checksum, and use a permitted fixture for automated tests. Do not rely on credentials or a private URL.
2. Choose one supported Python version by running the current pipeline in a clean environment. Prefer the currently documented Python 3.12 if it works; if it does not, choose one tested version and update documentation consistently. Pin the installed Python dependencies using the existing `pip` workflow; do not introduce Poetry, `uv`, or another packaging framework for this task.
3. Remove unused `DATABASE_PATH`, `API_HOST`, and `API_PORT` entries from `.env.example` rather than adding new configuration plumbing solely to make placeholders appear supported. For `MODEL_METRICS_PATH`, either load `.env` before the metrics service reads environment variables or remove the setting from the example until it works as documented. If Streamlit is kept in the documented setup path, declare `requests` directly; otherwise label that path optional/unverified rather than adding a dependency for an unadvertised feature.
4. Before running training, copy the current Markdown and CSV comparison byte-for-byte to clearly named legacy single-split artifacts and record their source revision. The tracked model pickle is absent by design; do not claim that the historical fitted binary was preserved.
5. Run the existing pipeline in a clean environment and record Python/package versions, input hash and seed with the reproduction result. If the pinned rerun differs from the committed values, retain both records and explain the difference; do not overwrite the legacy result without a labelled replacement.

### Tests/checks

- Create a fresh virtual environment using only the documented commands and install only the pinned dependency set.
- Run ETL, schema/view creation, current training/evaluation, API startup and the full test suite from a clean artifact state.
- Confirm generated database/model files remain ignored and secrets remain outside Git.
- Check that the recorded data checksum matches the actual input file, if redistribution is allowed.

### Expected output

A clean, documented environment and input policy that a reviewer can use to reproduce the pipeline. Existing reported metrics remain available as explicitly historical evidence; a pinned reproduction has its own traceable result and provenance.

### Acceptance criteria

- One supported Python/dependency combination is stated and installed from the committed manifest/lock.
- The input file is either legally/appropriately tracked with a source/version/hash, or obtained through documented permitted steps with a checksum check.
- The complete local path works from a clean checkout without undocumented model/database files.
- No unused environment variable is presented as a live setting, and no secret is committed.

### Rollback/risk considerations

Package pins can alter numerical output, especially for XGBoost/LightGBM. That is a provenance finding, not permission to change old values silently. Preserve the archived result and label the pinned rerun. If dataset redistribution is uncertain, prefer removing the raw file from the public copy and documenting acquisition over assuming permission; this may mean CI uses a separate permitted fixture in Phase 4.

---

## Phase 3 — Add a fair baseline and align comparable analytics

**Audit mapping:** FGA-05, FGA-06
**Objective:** Improve the validity and interpretability of the ML result with one bounded protocol; align or explicitly distinguish the tenure segment definitions used in reporting.

### Files/components affected

- `training/train_test_split.py`, `training/train_models.py`, `training/evaluate_models.py`
- `training/preprocessing.py` only if required to ensure every transformer is fit inside each training fold
- `tests/test_models.py` and SQL/view tests in `tests/test_sql_views.py`
- `evaluation/model_comparison.md`, `evaluation/model_comparison.csv`, and legacy copies created in Phase 2
- `sql/analysis_queries.sql`, `sql/views.sql`, `docs/data_dictionary.md`, `docs/sql_analysis_summary.md`
- `dashboard/churn_dashboard.pbix` or its captures only if the actual displayed grouping/results need updating

### Exact changes

1. Retain the existing five candidate models and the current Logistic Regression as the **incumbent**. Add a simple `DummyClassifier` majority/prior baseline. Do not add model families, threshold tuning or a hyperparameter search.
2. Use a fixed stratified outer 80/20 split (seed recorded). Use only the 80% training portion for model selection—for example, five-fold `StratifiedKFold` with a fixed seed and ROC AUC as the existing selection criterion. Fit preprocessing separately inside each fold through the existing model pipeline. Select the winner by mean training-side CV ROC AUC, refit on the full outer training portion, then evaluate the selected model and DummyClassifier once on the untouched outer test portion. Report fold variation and final confusion matrix/metrics. Keep the final test out of model selection.
3. Compare the incumbent Logistic Regression against every candidate within the same inner folds, so any model change is measured against the current choice under one protocol. Freeze the CV-selected winner before examining the outer test; evaluate that winner and the DummyClassifier on the untouched test set. If Logistic Regression is the selected winner, it receives the final test evaluation as the winner. Do not use outer-test results to switch models or tune. Preserve the old 0.8494 report as a historical single-split result; do not claim its value is directly comparable to the new final estimate. If the new protocol selects a different model or yields lower metrics, report that outcome rather than tuning until it looks better.
4. Generate the new current model/report only after the protocol and comparison are fixed. Include target, exclusions (`churn_score`, `churn_reason`, `cltv`, and other dropped identifiers/geography), engineered features, split/CV seeds, data hash, package versions, baseline, selection criterion, results and limits. Regenerate the CSV from the same run.
5. For tenure buckets, first check which definitions the PBIX and screenshots actually use. If the difference between the four-range analysis/features and the three-range SQL view is accidental, align the query/view/docs and test the boundaries. If it is intentional, name both definitions and keep their reported values separate. Do not change the trained feature definition or refresh a dashboard visual without recording the reason and updated output.

### Tests/checks

- Assert train/validation/test row separation and that the outer test is not passed to the model-selection code.
- Verify each preprocessor is fit only on its corresponding training fold; no category/target information from held-out rows is learned.
- Re-run the full pipeline twice under the Phase 2 environment and confirm the same selected model and reproducible metrics (within any documented numerical tolerance).
- Confirm the DummyClassifier and all five candidates—including incumbent Logistic Regression—use identical inner-fold definitions; report those results together, then report only the CV-frozen winner and DummyClassifier on the outer test.
- Add SQL/view boundary tests for the chosen tenure definitions and compare documented/dashboard group totals to the query output.

### Expected output

A new, clearly labelled evaluation report with a naive baseline, training-side CV model selection, one frozen final estimate and reproducibility metadata; the old single-split metrics remain available as historical evidence. SQL and dashboard tenure groupings are either aligned or explicitly distinguished.

### Acceptance criteria

- The new report contains no selection leakage from the final test and identifies the baseline and current Logistic Regression comparison.
- The model is not promoted or changed solely because one metric increased; all candidates and the baseline are measured under the same protocol.
- The old report and CSV remain recoverable and are labelled with their original protocol.
- Tenure segment definitions are consistent across comparable outputs or clearly named as different analyses.
- Any changed model metrics are regenerated and traceable to the pinned input/environment; the README does not mix old and new numbers.

### Rollback/risk considerations

A sounder protocol may lower the reported score or choose another model. That is an acceptable result. If the new pipeline is not reproducible, keep the old result explicitly historical and do not present it as a final estimate. Do not modify the incumbent artifact until the new model, report, API contract and tests all pass. If Power BI Desktop is unavailable, do not claim a refresh; retain only unaffected captures as current and label any model/tenure page capture as historical.

---

## Phase 4 — Add one minimal CI path

**Audit mapping:** FGA-04
**Objective:** Make the artifact-present test path run on pull requests without reviving deployment infrastructure or adding unnecessary tooling.

### Files/components affected

- `.github/workflows/deploy.yml` (retire the commented-out deploy workflow)
- A new `.github/workflows/ci.yml`
- Existing test/setup scripts and, only if the data policy requires it, a small permitted deterministic test fixture

### Exact changes

1. Add one CI workflow on pull requests and pushes to the working default branch. Use the Phase 2 Python/dependency lock and read-only repository permissions. No deployment secrets, SSH step, cloud service, Docker build or multi-version matrix is needed.
2. If the real CSV may be distributed, build the database and model from it in CI and run the complete suite/smoke tests against those artifacts. If it may not be distributed, make CI exercise the same schemas/API/model mechanics using a small permitted deterministic fixture; keep full real-dataset metric reproduction as the documented local run and do not claim the fixture validates real-data performance.
3. Run the test suite after artifact generation and fail on unexpected skips, failures or stale API smoke assertions. Use the already existing tests and commands; do not add a linter/coverage stack merely to decorate the workflow.
4. Remove or clearly retire the all-commented legacy deployment workflow. The repository remains undeployed.

### Tests/checks

- Run the workflow from a clean CI runner and inspect the test summary; artifact-dependent integration tests must execute, not silently skip.
- Verify that no secret is required and that the run cannot deploy or publish artifacts unintentionally.
- Re-run the same commands locally from the Phase 2 environment and compare outcomes.

### Expected output

A single green, reproducible CI check that exercises the relevant code path. If CI uses a fixture due data licensing, its scope is clearly stated and separated from the full local dataset/model evaluation.

### Acceptance criteria

- CI installs the committed environment and completes the intended full test path with zero failures and no unexplained skips.
- CI includes the KPI regression, pagination, API contract, leakage-free training/evaluation mechanics and smoke checks.
- No live deployment, external credentials or extra infrastructure is introduced.

### Rollback/risk considerations

Model libraries may lengthen CI installation or training. Start with one supported runner and one run; do not add a matrix or containers to solve a performance inconvenience. If rights prevent shipping the dataset, keep CI fixture-only and state that the real-data run is a separate local verification. A green fixture suite must never be described as real-data performance evidence.

---

## Phase 5 — Professional packaging and final verification

**Audit mapping:** FGA-08, plus final acceptance of FGA-01 through FGA-07.
**Objective:** Make the verified work understandable in a few minutes and finish with one coherent set of claims, results, links and contribution boundaries.

### Files/components affected

- `README.md`
- `STRUCTURE.md`
- `docs/api_examples.md`, `docs/qa_findings.md`, `docs/sql_analysis_summary.md`
- `dashboard/business_report.md` and existing dashboard screenshots only where their displayed claims/results need revision
- GitHub repository description/topics only if they no longer match the final framing; currently they are already broadly appropriate

### Exact changes

1. Reorder, do not rewrite from scratch: put the problem, architecture, candidate-owned work, team/mentor boundaries, current evaluation table, limitations, no-deployment status, clean quickstart and a direct link/embed to an existing unaffected screenshot near the top of the README. Keep the process/specification detail available through links rather than giving it equal prominence. Use an accurate diagram that shows data/SQL, training/model artifact, API and BI as distinct paths.
2. Correct `STRUCTURE.md` to the actual tree; correct API examples to the real `/customers` field names and current generated metric output; update the QA record with the final pinned run/CI results; remove “production model” and verified-live-ODBC wording where the evidence only supports a local artifact/import workflow.
3. State the final ML result and its exact evaluation protocol in one place. Keep the old single-split report accessible and explicitly historical. If a model/dashboard screenshot still shows old values, either regenerate and verify that page in Power BI Desktop or label it as a historical capture and do not use it as current evidence.
4. Preserve personal-contribution boundaries: link the integration/test PRs; distinguish teammate-owned ETL, training, API scaffold and dashboard work; retain mentor credit for pagination/scaffolding/stretch work. Claim post-sprint aggregate repair only after it has an attributable implementation and test.
5. Keep repository metadata accurate. The existing description/topics need no gratuitous changes. Do not add a homepage URL without a live demo. Record the license decision only after team-code and dataset rights are established.

### Tests/checks

- Perform the final clean-checkout run using the README instructions: environment install, data setup, ETL, views, training/evaluation, API checks and tests.
- Confirm the `/kpis` output against direct SQL; verify pagination and auth; confirm the API metrics match the generated current evaluation report.
- Confirm CI is green and its scope is accurately described.
- Check all local Markdown links, filenames, command paths, data policy and environment-variable names. Search for leakage-era headline metrics and unsupported “production/deployed/live-connected” claims.
- Compare the screenshots used as current evidence with their source report/output. If Power BI Desktop is unavailable, label unreproduced refresh/screenshots rather than implying verification.

### Expected output

A concise, accurate portfolio entry point that tells the reviewer what the project does, what the candidate built, how it was evaluated, what worked/failed, how to reproduce it, and where the demonstration evidence is. The repo remains a local, undeployed team capstone with candid limitations.

### Acceptance criteria

- A technically literate reviewer can answer the seven questions in `FLAGSHIP_GAP_AUDIT.md` within several minutes without relying on contradictory docs.
- Every current metric in the README, API example and dashboard evidence has a traceable protocol/input/environment; legacy values are labelled historical.
- Local setup commands, repository structure, API examples, screenshots and current CI status agree with the tree.
- No false deployment, production, business-impact, temporal-generalization or sole-authorship claim is made.
- All required Flagship Definition of Done checkboxes in the audit are satisfied, or any unavailable external verification is explicitly scoped and not claimed.

### Rollback/risk considerations

Documentation changes must not erase the team history or historical results. If a Power BI refresh cannot be reproduced, do not edit the binary report blindly; link to the existing screenshots with an accurate date/scope note. If new metrics change, update all current references together only after the Phase 3 report is accepted; retain the legacy report unchanged.

---

## Stop Conditions

Stop investing additional engineering time when any of the following applies:

1. **Definition of Done reached:** all P0 items and the required P1 work above pass. Do not continue into FGA-09 or the remaining FGA-10 hardening just because it is possible.
2. **The evaluation is complete, even if the result is modest:** run the prespecified baseline/CV/final-holdout comparison once under the pinned environment. If Logistic Regression does not beat the naive baseline, or the new best model offers no useful/consistent advantage over the incumbent, report that result and stop tuning. A negative or inconclusive result is acceptable portfolio evidence.
3. **Data permission is unresolved:** do not spend time trying to preserve a questionable public copy. Keep the dataset out of the public repository, provide a permitted acquisition/checksum path, and use a small permitted fixture for CI. Do not make unsupported license claims.
4. **External desktop verification is unavailable:** after one bounded attempt to verify Power BI, label unreproduced pages/captures honestly and present unaffected screenshots. Do not rebuild the dashboard to compensate.
5. **Dependency/tooling friction exceeds the bounded path:** after one supported runtime and at most one compatible fallback have been tested, document the working environment and narrow the reproduction claim. Do not replace the application stack or add a new package manager to chase perfect portability.
6. **Further work is only product expansion:** no new database, hosted service, model family, monitoring, user interface, or business-impact study is needed to complete this portfolio case. Keep those ideas out of the flagship budget.

**Finish line:** once Phase 5 acceptance criteria pass, freeze the scope and present the project as a reproducible local team-capstone integration/QA case study with a leakage-aware, fairly evaluated churn comparison—not as a production churn platform.
