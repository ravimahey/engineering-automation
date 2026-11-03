"""Security and Dependency Hygiene Check Script.

Performs:
1. Secret scanning across repository files to prevent credential leakage.
2. Verification of gitignore security policies.
3. Dependency configuration analysis (version pinning, specification integrity).
4. Dependency update availability lookup via PyPI API (with resilient offline fallback).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request


SECRET_PATTERNS = {
    "AWS Access Key": re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
    "GitHub Token": re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{82}"),
    "Generic Private Key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "Generic API Secret Assignment": re.compile(
        r"(?:secret|token|password|api_key|apikey)\s*[:=]\s*['\"][A-Za-z0-9\-_=]{20,}['\"]",
        re.IGNORECASE,
    ),
    "Slack Token": re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}"),
}

IGNORED_SCAN_EXTENSIONS = {
    ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".ico", ".pdf", ".zip", ".tar", ".gz"
}

IGNORED_SCAN_FILES = {
    "security_check.py",  # Avoid self-matching regex literals
    "validation_results.json",
    "security_results.json",
    "test_results.xml",
}


def scan_for_secrets(root_dir: Path) -> Dict[str, Any]:
    """Scan all non-ignored repository files for patterns resembling secrets."""
    results: Dict[str, Any] = {
        "status": "PASSED",
        "findings": [],
        "scanned_files_count": 0,
    }

    for dirpath, _, filenames in os.walk(root_dir):
        # Skip .git and cache directories
        parts = Path(dirpath).parts
        if ".git" in parts or "__pycache__" in parts or ".pytest_cache" in parts:
            continue

        for filename in filenames:
            file_path = Path(dirpath) / filename
            rel_path = file_path.relative_to(root_dir)

            if file_path.suffix in IGNORED_SCAN_EXTENSIONS or filename in IGNORED_SCAN_FILES:
                continue

            results["scanned_files_count"] += 1

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, start=1):
                        for label, pattern in SECRET_PATTERNS.items():
                            if pattern.search(line):
                                results["findings"].append({
                                    "file": str(rel_path),
                                    "line": line_no,
                                    "type": label,
                                })
            except Exception:
                # Binary or inaccessible file
                continue

    if results["findings"]:
        results["status"] = "FAILED"

    return results


def check_gitignore_policies(root_dir: Path) -> Dict[str, Any]:
    """Verify that sensitive patterns are covered in .gitignore."""
    gitignore_path = root_dir / ".gitignore"
    results: Dict[str, Any] = {
        "status": "PASSED",
        "missing_patterns": [],
    }

    recommended_patterns = [".env", "__pycache__", "*.pyc"]

    if not gitignore_path.is_file():
        results["status"] = "FAILED"
        results["missing_patterns"] = recommended_patterns
        return results

    content = gitignore_path.read_text(encoding="utf-8")
    for pattern in recommended_patterns:
        if pattern not in content:
            results["missing_patterns"].append(pattern)

    if results["missing_patterns"]:
        results["status"] = "WARNING"

    return results


def parse_requirements(req_path: Path) -> List[Dict[str, str]]:
    """Parse requirements.txt into package name and version specs."""
    packages: List[Dict[str, str]] = []
    if not req_path.is_file():
        return packages

    with open(req_path, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue

            # Match package spec e.g. PyYAML==6.0.2 or pytest>=8.0.0
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:([=><!~]+)(.+))?$", clean)
            if match:
                pkg_name, operator, version = match.groups()
                packages.append({
                    "package": pkg_name,
                    "operator": operator or "",
                    "version": version or "",
                    "spec": clean,
                })
    return packages


def check_pypi_updates(packages: List[Dict[str, str]], timeout: int = 4) -> Dict[str, Any]:
    """Check PyPI API for available updates for listed packages."""
    results: Dict[str, Any] = {
        "status": "PASSED",
        "online_check": True,
        "packages": [],
        "outdated_count": 0,
    }

    for pkg_info in packages:
        pkg_name = pkg_info["package"]
        current_ver = pkg_info["version"]
        url = f"https://pypi.org/pypi/{pkg_name}/json"

        item = {
            "package": pkg_name,
            "current_version": current_ver or "unpinned",
            "latest_version": "unknown",
            "update_available": False,
            "status": "OK",
        }

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "engineering-automation-checker/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    latest_ver = data.get("info", {}).get("version", "")
                    item["latest_version"] = latest_ver
                    if latest_ver and current_ver and latest_ver != current_ver:
                        item["update_available"] = True
                        item["status"] = "UPDATE_AVAILABLE"
                        results["outdated_count"] += 1
        except (urllib.error.URLError, TimeoutError, OSError):
            results["online_check"] = False
            item["status"] = "OFFLINE_SKIPPED"
            item["latest_version"] = "lookup_skipped_offline"

        results["packages"].append(item)

    if results["outdated_count"] > 0:
        results["status"] = "WARNING"

    return results


def run_all_security_checks(root_dir: Path) -> Dict[str, Any]:
    """Run all security and dependency health evaluations."""
    secret_results = scan_for_secrets(root_dir)
    gitignore_results = check_gitignore_policies(root_dir)

    req_file = root_dir / "requirements.txt"
    packages = parse_requirements(req_file)
    pypi_results = check_pypi_updates(packages)

    statuses = [secret_results["status"], gitignore_results["status"], pypi_results["status"]]
    if "FAILED" in statuses:
        overall_status = "FAILED"
    elif "WARNING" in statuses:
        overall_status = "WARNING"
    else:
        overall_status = "PASSED"

    return {
        "overall_status": overall_status,
        "secret_scanning": secret_results,
        "gitignore_policies": gitignore_results,
        "dependency_health": pypi_results,
    }


def main() -> int:
    """CLI entrypoint for security and dependency checks."""
    parser = argparse.ArgumentParser(description="Run security scans and dependency health checks.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Path to repository root directory (default: current directory).",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to output structured JSON results.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    print(f"[*] Executing security and dependency checks at: {repo_root}")

    report = run_all_security_checks(repo_root)

    print("\n--- Security Check Summary ---")
    print(f"Overall Status: {report['overall_status']}")
    print(f"Secret Scanning Status: {report['secret_scanning']['status']} "
          f"({report['secret_scanning']['scanned_files_count']} files scanned, "
          f"{len(report['secret_scanning']['findings'])} findings)")
    print(f"Gitignore Policy Status: {report['gitignore_policies']['status']}")
    print(f"Dependency Health Status: {report['dependency_health']['status']} "
          f"({report['dependency_health']['outdated_count']} updates available)")

    if report["secret_scanning"]["findings"]:
        print("\n[!] CRITICAL: Secret findings detected:")
        for item in report["secret_scanning"]["findings"]:
            print(f"  - {item['file']}:{item['line']} [{item['type']}]")

    for pkg in report["dependency_health"]["packages"]:
        print(f"  - {pkg['package']}: {pkg['current_version']} -> {pkg['latest_version']} [{pkg['status']}]")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[+] Security results written to {args.json_out}")

    return 0 if report["overall_status"] in ("PASSED", "WARNING") else 1


if __name__ == "__main__":
    sys.exit(main())
