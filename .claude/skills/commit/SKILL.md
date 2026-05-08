---
name: commit
description: GSMSV 프로젝트 컨벤션에 따라 Git 커밋을 생성합니다. 변경사항을 논리적 단위로 나누고 올바른 타입 prefix와 한국어 설명으로 커밋합니다.
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*), Bash(git log:*)
---

## Commit Message Rules

Format: `type: 설명`

- **콜론 앞뒤 공백 없음** — 항상 `type: 설명`, `type : 설명` 사용 금지
- **Types** (English): `feat` / `fix` / `update` / `add` / `test` / `docs` / `style` / `perf` / `refactor` / `merge`
- **Description**: 한국어, 마침표 없음, 간결하게
- Subject line only (본문 없음)
- **Co-Authored-By 포함 금지** — 워터마크 없이 클린한 커밋 메시지만

### Type Guide

| Type | When to use |
|------|------------|
| `feat` | 새로운 기능 |
| `add` | 파일, 설정, 의존성 추가 |
| `fix` | 버그 수정 |
| `update` | 기존 기능 수정 또는 리뷰 반영 |
| `refactor` | 동작 변경 없는 코드 구조 개선 |
| `test` | 테스트 추가 또는 수정 |
| `docs` | 문서만 변경 |
| `style` | 포맷팅, 린트 |
| `perf` | 성능 개선 |
| `merge` | 머지 커밋 |

### Examples

```
feat: VM 생성 API 구현
fix: 아바타 삭제 시 Path Traversal 취약점 수정
update: 리뷰 반영 - 비밀번호 필드 마스킹
style: ruff 포맷팅 적용
```

### Commit Template

```bash
git commit -m "type: 설명"
```

## Commit Flow

1. 변경사항 확인: `git status`, `git diff`
2. 논리적 단위로 분류 (기능 / 버그 수정 / 리팩토링 등)
3. 단위별로 파일 그룹화
4. 각 그룹:
   - `git add` 로 관련 파일만 스테이징
   - 위 규칙에 따른 커밋 메시지 작성
   - `git commit -m "..."` 실행
5. `git log --oneline -n <count>` 로 확인

## Important

- 사용자가 명시적으로 요청할 때만 커밋 (`커밋`, `커밋해줘`, `commit` 등)
- 명시적 요청 없이 자동 커밋 금지
