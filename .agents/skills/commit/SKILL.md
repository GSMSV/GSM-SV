---
name: commit
description: Create git commits following the GSMSV project convention. Split changes into logical units and commit with the correct type prefix and a Korean description.
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*), Bash(git log:*)
---

## Commit Message Rules

Format: `type: 설명`

- **No spaces around the colon** — always `type: 설명`, never `type : 설명`
- **Types** (English): `feat` / `fix` / `update` / `add` / `test` / `docs` / `style` / `perf` / `refactor` / `merge`
- **Description**: Korean, no period, concise
- Subject line only (no body)
- **Do not include Co-Authored-By** — keep a clean commit message without watermarks

### Type Guide

| Type | When to use |
|------|------------|
| `feat` | New feature |
| `add` | Add file, config, or dependency |
| `fix` | Bug fix |
| `update` | Modify existing feature or apply review feedback |
| `refactor` | Structural improvement without behavior change |
| `test` | Add or change tests |
| `docs` | Documentation-only change |
| `style` | Formatting or linting |
| `perf` | Performance improvement |
| `merge` | Merge commit |

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

1. Check changes: `git status`, `git diff`
2. Split by logical unit (feature / bug fix / refactor, etc.)
3. Group files per unit
4. For each group:
   - Stage related files with `git add`
   - Write a commit message following the rules above
   - Run `git commit -m "..."`
5. Verify with `git log --oneline -n <count>`

## Important

- Only commit when the user explicitly requests it (`커밋`, `커밋해줘`, `commit`, etc.)
- Do not auto-commit without explicit request
