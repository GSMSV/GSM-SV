---
name: code-review
description: Run a structured checklist for changed files in the GSMSV project — Python/FastAPI style, security, auth, and Next.js type correctness. Generate a ✓/⚠/✗ report and register findings as PR comments or issues.
allowed-tools: Bash(gh:*), Bash(git diff:*), Bash(git log:*)
---

# Code Review Guide

## Step 0 — Run the code-reviewer agent in the background

Before starting the main review, launch the `code-reviewer` subagent **in the background** at the same time.
Pass the same scope (argument) and the context below to the agent:

> "Please review GSMSV (FastAPI/Next.js) code.
> Review scope: {argument or develop...HEAD}.
> Checklist: auth (get_current_user), sensitive field exposure, resource access control, direct HTTPException usage, Pydantic body validation, any type usage, Suspense wrapping, status codes, RBAC, hardcoded secrets, SQL Injection.
> Return a ✓/⚠/✗ report."

When the agent completes, merge its results into the Step 3 report to produce a combined report for **main review + agent review**.

## Step 1 — Determine review scope

Determine the scope based on the argument:

| Argument | Scope |
|------|------|
| none | `develop...HEAD` (entire current branch) |
| PR number (`42`) | diff for that PR |
| file path (`api/routes/firewall.py`) | that file only |
| branch name (`feat/xxx`) | diff for that branch vs develop |

```bash
# No scope (default)
git diff develop...HEAD --stat
git diff develop...HEAD

# PR number
gh pr diff <number>
gh pr view <number> --json files -q '.files[].path'

# File path
git diff develop...HEAD -- <file_path>

# Branch name
git diff develop...<branch> --stat
git diff develop...<branch>
```

Read each changed file in detail and analyze it.

## Step 2 — Checklist

### Python / FastAPI
- [ ] Auth-required endpoints include `Depends(get_current_user)`?
- [ ] Responses do not expose sensitive fields (password, token, etc.)?
- [ ] Access to other users' resources is blocked/validated?
- [ ] Direct use of `HTTPException` (no subclass)?
- [ ] For file path manipulation, `Path.resolve()` + parent directory validation?
- [ ] Request bodies validated via Pydantic models?

### TypeScript / Next.js
- [ ] No `any` type usage?
- [ ] `useSearchParams()` usage wrapped with `<Suspense>`?
- [ ] Client components declare `"use client"`?
- [ ] API calls include error handling?
- [ ] Component props types are defined?

### API Design
- [ ] Correct status codes (GET 200, POST 201, DELETE 200/204)?
- [ ] URLs use plural nouns? (`/vms`, `/users`)
- [ ] Role-based access control (USER/PROJECT_OWNER/ADMIN) applied?

### Security
- [ ] No hardcoded secrets?
- [ ] No sensitive data in logs?
- [ ] No SQL Injection risk? (ORM usage)
- [ ] JWT validation cannot be bypassed?

### Test
- [ ] pytest tests for new features?
- [ ] Error cases tested (404, 403, 400)?

## Step 3 — Report

For each item:
- ✓ Pass
- ⚠ Warning (recommendation)
- ✗ Error (must fix)

Final summary: `{n} items — {p} passed, {w} warnings, {e} errors`

## Step 4 — Register findings

If there are ⚠/✗ items, ask the user how to register them:

> **Before creating any issue, call the `triage-issues` skill to check for duplicates first.**
> - If it returns `MERGED into #<n>` → do not create a new issue; report the existing issue number
> - If it returns `CREATED #<n>` → report the new issue number

> Found ⚠ {w} warnings and ✗ {e} errors.
> How should we handle them?
> 1. Register as PR comments (PR number required)
> 2. Register as GitHub issues
> 3. Report only (no registration)

### Register as PR comments

If an item can be pinpointed to a specific file/line, register it as an inline comment:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# Inline comment (file/line specific)
gh api "repos/$REPO/pulls/<pr_number>/comments" \
  -f body="<content>" \
  -f commit_id="$(gh pr view <pr_number> --json headRefOid -q .headRefOid)" \
  -f path="<file path>" \
  -F line=<line number> \
  -f side="RIGHT"

# General comment (no specific line)
gh pr comment <pr_number> --body "<content>"
```

### Register as GitHub issues

If the finding is out of PR scope or there is no PR, register it as an issue:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

gh issue create \
  --repo "$REPO" \
  --title "[code-review] <Korean summary>" \
  --body "$(cat <<'EOF'
## 발견 위치
- **파일**: `<file path>`
- **라인**: <line number>

## 문제
<구체적으로 무엇이 문제인지 한국어로>

## 수정 방향
<어떻게 수정해야 하는지 한국어로>
EOF
)" \
  --label "bug"
```

Choose labels by severity:
- ✗ Error → `bug`
- ⚠ Warning → `enhancement`
