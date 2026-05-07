---
name: "test"
description: "pytest \ud14c\uc2a4\ud2b8\ub97c \uc2e4\ud589\ud558\uace0 \uacb0\uacfc\ub97c \ub9ac\ud3ec\ud2b8\ud569\ub2c8\ub2e4. \ucee8\ud14d\uc2a4\ud2b8\uc5d0 \ub530\ub77c \ud14c\uc2a4\ud2b8 \ubc94\uc704\ub97c \uacb0\uc815\ud558\uace0 \uc2e4\ud328\ub97c \uc0c1\uc138\ud788 \ubd84\uc11d\ud569\ub2c8\ub2e4. \uc804\uccb4 \ud14c\uc2a4\ud2b8\ub294 \uaf2d \ud544\uc694\ud55c \uacbd\uc6b0\uc5d0\ub9cc \uc2e4\ud589\ud569\ub2c8\ub2e4."
---

다음 단계에 따라 테스트를 실행합니다:

## Steps

1. **테스트 범위 결정**:
   - 특정 파일/모듈 언급 시: 관련 테스트 파일만 실행 (권장)
   - 특정 기능 영역 변경 시: 해당 도메인 테스트만 실행
   - 명시적으로 전체 실행 요청 시: 전체 실행

2. **테스트 실행**:

   ```bash
   # 관련 테스트만 (권장)
   python -m pytest tests/test_{module}.py -v 2>&1

   # 특정 함수
   python -m pytest tests/test_{module}.py::test_{function_name} -v 2>&1

   # 전체 (꼭 필요한 경우만)
   python -m pytest tests/ -v 2>&1
   ```

3. **결과 분석**:
   - 테스트 요약 표시
   - 실패 시: 실패 메시지 및 traceback 표시, 근본 원인 분석
   - 성공 시: 통과한 테스트 수 확인

4. **리포트**:
   - 실행된 총 테스트 수
   - 통과/실패 수
   - 실패 시 수정 방향 제안

테스트를 실행하지 않고 성공했다고 주장하지 않습니다.
