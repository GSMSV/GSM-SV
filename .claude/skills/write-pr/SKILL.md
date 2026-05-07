---
name: write-pr
description: develop 브랜치 기준 커밋을 분석해 PR 제목과 본문을 생성하고 GitHub PR을 만듭니다. GSMSV 프로젝트 컨벤션을 따릅니다.
---

## Step 1 — 컨텍스트 수집

```bash
git branch --show-current
```

현재 브랜치가 `develop` 또는 `main`이면 즉시 중단:

```
현재 브랜치: develop
feature 브랜치를 먼저 생성하세요 (/new-branch)
```

feature 브랜치면 계속 진행:

```bash
git log origin/develop..HEAD --oneline
git diff origin/develop...HEAD --stat
git diff origin/develop...HEAD
```

## Step 2 — PR 제목 생성

Format: `type: 한국어 설명`

- commit 컨벤션과 동일한 type prefix 사용 (`feat` / `fix` / `update` / `docs` 등)
- 한국어, 간결하게, 마침표 없음, 50자 이내
- 3개 옵션 생성 후 가장 적합한 것에 `← 추천` 표시

## Step 3 — PR 본문 생성

아래 템플릿을 **그대로** 사용 (구조 변경 금지):

```markdown
## Summary
- **굵은 키워드**: 변경 내용 (한국어, 기술용어는 영어)
- `파일명`, `함수명` 등은 백틱 처리

## Test plan
- [x] 자동으로 확인된 항목
- [ ] 수동 확인 필요 항목


```

Rules:
- Summary는 bullet point로 변경 내용을 구체적으로 작성
- Test plan은 실제 테스트 가능한 항목만 포함
- 내용이 없는 섹션도 삭제하지 말고 비워둘 것

## Step 4 — 미리보기 & 확인

```
## 추천 PR 제목
1. [title1]
2. [title2]
3. [title3] ← 추천

## PR 본문 미리보기
[body content]
```

사용자에게 어떤 제목을 쓸지 확인. 응답 없으면 추천 옵션 사용.

## Step 5 — PR 생성

PR 본문에 `🤖 Generated with Claude Code` 등 워터마크를 **절대 포함하지 않는다**.

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

생성 후 PR URL을 출력한다.
