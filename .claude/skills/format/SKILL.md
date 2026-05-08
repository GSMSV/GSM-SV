---
name: format
description: Python은 ruff로, TypeScript는 ESLint로 코드 포맷팅을 실행합니다. 대규모 편집 후 또는 포맷팅이 필요할 때 사용하세요.
---

GSMSV 프로젝트 코드 포맷팅 실행:

## Python (ruff)

1. ruff 포맷 + 린트 자동 수정:
   ```bash
   ruff format . && ruff check . --fix
   ```

2. 결과 확인 후 수정된 파일 리포트

## TypeScript (ESLint + tsc)

1. ESLint 자동 수정:
   ```bash
   cd frontend && npx eslint . --ext .ts,.tsx --fix
   ```

2. 타입 체크 (수정 안 함, 확인만):
   ```bash
   cd frontend && npx tsc --noEmit
   ```

3. 결과 확인

## 자동 수정 불가 항목

자동 수정이 안 되는 에러가 남아있으면 에러 메시지를 출력하고 수동 수정이 필요한 항목을 안내합니다.
