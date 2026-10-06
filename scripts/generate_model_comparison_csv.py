"""
generate_model_comparison_csv.py

Reads the model comparison table out of evaluation/model_comparison.md and
produces evaluation/model_comparison.csv for Power BI consumption (Issue #12).

This script does not modify model_comparison.md. It only reads it.
Re-run this any time model_comparison.md changes upstream.

Which table is read (changed 2026-10-06, Phase 3 / FGA-05)
---------------------------------------------------------
The report now contains more than one table: the selected model + baseline
evaluation on the untouched holdout, and the cross-validated selection table.
This script reads the table under the `## Model selection` heading -- the
five candidates plus the naive baseline, one row per model, scored with the
same 5-fold cross-validation over the training portion only.

So the CSV's values are fold means on the *training* portion (ROC AUC is the
mean of the five fold values; confusion-matrix counts are summed across folds).
That is the fair model-versus-model comparison. The selected model's final
holdout metrics are in the Markdown report's "### Performance" block and are
deliberately not mixed into this table.

The CSV column set is unchanged from Issue #12 (`Model`, `Accuracy`,
`Precision`, `Recall`, `ROC_AUC`, `True_Negatives`, `False_Positives`,
`False_Negatives`, `True_Positives`) so the committed Power BI model keeps the
columns it already binds to.

Line endings (fixed 2026-10-06, NEW-10): this script used to emit CRLF while
the committed CSV was LF, so re-running the documented step produced a
whole-file diff even when every value was identical. It now writes exactly
what it prints, with LF line endings.
"""
import re
import csv
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE_MD = Path("evaluation/model_comparison.md")
OUTPUT_CSV = Path("evaluation/model_comparison.csv")

# The report section whose table this script converts. Kept as a constant so
# the coupling is explicit and greppable (see the report's own docstring note).
SELECTION_HEADING = "## Model selection"


def parse_confusion_matrix(raw: str) -> tuple[int, int, int, int]:
    """Parses '[[973, 62], [54, 320]]' -> (TN, FP, FN, TP)."""
    nums = [int(n) for n in re.findall(r"-?\d+", raw)]
    if len(nums) != 4:
        raise ValueError(f"Expected 4 values in confusion matrix, got: {raw}")
    tn, fp, fn, tp = nums
    return tn, fp, fn, tp


def parse_table(
    md_text: str, heading: str = SELECTION_HEADING
) -> list[dict[str, str]]:
    """
    Extracts the first contiguous Markdown table that follows `heading`.

    Raises ValueError if the heading is missing or no table follows it, rather
    than silently returning an empty or partial comparison.
    """
    if heading not in md_text:
        raise ValueError(
            f"Could not find the '{heading}' section in the report. The report "
            "format may have changed -- see training/evaluate_models.py"
            "::write_comparison_report."
        )

    section = md_text.split(heading, 1)[1]
    lines = section.splitlines()

    table_lines: list[str] = []
    for line in lines:
        if not table_lines and not line.strip().startswith("|"):
            continue
        if not line.strip().startswith("|"):
            break
        table_lines.append(line)

    if len(table_lines) < 3:
        raise ValueError(
            f"Could not find a Markdown table with data rows under '{heading}'."
        )

    header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]
    data_lines = table_lines[2:]  # skip header + separator row

    rows = []
    for line in data_lines:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != len(header_cells):
            logger.warning("Skipping malformed row: %s", line)
            continue
        rows.append(dict(zip(header_cells, cells)))
    return rows


def build_csv_rows(table_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for row in table_rows:
        tn, fp, fn, tp = parse_confusion_matrix(row["confusion_matrix"])
        out.append({
            "Model": row["model_name"],
            "Accuracy": row["accuracy"],
            "Precision": row["precision"],
            "Recall": row["recall"],
            "ROC_AUC": row["roc_auc"],
            "True_Negatives": tn,
            "False_Positives": fp,
            "False_Negatives": fn,
            "True_Positives": tp,
        })
    return out


def write_csv(csv_rows: list[dict[str, str]], output_path: Path = OUTPUT_CSV) -> None:
    """Write the rows as LF-terminated CSV (no CRLF) to `output_path`."""
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(csv_rows[0].keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(csv_rows)


def main(output_path: Path = OUTPUT_CSV) -> None:
    if not SOURCE_MD.exists():
        raise FileNotFoundError(f"{SOURCE_MD} not found. Run this from the repo root.")

    md_text = SOURCE_MD.read_text(encoding="utf-8")
    table_rows = parse_table(md_text)
    csv_rows = build_csv_rows(table_rows)

    if not csv_rows:
        raise ValueError("No rows parsed from model_comparison.md — refusing to write an empty CSV.")

    write_csv(csv_rows, output_path)

    logger.info(
        "Wrote %d rows (%s) to %s",
        len(csv_rows),
        f"table under '{SELECTION_HEADING}'",
        output_path,
    )


if __name__ == "__main__":
    # Allow an explicit output path (used by tests); default is the tracked CSV.
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_CSV)
