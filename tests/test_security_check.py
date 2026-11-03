"""Tests for security_check.py script."""

from pathlib import Path
import pytest

from scripts.security_check import (
    scan_for_secrets,
    check_gitignore_policies,
    parse_requirements,
    check_pypi_updates,
    run_all_security_checks,
)


def test_no_secrets_in_repository():
    """Verify that no sensitive credentials or keys exist in the repository."""
    repo_root = Path(__file__).parent.parent
    res = scan_for_secrets(repo_root)
    assert res["status"] == "PASSED"
    assert len(res["findings"]) == 0
    assert res["scanned_files_count"] > 0


def test_secret_scanner_detects_mock_credentials(tmp_path):
    """Verify that secret scanning catches known credential patterns."""
    fake_secret_file = tmp_path / "creds.py"
    # Using concatenation to prevent this test file from triggering raw scanner literals
    fake_secret_file.write_text(
        'AWS_KEY = "' + 'AKIA' + 'IOSFODNN7EXAMPLE' + '"\n',
        encoding="utf-8",
    )

    res = scan_for_secrets(tmp_path)
    assert res["status"] == "FAILED"
    assert len(res["findings"]) >= 1
    assert res["findings"][0]["type"] == "AWS Access Key"


def test_gitignore_contains_critical_patterns():
    """Verify that .gitignore includes basic security protections."""
    repo_root = Path(__file__).parent.parent
    res = check_gitignore_policies(repo_root)
    assert res["status"] == "PASSED"
    assert len(res["missing_patterns"]) == 0


def test_parse_requirements():
    """Verify that requirements parser correctly extracts package name and version."""
    repo_root = Path(__file__).parent.parent
    req_file = repo_root / "requirements.txt"
    packages = parse_requirements(req_file)

    pkg_names = [p["package"] for p in packages]
    assert "PyYAML" in pkg_names
    assert "pytest" in pkg_names


def test_pypi_checker_resilience():
    """Verify that PyPI check functions gracefully under network or offline conditions."""
    packages = [
        {"package": "PyYAML", "version": "6.0.2", "spec": "PyYAML==6.0.2"}
    ]
    # Check runs with a short timeout and must not raise unhandled exceptions
    res = check_pypi_updates(packages, timeout=2)
    assert "status" in res
    assert len(res["packages"]) == 1
