# Pinned rerun of the legacy protocol — 2026-10-05

This directory holds the output of re-running the **unchanged** legacy protocol
(single stratified 80/20 split, five candidates, winner by ROC AUC on that same
holdout) in the **pinned** environment that Phase 2 established.

| File | What it is |
|---|---|
| `model_comparison.md` | The report `training/evaluate_models.py` produced, captured verbatim |
| `model_comparison.csv` | `scripts/generate_model_comparison_csv.py` run against that report (note: the script writes CRLF line endings, the tracked legacy CSV is LF — see the reproduction record) |
| `training.log` | Full stdout/stderr of the training run, including the 52-used-features LightGBM line and the Logistic Regression `ConvergenceWarning` |

**These were NOT the repository's published metrics, and are not now either.**
At the time of this rerun, `evaluation/model_comparison.md` and `.csv` still held the
legacy committed values, byte-identical to [`../../legacy/`](../../legacy/); Phase 2
recorded this rerun without declaring new metrics. **Phase 3 has since replaced the
protocol and the current report** (see
[`../2026-10-06-phase3-cv-holdout/`](../2026-10-06-phase3-cv-holdout/README.md)), so
treat the single-split numbers below as the predecessor record, not as a reference
the current report should match.

Full environment, commands, timings, checksums and the value-by-value comparison
against the legacy result: [`docs/reproduction_record.md`](../../../docs/reproduction_record.md).

Headline difference: Logistic Regression is selected in both runs; its accuracy is
0.799148 here versus 0.801987 in the legacy file, and its ROC AUC is 0.849562
versus 0.849448. Decision Tree, Random Forest and LightGBM are identical; XGBoost
also moved. That difference is package-version drift, which is exactly what the
pins now freeze.
