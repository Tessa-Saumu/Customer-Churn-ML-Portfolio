"""
Issue #14 -- Real Integration -- app/services/metrics_service.py

NEW FILE (flagged in PR Notes -- not present in Issue #10's scaffold).

Why this exists: Issue #14 requires /model-metrics to return real
values from evaluation/model_comparison.md (Latifah, Issue #11). That
file is a human-readable Markdown report, not structured data (no
`evaluation/model_comparison.json` or similar was produced by #11).
Per the issue's own instructions -- "Coordinate with Latifah to update
[the artifact], or add a thin adapter layer in the API" -- this is
that adapter, since editing #11's artifact format is out of scope for
this PR and out of this contributor's ownership.

This module ONLY reads app/schemas' locked metric names -- accuracy,
precision, recall, roc_auc -- to keep /model-metrics' response shape
identical to Issue #10 (see routes.py's original placeholder, which
returned exactly these four keys). confusion_matrix and per-model rows
are intentionally not exposed here, since adding them would change the
endpoint's response shape, which Issue #14 explicitly forbids without
cross-team confirmation (Project_Specification.md, section 4).

The loaded prediction pipeline carries its evaluation metrics and the exact
report checksum. This service refuses a report from another fit, even if its
Markdown has valid-looking numbers. Regenerate model and report together and
restart the server after training.
"""

import logging
import hashlib
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Configurable via env var per Issue #14 acceptance criteria ("All
# model artifact paths are configurable and do not depend on one
# developer's machine"), same pattern as predict.py's MODEL_PATH.
MODEL_METRICS_PATH = Path(
    os.environ.get(
        "MODEL_METRICS_PATH",
        str(REPO_ROOT / "evaluation" / "model_comparison.md"),
    )
)

_METRIC_PATTERNS: dict[str, re.Pattern[str]] = {
    "accuracy": re.compile(r"-\s*Accuracy:\s*([0-9.]+)", re.IGNORECASE),
    "precision": re.compile(r"-\s*Precision:\s*([0-9.]+)", re.IGNORECASE),
    "recall": re.compile(r"-\s*Recall:\s*([0-9.]+)", re.IGNORECASE),
    "roc_auc": re.compile(r"-\s*ROC AUC:\s*([0-9.]+)", re.IGNORECASE),
}


def get_model_metrics() -> dict[str, float]:
    """
    Parses the "### Performance" block for the selected model out of
    evaluation/model_comparison.md and returns exactly the four keys
    Issue #10's /model-metrics response shape already committed to:
    accuracy, precision, recall, roc_auc.

    Raises:
        FileNotFoundError: if the evaluation report doesn't exist yet
            (e.g. training hasn't been run locally).
        ValueError: if the report exists but a required metric can't
            be found in it (format drift from what this parser
            expects).
    """
    if not MODEL_METRICS_PATH.exists():
        logger.error("Model metrics report not found at %s", MODEL_METRICS_PATH)
        raise FileNotFoundError(
            f"Model metrics report not found at {MODEL_METRICS_PATH}. "
            "Run the training pipeline (training/evaluate_models.py) first."
        )

    from predict import model

    report_bytes = MODEL_METRICS_PATH.read_bytes()
    metadata = getattr(model, "evaluation_metadata_", None)
    if not metadata or metadata.get("report_sha256") != hashlib.sha256(report_bytes).hexdigest():
        raise ValueError(
            "The evaluation report does not belong to the loaded model. "
            "Run training/evaluate_models.py to regenerate both artifacts, "
            "then restart the API."
        )
    report_text = report_bytes.decode("utf-8")

    metrics: dict[str, float] = {}
    for key, pattern in _METRIC_PATTERNS.items():
        match = pattern.search(report_text)
        if match is None:
            logger.error("Could not parse '%s' from %s", key, MODEL_METRICS_PATH)
            raise ValueError(
                f"Could not parse required metric '{key}' from {MODEL_METRICS_PATH}. "
                "Report format may have changed."
            )
        metrics[key] = float(match.group(1))

    if metrics != metadata["metrics"]:
        raise ValueError("The model's saved metrics do not match its evaluation report.")

    logger.info("Loaded real model metrics from %s: %s", MODEL_METRICS_PATH, metrics)
    return metrics
