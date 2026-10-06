"""
Phase 2 -- Reproducible input and runtime -- tests/test_reproducibility.py

Guards for the things FLAGSHIP_IMPLEMENTATION_PLAN.md Phase 2 (audit items
FGA-03 and FGA-07) established. Each test maps to a Phase 2 acceptance
criterion; the mapping is in the class docstrings.

    1. TestInputProvenance       the tracked raw input is the exact file the
                                 recorded results were produced from, and the
                                 ignore rules do not contradict its tracked
                                 status (FGA-07).
    2. TestGeneratedArtifacts    generated database/model files stay out of Git
                                 and no secret file is tracked.
    3. TestPinnedRuntime         one supported Python version and one pinned
                                 dependency set, stated consistently across the
                                 manifest, the lock, the version marker, the
                                 README and the container images (FGA-03).
    4. TestEnvironmentFile       no unused variable is presented as a live
                                 setting, and the variables that ARE documented
                                 actually reach the code that reads them
                                 (configuration cleanup from FGA-10).
    5. TestMetricsArtifacts      the committed model comparison stays
                                 byte-identical to its archived legacy copy, so
                                 neither `pytest` nor a local training run can
                                 silently change published metrics.

Everything here is a unit test except the two subprocess-based checks in
TestEnvironmentFile, which import the app and therefore need the model artifact
(same skip-guard pattern as tests/test_api.py).

Run everything:            pytest tests/test_reproducibility.py
Run only unit tests:       pytest tests/test_reproducibility.py -m unit
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RAW_CSV = REPO_ROOT / "data" / "raw" / "telco_churn_raw.csv"
PROVENANCE_DOC = REPO_ROOT / "docs" / "data_provenance.md"
REPRODUCTION_DOC = REPO_ROOT / "docs" / "reproduction_record.md"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
LOCKFILE = REPO_ROOT / "requirements.lock.txt"
PYTHON_VERSION_FILE = REPO_ROOT / ".python-version"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
MAIN_PY = REPO_ROOT / "app" / "main.py"
MODEL_PATH = REPO_ROOT / "models" / "best_model.pkl"
TRACKED_REPORT = REPO_ROOT / "evaluation" / "model_comparison.md"
TRACKED_REPORT_CSV = REPO_ROOT / "evaluation" / "model_comparison.csv"
LEGACY_REPORT = REPO_ROOT / "evaluation" / "legacy" / "model_comparison_single_split.md"
LEGACY_REPORT_CSV = (
    REPO_ROOT / "evaluation" / "legacy" / "model_comparison_single_split.csv"
)

requires_model_artifact = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason=(
        "models/best_model.pkl does not exist. The app loads the model at import "
        "time, so run training/evaluate_models.py first (see README 'Running the "
        "Project')."
    ),
)

# Variables that .env.example used to document but no code ever read. Removed in
# Phase 2; this list keeps them from creeping back in as dead configuration.
KNOWN_DEAD_SETTINGS = ("DATABASE_PATH", "API_HOST", "API_PORT")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_available() -> bool:
    return shutil.which("git") is not None


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _matched_ignore_rule(relative_path: str) -> str | None:
    """
    The .gitignore pattern that decides `relative_path`'s fate, or None if no
    pattern matches. `--no-index` makes git evaluate the rules themselves rather
    than the index, so this also describes paths that are not (yet) tracked.
    A returned pattern starting with `!` means the path is explicitly RE-INCLUDED.
    """
    proc = _git("check-ignore", "-v", "--no-index", relative_path)
    if proc.returncode == 1:  # no pattern matched
        return None
    assert proc.returncode == 0, f"git check-ignore failed: {proc.stderr}"
    first = proc.stdout.strip().splitlines()[0]
    # format: <source>:<lineno>:<pattern>\t<path>
    return first.split("\t")[0].split(":", 2)[2]


def _requirement_lines(path: Path) -> list[str]:
    """Non-empty, non-comment lines of a pip requirements file."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _split_pin(line: str) -> tuple[str, str] | None:
    """`name[extra]==version` -> (normalized name, version); None if not pinned."""
    match = re.fullmatch(r"([A-Za-z0-9_.\-]+)(\[[A-Za-z0-9_,.\-\[\]]+\])?==([^;\s]+)(.*)", line)
    if match is None:
        return None
    name = match.group(1).lower().replace("_", "-")
    return name, match.group(3)


def _env_example_assignments() -> dict[str, str]:
    """`KEY=value` lines in .env.example (comments excluded)."""
    out: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", stripped)
        assert match is not None, f"unparsable non-comment line in .env.example: {line!r}"
        out[match.group(1)] = match.group(2)
    return out


def _environment_names_read_by_source() -> set[str]:
    """Every NAME in os.environ.get / os.getenv / os.environ[...] across the repo."""
    pattern = re.compile(
        r"os\.(?:environ\.get|getenv|environ\[)\(?\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']"
    )
    names: set[str] = set()
    for py_file in REPO_ROOT.rglob("*.py"):
        parts = set(py_file.parts)
        if parts & {".git", "venv", ".venv", "env", "__pycache__", "build", "dist"}:
            continue
        names.update(pattern.findall(py_file.read_text(encoding="utf-8", errors="replace")))
    return names


# ======================================================================
# 1. INPUT PROVENANCE  (FGA-07)
# ======================================================================


@pytest.mark.unit
class TestInputProvenance:
    """
    Acceptance criterion: "The input file is either legally/appropriately tracked
    with a source/version/hash, or obtained through documented permitted steps
    with a checksum check."

    The owner's decision (2026-10-05, recorded in docs/data_provenance.md §3) is
    to keep the file tracked with its source, version and checksum documented,
    because redistribution rights could not be confirmed AND untracking would not
    remove it from public history nor provide a credential-free acquisition path.
    These tests hold that record to the actual bytes.
    """

    def test_tracked_input_exists(self) -> None:
        assert RAW_CSV.exists(), (
            f"{RAW_CSV.relative_to(REPO_ROOT)} is missing. It is tracked on "
            "purpose as the pipeline's only reproduction input -- see "
            "docs/data_provenance.md. If it was deliberately withdrawn, update "
            "that document and these tests in the same change."
        )

    def test_input_checksum_matches_the_recorded_value(self) -> None:
        documented = re.findall(
            r"^\|\s*SHA-256\s*\|\s*`([0-9a-f]{64})`\s*\|",
            PROVENANCE_DOC.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        assert len(documented) == 1, (
            "docs/data_provenance.md must record exactly one SHA-256 row for the "
            f"tracked input; found {len(documented)}."
        )
        assert _sha256(RAW_CSV) == documented[0], (
            "data/raw/telco_churn_raw.csv no longer matches the checksum recorded "
            "in docs/data_provenance.md. Every published metric in this repository "
            "is derived from that exact input: either restore the file or record a "
            "new reproduction (docs/reproduction_record.md) and update the "
            "provenance table together."
        )

    def test_input_shape_matches_the_recorded_values(self) -> None:
        raw = RAW_CSV.read_bytes()
        text = raw.decode("utf-8")
        lines = text.splitlines()
        header = lines[0].split(",")

        assert len(raw) == 1_736_765, "input file size changed"
        assert len(lines) == 7_044, "expected 1 header line + 7,043 data rows"
        assert len(header) == 33, f"expected 33 columns, got {len(header)}"
        assert header[0] == "CustomerID" and header[-1] == "Churn Reason"
        assert b"\r" not in raw, "input line endings changed (expected LF only)"

    def test_provenance_doc_records_source_version_and_status(self) -> None:
        text = PROVENANCE_DOC.read_text(encoding="utf-8")
        # The listing the README links to, the file Kaggle actually serves, the
        # licence string it declares, and an explicit statement that rights are
        # NOT confirmed. Any of these disappearing would make the record
        # look like a cleared-rights claim it is not.
        assert "yeanzc/telco-customer-churn-ibm-dataset" in text
        assert "Telco_customer_churn.xlsx" in text
        assert "Other (specified in description)" in text
        assert "unconfirmed" in text.lower()
        assert _sha256(RAW_CSV) in text

    def test_gitignore_does_not_contradict_the_tracked_input(self) -> None:
        if not _git_available():
            pytest.skip("git is not available")
        rule = _matched_ignore_rule("data/raw/telco_churn_raw.csv")
        assert rule == "!data/raw/telco_churn_raw.csv", (
            "the tracked reproduction input must be explicitly re-included by "
            f".gitignore (found rule {rule!r}). Before Phase 2 the rules ignored "
            "it while Git tracked it, which is the contradiction STRUCTURE.md "
            "then described as intentional."
        )

    def test_other_raw_downloads_are_still_ignored(self) -> None:
        if not _git_available():
            pytest.skip("git is not available")
        for candidate in ("data/raw/download.csv", "data/raw/Telco_customer_churn.xlsx"):
            assert _matched_ignore_rule(candidate) == "data/raw/*", (
                f"{candidate} should be ignored by the data/raw/* rule"
            )


# ======================================================================
# 2. GENERATED ARTIFACTS AND SECRETS
# ======================================================================


@pytest.mark.unit
class TestGeneratedArtifacts:
    """
    Acceptance criteria: "The complete local path works from a clean checkout
    without undocumented model/database files" and "no secret is committed".
    Generated binaries must stay ignored; the input must not.
    """

    @pytest.mark.parametrize(
        "relative_path",
        ["database/churn.db", "models/best_model.pkl", ".env"],
    )
    def test_generated_or_secret_paths_are_ignored(self, relative_path: str) -> None:
        if not _git_available():
            pytest.skip("git is not available")
        assert _matched_ignore_rule(relative_path) is not None, (
            f"{relative_path} is not covered by .gitignore"
        )

    def test_no_secret_or_generated_file_is_tracked(self) -> None:
        if not _git_available():
            pytest.skip("git is not available")
        tracked = _git("ls-files").stdout.split()
        forbidden = {
            ".env",
            ".env.local",
            "database/churn.db",
            "models/best_model.pkl",
        }
        assert not (set(tracked) & forbidden), (
            f"generated/secret files are tracked: {sorted(set(tracked) & forbidden)}"
        )
        assert ".env.example" in tracked, "the template must stay committed"

    def test_env_example_ships_a_placeholder_key_not_a_secret(self) -> None:
        assignments = _env_example_assignments()
        assert assignments["API_KEY"] == (
            "replace-with-a-real-key-before-running-locally"
        ), ".env.example must not contain a usable key"


# ======================================================================
# 3. PINNED RUNTIME  (FGA-03)
# ======================================================================


@pytest.mark.unit
class TestPinnedRuntime:
    """
    Acceptance criterion: "One supported Python/dependency combination is stated
    and installed from the committed manifest/lock."
    """

    def test_python_version_marker_is_recorded(self) -> None:
        assert PYTHON_VERSION_FILE.exists(), ".python-version is missing"
        version = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
        assert re.fullmatch(r"3\.\d+\.\d+", version), (
            f".python-version should hold an exact patch version, got {version!r}"
        )

    def test_supported_version_is_stated_consistently(self) -> None:
        """`.python-version`, the README prerequisite and the container base images
        must all name the same major.minor runtime."""
        supported = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
        major_minor = ".".join(supported.split(".")[:2])

        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        documented = re.findall(r"\*\*Python (\d+\.\d+)(?:\.\d+)?\*\*", readme)
        assert documented, "README Prerequisites must state a Python version"
        assert set(documented) == {major_minor}, (
            f"README documents Python {sorted(set(documented))} but the supported "
            f"runtime is {major_minor} (.python-version)"
        )

        for dockerfile in ("Dockerfile", "Dockerfile.streamlit"):
            text = (REPO_ROOT / dockerfile).read_text(encoding="utf-8")
            bases = re.findall(r"^FROM python:(\d+\.\d+)-slim", text, flags=re.MULTILINE)
            assert bases, f"{dockerfile} has no python:<ver>-slim base image"
            assert set(bases) == {major_minor}, (
                f"{dockerfile} builds on Python {sorted(set(bases))} but the "
                f"supported runtime is {major_minor}"
            )

    def test_every_direct_requirement_is_pinned_exactly(self) -> None:
        lines = _requirement_lines(REQUIREMENTS)
        assert lines, "requirements.txt has no requirement lines"
        unpinned = []
        for line in lines:
            if line.startswith("-"):  # e.g. the -c lock reference
                continue
            if _split_pin(line) is None:
                unpinned.append(line)
        assert not unpinned, (
            "every direct dependency must be pinned with == so a reproduced "
            f"metric is interpretable; unpinned lines: {unpinned}. See "
            "FLAGSHIP_GAP_AUDIT.md FGA-03."
        )

    def test_manifest_references_the_lock_as_constraints(self) -> None:
        lines = _requirement_lines(REQUIREMENTS)
        assert any(
            line.replace(" ", "") in ("-crequirements.lock.txt",) for line in lines
        ), (
            "requirements.txt must constrain itself with -c requirements.lock.txt "
            "so a plain `pip install -r requirements.txt` is deterministic"
        )

    def test_lock_file_is_fully_pinned(self) -> None:
        assert LOCKFILE.exists(), "requirements.lock.txt is missing"
        lines = _requirement_lines(LOCKFILE)
        assert len(lines) >= 40, (
            f"the lock should hold the full transitive closure, got {len(lines)} lines"
        )
        unpinned = [line for line in lines if _split_pin(line) is None]
        assert not unpinned, f"unpinned lock entries: {unpinned}"

    def test_direct_pins_agree_with_the_lock(self) -> None:
        locked = dict(
            pin for pin in (_split_pin(line) for line in _requirement_lines(LOCKFILE)) if pin
        )
        direct = dict(
            pin
            for pin in (
                _split_pin(line)
                for line in _requirement_lines(REQUIREMENTS)
                if not line.startswith("-")
            )
            if pin
        )
        missing = {name: ver for name, ver in direct.items() if name not in locked}
        assert not missing, f"direct pins absent from the lock: {missing}"
        mismatched = {
            name: (ver, locked[name])
            for name, ver in direct.items()
            if locked[name] != ver
        }
        assert not mismatched, (
            f"requirements.txt and requirements.lock.txt disagree (manifest vs "
            f"lock): {mismatched}. Regenerate the lock from a clean venv built "
            "from requirements.txt."
        )

    def test_reproduction_record_documents_environment_and_input(self) -> None:
        assert REPRODUCTION_DOC.exists(), "docs/reproduction_record.md is missing"
        text = REPRODUCTION_DOC.read_text(encoding="utf-8")
        supported = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
        assert supported in text, "the reproduction record must name the Python version used"
        assert _sha256(RAW_CSV) in text, "the reproduction record must name the input checksum"
        # The recorded package versions must be the committed pins.
        for line in _requirement_lines(REQUIREMENTS):
            if line.startswith("-"):
                continue
            pin = _split_pin(line)
            assert pin is not None
            name, version = pin
            assert version in text, (
                f"the reproduction record does not mention {name}=={version}"
            )


# ======================================================================
# 4. ENVIRONMENT FILE / CONFIGURATION  (FGA-10 configuration cleanup)
# ======================================================================


@pytest.mark.unit
class TestEnvironmentFile:
    """
    Acceptance criterion: "No unused environment variable is presented as a live
    setting, and no secret is committed."
    """

    def test_every_documented_setting_is_read_by_the_code(self) -> None:
        declared = set(_env_example_assignments())
        read = _environment_names_read_by_source()
        unread = sorted(declared - read)
        assert not unread, (
            f".env.example documents settings no module reads: {unread}. Either "
            "wire them up or remove them -- a placeholder that silently does "
            "nothing is how DATABASE_PATH/API_HOST/API_PORT ended up documented."
        )

    def test_known_dead_settings_stay_removed(self) -> None:
        declared = set(_env_example_assignments())
        resurrected = sorted(declared & set(KNOWN_DEAD_SETTINGS))
        assert not resurrected, (
            f"{resurrected} are not read by any module (database/db_connection.py "
            "hardcodes database/churn.db; uvicorn owns host/port via CLI flags). "
            "Do not re-add them without wiring them."
        )

    def test_app_loads_dotenv_before_importing_the_router(self) -> None:
        """
        Structural guard for the ordering fix: app/services/metrics_service.py
        resolves MODEL_METRICS_PATH at import time, and app/api/routes.py imports
        it, so `load_dotenv()` must run first or a .env-supplied value is
        silently ignored while the README documents it as supported.
        """
        tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        dotenv_call = None
        router_import = None
        for index, node in enumerate(tree.body):
            if (
                dotenv_call is None
                and isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", None) == "load_dotenv"
            ):
                dotenv_call = index
            if (
                router_import is None
                and isinstance(node, ast.ImportFrom)
                and node.module == "app.api.routes"
            ):
                router_import = index
        assert dotenv_call is not None, "app/main.py no longer calls load_dotenv()"
        assert router_import is not None, "app/main.py no longer imports the router"
        assert dotenv_call < router_import, (
            "load_dotenv() must run BEFORE `from app.api.routes import router`, "
            "otherwise MODEL_METRICS_PATH (and MODEL_PATH) set in .env are read "
            "too late and silently ignored."
        )


@pytest.mark.integration
@requires_model_artifact
class TestEnvironmentFileTakesEffect:
    """
    Behavioural counterpart to the structural guard above: a value in a real
    `.env` must reach the module that reads it at import time. Runs the import in
    a subprocess, because MODEL_METRICS_PATH is resolved once per process.
    """

    def test_dotenv_value_reaches_the_metrics_service(self, tmp_path: Path) -> None:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            pytest.skip(
                "a real .env exists at the repo root; this test will not overwrite it"
            )

        # A minimal report with unmistakable values, so a pass cannot come from
        # the tracked report happening to be read instead.
        alt_report = tmp_path / "alt_model_comparison.md"
        alt_report.write_text(
            "## Selected Model\n\n### Performance\n\n"
            "- Accuracy: 0.1111\n"
            "- Precision: 0.2222\n"
            "- Recall: 0.3333\n"
            "- ROC AUC: 0.4444\n",
            encoding="utf-8",
        )
        script = (
            "import json, app.main, app.services.metrics_service as m;"
            "print(json.dumps({'path': str(m.MODEL_METRICS_PATH),"
            "'metrics': m.get_model_metrics()}))"
        )
        child_env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"MODEL_METRICS_PATH", "MODEL_PATH", "API_KEY"}
        }
        child_env["PYTHONPATH"] = str(REPO_ROOT)

        env_file.write_text(f"MODEL_METRICS_PATH={alt_report}\n", encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        finally:
            env_file.unlink(missing_ok=True)

        assert proc.returncode == 0, f"importing the app failed:\n{proc.stderr}"
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        assert payload["path"] == str(alt_report), (
            "MODEL_METRICS_PATH from .env did not reach "
            f"app/services/metrics_service.py (it read {payload['path']!r})"
        )
        assert payload["metrics"] == {
            "accuracy": 0.1111,
            "precision": 0.2222,
            "recall": 0.3333,
            "roc_auc": 0.4444,
        }

    def test_env_file_is_not_left_behind(self) -> None:
        assert not (REPO_ROOT / ".env").exists(), (
            "a .env file was left at the repo root by a test run; it is gitignored "
            "but must not persist"
        )


# ======================================================================
# 5. COMMITTED METRICS ARE NOT SILENTLY CHANGED
# ======================================================================


@pytest.mark.unit
class TestMetricsArtifacts:
    """
    Metric-preservation rule (Phase 2), as amended by Phase 3.

    Phase 2 required the committed comparison to stay byte-identical to its
    archived legacy copy. Phase 3 then *deliberately* replaced the published
    protocol (baseline + training-side cross-validation + one frozen holdout
    evaluation, audit item FGA-05), so the tracked report is no longer the
    legacy bytes. What the rule protects now:

    * the legacy single-split bytes stay archived and frozen at their recorded
      hashes, labelled historical (they are evidence, never a current result);
    * the tracked report is the *current* protocol's output and says so;
    * the pinned single-split rerun stays a separately recorded reference.

    Nothing here may move without an explicit, documented replacement.
    """

    # The legacy single-split result is frozen evidence. These are the hashes
    # recorded in evaluation/legacy/README.md and docs/reproduction_record.md.
    LEGACY_REPORT_SHA256 = (
        "a976bb7b75f47a45bf59856c0d8d3c4fcd79700127bf34ff8c3f7ea82073bcf3"
    )
    LEGACY_REPORT_CSV_SHA256 = (
        "04d35816cc5300ee7dad379ed69874b13a2bfe253e28550009cc0fd4247053af"
    )

    def test_archived_legacy_result_stays_frozen(self) -> None:
        assert LEGACY_REPORT.exists(), (
            "evaluation/legacy/model_comparison_single_split.md is missing -- the "
            "legacy result must stay recoverable"
        )
        assert LEGACY_REPORT_CSV.exists()
        assert _sha256(LEGACY_REPORT) == self.LEGACY_REPORT_SHA256, (
            "the archived single-split result changed. It is historical evidence "
            "and must keep its exact bytes; if a new protocol replaces the current "
            "report, archive those bytes separately and label them."
        )
        assert _sha256(LEGACY_REPORT_CSV) == self.LEGACY_REPORT_CSV_SHA256

    def test_tracked_report_is_the_current_protocols_output(self) -> None:
        assert TRACKED_REPORT.exists(), "the current model comparison is missing"
        text = TRACKED_REPORT.read_text(encoding="utf-8")

        # It must be the Phase 3 protocol, and it must not be the legacy bytes.
        assert _sha256(TRACKED_REPORT) != self.LEGACY_REPORT_SHA256, (
            "evaluation/model_comparison.md is byte-identical to the archived "
            "legacy result, so the Phase 3 protocol's output was never published."
        )
        assert "## Model selection" in text, (
            "the current report must carry the cross-validated selection table "
            "(Phase 3 / FGA-05)"
        )
        assert "cross-validation" in text.lower()
        assert "untouched holdout" in text.lower(), (
            "the report must state that the holdout is evaluated once, after "
            "selection -- that is the point of the Phase 3 protocol"
        )
        assert "DummyClassifier" in text and "baseline" in text.lower(), (
            "the report must include the naive baseline"
        )

    def test_tracked_csv_matches_the_current_report(self) -> None:
        """The CSV is generated from the report's selection table, not hand-made."""
        assert TRACKED_REPORT_CSV.exists()
        assert _sha256(TRACKED_REPORT_CSV) != self.LEGACY_REPORT_CSV_SHA256, (
            "evaluation/model_comparison.csv still holds the archived legacy "
            "values while the report has moved on"
        )

        script = REPO_ROOT / "scripts" / "generate_model_comparison_csv.py"
        spec = importlib.util.spec_from_file_location(
            "generate_model_comparison_csv", script
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        report_text = TRACKED_REPORT.read_text(encoding="utf-8")
        rows = module.build_csv_rows(module.parse_table(report_text))
        tracked_csv = TRACKED_REPORT_CSV.read_text(encoding="utf-8").splitlines()

        # Line endings are checked on the RAW bytes: `splitlines()` strips "\r",
        # so a text-mode check here would pass even for a CRLF file (verified by
        # a negative control that converted the committed CSV to CRLF).
        assert b"\r" not in TRACKED_REPORT_CSV.read_bytes(), (
            "the committed CSV must use LF line endings (NEW-10)"
        )

        assert len(rows) == len(tracked_csv) - 1, (
            "the committed CSV has a different number of model rows than the "
            "report's selection table"
        )
        for row, csv_line in zip(rows, tracked_csv[1:]):
            expected = ",".join(str(row[column]) for column in row)
            assert csv_line == expected, (
                f"the committed CSV row {csv_line!r} does not match the report "
                f"row {expected!r}. Re-run scripts/generate_model_comparison_csv.py."
            )

    def test_csv_generator_writes_lf_line_endings(self, tmp_path: Path) -> None:
        """
        NEW-10's actual fix, checked on the generator's own output rather than on
        whatever happens to be committed.

        Before 2026-10-06 the script used csv.DictWriter's default lineterminator
        ("\r\n") while the committed CSV was LF, so re-running the documented
        step produced a whole-file diff even when every value was identical.
        """
        script = REPO_ROOT / "scripts" / "generate_model_comparison_csv.py"
        spec = importlib.util.spec_from_file_location(
            "generate_model_comparison_csv", script
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        rows = module.build_csv_rows(
            module.parse_table(TRACKED_REPORT.read_text(encoding="utf-8"))
        )
        output = tmp_path / "generated.csv"
        module.write_csv(rows, output)

        raw = output.read_bytes()
        assert b"\r" not in raw, (
            "scripts/generate_model_comparison_csv.py is writing CRLF again, which "
            "makes a re-run of the documented CSV step dirty the whole file (NEW-10)"
        )
        assert raw == TRACKED_REPORT_CSV.read_bytes(), (
            "the generator no longer reproduces the committed CSV byte-for-byte; "
            "re-run scripts/generate_model_comparison_csv.py and commit the result "
            "together with this phase's report"
        )

    def test_legacy_archive_is_labelled_historical(self) -> None:
        label = REPO_ROOT / "evaluation" / "legacy" / "README.md"
        assert label.exists(), "evaluation/legacy/README.md must label the archive"
        text = label.read_text(encoding="utf-8")
        assert "historical" in text.lower()
        assert "single" in text.lower() and "split" in text.lower()
        # The revision the archived bytes came from must be named.
        assert "b86c1b9" in text

    def test_pinned_rerun_is_recorded_separately(self) -> None:
        rerun_dir = REPO_ROOT / "evaluation" / "reproduction" / "2026-10-05-pinned-single-split"
        assert (rerun_dir / "model_comparison.md").exists()
        assert (rerun_dir / "model_comparison.csv").exists()
        assert (rerun_dir / "README.md").exists()
        label = (rerun_dir / "README.md").read_text(encoding="utf-8")
        assert "docs/reproduction_record.md" in label
        # The rerun is a different result from the legacy one; if these ever match
        # byte-for-byte the separate archive has stopped meaning anything.
        assert _sha256(rerun_dir / "model_comparison.md") != _sha256(TRACKED_REPORT)
