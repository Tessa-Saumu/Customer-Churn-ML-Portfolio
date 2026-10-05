# Flagship Implementation Plan — Customer Churn Prediction & BI Platform

**Source of scope:** [`FLAGSHIP_GAP_AUDIT.md`](FLAGSHIP_GAP_AUDIT.md)
**Plan type:** minimum consolidation needed for the audit's Flagship Definition of Done
**Implementation status:** plan only; no implementation has been made.

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
