# Current evaluation and serving run

Recorded 13 October 2026 on Windows x86_64, **CPython 3.11.12**, with `requirements.txt` and `requirements.lock.txt`. `.python-version` records that patch version. The input is the 7,043-row CSV with SHA-256 `e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34`; dataset redistribution permission remains unconfirmed.

## One current source

`evaluation/model_comparison.md` is the current recorded model comparison and holdout result. Its CSV export represents the **training-side cross-validation comparison**, not the selected model's final holdout scores. Logistic Regression was selected by five-fold training-only cross-validation and refitted before evaluating the selected model and baseline on the untouched 1,409-row holdout.

Current holdout: accuracy **0.8020**, precision **0.6480**, recall **0.5561**, ROC AUC **0.8494**; confusion matrix `[[922,113],[166,208]]`. Baseline accuracy **0.7346**, ROC AUC **0.5000**. No tuning or threshold changes were made. The Logistic Regression fit still reaches its iteration limit; these metrics do not establish future-period performance or a reliable intervention policy.

`models/best_model.pkl` is generated, not committed. Training saves its measured holdout metrics and the exact report checksum inside that fitted pipeline. `/model-metrics` validates both against the model loaded for prediction; stale reports and models without this metadata are rejected. Train the model/report together and restart the API after every new fit. Redirected experiments/tests save both outputs in their own directory and cannot replace the serving artifact.

The 6 October Linux result and earlier single-split result are **historical** in `evaluation/reproduction/` and `evaluation/legacy/`. They are retained for provenance, not as alternate current metrics. Native numerical libraries and the unconverged fit can yield slightly different numbers across systems even with pinned package versions. Another environment should report its own bound model/report pair rather than claim these exact Windows values.

## Reproduce and check

From the repository root, use the supported Python environment to run:

```text
python database/init_db.py
python etl/load_to_db.py
python database/init_views.py
python training/evaluate_models.py
python scripts/generate_model_comparison_csv.py
python -m pytest -q
```

Then start `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` with the configured `API_KEY`. After it is ready, run `scripts/verify_endpoints.ps1` with PowerShell 7 and the same key, or the Bash counterpart with curl/jq. These check API contracts and agreement with the active run; they do not verify a Power BI refresh, Docker or deployment. GitHub Actions account billing remains unchanged and no green remote run is claimed.

Verified on 13 October 2026:

- Full artifact-present suite: **154 passed, 0 failed, 0 skipped** (56.91 seconds).
- Live PowerShell 7 acceptance: **29 passed, 0 failed, 0 skipped**.
- Swapping the active report's ranking metric caused `/model-metrics` to return
  **500**; restoring the exact paired report returned **200**. Prediction and
  metric examples were recaptured from the same canonical model.
- Integration tests redirect the fresh model and report, check that the serving
  model checksum is unchanged, and independently recompute the fresh artifact's
  holdout metrics.
- The complete database initialization, ETL, views, training and CSV-export
  sequence was repeated successfully. The newly saved model's report checksum
  and four measured metrics still match the current report. No historical Linux
  report was restored over this run.

Historical archive files are retained unchanged except for explicit status notes
and the addition of the prior Linux report/CSV recovered from Git. No paid jobs,
provider calls, dashboard refresh, account settings or deployment were used.
