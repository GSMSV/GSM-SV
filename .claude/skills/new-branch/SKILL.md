---
name: new-branch
description: GSMSV 프로젝트의 브랜치 네이밍 컨벤션에 따라 새 git 브랜치를 생성합니다. 새 작업을 시작하거나 브랜치를 생성할 때 사용하세요.
---

GSMSV 프로젝트 브랜치 네이밍 컨벤션에 따라 새 브랜치를 생성하고 이동합니다.

Steps:
1. 브랜치 목적이 불명확하면 사용자에게 먼저 확인
2. 적절한 타입을 결정하고 영어 kebab-case 설명 작성
3. `develop` 브랜치 기반으로 생성: `git checkout develop && git checkout -b type/description`
4. `git branch --show-current` 로 확인

Branch name format: `type/description`

Types:
- feat: 새로운 기능
- fix: 버그 수정
- style: 코드 포맷팅 (로직 변경 없음)
- refactor: 코드 리팩토링
- docs: 문서 업데이트
- test: 테스트 관련 변경
- chore: 빌드 설정 또는 패키지 관리
- remove: 파일/폴더 삭제

Rules:
- description은 kebab-case 사용
- description은 짧고 명확하게
- description은 영어로 작성
- 항상 `develop` 브랜치에서 분기

Example: `feat/vm-snapshot-api`
