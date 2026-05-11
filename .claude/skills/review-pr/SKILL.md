---
name: review-pr
description: Review PR comments, apply valid feedback in code, then commit, push, and reply to each comment with the applied commit hash.
allowed-tools: Bash(gh:*), Bash(git push:*), Bash(git log:*)
---

## Step 1 — Collect PR Comments

```bash
gh pr view --json number -q .number
gh api "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<pr_number>/comments" \
  --jq '.[] | {id: .id, path: .path, line: .line, body: .body}'
```

## Step 2 — Evaluate Each Comment

Decide for each comment:
- **Apply** — valid suggestion, implement in code
- **Create issue** — valid but out of current PR scope or deferred → create GitHub issue
- **Ignore** — not applicable or intended design (explain in reply)

## Step 3 — Implement Changes

Apply code changes for accepted comments.

For Python changes, check syntax:
```bash
python -m py_compile {changed_file}
```

For TypeScript/Next.js changes, verify build:
```bash
cd frontend && npm run build 2>&1
```

## Step 4 — Create Issues for Out-of-Scope Comments

For out-of-scope or deferred comments, create a GitHub issue.

**Before creating any issue, call the `triage-issues` skill to check for duplicates first.**
- If it returns `MERGED into #<n>` → do not create a new issue; use the existing issue number in the reply
- If it returns `CREATED #<n>` → use the new issue number in the reply

Only if there is no duplicate, create the issue using:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
PR_URL=$(gh pr view --json url -q .url)

gh issue create \
  --repo "$REPO" \
  --title "[deferred] <Korean summary>" \
  --body "$(cat <<'EOF'
## 출처

PR: <PR_URL>
파일: `<file_path>`
원본 코멘트:
> <comment_body>

## 내용

<구체적으로 무엇을 해야 하는지 한국어로>
EOF
)" \
  --label "enhancement"
```

After creation (or merge), record the issue number and include the issue link in the reply.

## Step 5 — Commit & Push

Only when the user requests a commit:

1. Use the commit skill to stage and commit changes (convention: `type: 설명`, no Co-Authored-By)
2. Push after commit:
```bash
git push
```

3. Get the short commit hash:
```bash
git log --oneline -1
```

## Step 6 — Reply to Each Comment

**Applied comments:**
```bash
gh api "repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies" \
  -f body="Applied in <short_hash>."
```

**Comments registered as issues:**
```bash
gh api "repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies" \
  -f body="Out of scope for this PR. Registered as <issue_url> for later."
```

**Ignored comments:**
```bash
gh api "repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies" \
  -f body="Not applied because <reason>."
```

## Step 7 — Report

```
## Applied comments
- [file] "comment" → applied in <hash>

## Comments registered as issues
- [file] "comment" → <issue_url>

## Ignored comments
- [file] "comment" → reason: ...
```

## Important

- Commit first, replies later (replies must include hash/issue link)
- Do not reply before committing
- Confirm the PR is based on develop
