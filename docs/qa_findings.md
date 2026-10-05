# QA Findings

This document is maintained across four issues: **Issue #13** (ETL
& Database), **Issue #16** (FastAPI), **Issue #17** (Model Training
& Prediction), and **Issue #19** (Full Regression Pass — added
after all four were merged, per Issue #19's own acceptance
criteria). Each finding below was reproduced directly against the
real codebase during test authorship — not inferred from reading
code alone — and each is backed by a corresponding test in
`tests/test_etl.py`, `tests/test_api.py`, `tests/test_models.py`,
or `tests/test_sql_views.py` that documents the *current* behaviour
so any future change to it is caught, not silently reversed.

**Navigation note:** this file is carried in full on each of the three
test-authoring branches (`theresia/etl-tests`, `theresia/api-tests`,
`theresia/model-tests`) to avoid merge conflicts from three PRs editing
the same file concurrently. Each branch's PR description states which
section(s) below that PR is responsible for -- reviewers should check
the PR description, not assume every section in this file was authored
by that specific branch. Section ownership: `## Issue #13` is
authored on `theresia/etl-tests`; `## Issue #16` and
`## Cross-Cutting` are authored on `theresia/api-tests`; `## Issue #17`
is authored on `theresia/model-tests`.

None of these were fixed as part of writing the test suites, per each
issue's own instruction to document findings rather than silently
patch implementation code owned by someone else -- with one exception
noted in Finding 10, where Theresia is claiming the fix as a joint
owner of that file.

---

## Issue #13 -- ETL & Database

### Finding 1: `clean_data()` raises `KeyError` on a `count`-less input

**Steps to reproduce:**
```python
from etl.clean_data import clean_data
import pandas as pd

df = pd.DataFrame({"CustomerID": ["1234-ABCDE"], "Total Charges": ["100.5"]})
clean_data(df)  # raises KeyError: "['count'] not found in axis"
```

**Expected behaviour:** Given that every other column-drop in this
codebase uses `errors="ignore"` (see `training/preprocessing.py`'s
`DROP_COLUMNS` handling), a missing `count` column would either be
silently skipped or raise a clear, purpose-built validation error
(e.g. "input is missing required column: count").

**Actual behaviour:** `etl/clean_data.py` calls
`df.drop(columns=["count"])` with no `errors="ignore"`, so a `count`-less
input raises a generic pandas `KeyError` instead.

**Test coverage:** `tests/test_etl.py::TestCleanDataEdgeCases::test_missing_count_column_raises_keyerror`
asserts this is the current behaviour, so a future fix is confirmed
(test starts failing, signalling the fix landed) rather than silently
forgotten.

**Recommendation:** Add `errors="ignore"` to match the rest of the
codebase's convention, or raise a clearer, named validation error if
strict column presence should be enforced. Flagging for Mercy/Theresia
to decide -- not changed here.

---

### Finding 2: literal empty-string values are not normalized by `fillna()`

**Steps to reproduce:**
```python
import pandas as pd
s = pd.Series([""])
s.fillna("Not Applicable")  # value stays "" -- fillna only replaces real NaN
```

**Expected behaviour:** The code comment above the `churn_reason`
handling in `etl/clean_data.py` states the intent: "Churn reason is
only applicable to customers who churned" (filled with `"Not Applicable"`).

**Actual behaviour:** This works correctly for the real production
input path, because `pd.read_csv` (used by `etl/inspect_raw_data.py::load_data`)
converts a genuinely blank CSV cell into a real `NaN`, which `fillna()`
does replace -- confirmed against the real loaded database
(`SELECT DISTINCT churn_reason ...` returns only `"Not Applicable"` or
a real value, never `""`). However, `clean_data()` itself does not
enforce or validate that its input always comes from `pd.read_csv`. If
it is ever called on a DataFrame from a different source that
represents a blank value as a literal `""` (e.g. a different loader, a
JSON/API payload, a CSV re-export that quotes empty fields), the value
silently stays as `""` with no error or warning.

**Test coverage:**
- `tests/test_etl.py::TestCleanDataBaselineCorrectness::test_churn_reason_null_becomes_not_applicable`
  confirms the real-NaN case works as intended.
- `tests/test_etl.py::TestCleanDataEdgeCases::test_literal_empty_string_churn_reason_is_not_normalized`
  documents the literal-empty-string fragility explicitly.

**Recommendation:** Low priority given the current single input source
(`pd.read_csv`), but worth a one-line hardening
(`.replace("", pd.NA)` before `fillna`) if `clean_data()` is ever
called from a second entry point.

---

### Finding 3: SQL `CHECK` constraints are enforced correctly (not a bug -- confirmation)

Verified directly (not just read from `sql/schema.sql`) that negative
`monthly_charges`, a `churn_value` outside `{0, 1}`, and a null
`churn_label` are all rejected by SQLite with `IntegrityError` at
insert time. See `tests/test_etl.py::TestSchemaConstraints`. No action
needed -- included here so the review record shows this was actually
tested, not assumed from the DDL text.

---

## Issue #16 -- FastAPI

### Finding 4: the app cannot be imported -- and therefore `/health` cannot be tested -- without a valid model artifact on disk

**Steps to reproduce:**
```bash
mv models/best_model.pkl /tmp/backup.pkl
python3 -c "from app.main import app"  # raises FileNotFoundError
```

**Expected behaviour:** `/health` is documented (README, Project
Specification section 2.3) as a dependency-free endpoint -- "no auth,"
implicitly no other requirements either. A reasonable expectation is
that `/health` works even if the model artifact is temporarily
missing or corrupted, since a health check's purpose is partly to
detect exactly that kind of problem.

**Actual behaviour:** `app/api/routes.py` imports `predict` from
repo-root `predict.py` at module level, and `predict.py` calls
`joblib.load(MODEL_PATH)` at ITS module level (not lazily). This means
importing `app.main` -- which happens before any route, including
`/health`, can be reached -- fails outright if
`models/best_model.pkl` is missing or unreadable. A missing model
currently takes down the entire app, not just `/predict`.

**Test coverage:** `tests/test_api.py` is guarded by
`requires_app_dependencies`, which skips (not fails) the whole file if
the model artifact is absent -- this was necessary specifically
because of this finding, not just a generic precaution.

**Recommendation:** Consider lazy-loading the model (load on first
`/predict` call, or in a FastAPI startup event with a try/except that
still allows `/health` to serve). This is an `app/api` and
`predict.py`-ownership decision (Praise/Latifah), not made
unilaterally here.

---

### Finding 5: (confirmation, not a bug) unseen categories and out-of-range values are handled correctly end-to-end

Verified through the full HTTP layer (not just at the `predict()`
function level) that an unseen `InternetService` category returns 200
with a valid prediction, and that `SeniorCitizen=5`, negative
`tenure`, and negative `MonthlyCharges` are all correctly rejected with
422 by Pydantic's field validators before ever reaching the model. See
`tests/test_api.py::TestPredictEndpointEdgeCases`. No action needed.

---

## Issue #17 -- Model Training & Prediction

### Finding 6: `add_tenure_bucket()` has an open top bin -- `tenure_months > 72` silently becomes `NaN`

**Steps to reproduce:**
```python
from training.feature_engineering import add_tenure_bucket
import pandas as pd

df = pd.DataFrame({"tenure_months": [72, 73, 100]})
add_tenure_bucket(df)
# tenure_months=72  -> TenureBucket="49+"   (correct, inclusive)
# tenure_months=73  -> TenureBucket=NaN     (silently unbucketed)
# tenure_months=100 -> TenureBucket=NaN     (silently unbucketed)
```

**Expected behaviour:** Every valid `tenure_months` value should map to
exactly one `TenureBucket` label. The current dataset's real maximum
is 72 months, so this has not caused a visible problem yet, but the
function does not itself guard against or document this ceiling.

**Actual behaviour:** `bins=[-1, 12, 24, 48, 72]` in
`training/feature_engineering.py::add_tenure_bucket` leaves the top of
the range open (`pd.cut`'s default behaviour for values above the
highest bin edge is `NaN`). Any future customer record with
`tenure_months > 72` (a new customer eventually will cross this
threshold as the business ages, or if this code is reused on a
dataset with a longer observation window) will silently get a null
`TenureBucket`, which then becomes a null/NaN category during one-hot
encoding rather than a validation error.

**Test coverage:** Confirmed directly and left as an inline discovery
during this issue's testing; not separately unit-tested in
`tests/test_models.py` because it is exercised indirectly by every
`predict()` call using realistic tenure values (0-72), which is the
full range currently possible in production. Flagging in this document
per Issue #13/#17's "document rather than silently patch" instruction,
since `training/feature_engineering.py` belongs to Latifah's `training/`
ownership, not Theresia's test-authoring scope.

**Recommendation:** Add an explicit upper bin (e.g. `bins=[-1, 12, 24,
48, 72, float("inf")]` with a `"72+"` label replacing `"49+"`, or
similar) so no valid tenure value can ever fall outside the defined
buckets.

---

### Finding 7: a missing field vs. a `None` field in `predict()` fail very differently

**Steps to reproduce:**
```python
from predict import predict

payload = {...}  # valid payload
del payload["tenure"]
predict(payload)  # raises KeyError: 'tenure' -- names the missing field clearly

payload2 = {...}  # valid payload
payload2["tenure"] = None
predict(payload2)  # raises TypeError: '<' not supported between instances of 'NoneType' and 'NoneType'
```

**Expected behaviour:** Per Issue #17's acceptance criteria, a
customer record with missing or null fields should either raise a
clear validation error, or be handled per a documented strategy.

**Actual behaviour:** A **missing** field produces a `KeyError`
naming the exact field that's absent -- this is a reasonably clear
error. A **present-but-`None`** field for `tenure` produces a much
less clear `TypeError` from deep inside `pandas.cut`'s internal
comparison logic (triggered by
`training/feature_engineering.py::add_tenure_bucket`), which does not
name the offending field or explain that the root cause is a null
value. Both cases correctly *fail* rather than silently producing a
wrong prediction (confirmed -- see Finding 8), but the error quality
differs substantially between the two.

**Test coverage:**
- `tests/test_models.py::TestPredictEdgeCases::test_predict_with_missing_field_raises_clear_error`
- `tests/test_models.py::TestPredictEdgeCases::test_predict_with_null_tenure_raises_rather_than_silently_mispredicting`

**Recommendation:** Add explicit input validation at the top of
`predict()` (or in `_adapt_api_fields_to_training_schema`) that checks
for `None` values and raises a named `ValueError` before any
downstream processing -- unifying both failure modes into one clear,
predictable error type. This is a `predict.py`-ownership decision
(Latifah/Praise per the Issue #14 adapter), not made unilaterally
here.

---

### Finding 8: (confirmation, not a bug) a null value in an optional categorical field does not silently mispredict

A `None` value in a non-tenure categorical field (e.g.
`OnlineSecurity`) passes through to the one-hot encoder as a NaN
category and does not raise, and does not produce an out-of-range
result. Confirmed directly. See
`tests/test_models.py::TestPredictEdgeCases::test_predict_with_null_optional_service_field_does_not_silently_mispredict`.
No action needed, but worth knowing this is inconsistent with the
`tenure` case above (Finding 7) -- one field-type fails loudly, the
other silently accepts a null. Recommend the team decide whether ALL
null fields should be rejected uniformly, or whether the current
mixed behaviour is acceptable.

---

### Finding 9: two separate `predict()` implementations exist; only one is actually used

**Steps to reproduce:** Compare `predict.py` (repo root) with
`training/predict.py`. Both define a function named `predict(customer_data: dict) -> dict`
with a near-identical body and docstring style, but:
- Repo-root `predict.py` includes `_adapt_api_fields_to_training_schema()`,
  the Issue #14 adapter that translates `CustomerPredictionRequest`
  field names/casing into the DB/training column convention.
- `training/predict.py` does **not** include this adapter -- it
  expects input already in the DB-column shape.

`app/api/routes.py` imports only from repo-root `predict.py`
(confirmed via `ast`-based static analysis in
`tests/test_models.py::TestTrainingPredictDeprecationFlag::test_app_package_does_not_import_training_predict`,
which passes today and will fail loudly if this ever changes).

**Expected behaviour:** One clear, single, documented prediction
entry point per the Project Specification's "known interface
contracts" table (section 4), which names `predict()`'s return shape
as a locked interface but does not mention two separate modules.

**Actual behaviour:** `training/predict.py` appears to be an earlier
or superseded version that was not removed once the repo-root
`predict.py` + Issue #14 adapter became the real, wired-in
implementation. It is currently harmless (nothing imports it), but
it's a maintenance/confusion risk -- someone could reasonably import
`training.predict.predict` by mistake in a future feature, bypassing
the Issue #14 adapter entirely and silently breaking the API contract
the moment CustomerPredictionRequest fields are passed to it directly.

**Test coverage:** `tests/test_models.py::TestTrainingPredictDeprecationFlag`
(two tests) -- one confirms `app/` never imports it today, the other
confirms the two functions are NOT interchangeable (documenting
exactly why swapping one for the other would silently break the
adapter contract).

**Recommendation:** Raise with Latifah/Theresia: either delete
`training/predict.py` entirely, or add a clear module-level docstring
marking it as superseded/reference-only (the same pattern already
used for `app/services/mock_prediction_service.py`). Not resolved
unilaterally in this PR, per the "flag scope deviations, don't
silently fix" rule (Project_Specification.md section 3).

---

## Note on cross-file test isolation (test-authoring finding, not a production bug)

While validating this test suite against a fully fresh clone (no
`database/churn.db`, no `models/best_model.pkl`), an issue was found
and fixed in `tests/test_models.py` itself, not in production code:
its `requires_populated_db` skip guard originally only checked whether
`database/churn.db` **existed**, not whether it actually contained
customer rows. Because `pytest` runs all three test files in one
session, `tests/test_etl.py`'s idempotency tests
(`TestDatabaseIdempotency`) call `init_db()`, which creates an empty
schema-only `database/churn.db` as a side effect if one doesn't
already exist. When `tests/test_models.py` ran afterward in the same
session, its file-existence check passed even though the database had
zero rows, causing training to be attempted against an empty dataset
and fail with a confusing `sklearn` `ValueError` instead of skipping
cleanly with a clear reason.

**Fixed** by changing the guard to check `SELECT COUNT(*) FROM
customers > 0`, matching the more correct pattern already used in
`tests/test_etl.py`. Confirmed via a full clean-room re-run (deleting
all generated artifacts and running `pytest tests/` fresh) that the
suite now exits 0 and skips gracefully in that state. Recorded here
because it's a good example of why running the *entire* suite
together, not just each file in isolation, matters before signing off.

---

## Cross-Cutting -- Discovered While Validating All Three Suites Together

The two findings below were not tied to writing tests for a single
issue -- they surfaced as `pytest` warnings only after running all
three suites together with `pytest.ini` correctly in place, and each
touches a file owned outside the three testing issues (Finding 10:
`app/schemas/`, jointly Praise/Theresia; Finding 11: `etl/`, Mercy's).
Kept as their own section rather than folded into #13/#16/#17 above so
it's clear neither is a `test_etl.py`/`test_api.py`/`test_models.py`
authorship finding -- both are dependency-version/deprecation findings
about the underlying implementation files.

### Finding 10: `CustomerPredictionRequest`/`CustomerPredictionResponse` `Field(..., example=...)` kwargs are deprecated in Pydantic V2

**Steps to reproduce:** run the full suite with default warning
visibility (`pytest tests/ -W default`) against a Pydantic V2
environment. Every field in `app/schemas/customer_schema.py` that
passes `example=...` directly to `Field(...)` raises
`PydanticDeprecatedSince20`.

**Expected behaviour:** no deprecation warnings from a schema file
that's otherwise fully valid Pydantic V2 code.

**Actual behaviour:** confirmed against Pydantic's own migration guide
(<https://pydantic.dev/docs/validation/latest/get-started/migration/#changes-to-pydanticfield>):
*"`Field` no longer supports arbitrary keyword arguments to be added
to the JSON schema. Instead, any extra data you want to add to the
JSON schema should be passed as a dictionary to the
`json_schema_extra` keyword argument."* Every `example=` kwarg in both
`CustomerPredictionRequest` and `CustomerPredictionResponse` (20
fields total) triggers this. It's cosmetic today -- the schema still
validates and serializes correctly, and this doesn't affect any test
result -- but Pydantic's own docs mark `example=` for eventual removal
in V3, at which point this would become a hard error, not a warning.

**Owner note:** `app/schemas/customer_schema.py` is jointly owned --
originally Praise's Issue #10 deliverable, later repaired by Theresia
(per the file's own docstring: *"STATUS: repaired by Theresia"*).
Since I (Theresia) touched this file last, I'm claiming this one as
mine to fix rather than only flagging it for Praise -- noting it here
for the record and for Praise's visibility, but I'll handle the actual
fix.

**Recommended fix** (mechanical, one line per field):
```python
# Before:
gender: str = Field(..., description="...", example="Female")

# After:
gender: str = Field(..., description="...", json_schema_extra={"example": "Female"})
```
Applies to all 18 fields in `CustomerPredictionRequest` and both
fields in `CustomerPredictionResponse`. No behavioural change -- purely
a kwarg migration.

---

### Finding 11: `etl/clean_data.py`'s `select_dtypes(include="object")` is deprecated under pandas 3.x string-dtype migration

**Steps to reproduce:** run the full suite with default warning
visibility on an environment with `pandas>=3.0` installed. The line
`object_columns = df.select_dtypes(include="object").columns` in
`etl/clean_data.py` raises `Pandas4Warning`.

**Expected behaviour:** no deprecation warnings from a stable,
already-merged ETL file.

**Actual behaviour:** confirmed against pandas' own migration guide
(<https://pandas.pydata.org/docs/user_guide/migration-3-strings.html#string-migration-select-dtypes>):
pandas 3's new string dtype means `"object"` and `"str"` are no longer
reliably the same selector, and `select_dtypes(include="object")` is
deprecated in favour of being explicit about which one is meant. This
is purely a forward-compatibility warning today -- `requirements.txt`
pins `pandas` with no upper bound, so any environment that resolves to
pandas 3.x will show this, while one on pandas 2.x will not. It does
not affect current correctness; all `tests/test_etl.py` assertions
about whitespace-stripping on string columns still pass either way.

**Owner note:** `etl/clean_data.py` is Mercy's Issue #8 deliverable.
Flagging for Mercy to decide the fix, per the "document, don't
silently patch other owners' files" rule -- not changed as part of
this testing PR.

**Recommended fix** (Mercy to confirm/apply): replace
`include="object"` with an explicit selector that covers both legacy
object-dtype strings and pandas 3's new native string dtype, e.g.
`include=["object", "string"]`, so the same line behaves identically
whether the running environment resolves pandas 2.x or 3.x.

---

## Issue #19 — Full Regression Pass

> **STATUS: HISTORICAL RECORD — superseded in part. Do not read this
> section as a statement about the current tree.**
>
> The run described below was performed on **2026-07-29**, after Issues
> #13/#14/#16/#17 were merged. On **2026-08-12** the mentor's stretch
> commit `806705c` added pagination to
> `CustomerRepository.get_all()` (default page size 100) without
> re-running these checks. `kpi_service.get_kpis()` had been computing
> the executive KPIs from `get_all()` with no arguments, so from that
> commit onward `/kpis` summarized **only the first 100 rows** and
> presented them as the whole population — on the tracked dataset it
> returned `customer_count: 100` and `overall_churn_rate: 100.0`. No
> test caught it: the KPI tests asserted the response keys and that
> churn + retention sums to ~100, a check that `100.0 + 0.0` satisfies
> trivially. Both endpoint verification scripts therefore also failed
> from that date (16 passed / 3 failed for `verify_endpoints.sh` as
> measured on 2026-10-05).
>
> **This is an aggregate-path regression introduced after the pass
> below, not a defect in the pass itself.** It was found during the
> post-sprint gap audit and repaired in Phase 1 (audit item FGA-01,
> 2026-10-05): `/kpis` now reads a single whole-table SQL aggregate
> (`CustomerRepository.get_kpi_aggregate()`), `/customers` keeps its
> paginated default, and `tests/test_kpi_aggregate.py` plus new
> `/kpis` population guards in `tests/test_api.py` fail loudly if the
> service ever reads only a page again. The verification scripts were
> rewritten to assert the current contract (FGA-02).
>
> **Pass/skip counts are deliberately not restated here.** A clean,
> artifact-present re-run is part of Phase 4; until that run exists,
> the counts below are a dated historical result only.

**Scope note:** this section covers the full-system regression pass
performed after Issues #13, #14, #16, and #17 were all merged, owned
by Theresia. Issue #19's own mandate explicitly authorizes editing
the existing test suite directly during this final pass — unlike
Issues #13/#16/#17, which were each scoped to one component's test
file under strict single-owner authorship rules (spec section 2.6),
this issue exists specifically to catch and close cross-suite gaps
the component-level passes couldn't see, including in files owned by
others. Findings 12 and 15 below are both fixed directly under that
mandate; Finding 14 is documented only, since it sits in `training/`
(Latifah's Issue #11 ownership) rather than in the test suite itself,
and is scoped to Issue #20 (final integration/cleanup) rather than to
this pass.

### Finding 12: `tests/test_sql_views.py` (Salome, Issue #9) had no skip-guard — the only one of the four test files that hard-failed on a fresh clone instead of skipping

**Steps to reproduce:**
```bash
git clone <repo> && cd <repo>
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

**Expected behaviour:** Every test in the suite that depends on
`database/churn.db` (or a model artifact) existing should skip with a
clear reason on a fresh clone with no pipeline run yet — this is
already the established pattern in `tests/test_etl.py`
(`requires_populated_db`), `tests/test_api.py`
(`requires_app_dependencies`), and `tests/test_models.py`
(`requires_model_artifact`/`requires_populated_db`).

**Actual behaviour:** `tests/test_sql_views.py` (originally Salome's,
Issue #9 — the views themselves are her deliverable per spec section
2.2) had no `pytest` import, no marker, and no skip-guard at all —
confirmed via direct inspection, it was the only one of the four test
files structured this way. On a fresh clone, all 6 of its tests
hard-failed: `test_view_churn_by_contract_exists` /
`test_view_churn_by_tenure_bucket_exists` failed on `assert
cursor.fetchone() is not None`, and the other four failed with
`sqlite3.OperationalError: no such table: view_churn_by_contract` /
`view_churn_by_tenure_bucket`. This produced exactly the confusing
failure mode (raw `sqlite3` errors instead of a clear skip reason)
that the other three files were specifically designed to avoid — see
Finding 4's discussion of the same principle. Confirmed the
underlying view definitions themselves are correct: once the full
pipeline is run (`init_db.py` → `load_to_db.py` → `init_views.py` →
`evaluate_models.py`), all 87 tests in the suite pass, including all
6 original assertions in this file unchanged. This was a test-suite
gap, not a product bug — `sql/views.sql` and `database/init_views.py`
are both correct as shipped.

**Test coverage:** Rewrote `tests/test_sql_views.py` with a
`requires_views` skip-guard following the exact idiom already used in
the other three files (checks `database/churn.db` exists AND both
`view_churn_by_contract`/`view_churn_by_tenure_bucket` exist in
`sqlite_master` before running). Verified against three real pipeline
states — empty clone, schema-initialized-but-no-views, and fully
populated — confirming clean skip / partial-idempotency-only-run /
full-pass behaviour at each stage respectively. All 6 original
assertions are preserved unchanged; the guard, an import of the
shared `database.db_connection.get_connection` (replacing a
second local copy of the same connection logic, matching the
convention already used in `test_etl.py`), and file organization
(grouped into `TestViewsExist` / `TestViewsReturnData` /
`TestViewSchemas` classes, matching the class-based structure already
used in `test_api.py`/`test_models.py`) were added.

**Recommendation:** Fixed directly as part of this regression pass,
under Issue #19's explicit authorization to edit the test suite during
the final pass. Not a Finding-10-style "joint owner claiming a fix" —
Theresia is not a joint owner of this file the way she is of
`customer_schema.py`; the authority here comes from Issue #19 itself,
scoped to this pass only.

---

### Finding 13: `database/init_views.py` (Mercy, Issue #8) had no idempotency test, unlike its `init_db.py` counterpart

**Steps to reproduce:** Compare `tests/test_etl.py`'s
`TestDatabaseIdempotency` class (covers `init_db()` — checks it can
run twice without error and doesn't duplicate tables) against any
existing coverage of `init_views()`. `grep -rn "init_views"
tests/` returned exactly one hit before this pass: a docstring comment
in `test_etl.py` mentioning it as a pipeline step, never an actual
call or assertion.

**Expected behaviour:** `init_views.py`'s own docstring states it "is
idempotent by dropping existing views before recreating them" — the
same claim `init_db.py` makes about itself, and that claim IS tested
for `init_db.py`. The equivalent claim for `init_views.py` was
untested.

**Actual behaviour:** Confirmed by direct execution that
`init_views()` is in fact safely idempotent (calling it twice
back-to-back does not raise, and both views remain queryable
afterward) — so this is a coverage gap, not a bug. Found only because
the walkthrough explicitly called for running the pipeline steps in
sequence and checking each one, rather than just running the test
suite in isolation.

**Test coverage:** Added
`tests/test_sql_views.py::TestViewsIdempotency::test_init_views_can_run_twice_without_error`,
mirroring `TestDatabaseIdempotency`'s pattern. Requires only that
`database/churn.db` exist (schema initialized) — does not require
the `customers` table to be populated, since `init_views()`'s own
`CREATE VIEW` DDL only requires the table to exist, not contain rows.

**Recommendation:** Fixed directly, same authorization as Finding 12
— this is new test coverage added to the test suite during the final
pass, not an edit to `database/init_views.py` itself (which was not
touched).

---

### Finding 14: three `training/` functions have untyped parameters, against the project's own established typing convention

**Steps to reproduce:** AST-based scan of every function definition
in all 28 project-owned `.py` files for missing parameter or return
annotations (excluding `self`/`cls` and standard pytest fixture
injections like `tmp_path`).

**Expected behaviour:** Project_Specification.md section 3 states
"Typing: every function has type hints. No exceptions." The
project's own `training/` files already follow this rigorously
elsewhere — e.g. `training/preprocessing.py`'s
`build_preprocessor(X: pd.DataFrame) -> ColumnTransformer`.

**Actual behaviour:** Three functions in Latifah's `training/`
files (Issue #11 ownership, per spec section 2.4) don't follow that
same convention:

| File | Function | Missing |
|---|---|---|
| `training/train_test_split.py` | `split_training_data()` | return annotation |
| `training/train_models.py` | `train_single_model(model_name, model, preprocessor, X_train, y_train)` | `model`, `preprocessor`, `X_train`, `y_train` |
| `training/evaluate_models.py` | `evaluate_model(model_name, model, X_test, y_test)` | `model`, `X_test`, `y_test` |

Traced call sites to confirm the correct types: `model` is one of the
five sklearn/XGBoost/LightGBM estimator instances constructed in
`train_models()` (`sklearn.base.ClassifierMixin` covers all five
uniformly); `preprocessor` is the `ColumnTransformer` returned by
`training/preprocessing.py::build_preprocessor`; `X_train`/`X_test`
are `pd.DataFrame`; `y_train`/`y_test` are `pd.Series` (all confirmed
against `split_training_data()`'s actual return values, which come
from `sklearn.model_selection.train_test_split` on a DataFrame/Series
pair).

**Severity: Low.** No behavioral impact — every affected function
runs correctly today and is exercised successfully by
`tests/test_models.py::TestTrainingPipelineEndToEnd`. This is purely a
cross-cutting-standards gap (spec section 3) against the project's
own typing convention, not a correctness defect.

**Test coverage:** N/A — this is a typing gap, not a behavioral bug;
no test currently checks type annotations (nor would that typically
be tested at runtime — this was found via static AST analysis, not a
failing test).

**Recommendation:** Mechanical, no behavioral change:
```python
# training/train_test_split.py
from sklearn.compose import ColumnTransformer

def split_training_data() -> tuple[
    pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, ColumnTransformer
]:
    ...

# training/train_models.py
from sklearn.base import ClassifierMixin

def train_single_model(
    model_name: str,
    model: ClassifierMixin,
    preprocessor: ColumnTransformer,
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> Pipeline:
    ...

# training/evaluate_models.py
def evaluate_model(
    model_name: str,
    model: ClassifierMixin,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    ...
```
**Not fixed here.** `training/` belongs to Latifah (Issue #11), and
per the "document, don't silently patch another owner's file" rule
already applied to Findings 6, 7, and 9, this is documented rather
than corrected in this pass. **Fixed in Issue #20** (final
integration pass / repo-wide cleanup and standards sign-off, owned by
Theresia), where the full codebase's typing/logging/print compliance
gets a final, authoritative sweep and any remaining gaps like this
one are resolved directly rather than only flagged.

---

### Finding 15: `tests/test_api.py`'s `client` fixture had no return type annotation, which cascaded into every test method using it

**Steps to reproduce:** Same AST scan as Finding 14, scoped to
`tests/test_api.py`.

**Actual behaviour:** The `client` fixture
(`tests/test_api.py`, `@pytest.fixture() def client(monkeypatch:
pytest.MonkeyPatch):`) had no return annotation. Because every one of
the 30 test methods in the file receives `client` as a parameter, the
AST scan flagged 30 "missing param" instances plus the fixture itself
— but these all trace back to this one root cause, not 31 independent
gaps.

**Expected behaviour:** Consistent with section 3's "every function
has type hints, no exceptions," the fixture itself should be
annotated, and each consuming test's `client` parameter annotated to
match.

**Test coverage / fix:** Fixed directly. `tests/test_api.py` was
authored this sprint by Theresia (standing in for Pamela, who was
unavailable) — not carried over from anyone else — so this sits
squarely within the same edit authority as Findings 12/13, without
even needing Issue #19's broader final-pass mandate to justify it.
Added a `TYPE_CHECKING`-guarded import of `fastapi.testclient.TestClient`
at module level (safe under this file's existing `from __future__
import annotations`, so it does not reintroduce the model-loading
import at collection time that the fixture's own docstring
specifically avoids), annotated the fixture as `-> "TestClient"`, and
annotated all 30 consuming test methods as `client: "TestClient"`.
Verified: the file still collects and skips correctly with no model
artifact present (confirms the `TYPE_CHECKING` import is never
evaluated at runtime), and the three `/health` tests pass for real
against a live `TestClient` instance once a minimal app stub and the
skip-guard's required files are in place.

**Recommendation:** No further action — fixed in this pass.

---


| # | Component | Severity | Status |
|---|---|---|---|
| 1 | `etl/clean_data.py` -- missing `count` column raises raw `KeyError` | Low (only affects non-standard input) | Documented, test pins current behaviour |
| 2 | `etl/clean_data.py` -- literal `""` not normalized by `fillna` | Low (harmless with current input source) | Documented, test pins current behaviour |
| 3 | `sql/schema.sql` CHECK constraints | N/A | Confirmed working correctly |
| 4 | `app/api/routes.py` + `predict.py` -- app import fails entirely if model artifact missing | Medium (health check should arguably survive this) | Documented, test suite skips gracefully around it |
| 5 | `/predict` unseen-category / out-of-range handling | N/A | Confirmed working correctly |
| 6 | `training/feature_engineering.py` -- open top tenure bin | Low today, latent risk as data ages | Documented |
| 7 | `predict.py` -- missing vs. null field error clarity mismatch | Medium | Documented, both pinned by tests |
| 8 | `predict.py` -- null optional categorical field handling | N/A | Confirmed working correctly, inconsistency with Finding 7 noted |
| 9 | `training/predict.py` vs. root `predict.py` duplication | Medium (maintenance/confusion risk, not currently exploitable) | Documented, guarded by a live regression test |
| 10 | `app/schemas/customer_schema.py` -- deprecated `Field(example=...)` kwargs (Pydantic V2) | Low (cosmetic today, breaks under Pydantic V3) | Documented; Theresia (joint owner) claiming the fix |
| 11 | `etl/clean_data.py` -- deprecated `select_dtypes(include="object")` (pandas 3.x) | Low (cosmetic today, environment-dependent) | Documented, flagged for Mercy |
| 12 | `tests/test_sql_views.py` (Salome) — no skip-guard, hard-fails on fresh clone | Medium (blocked a clean regression pass; product code unaffected) | **Fixed** — skip-guard added under Issue #19's test-suite edit mandate, verified across 3 pipeline states |
| 13 | `database/init_views.py` (Mercy) — no idempotency test coverage | Low (function itself confirmed safe; coverage gap only) | **Fixed** — `TestViewsIdempotency` added |
| 14 | `training/` (Latifah) — 3 functions with untyped params (`evaluate_models.py`, `train_models.py`, `train_test_split.py`) | Low (no behavioral impact; inconsistent with project's own typing convention) | Documented with exact fix; **fixed in Issue #20** (final integration/cleanup, Theresia) |
| 15 | `tests/test_api.py` (Theresia, this sprint) — `client` fixture lacked return annotation (cascaded to 30 call sites) | Low (no behavioral impact; single root cause) | **Fixed** — fixture and all 30 call sites annotated, verified live |
| 16 | `app/services/kpi_service.py` — `/kpis` computed over `get_all()`'s first page after pagination was added (`806705c`, 2026-08-12) | **High** — a live endpoint reported a 100-row page as the whole population (`customer_count: 100`, `overall_churn_rate: 100.0`) | **Fixed in Phase 1** (2026-10-05, audit item FGA-01) — single whole-table SQL aggregate at the repository boundary; `/customers` pagination deliberately untouched; new `tests/test_kpi_aggregate.py` plus `/kpis` population guards in `tests/test_api.py` |

**On the table above:** rows 1–15 are the record as it stood at the
end of Issue #19 (2026-07-29). Row 16 records a regression that
entered `main` afterwards and was repaired post-sprint. The closing
statement of this table used to read "No blocking issues remain";
that was true of the tree as tested on 2026-07-29 and is **not** a
claim about the tree that shipped on 2026-08-12, nor about the tree
before the Phase 1 repair.

Findings 1-11 are unchanged from the
original three test-authoring issues. Findings 12, 13, and 15
(test-suite gaps discovered during the Issue #19 full regression
pass) were fixed directly as part of this pass, under Issue #19's
explicit authorization for Theresia to edit the test suite during
the final regression pass. Finding 14 is a low-severity typing gap
in `training/` (Latifah's ownership) with no behavioral impact —
documented with an exact recommended fix, and deferred to Issue #20
(final integration/cleanup pass) rather than corrected here, per the
"document, don't silently patch another owner's file" rule. Fact,
for the record: `pytest.ini`'s `filterwarnings =
ignore::DeprecationWarning` / `ignore::UserWarning` was merged to
`main` through the original test-authoring PRs, reviewed and
approved by Michael at the time — it is documented behavior, not an
oversight of this pass. It does mean Findings 10 and 11's warnings
will not surface in a default `pytest` run regardless of
environment; they were originally reproduced with `pytest -W
default` and remain accurate as documented, but a plain `pytest` run
alone will not reveal them going forward — expected, not a
regression.
>
**Full regression pass (Issue #19) — final status AS AT 2026-07-29
(historical; see the status note at the top of this section for what
changed afterwards):**
- **Total tests executed:** 87 (fresh-clone run, full pipeline
  applied) — 21 passed / 60 skipped / 6 failed before this pass's
  fixes; 87 passed / 0 failed / 0 skipped after running the full
  pipeline, consistent across two independent full runs.
- **Fresh-clone-only run (no pipeline yet):** 21 passed, 66 skipped,
  0 failed (60 pre-existing skips + 6 newly-skip-guarded
  `test_sql_views.py` tests; its 7th test,
  `TestViewsIdempotency`, only requires `database/churn.db` to
  exist, so it runs and passes once `init_db.py` alone has been run,
  ahead of the other 6).
- **API endpoint verification:** all 19 checks in
  `scripts/verify_endpoints.ps1` passed **at that date** (health,
  auth on all 4 protected endpoints, real-data checks against Issue
  #10's retired mocks/placeholders, and 422 validation). The scripts
  then drifted: `verify_endpoints.sh` still asserted the
  pre-leakage LightGBM figures, and both scripts asserted a
  whole-table `customer_count` that the paginated `/kpis` no longer
  returned. Both were rewritten in Phase 1 (FGA-02) and now assert
  29 checks against the current contract; they have not yet been
  re-run as a pair on a PowerShell-capable machine.
- **Manual end-to-end walkthrough:** completed in full at that date
  — CSV load →
  ETL → DB population (7,043 rows) → model training (5 models,
  Logistic Regression selected as best) → API startup → all 5
  endpoints verified live → Power BI dashboard connects via ODBC and
  refreshes correctly against a fresh clone, including the
  `ProjectPath` parameter reset (already documented in README Power
  BI setup section 3, confirmed still accurate).
- **Code quality:** zero `print()` statements in project-owned code
  (confirmed via full-repo search). Typing is complete across all
  files except Finding 14's documented gap, deferred to Issue #20.
  Logging coverage confirmed present everywhere it's meaningful; the
  two files with no logger (`database/models.py`,
  `app/schemas/customer_schema.py`) are pure declarative schema
  definitions with no runtime logic to log, and `app/main.py`'s
  `logging` import is solely for `basicConfig()` root-handler setup
  rather than emitting messages itself — none of these are gaps.
- **Remaining issues as recorded then:** none blocking. Finding 14
  (Low severity, documented above with an exact fix) was the only
  open item, assigned to Issue #20 for final resolution. That "none
  blocking" statement is **no longer accurate as a description of the
  shipped tree**: the `/kpis` aggregate regression described at the
  top of this section was live in `main` from 2026-08-12 until the
  Phase 1 repair.