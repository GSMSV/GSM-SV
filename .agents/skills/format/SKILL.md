---
name: "format"
description: "Python\uc740 ruff\ub85c, TypeScript\ub294 ESLint\ub85c \ucf54\ub4dc \ud3ec\ub9f7\ud305\uc744 \uc2e4\ud589\ud569\ub2c8\ub2e4. \ub300\uaddc\ubaa8 \ud3b8\uc9d1 \ud6c4 \ub610\ub294 \ud3ec\ub9f7\ud305\uc774 \ud544\uc694\ud560 \ub54c \uc0ac\uc6a9\ud558\uc138\uc694."
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
