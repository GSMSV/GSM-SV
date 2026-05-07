---
name: "triage-issues"
description: "\uc0c8 \uc774\uc288 \ub4f1\ub85d \uc804 \uae30\uc874 \uc624\ud508 \uc774\uc288\uc640 \uc720\uc0ac\ud55c \ud56d\ubaa9\uc774 \uc788\ub294\uc9c0 \ud655\uc778\ud569\ub2c8\ub2e4. \uc720\uc0ac \uc774\uc288\uac00 \uc788\uc73c\uba74 \uc0c8 \uc774\uc288 \ub300\uc2e0 \uae30\uc874 \uc774\uc288\uc5d0 \ucf54\uba58\ud2b8\ub97c \ucd94\uac00\ud569\ub2c8\ub2e4. \uc778\uc218 \uc5c6\uc774 \ub2e8\ub3c5 \uc2e4\ud589 \uc2dc \uc804\uccb4 \uc624\ud508 \uc774\uc288\ub97c \uc815\ub9ac\u00b7\ubcd1\ud569\ud569\ub2c8\ub2e4."
---

# Triage Issues

## 실행 모드

| 호출 방식 | 동작 |
|-----------|------|
| 인수 없음 (`/triage-issues`) | 전체 오픈 이슈 정리 모드 |
| 제목 + 내용 전달 (다른 스킬에서 호출) | 단일 이슈 중복 체크 모드 |

---

## Mode A — 단일 이슈 중복 체크 (code-review / review-pr 에서 호출)

새 이슈를 등록하기 전에 이 절차를 실행합니다.

### Step 1 — 오픈 이슈 목록 조회

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh issue list --repo "$REPO" --state open --limit 100 \
  --json number,title,labels,body \
  -q '.[] | "#\(.number) [\(.labels[].name // "no-label")] \(.title)"'
```

### Step 2 — 유사 이슈 판단

등록하려는 이슈와 기존 이슈를 비교해 유사 여부를 판단합니다.

유사로 판단하는 기준:
- **같은 파일**이 언급된 경우
- **같은 도메인** (auth, vm, firewall, monitoring 등)에서 같은 종류의 문제
- **제목 키워드 70% 이상 겹치는** 경우

### Step 3 — 분기 처리

**유사 이슈 없음 → 새 이슈 생성**

호출한 스킬(code-review / review-pr)의 이슈 생성 절차대로 진행합니다.

**유사 이슈 있음 → 기존 이슈에 코멘트 추가**

새 이슈를 만들지 않고, 가장 유사한 기존 이슈에 코멘트를 추가합니다:

```bash
gh issue comment <existing_issue_number> --repo "$REPO" --body "$(cat <<'EOF'
## 추가 발견 사례

- **출처**: <code-review / review-pr / 파일명>
- **파일**: `<파일 경로>`
- **라인**: <라인 번호>

<새로 발견된 내용 요약>
EOF
)"
```

결과를 호출한 스킬에 반환합니다:
- 새 이슈 생성 시: `CREATED #<number>`
- 기존 이슈에 추가 시: `MERGED into #<number>`

---

## Mode B — 전체 이슈 정리 (`/triage-issues` 단독 실행)

### Step 1 — 전체 오픈 이슈 조회

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh issue list --repo "$REPO" --state open --limit 100 \
  --json number,title,labels,body,createdAt \
  -q '.[] | "#\(.number) \(.title)"'
```

### Step 2 — 그룹핑

아래 기준으로 유사 이슈를 묶어 그룹을 구성합니다:
- 같은 파일/경로 언급
- 같은 도메인 (auth / vm / firewall / monitoring / frontend 등)
- 같은 타입 (`[code-review]` / `[deferred]` 등 prefix 동일 + 내용 유사)

### Step 3 — 정리 계획 출력

병합 계획을 사용자에게 먼저 보여줍니다:

```
## 정리 계획

### 그룹 1 — <도메인/파일명>
- 대표 이슈: #<number> <title>
- 병합 대상: #<number> <title>, #<number> <title>
- 처리: 병합 대상을 대표 이슈에 코멘트로 통합 후 close

### 그룹 2 — ...

병합하지 않는 이슈: #<n>, #<n> (유사 없음)
```

### Step 4 — 사용자 확인 후 실행

확인을 받으면:

1. 병합 대상 이슈 내용을 대표 이슈에 코멘트로 추가
2. 병합 대상 이슈 close + `duplicate` 라벨 부착

```bash
# 대표 이슈에 코멘트 추가
gh issue comment <canonical_number> --body "<병합 내용>"

# 중복 이슈 close
gh issue close <duplicate_number> --repo "$REPO" \
  --comment "Duplicate of #<canonical_number>"

# duplicate 라벨 부착 (라벨 없으면 생성)
gh issue edit <duplicate_number> --add-label "duplicate"
```

### Step 5 — 정리 결과 리포트

```
## 정리 완료

- 병합: #<n> → #<n>, #<n> → #<n>
- 변경 없음: #<n>, #<n>
- 남은 오픈 이슈: <count>개
```

## Codex Notes

The original Claude `allowed-tools` list is preserved as workflow guidance. It is not a Codex permission boundary.

You're allowed to use these tools:

- Bash(gh:*)
