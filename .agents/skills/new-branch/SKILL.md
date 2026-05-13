---
name: new-branch
description: Create a new git branch following the GSMSV naming convention. Use when starting new work or creating a branch.
allowed-tools: Bash(git checkout:*), Bash(git branch:*)
---

Create and switch to a new branch following GSMSV naming conventions.

Steps:
1. If the branch purpose is unclear, ask the user first
2. Choose the appropriate type and write an English kebab-case description
3. Create from `develop`: `git checkout develop && git checkout -b type/description`
4. Verify with `git branch --show-current`

Branch name format: `type/description`

Types:
- feat: new feature
- fix: bug fix
- style: code formatting (no logic change)
- refactor: code refactor
- docs: documentation updates
- test: test-related changes
- chore: build config or package management
- remove: delete files/folders

Rules:
- Use kebab-case for description
- Keep description short and clear
- Description must be English
- Always branch from `develop`

Example: `feat/vm-snapshot-api`
