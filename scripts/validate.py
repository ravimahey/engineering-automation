"""Repository and Workflow Validation Script.

This script executes production-grade validation checks on:
1. Repository structure and presence of required directories/files.
2. Absence of disallowed temporary, cache, or environment files.
3. YAML syntax across all YAML configuration and workflow files.
4. GitHub Actions workflow best practices:
   - Explicit permissions scoping.
   - Action pinning with full commit SHAs.
   - Job-level timeout configurations.
   - Concurrency controls to prevent race conditions.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    print("Error: PyYAML is required. Run 'pip install PyYAML'.", file=sys.stderr)
    sys.exit(1)


REQUIRED_DIRS = [
    Path(".github/workflows"),
    Path("scripts"),
    Path("reports"),
    Path("tests"),
]

REQUIRED_FILES = [
    Path("requirements.txt"),
    Path("README.md"),
    Path(".gitignore"),
    Path("reports/daily-maintenance.md"),
    Path(".github/workflows/daily-maintenance.yml"),
    Path("scripts/validate.py"),
    Path("scripts/security_check.py"),
    Path("scripts/generate_report.py"),
]

DISALLOWED_FILE_PATTERNS = [
    r"^\.env(\..+)?$",
    r".*\.pyc$",
    r".*\.pyo$",
    r".*\.tmp$",
    r".*\.bak$",
    r"^\.DS_Store$",
    r"^Thumbs\.db$",
]

SHA_PIN_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.\/]+@[0-9a-fA-F]{40}")


def validate_repository_structure(root_dir: Path) -> Dict[str, Any]:
    """Validate directory hierarchy, required files, and forbidden patterns."""
    results: Dict[str, Any] = {
        "status": "PASSED",
        "missing_dirs": [],
        "missing_files": [],
        "disallowed_files": [],
        "checked_dirs": [str(d) for d in REQUIRED_DIRS],
        "checked_files": [str(f) for f in REQUIRED_FILES],
    }

    # Verify directories
    for req_dir in REQUIRED_DIRS:
        full_path = root_dir / req_dir
        if not full_path.is_dir():
            results["missing_dirs"].append(str(req_dir))

    # Verify files
    for req_file in REQUIRED_FILES:
        full_path = root_dir / req_file
        if not full_path.is_file():
            results["missing_files"].append(str(req_file))

    # Scan for disallowed files
    for dirpath, _, filenames in os.walk(root_dir):
        parts = Path(dirpath).parts
        # Skip internal cache and git directories
        if ".git" in parts or "__pycache__" in parts or ".pytest_cache" in parts or ".venv" in parts:
            continue
        for filename in filenames:
            for pattern in DISALLOWED_FILE_PATTERNS:
                if re.match(pattern, filename):
                    rel_path = (Path(dirpath) / filename).relative_to(root_dir)
                    results["disallowed_files"].append(str(rel_path))

    if results["missing_dirs"] or results["missing_files"] or results["disallowed_files"]:
        results["status"] = "FAILED"

    return results


def validate_yaml_files(root_dir: Path) -> Dict[str, Any]:
    """Validate syntax of all YAML files in the repository."""
    results: Dict[str, Any] = {
        "status": "PASSED",
        "scanned_files": [],
        "invalid_files": {},
    }

    yaml_candidates = list(root_dir.glob("**/*.yml")) + list(root_dir.glob("**/*.yaml"))
    
    for yml_path in yaml_candidates:
        if ".git" in yml_path.parts:
            continue
        rel_str = str(yml_path.relative_to(root_dir))
        results["scanned_files"].append(rel_str)
        try:
            with open(yml_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as exc:
            results["invalid_files"][rel_str] = str(exc)

    if results["invalid_files"]:
        results["status"] = "FAILED"

    return results


def validate_workflow_configurations(root_dir: Path) -> Dict[str, Any]:
    """Validate GitHub Actions workflows against enterprise security standards."""
    workflows_dir = root_dir / ".github" / "workflows"
    results: Dict[str, Any] = {
        "status": "PASSED",
        "workflows": {},
        "issues": [],
        "warnings": [],
    }

    if not workflows_dir.is_dir():
        results["status"] = "FAILED"
        results["issues"].append(f"Workflows directory not found: {workflows_dir}")
        return results

    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    if not workflow_files:
        results["status"] = "FAILED"
        results["issues"].append("No workflow files found in .github/workflows")
        return results

    for wf_file in workflow_files:
        rel_path = str(wf_file.relative_to(root_dir))
        wf_info: Dict[str, Any] = {
            "has_name": False,
            "has_triggers": False,
            "has_concurrency": False,
            "has_permissions": False,
            "unpinned_actions": [],
            "missing_timeouts": [],
        }

        try:
            with open(wf_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
        except Exception as exc:
            results["issues"].append(f"{rel_path}: Invalid YAML: {exc}")
            continue

        # Check name
        if "name" in content:
            wf_info["has_name"] = True
        else:
            results["warnings"].append(f"{rel_path}: Missing top-level 'name' attribute.")

        # Check triggers ('on' is parsed as True or string in some YAML parsers)
        if "on" in content or True in content:
            wf_info["has_triggers"] = True
        else:
            results["issues"].append(f"{rel_path}: Missing trigger specification ('on').")

        # Check concurrency
        if "concurrency" in content:
            wf_info["has_concurrency"] = True
        else:
            results["warnings"].append(f"{rel_path}: Missing 'concurrency' configuration to prevent overlapping runs.")

        # Check permissions
        if "permissions" in content:
            wf_info["has_permissions"] = True
            # Warn on overly permissive settings
            if content["permissions"] == "write-all":
                results["issues"].append(f"{rel_path}: Insecure permission setting 'write-all'. Use granular scopes.")
        else:
            results["warnings"].append(f"{rel_path}: Missing explicit top-level 'permissions' block.")

        # Inspect jobs
        jobs = content.get("jobs", {})
        if not jobs or not isinstance(jobs, dict):
            results["issues"].append(f"{rel_path}: No jobs defined in workflow.")
        else:
            for job_id, job_data in jobs.items():
                if not isinstance(job_data, dict):
                    continue
                # Check timeout-minutes
                if "timeout-minutes" not in job_data:
                    wf_info["missing_timeouts"].append(job_id)
                    results["warnings"].append(
                        f"{rel_path}: Job '{job_id}' does not specify 'timeout-minutes'."
                    )

                # Check steps for action pinning
                steps = job_data.get("steps", [])
                if isinstance(steps, list):
                    for step in steps:
                        if not isinstance(step, dict):
                            continue
                        uses = step.get("uses", "")
                        if uses and not uses.startswith("./"):
                            # Third party action check
                            if not SHA_PIN_REGEX.match(uses):
                                wf_info["unpinned_actions"].append(uses)
                                results["warnings"].append(
                                    f"{rel_path}: Action '{uses}' is not pinned to a 40-character commit SHA."
                                )

        results["workflows"][rel_path] = wf_info

    if results["issues"]:
        results["status"] = "FAILED"
    elif results["warnings"]:
        results["status"] = "WARNING"

    return results


def run_all_validations(root_dir: Path) -> Dict[str, Any]:
    """Execute all repository and workflow validation routines."""
    struct_res = validate_repository_structure(root_dir)
    yaml_res = validate_yaml_files(root_dir)
    wf_res = validate_workflow_configurations(root_dir)

    all_statuses = [struct_res["status"], yaml_res["status"], wf_res["status"]]
    if "FAILED" in all_statuses:
        overall_status = "FAILED"
    elif "WARNING" in all_statuses:
        overall_status = "WARNING"
    else:
        overall_status = "PASSED"

    return {
        "overall_status": overall_status,
        "repository_structure": struct_res,
        "yaml_syntax": yaml_res,
        "workflow_configurations": wf_res,
    }


def main() -> int:
    """CLI entrypoint for repository validation."""
    parser = argparse.ArgumentParser(description="Validate repository structure and GitHub workflows.")
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
    print(f"[*] Validating repository at: {repo_root}")

    report = run_all_validations(repo_root)

    print(f"\n--- Validation Summary ---")
    print(f"Overall Status: {report['overall_status']}")
    print(f"Structure Status: {report['repository_structure']['status']}")
    print(f"YAML Syntax Status: {report['yaml_syntax']['status']}")
    print(f"Workflow Config Status: {report['workflow_configurations']['status']}")

    if report["workflow_configurations"]["warnings"]:
        print("\nWarnings:")
        for w in report["workflow_configurations"]["warnings"]:
            print(f"  [!] {w}")

    if report["overall_status"] == "FAILED":
        print("\nFailures:")
        for m in report["repository_structure"]["missing_dirs"]:
            print(f"  [X] Missing directory: {m}")
        for m in report["repository_structure"]["missing_files"]:
            print(f"  [X] Missing file: {m}")
        for d in report["repository_structure"]["disallowed_files"]:
            print(f"  [X] Disallowed file detected: {d}")
        for f, err in report["yaml_syntax"]["invalid_files"].items():
            print(f"  [X] YAML syntax error in {f}: {err}")
        for err in report["workflow_configurations"]["issues"]:
            print(f"  [X] Workflow error: {err}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[+] Validation results written to {args.json_out}")

    return 0 if report["overall_status"] in ("PASSED", "WARNING") else 1


if __name__ == "__main__":
    sys.exit(main())
