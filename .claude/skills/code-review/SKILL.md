---
name: code-review
description: 변경된 파일에 대해 GSMSV 프로젝트 컨벤션 — Python/FastAPI 스타일, 보안, 인증, Next.js 타입 정확성 — 구조적 체크리스트를 실행합니다. ✓/⚠/✗ 리포트를 생성하고, 발견된 항목을 PR 코멘트 또는 이슈로 등록합니다.
allowed-tools: Bash(gh:*), Bash(git diff:*), Bash(git log:*)
---

# Code Review Guide

## Step 0 — code-reviewer 에이전트 백그라운드 실행

메인 리뷰를 시작하기 전에 `code-reviewer` 서브에이전트를 **백그라운드**로 동시에 실행합니다.
에이전트에게는 동일한 범위(인수)와 아래 컨텍스트를 전달합니다:

> "GSMSV 프로젝트(FastAPI/Next.js)의 코드 리뷰를 수행해줘.
> 리뷰 범위: {인수 또는 develop...HEAD}.
> 체크 항목: 인증(get_current_user), 민감 필드 노출, 리소스 접근 제어, HTTPException 직접 사용, Pydantic 바디 검증, any 타입, Suspense 래핑, 상태 코드, RBAC, 하드코딩 시크릿, SQL Injection.
> ✓/⚠/✗ 리포트를 반환해줘."

에이전트가 완료되면 Step 3 리포트에 에이전트 결과를 병합하여 **메인 리뷰 + 에이전트 리뷰** 통합 리포트를 생성합니다.

## Step 1 — 리뷰 범위 결정

인수(argument)에 따라 범위를 결정합니다:

| 인수 | 범위 |
|------|------|
| 없음 | `develop...HEAD` (현재 브랜치 전체) |
| PR 번호 (`42`) | 해당 PR의 diff |
| 파일 경로 (`api/routes/firewall.py`) | 해당 파일만 |
| 브랜치명 (`feat/xxx`) | develop 대비 해당 브랜치 diff |

```bash
# 범위 없음 (기본)
git diff develop...HEAD --stat
git diff develop...HEAD

# PR 번호 지정
gh pr diff <number>
gh pr view <number> --json files -q '.files[].path'

# 파일 지정
git diff develop...HEAD -- <file_path>

# 브랜치 지정
git diff develop...<branch> --stat
git diff develop...<branch>
```

변경된 각 파일을 상세히 읽어서 분석합니다.

## Step 2 — Checklist

### Python / FastAPI
- [ ] 인증 필요 엔드포인트에 `Depends(get_current_user)` 있는가?
- [ ] 응답에 password, token 등 민감 필드 없는가?
- [ ] 다른 사용자 리소스 접근 차단 검증 있는가?
- [ ] `HTTPException` 직접 사용 (서브클래스 X)?
- [ ] 파일 경로 조작 시 `Path.resolve()` + 상위 디렉토리 검증 있는가?
- [ ] Pydantic 모델로 요청 바디 검증하는가?

### TypeScript / Next.js
- [ ] `any` 타입 사용 없는가?
- [ ] `useSearchParams()` 사용 시 `<Suspense>` 래핑 있는가?
- [ ] 클라이언트 컴포넌트에 `"use client"` 선언 있는가?
- [ ] API 호출 에러 처리 있는가?
- [ ] 컴포넌트 props 타입 정의 있는가?

### API Design
- [ ] GET 200, POST 201, DELETE 200/204 상태 코드 맞는가?
- [ ] URL은 복수형 명사인가? (`/vms`, `/users`)
- [ ] 역할 기반 접근 제어 (USER/PROJECT_OWNER/ADMIN) 적용되었는가?

### Security
- [ ] 하드코딩된 시크릿 없는가?
- [ ] 로그에 민감 정보 없는가?
- [ ] SQL Injection 위험 없는가? (ORM 사용)
- [ ] JWT 검증 우회 불가한가?

### Test
- [ ] 신규 기능에 pytest 테스트 있는가?
- [ ] 에러 케이스(404, 403, 400) 테스트 있는가?

## Step 3 — Report

각 항목에 대해:
- ✓ Pass
- ⚠ Warning (권고)
- ✗ Error (수정 필요)

Final summary: `{n} items — {p} passed, {w} warnings, {e} errors`

## Step 4 — 발견 항목 등록

⚠/✗ 항목이 있을 경우, 사용자에게 등록 방식을 확인합니다:

> **이슈 등록 전 반드시 `triage-issues` 스킬을 호출해 중복 체크를 먼저 수행합니다.**
> - `MERGED into #<n>` 반환 시 → 새 이슈 생성 없이 기존 이슈 번호를 리포트에 표시
> - `CREATED #<n>` 반환 시 → 새 이슈 번호를 리포트에 표시

> ⚠ {w}개, ✗ {e}개 발견되었습니다.
> 어떻게 처리할까요?
> 1. PR 코멘트로 등록 (PR 번호 필요)
> 2. GitHub 이슈로 등록
> 3. 리포트만 (등록 안 함)

### PR 코멘트로 등록

특정 파일·라인에 pinpoint 가능한 항목은 인라인 코멘트로 등록합니다:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# 인라인 코멘트 (파일·라인 특정 가능한 경우)
gh api "repos/$REPO/pulls/<pr_number>/comments" \
  -f body="<내용>" \
  -f commit_id="$(gh pr view <pr_number> --json headRefOid -q .headRefOid)" \
  -f path="<파일 경로>" \
  -F line=<라인 번호> \
  -f side="RIGHT"

# 일반 코멘트 (라인 특정 불가한 경우)
gh pr comment <pr_number> --body "<내용>"
```

### GitHub 이슈로 등록

PR 범위 밖이거나 PR이 없는 경우 이슈로 등록합니다:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

gh issue create \
  --repo "$REPO" \
  --title "[code-review] <한국어 요약>" \
  --body "$(cat <<'EOF'
## 발견 위치
- **파일**: `<파일 경로>`
- **라인**: <라인 번호>

## 문제
<구체적으로 무엇이 문제인지 한국어로>

## 수정 방향
<어떻게 수정해야 하는지 한국어로>
EOF
)" \
  --label "bug"
```

항목별로 심각도에 따라 라벨을 선택합니다:
- ✗ Error → `bug`
- ⚠ Warning → `enhancement`
