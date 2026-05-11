---
name: write-pr
description: Analyze commits against develop, generate a PR title/body, and create a GitHub PR. Follow GSMSV project conventions.
allowed-tools: Bash(git log:*), Bash(git diff:*), Bash(git branch:*), Bash(gh:*), Bash(cat:*)
---

## Step 1 — Gather context

```bash
git branch --show-current
```

If the current branch is `develop` or `main`, stop immediately:

```
Current branch: develop
Create a feature branch first (/new-branch)
```

If on a feature branch, continue:

```bash
git log origin/develop..HEAD --oneline
git diff origin/develop...HEAD --stat
git diff origin/develop...HEAD
```

## Step 2 — Create PR title

Format: `type: 한국어 설명`

- Use the same type prefix as commit convention (`feat` / `fix` / `update` / `docs`, etc.)
- Korean, concise, no period, within 50 characters
- Generate 3 options and mark the best with `← recommended`

## Step 3 — Create PR body

Use the template **exactly as-is** (do not change structure):

```markdown
## Summary
- **굵은 키워드**: 변경 내용 (한국어, 기술용어는 영어)
- `파일명`, `함수명` 등은 백틱 처리

## Test plan
- [x] 자동으로 확인된 항목
- [ ] 수동 확인 필요 항목


```

Rules:
- Summary uses bullet points with concrete changes
- Test plan includes only real, runnable items
- Do not delete empty sections

## Step 4 — Preview & confirm

```
## Recommended PR titles
1. [title1]
2. [title2]
3. [title3] ← recommended

## PR body preview
[body content]
```

Ask the user which title to use. If no response, use the recommended option.

## Step 5 — Create PR

Never include watermarks like `🤖 Generated with Claude Code` in the PR body.

```bash
gh pr create \
  --title "<title>" \
  --base develop \
  --assignee "@me" \
  --body "$(cat <<'EOF'
## Summary
- **키워드**: 내용

## Test plan
- [x] 항목
- [ ] 항목
EOF
)"
```

After creation, output the PR URL.
