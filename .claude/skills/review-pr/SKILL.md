---
name: review-pr
description: PR 리뷰 코멘트를 확인하고 유효한 피드백을 코드에 반영한 후 커밋, 푸시, 각 코멘트에 반영 완료 해시로 답글을 답니다.
allowed-tools: Bash(gh:*), Bash(git push:*), Bash(git log:*)
---

## Step 1 — Collect PR Comments

```bash
gh pr view --json number -q .number
gh api "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<pr_number>/comments" \
  --jq '.[] | {id: .id, path: .path, line: .line, body: .body}'
```

## Step 2 — Evaluate Each Comment

각 코멘트에 대해 결정:
- **반영** — 유효한 제안, 코드에 반영
- **이슈 등록** — 유효하지만 현재 PR 범위 밖이거나 추후 적용 예정 → GitHub 이슈 생성
- **무시** — 해당 없음 또는 의도된 설계 (이유를 답글에 설명)

## Step 3 — Implement Changes

수락한 코멘트에 대해 코드 변경을 적용합니다.

Python 변경 시 문법 확인:
```bash
python -m py_compile {changed_file}
```

TypeScript/Next.js 변경 시 빌드 확인:
```bash
cd frontend && npm run build 2>&1
```

## Step 4 — Create Issues for Out-of-Scope Comments

범위 밖 또는 추후 적용 예정 코멘트는 GitHub 이슈로 등록합니다.

**이슈 등록 전 반드시 `triage-issues` 스킬을 호출해 중복 체크를 먼저 수행합니다.**
- `MERGED into #<n>` 반환 시 → `gh issue create` 없이 기존 이슈 번호를 답글에 사용
- `CREATED #<n>` 반환 시 → 새 이슈 번호를 답글에 사용

중복이 없을 때만 아래 명령어로 이슈를 생성합니다:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
PR_URL=$(gh pr view --json url -q .url)

gh issue create \
  --repo "$REPO" \
  --title "[deferred] <한국어 요약>" \
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

이슈 생성(또는 병합) 후 이슈 번호를 기록해두고 답글에 이슈 링크를 포함합니다.

## Step 5 — Commit & Push

사용자가 커밋 요청 시에만:

1. commit 스킬을 사용해 변경사항을 스테이징 후 커밋 (컨벤션: `type: 설명`, Co-Authored-By 없음)
2. 커밋 완료 후 푸시:
```bash
git push
```

3. 짧은 커밋 해시 확인:
```bash
git log --oneline -1
```

## Step 6 — Reply to Each Comment

**반영한 코멘트:**
```bash
gh api "repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies" \
  -f body="<short_hash> 에서 반영했습니다."
```

**이슈로 등록한 코멘트:**
```bash
gh api "repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies" \
  -f body="현재 PR 범위 밖의 내용입니다. <issue_url> 이슈로 등록해 추후 반영하겠습니다."
```

**무시한 코멘트:**
```bash
gh api "repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies" \
  -f body="<이유> 때문에 반영하지 않았습니다."
```

## Step 7 — Report

```
## 반영한 코멘트
- [file] "comment" → <hash> 에서 반영했습니다.

## 이슈로 등록한 코멘트
- [file] "comment" → <issue_url>

## 반영하지 않은 코멘트
- [file] "comment" → 사유: ...
```

## Important

- 커밋 먼저, 답글은 나중에 (답글에 해시/이슈 링크 포함해야 하므로)
- 커밋 전에 답글 달지 않음
- develop 브랜치 기반 PR인지 확인
