# Reproduction Record — pinned environment, 2026-10-05

**Phase:** 2 (audit items FGA-03 and FGA-07) of `FLAGSHIP_IMPLEMENTATION_PLAN.md`.
**What this document is:** the single authoritative record of *one* supported
runtime, *one* pinned dependency set, the exact input, the exact commands, and the
result they produced — so a reviewer can tell whether a changed metric is a bug or
package drift.
**What it is not:** a new headline result. The repository's published metrics are
unchanged; see [§8 What is canonical after Phase 2](#8-what-is-canonical-after-phase-2).

---

## 1. Supported runtime

| | |
|---|---|
| **Supported Python** | **CPython 3.11** — verified on **3.11.2** (`main`, Apr 8 2026, GCC 12.2.0) |
| Marker file | `.python-version` → `3.11.2` |
| OS / arch | Debian GNU/Linux 12 (bookworm), x86_64, 2 vCPU |
| pip | 26.2.1 |

**Why not the previously documented Python 3.12.** `README.md` and both
`Dockerfile`s claimed 3.12, and the plan says to prefer it if it works. It could
not be tested here: the only interpreter in this environment is 3.11.2, there are
no `apt` package lists for 3.12, and every network path to a 3.12 build was
unreachable (python.org and `codeload.github.com` refused the connection; GitHub
release assets failed the TLS handshake). Rather than document a version nobody had
run, the supported runtime is now the one that was actually verified end-to-end, and
`README.md`, `.python-version`, `Dockerfile` and `Dockerfile.streamlit` all say 3.11.
**3.12 is neither validated nor excluded** — the pins are plain version numbers and
every package here publishes 3.12 wheels, but nobody has run this pipeline on 3.12
and this document does not claim otherwise.

## 2. Dependency set

| File | Role |
|---|---|
| `requirements.txt` | The 15 **direct** dependencies, each pinned with `==`, plus `-c requirements.lock.txt` so a normal install is fully constrained |
| `requirements.lock.txt` | The complete 63-package transitive closure from the verified environment (`pip freeze`), used as the constraints file |

Direct pins as verified:

```text
pandas==3.0.6            numpy==2.4.6           scikit-learn==1.9.1
xgboost==3.2.0           lightgbm==4.7.0        joblib==1.6.0
tabulate==0.10.0         fastapi==0.142.2       uvicorn[standard]==0.54.0
python-dotenv==1.2.4     sqlalchemy==2.1.3      pytest==9.1.1
httpx==0.28.1            streamlit==1.65.0      requests==2.34.2
```

**Determinism proof.** Two *separate* clean virtual environments were built with
only the documented commands — one from the then-unpinned `requirements.txt` (which
produced the lock), then a second one from the pinned manifest. The second
environment's `pip freeze` was **identical, line for line, to the committed
`requirements.lock.txt`**. `tests/test_reproducibility.py::TestPinnedRuntime` keeps
the manifest, the lock and the version marker consistent from here on.

**Lock platform scope.** The freeze was taken on Linux and therefore contains
Linux-only transitive packages — `nvidia-nccl-cu12==2.32.3` (351 MB, pulled in by
xgboost's GPU support) and `uvloop`/`httptools`/`watchfiles`/`websockets` (from
`uvicorn[standard]`). Used as a *constraints* file (the normal path, via
`requirements.txt`) those entries are inert on macOS/Windows because nothing there
requires them. Installing `requirements.lock.txt` **directly** on macOS/Windows will
fail; install `requirements.txt` instead. This is stated in the lock file's header
too.

## 3. Input

| | |
|---|---|
| File | `data/raw/telco_churn_raw.csv` (tracked) |
| SHA-256 | `e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34` |
| Size / shape | 1,736,765 bytes · 7,044 lines (1 header + 7,043 rows) · 33 columns · LF |
| Source, version and rights | [`docs/data_provenance.md`](data_provenance.md) — redistribution rights **unconfirmed**, retention decision recorded there |

## 4. Protocol as run (unchanged from the legacy result)

Phase 2 does not change the modelling protocol; Phase 3 does. What ran:

- `training/preprocessing.py` — target `churn_value`; `churn_score`, `churn_reason`,
  `cltv`, `customer_id`, geography and the text label dropped (leakage-free);
  3 engineered features (`TenureBucket`, `TotalServicesCount`, `AvgMonthlySpend`);
  22 columns into the `ColumnTransformer`, **52 used features** after one-hot
  encoding (LightGBM's own log line, in `training.log`).
- `training/train_test_split.py` — single **stratified** split, `TEST_SIZE = 0.2`,
  `RANDOM_STATE = 42` → **5,634 train / 1,409 test** rows.
- `training/train_models.py` — Logistic Regression (`max_iter=1000`), Decision Tree,
  Random Forest, XGBoost (`eval_metric="logloss"`), LightGBM, all `random_state=42`,
  each wrapped in a `Pipeline(preprocessor, classifier)`.
- `training/evaluate_models.py` — accuracy/precision/recall/ROC AUC/confusion matrix
  per model; winner = highest **ROC AUC on that same holdout**; joblib dump to
  `models/best_model.pkl`.

No baseline, no cross-validation, no untouched final holdout. Those are Phase 3
(audit FGA-05), and the legacy numbers must not be read as if they had them.

## 5. Commands run, from a clean artifact state

Starting state: **no** `database/churn.db`, **no** `models/` directory, tracked
`evaluation/model_comparison.md` present at SHA-256 `a976bb7b…`.

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt          # constrained by requirements.lock.txt

python database/init_db.py               # 0.08 s  -> Database initialized from sql/schema.sql
python etl/load_to_db.py                 # 0.54 s  -> Rows inserted: 7043
python database/init_views.py            # 0.04 s  -> Views initialized from sql/views.sql
python training/evaluate_models.py       # 3.28 s  -> Best model: Logistic Regression, saved
uvicorn app.main:app --reload            # API live on :8000
python -m pytest                         # full suite
API_KEY=<your-key> ./scripts/verify_endpoints.sh
```

Wall-clock timings above are from this environment (2 vCPU); the whole ETL → training
path takes well under 10 seconds, so there is no performance reason to skip a rerun.

The regenerated report and CSV were captured to
[`evaluation/reproduction/2026-10-05-pinned-single-split/`](../evaluation/reproduction/2026-10-05-pinned-single-split/)
and the tracked report was restored byte-for-byte (`git checkout --
evaluation/model_comparison.md`, hash re-verified afterwards).

## 6. Result of the pinned rerun vs. the committed legacy result

Selected model: **Logistic Regression** in both runs.

| Model | Metric | Legacy (committed, unpinned) | Pinned rerun (this record) | Δ |
|---|---|---|---|---|
| **Logistic Regression** | accuracy | 0.801987 | **0.799148** | −0.002839 |
| | precision | 0.647975 | **0.643533** | −0.004442 |
| | recall | 0.556150 | **0.545455** | −0.010695 |
| | ROC AUC | 0.849448 | **0.849562** | +0.000114 |
| | confusion matrix | [[922, 113], [166, 208]] | [[922, 113], [170, 204]] | 4 rows moved TP→FN |
| XGBoost | accuracy | 0.790632 | **0.784244** | −0.006388 |
| | ROC AUC | 0.828214 | **0.831920** | +0.003706 |
| | confusion matrix | [[910, 125], [170, 204]] | [[906, 129], [175, 199]] | — |
| Decision Tree | all metrics | 0.731725 / 0.494737 / 0.502674 / 0.658343 | **identical** | 0 |
| Random Forest | all metrics | 0.789212 / 0.622222 / 0.524064 / 0.833522 | **identical** | 0 |
| LightGBM | all metrics | 0.805536 / 0.658228 / 0.556150 / 0.848423 | **identical** | 0 |

**Reading of the difference.** Three of the five candidates are bit-identical; the
two that moved (Logistic Regression, XGBoost) are the two whose fitted state depends
most on library internals (lbfgs iteration path; XGBoost's histogram builder). The
selection outcome did not change, and the gaps are far smaller than the
selection-protocol weakness the audit already records (the same holdout picks the
winner, and the top two candidates are ~0.001 ROC AUC apart). This is **not** a
reason to prefer either number: the legacy values stay published and labelled
historical, the pinned values stay labelled as this rerun, and Phase 3 produces the
result that becomes current.

## 7. Determinism evidence

| Check | Result |
|---|---|
| Two consecutive `evaluate_all_models(report_dir=…)` runs in the pinned env | reports **byte-identical** (SHA-256 `23c73d8a7fcbf06d0439f5a39d46a19275d5f6ccde363432a4ca03bcb11bde54` both times) |
| A third run's `models/best_model.pkl` vs. the second's | **byte-identical** (SHA-256 `7f54533733373d60d8de2d962887e9786fb6394475783d28db4ea45599b4b04d`) |
| Second clean venv from the pinned manifest | freeze **identical** to `requirements.lock.txt` |
| Tracked `evaluation/model_comparison.md` after the full test suite | **unchanged** (SHA-256 `a976bb7b…`, verified before and after; guarded by `tests/test_reproducibility.py` and `tests/test_models.py`) |

So: with the pins in place, this pipeline is bit-reproducible *in this environment*.
That is a narrower claim than "reproducible everywhere" — see §9.

## 8. What is canonical after Phase 2

| Artifact | State |
|---|---|
| `evaluation/model_comparison.md` / `.csv` | **Unchanged.** Still the legacy single-split values, byte-identical to `evaluation/legacy/`. This is what `/model-metrics` serves and what `README.md` quotes. |
| `evaluation/legacy/` | **New.** Labelled byte-identical archive of the above, with its protocol and source revision. |
| `evaluation/reproduction/2026-10-05-pinned-single-split/` | **New.** The pinned rerun's report, CSV and training log. Reference material, not the published result. |
| `models/best_model.pkl` | Gitignored, generated. After this record's run it holds the **pinned** Logistic Regression fit (accuracy 0.799148). |
| `database/churn.db` | Gitignored, generated: 7,043 rows, `customers` table, both views. |

**Known consequence, recorded not hidden (backlog NEW-03).** `/model-metrics` reads
the tracked legacy report (0.8020 / 0.8494) while `/predict` serves a pickle whose
own held-out score in the pinned environment is 0.7991 / 0.8496. Nothing asserts the
two agree. This mismatch predates Phase 2 — any local retrain caused it — but it is
now *measured*, and Phase 2 deliberately does not resolve it by republishing drifted
numbers as current. Phase 3 closes it by regenerating the canonical report and the
pickle together under the new protocol (audit FGA-05; FGA-09 would additionally give
the API a structured source).

Data-level cross-checks from the same run (independent of the model):

```text
customer_count = 7043   churned = 1869   churn_rate = 26.54%   retention = 73.46%
avg monthly charges = 64.76   total monthly charges = 456116.6
tables = ['customers']   views = ['view_churn_by_contract', 'view_churn_by_tenure_bucket']
```

These match the `/kpis` aggregate repaired in Phase 1 and `docs/api_examples.md`.

## 9. Caveats and newly discovered problems

1. **Logistic Regression does not converge.** The training log carries
   `ConvergenceWarning: lbfgs failed to converge after 1000 iteration(s)` — the
   selected model is stopped by its iteration cap on unscaled one-hot features. This
   was almost certainly true of the legacy runs too (same `max_iter=1000`, same
   absence of scaling). It is recorded here, **not fixed**: changing it would move
   the metrics, which is Phase 3's decision under a documented protocol. → backlog.
2. **`scripts/generate_model_comparison_csv.py` writes CRLF.** The tracked legacy CSV
   is LF, so re-running the documented CSV step produces a whole-file line-ending
   diff even when the values are unchanged. The CSV in this directory is the script's
   verbatim output (CRLF) on purpose. → backlog (relevant to Phase 3, which
   regenerates the CSV).
3. **The lock is Linux-scoped** (§2). A macOS/Windows reviewer gets the same direct
   pins but a different transitive closure; only the Linux closure was verified.
4. **The container path is unverified.** No Docker daemon exists in this environment,
   so neither `Dockerfile` was built. Their base images were aligned to
   `python:3.11-slim` and they now copy the lock file, but "the images build" remains
   a documented-not-reproduced claim, exactly as the audit found it.
5. **Python 3.12 was not tested** (§1).
6. **`data/raw/telco_churn_raw.csv` is a conversion** of Kaggle's `.xlsx` with no
   committed conversion step, so the tracked bytes cannot be regenerated from the
   upstream download; and the IBM Community page the Kaggle listing cites is a 404.
   Both are recorded in `docs/data_provenance.md`.
7. **The container path generates its own report.** `.dockerignore` excludes the
   host's `evaluation/model_comparison.md` and `.csv` from the build context, and the
   trainer stage runs `training/evaluate_models.py` inside the image, so a
   containerised `/model-metrics` reports whatever the in-image training produced —
   not the tracked legacy file. With the pins in place those numbers are now the ones
   in §6 (accuracy 0.7991), i.e. a containerised API and a locally served one can
   report slightly different metrics for the same code. Pre-existing design, recorded
   here because the pins make it visible.

## 10. Verification runs (Phase 2, this environment)

| Run | Result |
|---|---|
| Full suite, artifacts present | **130 passed / 0 failed** in 11.1 s |
| Per file | `test_api` 34 · `test_etl` 28 · `test_kpi_aggregate` 12 · `test_models` 22 · `test_reproducibility` 27 · `test_sql_views` 7 |
| Markers | `-m unit` → 58 passed · `-m integration` → 72 passed |
| Full suite, fresh state (no `database/churn.db`, no `models/`) | 59 passed / 71 skipped / **0 failed**. 25 of the 27 new guards still run in this state, so the reproducibility properties are checkable on a clean clone |
| Tracked metrics after the entire suite | **unchanged** (`a976bb7b…` / `04d35816…` before and after) — this is the NEW-02 fix holding |
| Clean rebuild from the fresh state | ETL → 7,043 rows → views → training; the CLI-regenerated report was **byte-identical to the recorded pinned rerun**, then the committed legacy bytes were restored |
| Live API (`uvicorn app.main:app --host 0.0.0.0 --port 8000`) | `/health` 200 · `/customers` 401 unauthenticated, 100 rows by default, 5 rows at `?page=1&size=5` · `/kpis` `{customer_count: 7043, overall_churn_rate: 26.54, retention_rate: 73.46, average_monthly_charges: 64.76, total_monthly_revenue: 456116.6}` · `/model-metrics` `{accuracy: 0.802, precision: 0.648, recall: 0.5561, roc_auc: 0.8494}` (legacy values, unchanged) · `/predict` 422 on a malformed payload |
| `scripts/verify_endpoints.sh` against that API | **29 passed / 0 failed / 0 skipped, exit 0** |
| Smoke-script failure paths | `EXPECTED_CUSTOMER_COUNT=999` → exit 1 · `API_KEY` unset → exit 2 · `EXPECTED_CUSTOMER_COUNT=abc` → exit 2 |
| `python -m compileall` | clean |
| `ruff check` 0.16.10 (ad-hoc; no linter is configured in this repo) | Files this phase added or rewrote are clean (`tests/test_reproducibility.py`, `app/main.py`: 0 findings). Repo-wide: **61 findings before this phase and 61 after**. The pre-existing items sit in files this phase did not author (`tests/test_api.py` 36, `tests/test_models.py` 9, `tests/test_etl.py` 3, `training/evaluate_models.py` 2, `predict.py` 1); `tests/test_models.py` and `training/evaluate_models.py` lint identically rule-for-rule at the pre-Phase-2 revision. Not fixed: out of scope |
| Negative controls (run in a scratch copy of the repo) | Every new guard was confirmed to **fail** when its property is broken: dead `.env` setting re-added; a requirement unpinned; manifest/lock disagreement; `app/main.py` ordering reverted (structural *and* behavioural test); tracked report tampered with; input CSV tampered with; `Dockerfile` put back on 3.12; `.gitignore` contradiction restored |

**Not run, therefore not claimed:** `scripts/verify_endpoints.ps1` (no PowerShell
runtime in this environment — unchanged status from Phase 1) and any Docker build (no
daemon). One manual `/predict` probe during this run sent database column names
instead of the API schema's field names (`SeniorCitizen`, `tenure`, …) and correctly
got a 422; the smoke script's payload — which matches
`app/schemas/customer_schema.py` and `docs/api_examples.md` — returns 200.

## 11. Reproduce this record yourself

```bash
git clone https://github.com/Tessa-Saumu/Customer-Churn-ML-Portfolio.git
cd Customer-Churn-ML-Portfolio

# 1. confirm the input is the input these numbers came from
echo "e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34  data/raw/telco_churn_raw.csv" | sha256sum -c -

# 2. build the supported environment (Python 3.11, see .python-version)
python3.11 -m venv venv && source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt

# 3. run the pipeline (writes only gitignored artifacts, plus the report below)
python database/init_db.py && python etl/load_to_db.py && python database/init_views.py
python training/evaluate_models.py

# 4. compare against this record; then put the tracked report back
diff evaluation/model_comparison.md evaluation/reproduction/2026-10-05-pinned-single-split/model_comparison.md
git checkout -- evaluation/model_comparison.md

# 5. tests and API checks
python -m pytest
uvicorn app.main:app --port 8000 &   # then, in another shell:
API_KEY=<your-key-from-.env> ./scripts/verify_endpoints.sh
```

Step 3 leaves `evaluation/model_comparison.md` modified — that is expected, it is the
legacy protocol's output in your environment, and step 4 restores the committed file.
`pytest` does **not** modify it (see §7).
