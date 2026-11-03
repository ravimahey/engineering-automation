"""Tests for generate_report.py script."""

from pathlib import Path
import pytest

from scripts.generate_report import (
    parse_junit_xml,
    extract_existing_history,
    build_markdown_report,
)


def test_parse_junit_xml_with_mock(tmp_path):
    """Verify JUnit XML parser extracts test counts, duration, and failures."""
    xml_file = tmp_path / "results.xml"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
    <testsuite name="pytest" tests="5" failures="0" errors="0" skipped="0" time="1.25">
    </testsuite>
</testsuites>
"""
    xml_file.write_text(xml_content, encoding="utf-8")

    metrics = parse_junit_xml(xml_file)
    assert metrics["total"] == 5
    assert metrics["passed"] == 5
    assert metrics["failures"] == 0
    assert metrics["status"] == "PASSED"
    assert metrics["duration_seconds"] == 1.25


def test_parse_junit_xml_with_failure(tmp_path):
    """Verify JUnit XML parser flags failures."""
    xml_file = tmp_path / "results.xml"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="3" failures="1" errors="0" skipped="0" time="0.50">
</testsuite>
"""
    xml_file.write_text(xml_content, encoding="utf-8")

    metrics = parse_junit_xml(xml_file)
    assert metrics["total"] == 3
    assert metrics["passed"] == 2
    assert metrics["failures"] == 1
    assert metrics["status"] == "FAILED"


def test_extract_existing_history_from_report(tmp_path):
    """Verify historical log entries are preserved when updating report."""
    report_file = tmp_path / "report.md"
    sample_report = """# Title
## Execution History Log

| Date | UTC Timestamp | Status | Trigger | Commit | Summary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-01 | 2026-11-01 04:00:00 UTC | PASSED | schedule | abcdef12 | 10/10 tests passed |
| 2026-11-02 | 2026-11-02 04:00:00 UTC | PASSED | schedule | 12345678 | 10/10 tests passed |
"""
    report_file.write_text(sample_report, encoding="utf-8")

    history = extract_existing_history(report_file)
    assert len(history) == 2
    assert "2026-11-01" in history[0]
    assert "2026-11-02" in history[1]


def test_build_markdown_report_structure():
    """Verify generated markdown contains all required sections."""
    val_data = {
        "overall_status": "PASSED",
        "repository_structure": {"status": "PASSED", "missing_files": []},
        "workflow_configurations": {"status": "PASSED", "issues": []},
    }
    sec_data = {
        "overall_status": "PASSED",
        "secret_scanning": {"status": "PASSED", "findings": [], "scanned_files_count": 8},
        "dependency_health": {
            "status": "PASSED",
            "packages": [
                {
                    "package": "PyYAML",
                    "current_version": "6.0.2",
                    "latest_version": "6.0.2",
                    "update_available": False,
                    "status": "OK",
                }
            ],
        },
    }
    test_metrics = {
        "total": 10,
        "passed": 10,
        "failures": 0,
        "errors": 0,
        "duration_seconds": 0.42,
        "status": "PASSED",
    }

    report = build_markdown_report(
        validation_data=val_data,
        security_data=sec_data,
        test_metrics=test_metrics,
        existing_history=[],
        git_sha="abcdef1234567890",
        event_name="schedule",
    )

    assert "# Engineering Daily Maintenance Report" in report
    assert "## Executive Summary" in report
    assert "## Automated Activities Performed" in report
    assert "## Dependency Health Matrix" in report
    assert "## Issues & Findings" in report
    assert "## Recommended Actions" in report
    assert "## Execution History Log" in report
    assert "abcdef12" in report
    assert "schedule" in report
