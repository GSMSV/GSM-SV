---
name: security-checklist
description: 보안 취약점을 검증합니다 — 하드코딩된 시크릿, Path Traversal, SQL Injection, JWT 검증, 민감 정보 로깅, 역할 기반 접근 제어. 인증/API 관련 변경사항 머지 전에 실행하세요.
---

# Security Checklist (GSMSV)

## 검증 항목

### 1. 하드코딩된 시크릿
- [ ] 코드에 API Key, Secret, Password 없는가?
- [ ] 환경변수 또는 `.env` 파일 사용하는가?

```bash
grep -r "password.*=.*['\"]" --include="*.py" api/ services/
grep -r "secret.*=.*['\"]" --include="*.py" api/ services/
grep -r "API_KEY\|SECRET_KEY" --include="*.ts" --include="*.tsx" frontend/
```

### 2. Path Traversal
- [ ] 파일 경로 생성 시 `Path.resolve()` 사용하는가?
- [ ] 허용된 디렉토리 하위인지 검증하는가?
- [ ] `../` 또는 절대경로 입력 차단하는가?

```bash
grep -r "Path(" --include="*.py" api/ services/
grep -r "os.path\|open(" --include="*.py" api/ services/
```

### 3. SQL Injection
- [ ] ORM (SQLAlchemy) 사용하는가?
- [ ] Raw SQL 사용 시 파라미터 바인딩 사용하는가?
- [ ] 직접 문자열 포맷팅으로 SQL 조합하지 않는가?

### 4. JWT 검증
- [ ] JWT 서명 검증하는가?
- [ ] 만료 시간 확인하는가?
- [ ] 사용자 식별은 토큰 클레임에서 (요청 바디 user_id X)?

### 5. 로깅
- [ ] 로그에 password, token, secret 출력 없는가?
- [ ] 적절한 로그 레벨 사용하는가?

```bash
grep -r "logger\.\|print(" --include="*.py" api/ services/ | grep -i "password\|token\|secret"
```

### 6. 역할 기반 접근 제어
- [ ] 인증 필요 엔드포인트에 `Depends(get_current_user)` 있는가?
- [ ] 역할 검증 (USER/PROJECT_OWNER/ADMIN) 서버측에서 하는가?
- [ ] 프론트엔드 UI 숨김만으로 접근 제어하지 않는가?
- [ ] 다른 사용자 리소스 접근 차단 검증 있는가?

### 7. CORS
- [ ] 허용된 출처만 CORS 설정에 포함되는가?
- [ ] `*` 와일드카드 사용 이유가 있는가? (의도된 설계인 경우 허용)

## Report Format

각 항목에 대해:
- ✓ Pass
- ⚠ Warning (권고)
- ✗ Error (수정 필요)

Final summary: `{n} items — {p} passed, {w} warnings, {e} errors`
