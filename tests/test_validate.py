"""Tests for validate.py script."""

from pathlib import Path
import pytest
import yaml

from scripts.validate import (
    validate_repository_structure,
    validate_yaml_files,
    validate_workflow_configurations,
    run_all_validations,
)


def test_validate_current_repository():
    """Verify that the repository itself satisfies all structural requirements."""
    repo_root = Path(__file__).parent.parent
    result = validate_repository_structure(repo_root)

    assert result["status"] == "PASSED", f"Missing items: {result}"
    assert len(result["missing_dirs"]) == 0
    assert len(result["missing_files"]) == 0
    assert len(result["disallowed_files"]) == 0


def test_structure_detects_missing_directory(tmp_path):
    """Verify that missing directories are detected."""
    res = validate_repository_structure(tmp_path)
    assert res["status"] == "FAILED"
    assert len(res["missing_dirs"]) > 0


def test_structure_detects_disallowed_files(tmp_path):
    """Verify that forbidden files like .env or .tmp are flagged."""
    # Setup dummy structure
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "tests").mkdir()
    for f in [
        "requirements.txt",
        "README.md",
        ".gitignore",
        "reports/daily-maintenance.md",
        ".github/workflows/daily-maintenance.yml",
        "scripts/validate.py",
        "scripts/security_check.py",
        "scripts/generate_report.py",
    ]:
        (tmp_path / f).write_text("ok", encoding="utf-8")

    # Add disallowed file
    (tmp_path / ".env").write_text("SECRET=123", encoding="utf-8")

    res = validate_repository_structure(tmp_path)
    assert res["status"] == "FAILED"
    assert ".env" in res["disallowed_files"]


def test_yaml_validation_on_repo():
    """Verify that all YAML files in the repository have valid syntax."""
    repo_root = Path(__file__).parent.parent
    res = validate_yaml_files(repo_root)
    assert res["status"] == "PASSED"
    assert len(res["invalid_files"]) == 0
    assert len(res["scanned_files"]) > 0


def test_yaml_validation_detects_syntax_error(tmp_path):
    """Verify that syntax errors in YAML files are caught."""
    bad_yaml = tmp_path / "broken.yml"
    bad_yaml.write_text("foo: [bar: 123", encoding="utf-8")

    res = validate_yaml_files(tmp_path)
    assert res["status"] == "FAILED"
    assert "broken.yml" in res["invalid_files"]


def test_workflow_best_practices_on_repo():
    """Verify that the daily-maintenance workflow follows enterprise security standards."""
    repo_root = Path(__file__).parent.parent
    res = validate_workflow_configurations(repo_root)

    assert res["status"] in ("PASSED", "WARNING")
    assert len(res["issues"]) == 0

    wf_key = str(Path(".github/workflows/daily-maintenance.yml"))
    wf_info = res["workflows"].get(wf_key)
    assert wf_info is not None
    assert wf_info["has_name"] is True
    assert wf_info["has_triggers"] is True
    assert wf_info["has_concurrency"] is True
    assert wf_info["has_permissions"] is True
    assert len(wf_info["unpinned_actions"]) == 0
    assert len(wf_info["missing_timeouts"]) == 0
