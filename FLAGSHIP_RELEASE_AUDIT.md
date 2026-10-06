# Flagship Release Audit — Customer Churn Prediction & BI Platform

**Audit date:** 6 October 2026
**Auditor:** independent re-verification pass (fresh environment, fresh clone, live HTTP runs)
**Target:** `Tessa-Saumu/Customer-Churn-ML-Portfolio`, branch `arena/d1941adb-customer-churn-ml-portfolio`, HEAD `11bb55a` ("Flagship consolidation Phase 4 + 5", merge of PR #5)
**Checklist audited against:** [`FLAGSHIP_GAP_AUDIT.md`](FLAGSHIP_GAP_AUDIT.md) — "Flagship Definition of Done" (9 items) plus the repair backlog FGA-01…FGA-10
**Method statement:** no claim in any repository document was trusted. Every claim below was re-executed from scratch in a clean virtualenv built from `.python-version` + `requirements.txt`, against a fresh `git clone` where noted, and against a live `uvicorn` server over HTTP (not only `TestClient`). Documentation was checked *against* observed behaviour, never the reverse.

---

## 1. Verification environment and what was actually executed

| Step | Command (as documented) | Observed result |
|---|---|---|
| Runtime | `python3.11 -m venv` | CPython **3.11.2**, matching `.python-version` (`3.11.2`) exactly |
| Install | `pip install --upgrade pip wheel && pip install -r requirements.txt` | exit 0; pip 26.2.1; 63 distributions installed |
| Closure check | `pip freeze` vs `requirements.lock.txt` | **identical** — `diff` of sorted lock (63 lines) vs sorted freeze (63 lines) empty |
| Consistency | `pip check` | `No broken requirements found.` |
| Input identity | `sha256sum data/raw/telco_churn_raw.csv` | `e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34`, 7,043 rows × 33 cols — matches README, `docs/data_provenance.md`, and `tests/test_reproducibility.py` |
| ETL | `python database/init_db.py && python etl/load_to_db.py && python database/init_views.py` | exit 0 ×3; "Rows inserted: 7043"; `customers`, `view_churn_by_contract`, `view_churn_by_tenure_bucket` present |
| Training | `python training/evaluate_models.py` | exit 0 (~11 s); selected Logistic Regression, holdout acc 0.799148 / ROC AUC 0.849562 |
| Report reproducibility | `git hash-object evaluation/model_comparison.md` before/after training | `77336920e02d864e0f0d8ae0b93f7b3ac940d37d` both times — **byte-identical regeneration**; `git status` clean afterwards |
| CSV reproducibility | `python scripts/generate_model_comparison_csv.py` | exit 0; `evaluation/model_comparison.csv` unchanged (no `git diff`) |
| Suite, artifacts present | `python -m pytest -q` | **151 passed, 0 failed, 0 skipped** in 42.8 s |
| Suite, fresh clone | clone → `python -m pytest -q -rs` (no artifacts) | **68 passed, 83 skipped, 0 failed** (skips carry actionable reasons) |
| API live | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | all 5 endpoints exercised over HTTP (see §4) |
| Acceptance checks | `API_KEY=… ./scripts/verify_endpoints.sh` | **29 passed / 0 failed / 0 skipped, exit 0** |
| Regression behaviour | same script with `EXPECTED_CUSTOMER_COUNT=100` | 1 failed, **exit 1** |
| Preflight behaviour | same script with no `API_KEY` | **exit 2** with instructions |
| Archive hashes | `sha256sum` of report/CSV/training.log vs `evaluation/reproduction/2026-10-06-phase3-cv-holdout/README.md` | `e035eb78…`, `12958fb0…`, `c35eafb1…` — all three match |
| CI platform state | `gh run list` / `gh run view 37480402821` | latest run on `main` **failed with zero steps**: annotation *"The job was not started because your account is locked due to a billing issue."* — identical wording to the README/qa disclosure |
| Evidence links | `gh api …/pulls/{27,29,30,31}` on the team repo | all four exist and are **merged**, authored by `Tessa-Saumu` |

Nothing in the working tree was modified by this audit except the addition of this file; `database/churn.db` and `models/best_model.pkl` are gitignored generated artifacts.

---

## 2. Definition-of-done assessment (FLAGSHIP_GAP_AUDIT.md, 9 items)

| # | Definition-of-done item | Verdict | Evidence from this audit |
|---|---|---|---|
| 1 | **Correct core behavior** — `/customers` paginated by default, boundaries tested; `/kpis` full-dataset via bounded DB aggregate, with a test that fails if it only sees the first 100 rows | **PASS** | Live `/customers` default returned exactly 100 rows; `?page=1&size=5` returned 5; `page=-1`/`size=0` → 422. Live `/kpis` = `{7043, 26.54, 73.46, 64.76, 456116.6}`, byte-for-byte the independent SQL aggregate I ran by hand. `get_kpi_aggregate()` is one `COUNT/SUM` statement (no row materialisation). `tests/test_kpi_aggregate.py::TestKpiAggregateIsWholeTable::test_kpis_are_not_scoped_to_the_default_page` uses a 150-row fixture whose first 100 rows are all churned (I confirmed the tracked DB's first page is likewise 100 % churned), so a page-scoped implementation cannot pass; `TestPaginationIsPreserved` keeps the mentor's default. |
| 2 | **Honest acceptance evidence** — current Bash/PowerShell (or chosen canonical) checks pass, fail nonzero on regression, assert no pre-leakage metrics; historical QA labelled historical | **PARTIAL** | Bash script: 29/29 exit 0 against the live API; exit 1 on an injected regression; exit 2 on missing key; asserts the *absence* of the pre-leakage LightGBM figures (0.9304/0.9818) rather than their presence. `docs/qa_findings.md` Issue #19 carries an explicit "STATUS: HISTORICAL RECORD — superseded in part" banner plus a correct "CURRENT STATUS" block (151 / 68+83 / 29-29 — all three match my measurements). **Residual:** `scripts/verify_endpoints.ps1` has still never been executed anywhere (disclosed in README and qa_findings), and no document designates which of the two scripts is canonical, so "the current checks pass" is proven only for the Bash twin. See P2-2. |
| 3 | **Reproducible setup** — one documented supported environment builds DB, model and evaluation outputs from an identified input; clean-checkout commands work without undocumented artifacts | **PASS** | Built from nothing: clean venv on the pinned runtime, `pip install -r requirements.txt` → freeze identical to the committed lock; ETL → training → report/CSV byte-identical to the committed bytes; full suite green with zero skips. Input checksum machine-checked by `tests/test_reproducibility.py::TestInputProvenance`. The only deviation found is the front-page one-liner orchestration race (item 7 / P1-1), not the setup path itself — the canonical sequence in README "Running the Project" §§1–4 worked exactly as written. |
| 4 | **Enforced full test run** — CI or an equivalently repeatable check runs the artifact-present suite with no unexpected skips and verifies central API/KPI behavior; no deployment job required | **PARTIAL** | `.github/workflows/ci.yml` is exactly the prescribed gate: pinned install → freeze-vs-lock diff → fresh-state suite (skips reported) → artifacts built from the tracked CSV → `git diff --exit-code -- evaluation/` → artifact-present suite with **any skip = failure** → required-test collection check → live API → both smoke scripts (incl. a `pwsh` step). I executed every step locally in order: 151/0/0 and 29/29. **Residual:** the gate has **zero executed runs on GitHub** — every run, including `main` HEAD, failed at queue time with the account-billing annotation. The README and qa_findings disclose this verbatim and claim no green run, which I confirmed against the run annotation. The blocker is account-level, outside the repository. See P2-6. |
| 5 | **Defensible ML result** — target/exclusions/leakage explicit; simple baseline reported; selection separated from final holdout; metrics regenerated from that protocol and labelled with provenance | **PASS** | `training/preprocessing.py::DROP_COLUMNS` drops `churn_score`, `cltv`, `churn_reason`, `churn_label`, identifiers and geography; target is `churn_value`. `select_best_model()` takes only `X_train/y_train` (no holdout parameter exists); 5-fold `StratifiedKFold` selection on the training 80 %, `DummyClassifier(strategy="prior")` reported and ineligible; winner refit then scored once on the frozen 20 %. I regenerated the report and it is byte-identical; `/model-metrics` serves the holdout block (0.7991/0.6435/0.5455/0.8496), not the CV means; limits section states no temporal claim, single seed, no tuning, and the open `max_iter=1000` non-convergence. Legacy single-split result archived and labelled non-comparable. |
| 6 | **Consistent analytics** — SQL analysis, views, docs and dashboard share one documented tenure grouping or explain the difference | **PASS** | `sql/analysis_queries.sql` Business Question 3 now uses the view's three buckets (0–12 / 13–36 / 37+); `docs/data_dictionary.md` and `docs/sql_analysis_summary.md` state the model's finer four-range `TenureBucket` is a separate modelling input whose counts must not be compared; `tests/test_sql_views.py::TestTenureBucketDefinitions` pins both. Live view output (2186/1856/3001; 47.44/25.54/11.93) matches the featured screenshot's tenure table (47/26/12 displayed). |
| 7 | **Accurate portfolio front page** — problem, architecture, contribution, team/mentor boundaries, results, limitations, local demo path and committed screenshot(s) findable in minutes; no deployment claimed | **PARTIAL** | All content is present and accurate: contribution boundary with four merged evidence PRs (verified live), mentor pagination credit, leakage story, results table matching the regenerated report, featured *verified-current* screenshot, explicit "nothing here is deployed". **Residual:** the headline "five commands reproduce the whole local path" block fails deterministically as written — line 5 (`uvicorn … & … verify_endpoints.sh`) has no readiness wait; 3/3 copy-paste attempts returned `18 passed, 10 failed`, exit 1, while the same script after a readiness wait returns 29/29 exit 0. A reviewer pasting the front-page block gets a false red. See P1-1. |
| 8 | **No contradictory docs** — structure, API examples, QA status, setup variables, model/dashboard claims match the tree and outputs; local links resolve; description/topics appropriate; no demo URL advertised | **PASS** | `STRUCTURE.md` verified field-by-field (85 tracked files — exact; `training/README.md` 0 bytes — exact; absent `training/predict.py` and `training/scripts/` confirmed). `docs/api_examples.md` `/predict` example reproduced to the last digit (`0.7113677247256835`); `/customers` example matches the live first record (33 columns, `senior_citizen: "No"`, `tenure_months`); `/kpis` and `/model-metrics` examples match live responses. `.env.example` lists only variables the code reads (guarded by test). `dashboard/business_report.md` "production model"/live-connection phrasing is qualified by dated notes. All 10 internal README links and all 14 TOC anchors resolve (GitHub slug rules). Repo metadata: description + 4 topics set, `homepage: null`, no LICENSE (deliberate, documented), no Pages, no demo URL anywhere. Nits (comment-level, not doc claims) in P2-3/P2-4/P2-5. |
| 9 | **Rights and attribution are clear** — dataset source/version/hash and distribution policy documented; licence only if appropriate; mentor/team credit preserved | **PASS** | `docs/data_provenance.md` records listing, publisher, version, SHA-256/MD5, blob hash (verified: blob size 1,736,765 = on-disk size), the two provenance gaps (conversion-not-download; upstream 404), and an explicit **"redistribution permission is unconfirmed"** conclusion with the retention decision, its three reasons and a reversal procedure. No blanket LICENSE, with rationale. `CONTRIBUTORS.md` + README preserve team/mentor ownership including pagination and scaffolding. |

**Count: 6 PASS · 3 PARTIAL · 0 FAIL · 0 NOT APPLICABLE.**

---

## 3. Requested verification areas (audit brief)

| Area | Verdict | Evidence / note |
|---|---|---|
| Clean environment setup | **PASS** | Clean venv on CPython 3.11.2; no pre-existing artifacts required; `.env` absent and untracked (`git ls-files` has no `.env`). |
| Dependency installation | **PASS** | `requirements.txt` (pinned direct deps, `-c requirements.lock.txt`) installs cleanly; freeze ≡ lock; `pip check` clean. |
| Configuration | **PASS** | `.env.example` = exactly the three variables the code reads (`API_KEY`, `MODEL_PATH`, `MODEL_METRICS_PATH`); `load_dotenv()` precedes router import (structurally tested); unread legacy vars removed and the removal documented. |
| Core execution path | **PASS** | ETL → SQLite → views → training → API → checks, all exit 0 in one pass. |
| Tests | **PASS** | 151/0/0 artifact-present; 68/83/0 fresh clone with actionable skip reasons; KPI, pagination, leakage, protocol, provenance and report-immutability guards all present and collected. |
| Model inference / training | **PASS** | Training reproduces the committed report byte-for-byte; live `/predict` returns the documented probability for the documented payload; locked two-key response shape; 422 on schema violations; 401 without key. |
| API endpoints | **PASS** | All five verified over HTTP incl. auth matrix, pagination bounds and whole-population KPI semantics (details §4). |
| Frontend / build | **NOT APPLICABLE** | There is no frontend build: Streamlit is a single optional script (compiles; labelled optional/unverified, exercised by no test), Docker/Compose exist but no daemon was available and no build is claimed. The audit's out-of-scope list forbids adding one. |
| Persisted data / database expectations | **PASS** | `database/churn.db` gitignored and regenerable; schema carries `PRIMARY KEY`, `CHECK` (charges ≥ 0, `churn_value IN (0,1)`, lat/long bounds, tenure ≥ 0) and `NOT NULL` constraints; both views created idempotently; row count 7,043. |
| Current deployment links | **PASS (as labelled: none)** | No homepage URL, no Pages, no live service advertised; legacy `deploy.yml` removed (single workflow remains); README/qa state undeployed. GitHub Actions shows red Xs — disclosed verbatim and confirmed (billing lock, zero steps). |
| Screenshots / demo assets | **PASS** | 5 valid JPEGs + `.pbix` committed. `churn_drivers.jpg` re-verified by me against the live views: 26.54 %, 1,869 / 5,174, contract 42.71/11.27/2.83 (1,655/166/48 of 3,875/1,473/1,695), tenure 47/26/12 (1,037/474/358 of 2,186/1,856/3,001) — every figure matches. `model_predictions.jpg` shows exactly the legacy archive's numbers (80.20/64.80/55.62/84.94, CM 922/113/166/208) and is labelled historical in README, STRUCTURE.md and the business report. |
| README commands | **PARTIAL** | Canonical sequence (Running the Project §§1–4) works verbatim. The 5-command at-a-glance block's line 5 fails 3/3 without a readiness wait (P1-1). |
| Metrics / results | **PASS** | README table ≡ regenerated `evaluation/model_comparison.md` ≡ live `/model-metrics` ≡ `docs/reproduction_record.md` §12 ≡ archived training log; archive SHA-256s verified; legacy values archived and labelled; baseline and fold variation published. |

---

## 4. Live endpoint matrix (observed, `uvicorn` on `0.0.0.0:8000`)

| Request | Expected | Observed |
|---|---|---|
| `GET /health` (no key) | 200 | 200 `{"status":"ok"}` |
| `GET /customers` no key / bad key | 401 | 401 / 401 |
| `GET /customers` with key | 200, ≤100 rows | 200, exactly 100 rows, 33 snake_case columns |
| `GET /customers?page=1&size=5` | 200, 5 rows | 200, 5 rows (page offset correct) |
| `GET /customers?page=-1`, `?size=0` | 422 | 422 / 422 |
| `GET /kpis` with key | whole population | `{7043, 26.54, 73.46, 64.76, 456116.6}` = hand-run SQL aggregate |
| `GET /model-metrics` | report's holdout block | `{0.7991, 0.6435, 0.5455, 0.8496}` |
| `POST /predict` valid | 200, locked 2 keys | 200 `{"churn_probability":0.7113677247256835,"churn_prediction":true}` (matches `docs/api_examples.md` exactly) |
| `POST /predict` no key | 401 | 401 |
| `POST /predict` missing fields / negative tenure | 422 | 422 / 422 |
| `POST /predict` `tenure: 200` | documented open edge (FGA-10) | 200 with a prediction (bucket becomes NaN) — documented limitation, P2 |
| Missing model artifact → `import app.main` | documented import-time load | `FileNotFoundError` at import (so `/health` unreachable) — documented P2, FGA-10 |

---

## 5. Findings

### P0 — none

No correctness or reproducibility blocker was found. Every P0 item of the gap audit (FGA-01 KPI aggregate, FGA-02 acceptance-check repair, FGA-03 pinned reproduction) is implemented and independently confirmed working.

### P1 — one item

**P1-1. The README's front-page "five commands" block fails deterministically as written.**
*Evidence:* line 5 is `API_KEY=<any-key> uvicorn app.main:app & API_KEY=<any-key> ./scripts/verify_endpoints.sh`. With no readiness wait, 3/3 executions produced `Results: 18 passed, 10 failed, 1 skipped`, exit 1, with `FAIL [000, expected 200] GET /health` (connection refused while uvicorn boots). The identical script, preceded by a `curl` readiness loop, returns `29 passed, 0 failed, 0 skipped`, exit 0. The canonical "Running the Project" instructions (separate terminals) are correct; only the convenience block is racy.
*Why P1:* it is the first thing a copy-pasting reviewer runs, and it prints a false red against a healthy system — precisely the "reviewer encounters a contradiction" failure mode the gap audit exists to eliminate.
*Smallest required fix:* insert a readiness wait into that one line, e.g.
`API_KEY=<any-key> uvicorn app.main:app & for i in $(seq 1 30); do curl -fsS localhost:8000/health >/dev/null && break; sleep 1; done; API_KEY=<any-key> ./scripts/verify_endpoints.sh`
(or replace line 5 with a pointer to the two-terminal instructions in "Running the Project" §3). One-line documentation change; no code change.

### P2 — optional; do not pursue (with one external exception)

- **P2-1 `scripts/verify_endpoints.sh` reports vacuous content passes when the body is empty.** `jq -e` (jq 1.6) exits 0 on a zero-byte file, so against an unreachable server the script printed 18 spurious `PASS [content]` lines plus `line 219: [: : integer expression expected` (unguarded `[ "$default_page_length" -eq 100 ]`). It still exits 1 (never all-green), and its header comment's claim of exit 2 for "no server reachable" is false (actual: 1). *Smallest fix:* copy the connectivity preflight the `.ps1` twin already has (fail fast, exit 2), or guard `check_content` with `[ -s "$BODY_FILE" ]`.
- **P2-2 No canonical acceptance script is designated; the PowerShell twin has never executed.** Disclosed honestly in README and qa_findings; CI contains a `pwsh` step that would execute it once the account is unlocked. *Smallest fix:* one sentence in README naming `verify_endpoints.sh` the canonical executed gate and the `.ps1` an unexecuted mirror.
- **P2-3 Stale numbers in a CI comment:** `.github/workflows/ci.yml` header says "82 of 148 tests skip" on a fresh clone; measured today: **83 of 151**. *Smallest fix:* correct the two numbers.
- **P2-4 `docs/reproduction_record.md` §12 verification table is Phase-3-dated** (148 passed; 66/82 fresh) while the current suite is 151 (68/83). The table is labelled "Phase 3, this environment" and qa_findings carries the correct current figures, so this is a completeness nit, not a contradiction. *Smallest fix:* append a Phase 4/5 row.
- **P2-5 README tail contains a dangling commit-message fragment** — the line "Added Containerization" sits between the lead-in sentence and the `PROCESS.md` bullet. Cosmetic.
- **P2-6 (external, not repository engineering) GitHub account billing lock.** CI has zero executed runs; the Actions tab shows a red X on every push including `main` HEAD. Nothing in the repository can change this. Resolving the billing issue and re-pushing is the only step between the committed gate and its first real (and, per this audit, expected-green) run.
- **P2-7 Open-by-design backlog the README makes no stronger claim about** (audit items FGA-09/FGA-10 and recorded caveats): `/model-metrics` regex-parses the Markdown report; model load at import time makes `/health` unreachable when the artifact is missing; `tenure > 72` yields a NaN bucket yet a 200 response; a full `pytest` run rewrites the gitignored `models/best_model.pkl` to a byte-different serialization of the same fit (NEW-20, hashes reproduced exactly by this audit); and the dashboard's "AVG CHURN SCORE 58.70" KPI card displays the outcome-derived column as a descriptive business metric (never a model input) without a footnote.

---

## 6. Release conclusion

**Is this repository currently ready to be used as professional portfolio evidence? Yes.**

Judged only as a repository: the system does what its documentation says it does, and its documentation says nothing the system does not do. The three properties a technical interviewer will probe hardest were each confirmed by independent execution rather than by reading claims — (a) the `/kpis` whole-population aggregate equals a hand-computed SQL aggregate and cannot regress silently (a 150-row fixture with an all-churned first page defeats any page-scoped implementation); (b) the pinned environment reproduces the published metrics, the report and the CSV byte-for-byte from a clean venv and a checksummed input; (c) the evaluation protocol genuinely separates selection from the frozen holdout, reports a naive baseline, and labels its own limits, including the non-convergence it chose not to hide. Attribution, provenance and the unconfirmed dataset-rights question are documented with unusual precision, and every historical artifact (legacy metrics, historical QA pass, historical dashboard capture, unexecuted PowerShell script, never-green CI) is labelled as historical or unexecuted rather than presented as current.

There are **no P0 problems**. The repository may be presented now, exactly as the gap audit's stop condition prescribes: a reproducible, local, team-capstone integration and QA case study with a corrected, modest churn model comparison — not a production platform.

**However, engineering should not stop yet for one reason only: P1-1.** The front-page five-command block hands a copy-pasting reviewer a deterministic false failure. It is a one-line documentation fix. Make that single edit (and, if convenient, the external billing action in P2-6, which is account administration rather than engineering), and then **stop**: every remaining item in §5 is optional P2 polish, the README makes no claim that depends on any of it, and pursuing them would add churn to a repository whose principal asset is now its demonstrable honesty.

*Post-fix state prediction:* with P1-1 applied, all nine definition-of-done items read PASS except item 2 and item 4, which remain PARTIAL solely because (i) the PowerShell twin cannot be executed in any available environment and (ii) the committed CI gate cannot start on a billing-locked account — both disclosed, both outside the repository's code, and both removable only by running the existing `pwsh` CI step once the account is restored.
