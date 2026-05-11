---
name: triage-issues
description: Check for similar open issues before creating a new one. If a match exists, comment on the existing issue instead. Running without arguments organizes and deduplicates all open issues.
allowed-tools: Bash(gh:*)
---

# Triage Issues

## Modes

| Invocation | Behavior |
|-----------|------|
| No args (`/triage-issues`) | Full open-issue cleanup mode |
| Title + body provided (called by other skills) | Single-issue duplicate check mode |

---

## Mode A — Single-issue duplicate check (called by code-review / review-pr)

Run this before creating any new issue.

### Step 1 — List open issues

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh issue list --repo "$REPO" --state open --limit 100 \
  --json number,title,labels,body \
  -q '.[] | "#\(.number) [\(.labels[].name // "no-label")] \(.title)"'
```

### Step 2 — Determine similarity

Compare the new issue with existing issues to decide similarity.

Similarity criteria:
- **Same file** mentioned
- **Same domain** (auth, vm, firewall, monitoring, etc.) and same type of problem
- **70%+ title keyword overlap**

### Step 3 — Branching

**No similar issue → create a new issue**

Follow the issue creation steps of the calling skill (code-review / review-pr).

**Similar issue found → comment on existing issue**

Do not create a new issue; comment on the most similar existing issue instead:

```bash
gh issue comment <existing_issue_number> --repo "$REPO" --body "$(cat <<'EOF'
## 추가 발견 사례

- **출처**: <code-review / review-pr / file name>
- **파일**: `<file path>`
- **라인**: <line number>

<새로 발견된 내용 요약 (한국어)>
EOF
)"
```

Return to the calling skill:
- New issue created: `CREATED #<number>`
- Merged into existing issue: `MERGED into #<number>`

---

## Mode B — Full issue triage (`/triage-issues` standalone)

### Step 1 — List all open issues

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh issue list --repo "$REPO" --state open --limit 100 \
  --json number,title,labels,body,createdAt \
  -q '.[] | "#\(.number) \(.title)"'
```

### Step 2 — Grouping

Group similar issues by:
- Same file/path mentioned
- Same domain (auth / vm / firewall / monitoring / frontend, etc.)
- Same type (`[code-review]` / `[deferred]` prefix + similar content)

### Step 3 — Output the merge plan

Show the plan to the user before executing:

```
## Merge plan

### Group 1 — <domain/file name>
- Canonical issue: #<number> <title>
- To merge: #<number> <title>, #<number> <title>
- Action: merge as comments into canonical issue, then close duplicates

### Group 2 — ...

Issues not merged: #<n>, #<n> (no similarity)
```

### Step 4 — Execute after confirmation

After user confirmation:

1. Add merged issue content as a comment to the canonical issue
2. Close duplicates and add `duplicate` label

```bash
# Add comment to canonical issue
gh issue comment <canonical_number> --body "<merged content>"

# Close duplicate issue
gh issue close <duplicate_number> --repo "$REPO" \
  --comment "Duplicate of #<canonical_number>"

# Add duplicate label (create if missing)
gh issue edit <duplicate_number> --add-label "duplicate"
```

### Step 5 — Report results

```
## Triage complete

- Merged: #<n> → #<n>, #<n> → #<n>
- No change: #<n>, #<n>
- Remaining open issues: <count>
```
