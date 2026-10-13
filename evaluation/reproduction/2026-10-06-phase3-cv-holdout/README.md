# Historical Linux evaluation — 6 October 2026

This directory retains the original log and unchanged prior model report/CSV
from the Linux CPython 3.11.2 run. The report and CSV were recovered from commit
`d8430af` when the active canonical run moved to Windows on 13 October.

The earlier five-fold training-only selection/frozen-holdout protocol selected
Logistic Regression. Its holdout accuracy 0.7991 and ROC AUC 0.8496 are
**historical environment-specific results**, not the current serving scores.
The current result is [evaluation/model_comparison.md](../../model_comparison.md),
with its runtime and model/report pairing documented in
[docs/current_run.md](../../../docs/current_run.md).

No archived model binary is included. Original log bytes are retained for
provenance; this directory must not be used as an active serving report.
