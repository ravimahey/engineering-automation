# Engineering Automation Pipeline (`engineering-automation`)

[![Daily Engineering Maintenance](https://github.com/OWNER/engineering-automation/actions/workflows/daily-maintenance.yml/badge.svg)](https://github.com/OWNER/engineering-automation/actions/workflows/daily-maintenance.yml)
[![Repository Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg)](#)
[![Python Version](https://img.shields.io/badge/Python-3.12-blue.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#)

A zero-touch, enterprise-grade engineering maintenance pipeline implemented with GitHub Actions. This repository performs scheduled daily health verification, dependency auditing, secret scanning, repository structure validation, and regression testing—recording audit-ready maintenance reports without manual intervention.

---

## Table of Contents

- [Overview & Objectives](#overview--objectives)
- [Architecture & Workflow Design](#architecture--workflow-design)
- [Repository Structure](#repository-structure)
- [Daily Automated Activities](#daily-automated-activities)
- [Workflow Configuration & Security Scopes](#workflow-configuration--security-scopes)
- [Execution Schedule & Triggers](#execution-schedule--triggers)
  - [Scheduled Execution](#scheduled-execution)
  - [Manual Execution (`workflow_dispatch`)](#manual-execution-workflow_dispatch)
- [Automated Maintenance Report](#automated-maintenance-report)
- [Git Automation & Idempotency](#git-automation--idempotency)
- [Setup & Deployment Guide](#setup--deployment-guide)
- [Verification & Observability](#verification--observability)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Security & Maintenance Recommendations](#security--maintenance-recommendations)

---

## Overview & Objectives

In production engineering, repositories degrade over time due to dependency drift, unpinned actions, deprecated workflows, and configuration changes. `engineering-automation` establishes an autonomous daily maintenance cycle that:

1. **Continuously audits repository integrity**: Verifies workflow syntax, timeouts, permissions, and structure.
2. **Safeguards code and credentials**: Scans for accidental API keys, tokens, or improperly ignored files.
3. **Monitors dependency freshness**: Identifies outdated or unpinned packages against upstream registries (PyPI).
4. **Executes regression tests**: Validates that automation scripts remain operational.
5. **Maintains a verifiable audit record**: Compiles reports into [`reports/daily-maintenance.md`](reports/daily-maintenance.md) with historical trend tracking.
6. **Eliminates synthetic noise**: Never produces empty commits, fake edits, or artificial contribution events. Commits occur **only** when legitimate audit results update the report.

---

## Architecture & Workflow Design

The automation architecture follows a modular, non-overlapping sequence governed by strict security boundaries and failure handling:

```
+-----------------------------------------------------------------------------------+
|                           GitHub Actions Runner (Ubuntu)                          |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [Triggers]                                                                       |
|    |-- Cron: 04:00 UTC Daily                                                      |
|    +-- Manual: workflow_dispatch                                                  |
|                                                                                   |
|  [Step 1: Environment Setup]                                                      |
|    |-- actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 (Pinned SHA)     |
|    |-- actions/setup-python@42375524e23c412d93fb67b49958b491fce71c38 (Pinned SHA) |
|    +-- Install pinned dependencies from requirements.txt                          |
|                                                                                   |
|  [Step 2: Automated Verification]                                                 |
|    |-- scripts/validate.py        --> reports/validation_results.json             |
|    |-- scripts/security_check.py  --> reports/security_results.json               |
|    +-- pytest tests/              --> reports/test_results.xml                    |
|                                                                                   |
|  [Step 3: Synthesis & Audit]                                                      |
|    +-- scripts/generate_report.py --> reports/daily-maintenance.md                |
|                                                                                   |
|  [Step 4: Git Synchronization]                                                    |
|    |-- Dedicated Identity: github-actions[bot]                                    |
|    |-- Idempotent check (git diff --porcelain)                                    |
|    |-- Safe pull --rebase & push origin main                                      |
|    +-- Message: chore(maintenance): automated daily maintenance report [skip ci]   |
+-----------------------------------------------------------------------------------+
```

---

## Repository Structure

```
engineering-automation/
├── .github/
│   └── workflows/
│       └── daily-maintenance.yml   # Enterprise CI/CD workflow specification
├── scripts/
│   ├── validate.py                 # Structure, YAML, & workflow security validator
│   ├── security_check.py           # Secret scanning & PyPI dependency health auditor
│   └── generate_report.py          # Markdown synthesizer with historical rollups
├── reports/
│   └── daily-maintenance.md        # Living daily maintenance log & history
├── tests/
│   ├── __init__.py                 # Test package marker
│   ├── test_validate.py            # Unit tests for structure and workflow validator
│   ├── test_security_check.py      # Unit tests for secret scanner and package parser
│   └── test_generate_report.py     # Unit tests for report generator and XML parser
├── requirements.txt                # Pinned production dependencies (PyYAML, pytest)
├── README.md                       # Engineering documentation and runbook
└── .gitignore                      # Git exclusion rules for secrets, cache, and reports
```

---

## Daily Automated Activities

Every daily execution performs 8 structured maintenance operations:

| # | Activity | Implementation | Objective |
| :--- | :--- | :--- | :--- |
| **1** | **Repository Structure Validation** | `scripts/validate.py` | Enforces standard directory trees, core config presence, and prevents junk files (`.env`, `*.tmp`, `*.bak`). |
| **2** | **Configuration & YAML Linting** | `scripts/validate.py` | Validates YAML syntax across all workflows and configs using `yaml.safe_load`. |
| **3** | **GitHub Actions Security Check** | `scripts/validate.py` | Enforces explicit permissions, detects unpinned third-party actions, and verifies job timeouts. |
| **4** | **Secret & Credential Scanning** | `scripts/security_check.py` | Audits files for AWS keys, GitHub tokens, private keys, and credential assignments. |
| **5** | **Gitignore Policy Audit** | `scripts/security_check.py` | Ensures sensitive file extensions and local cache directories are safely ignored. |
| **6** | **Dependency Health & Freshness** | `scripts/security_check.py` | Compares pinned requirements against upstream PyPI releases using PyPI's JSON API. |
| **7** | **Automated Regression Suite** | `pytest tests/` | Runs comprehensive unit tests on all automation scripts and outputs JUnit XML metrics. |
| **8** | **Audit Report Generation** | `scripts/generate_report.py`| Aggregates metrics into `reports/daily-maintenance.md`, preserving audit history. |

---

## Workflow Configuration & Security Scopes

The workflow file [`.github/workflows/daily-maintenance.yml`](.github/workflows/daily-maintenance.yml) adheres to the **Principle of Least Privilege**:

### 1. Minimal GitHub Token Permissions
```yaml
permissions:
  contents: write    # Required strictly to commit and push updated maintenance reports
```
No extraneous privileges (`pull-requests: write`, `issues: write`, or `admin`) are granted.

### 2. Action Pinning with Full 40-Character Commit SHAs
To protect against supply chain tampering, all third-party actions are pinned to immutable commit hashes:
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
- uses: actions/setup-python@42375524e23c412d93fb67b49958b491fce71c38 # v5.4.0
```

### 3. Concurrency Locking
Prevents overlapping runs from colliding when pushing git commits:
```yaml
concurrency:
  group: daily-maintenance-${{ github.ref }}
  cancel-in-progress: false
```

### 4. Runner Timeout Controls
Protects runner budgets from rogue hanging processes:
```yaml
timeout-minutes: 15
```

---

## Execution Schedule & Triggers

### Scheduled Execution
The workflow runs automatically once daily at **04:00 UTC** (off-peak hours):
```yaml
on:
  schedule:
    - cron: '0 4 * * *'
```

### Manual Execution (`workflow_dispatch`)
To trigger an immediate maintenance run:
1. Navigate to your repository on GitHub.
2. Select **Actions** > **Daily Engineering Maintenance**.
3. Click **Run workflow**.
4. *(Optional)* Check `dry_run` to execute all verification steps without pushing report changes to git.

Alternatively, trigger via GitHub CLI:
```bash
gh workflow run daily-maintenance.yml
```

---

## Automated Maintenance Report

The report [`reports/daily-maintenance.md`](reports/daily-maintenance.md) provides an executive overview and an append-only historical log:

- **Executive Summary**: Table showing status across Structure, YAML, Tests, Secrets, and Dependencies.
- **Dependency Health Matrix**: Real-time snapshot of packages, current spec, upstream version, and update status.
- **Issues & Findings**: Actionable alerts categorizing warnings or errors.
- **Recommended Actions**: Clear remediation steps for the engineering team.
- **Execution History Log**: Retains a rolling log of past daily runs (date, UTC timestamp, trigger, commit hash, summary).

---

## Git Automation & Idempotency

To ensure reliable, loop-free Git operations:

1. **Automation Identity**:
   ```bash
   git config user.name "github-actions[bot]"
   git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
   ```
2. **Idempotent Commits**:
   The workflow checks `git status --porcelain reports/daily-maintenance.md`. If no changes occurred, no commit is generated.
3. **Loop Prevention (`[skip ci]`)**:
   Commits use the message:
   ```
   chore(maintenance): automated daily maintenance report [skip ci]
   ```
   Combined with the fact that the workflow triggers **only** on `schedule` and `workflow_dispatch` (not on `push`), infinite recursive triggers are impossible.
4. **History Preservation**:
   Uses `git pull --rebase origin main` before `git push origin main`. It never uses `--force` and never overwrites commit history.

---

## Setup & Deployment Guide

Follow these steps to initialize and deploy this repository:

### Step 1: Create a Private GitHub Repository
1. Open GitHub and create a new repository named `engineering-automation`.
2. Set visibility to **Private**.
3. Do not initialize with template files (use the local files created here).

### Step 2: Initialize Git and Push Local Files
From the project directory:
```bash
# Initialize git if not already initialized
git init -b main

# Add remote repository
git remote add origin https://github.com/<YOUR-USERNAME-OR-ORG>/engineering-automation.git

# Stage and commit all files
git add .
git commit -m "feat(init): production engineering automation baseline"

# Push to default branch
git push -u origin main
```

### Step 3: Enable Workflow Permissions in Repository Settings
To allow the GitHub Actions bot to push report updates:
1. Go to repository **Settings** > **Actions** > **General**.
2. Scroll to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Check **Allow GitHub Actions to create and approve pull requests** (optional, recommended for PR automations).
5. Click **Save**.

---

## Verification & Observability

### Local Verification
Run the verification suite locally before pushing:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run repository structure and workflow validation
python scripts/validate.py

# 3. Run security and dependency scans
python scripts/security_check.py

# 4. Run automated unit tests
pytest tests/ -v

# 5. Generate a test report
python scripts/generate_report.py
```

### Cloud Verification on GitHub
1. After pushing to GitHub, go to **Actions** tab.
2. Under **Workflows**, click **Daily Engineering Maintenance**.
3. Click **Run workflow** to trigger a manual run (`workflow_dispatch`).
4. Wait for completion (typically under 45 seconds).
5. Verify:
   - Green checkmark on the workflow run.
   - Inspect step logs: `Validate Repository Structure and Workflows`, `Run Security and Dependency Audits`, `Execute Automated Regression Tests`.
   - Inspect [`reports/daily-maintenance.md`](reports/daily-maintenance.md) to confirm the new execution entry was recorded.

---

## Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`Permission to ... denied to github-actions[bot]`** | Repository permissions restrict GITHUB_TOKEN write access. | Navigate to **Settings > Actions > General > Workflow permissions**, select **Read and write permissions**, and save. |
| **Action fails on PyPI lookup** | Transient network timeout during PyPI query. | The script handles network errors gracefully with `OFFLINE_SKIPPED` without failing the workflow. If persistent, check GitHub runner outbound networking. |
| **Merge conflict during report push** | Another commit was pushed to `main` while workflow ran. | The workflow executes `git pull --rebase origin main` before pushing. Concurrency lock prevents overlapping runs. |
| **Action pinning warning in `validate.py`** | A workflow step references a mutable tag (e.g. `@v4`). | Replace tag with the full 40-character commit SHA (e.g. `@11bd71901bbe5b1630ceea73d27597364c9af683`). |
| **Scheduled cron not triggering** | GitHub disables cron on inactive private repositories (after 60 days of no repo activity). | Trigger the workflow manually via `workflow_dispatch` or push a commit to re-enable cron scheduling. |

---

## Security & Maintenance Recommendations

1. **Keep Repository Private**: Ensure the repository settings maintain **Private** visibility to protect internal audit reports and operational logs.
2. **Regularly Audit Dependencies**: When `reports/daily-maintenance.md` highlights outdated packages in the Dependency Health Matrix, update version bounds in `requirements.txt`.
3. **Never Store Secrets in Code**: All sensitive credentials must use GitHub Secrets (`${{ secrets.SECRET_NAME }}`).
4. **Monitor Runner Costs**: The pipeline uses `ubuntu-latest` and completes in under 1 minute per day (~30 minutes/month), remaining well within the GitHub Actions free tier (2,000 minutes/month for private repositories).
5. **Enforce Branch Protection**: Configure branch protection rules on `main` to require status checks to pass before merging PRs.
