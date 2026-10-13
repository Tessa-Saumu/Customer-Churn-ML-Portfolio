"""Reject stale reports instead of reporting metrics for another fitted model."""

import hashlib
import sys
from types import SimpleNamespace

import pytest

from app.services import metrics_service


@pytest.fixture
def paired_report(tmp_path, monkeypatch):
    report = tmp_path / "model_comparison.md"
    report.write_bytes(
        b"- Accuracy: 0.8\n- Precision: 0.6\n- Recall: 0.5\n- ROC AUC: 0.85\n"
    )
    metrics = {"accuracy": 0.8, "precision": 0.6, "recall": 0.5, "roc_auc": 0.85}
    metadata = {
        "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        "metrics": metrics,
    }
    monkeypatch.setattr(metrics_service, "MODEL_METRICS_PATH", report)
    monkeypatch.setitem(sys.modules, "predict", SimpleNamespace(
        model=SimpleNamespace(evaluation_metadata_=metadata)
    ))
    return report, metadata


def test_metrics_match_the_loaded_models_evaluation(paired_report):
    _, metadata = paired_report
    assert metrics_service.get_model_metrics() == metadata["metrics"]


def test_restored_or_edited_report_is_rejected(paired_report):
    report, _ = paired_report
    report.write_bytes(report.read_bytes().replace(b"0.85", b"0.95"))
    with pytest.raises(ValueError, match="does not belong to the loaded model"):
        metrics_service.get_model_metrics()


def test_different_models_metadata_is_rejected(paired_report):
    _, metadata = paired_report
    metadata["metrics"]["recall"] = 0.9
    with pytest.raises(ValueError, match="saved metrics do not match"):
        metrics_service.get_model_metrics()
