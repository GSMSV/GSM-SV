# GSMSV — Claude 프로젝트 지침서

Proxmox VE 기반 VM 신청·관리 플랫폼. Backend: FastAPI/SQLAlchemy/PostgreSQL, Frontend: Next.js 16 App Router/TypeScript/shadcn-ui, Auth: JWT (access 30분 / refresh 7일), 역할: USER / PROJECT_OWNER / ADMIN

---

## 📁 디렉터리 구조

`api/routes/` 라우터, `services/` 비즈니스 로직, `models/` SQLAlchemy 모델, `schemas/` Pydantic 스키마, `core/` 설정·DB·보안, `main.py` 앱 진입점·백그라운드 태스크  
`frontend/app/` Next.js 페이지, `frontend/components/` React 컴포넌트, `frontend/lib/` api.ts·types.ts·유틸

---

## 🗂 기능 도메인별 주요 파일

**인증 (Auth)**
- `api/routes/auth.py` — 회원가입·이메일 인증·로그인·토큰 갱신·비밀번호 재설정
- `api/routes/oauth.py` — Google OAuth
- `models/user.py`, `models/email_verification.py`, `schemas/user_schema.py`
- `core/security.py` (JWT), `services/email_service.py`
- FE: `app/login/`, `app/signup/`, `app/verify/`, `app/reset-password/`, `lib/auth-context.tsx`

**VM 관리 (VM Control)**
- `api/routes/vmcontrol.py` — VM 목록·상태·생성·액션·리사이즈·스냅샷
- `services/vm_service.py` (비즈니스 로직), `services/proxmox_client.py` (Proxmox API 래퍼)
- `models/vm.py`, `models/server.py`, `schemas/vm_schema.py`
- `main.py` — `_expire_vms_loop`, `_daily_snapshot_loop`
- FE: `app/(dashboard)/instances/`, `components/instances/` (테이블·overview·metrics·backups·settings 탭)

**VM 신청 (Deploy)**
- `api/routes/vmcontrol.py` — `POST /create`, `services/vm_service.py` — `create_vm()`
- `services/network_service.py` — IP 할당·포트 계산
- FE: `app/(dashboard)/deploy/`, `components/deploy/deploy-wizard.tsx`

**방화벽 & 포트포워딩**
- `api/routes/firewall.py` — Proxmox 방화벽 룰·커스텀 포트 CRUD
- `api/routes/network.py` — 포워딩 포트 조회
- `services/network_service.py` — iptables 관리, `models/vm_port.py`, `schemas/fw_schema.py`
- FE: `components/instances/tabs/firewall-tab.tsx`

**모니터링**
- `api/routes/monitoring.py` — 노드 통계, `services/mon_service.py` — Proxmox 메트릭
- FE: `components/instances/tabs/metrics-tab.tsx`

**알림**
- `api/routes/notifications.py`, `models/notification.py`
- FE: `lib/notification-context.tsx`, `components/dashboard/top-navbar.tsx`

**관리자 (Admin)**
- `api/routes/auth.py` — `/pending-approvals`, `/approve/{id}`, `/reject/{id}`
- `api/routes/vmcontrol.py` — `/admin/all-vms`
- FE: `app/(dashboard)/admin/approvals/`

**FAQ**
- `api/routes/faq.py`, `models/faq_question.py`
- FE: `app/(dashboard)/docs/`, `components/docs/docs-layout.tsx`

**공통**
- `frontend/lib/types.ts` — 전체 프론트 타입, `frontend/lib/api.ts` — 백엔드 호출 함수
- `core/config.py` — Settings (.env), `core/init_servers.py` — 노드 동기화
- `services/datagsm_service.py` — DataGSM 연동

---

## 🧭 작업 시작 전 계획 수립

새로운 기능 구현·버그 수정 요청이 들어오면, **진행 중이던 작업의 연속이 아닌 경우** 코드 작성 전에 반드시 `/plan-deep-dive`로 계획을 먼저 수립한다.

진행 중인 작업의 연속으로 판단하는 기준:
- 같은 대화에서 이어지는 후속 요청
- `/catchup` 결과 이미 작업 중인 브랜치·태스크가 있고, 해당 작업과 직결되는 요청

---

## ⚙️ 개발 컨벤션

**커밋:** `type: 한국어 설명` — 타입: `feat/fix/update/add/docs/style/refactor/test/perf/merge`, 마침표 없음, Co-Authored-By 반드시 포함

**브랜치:** `develop`에서 분기 → feature 브랜치 → PR → develop → main (수동 머지). `main` 직접 push 금지

**PR:** 한국어 Summary (굵은 키워드, 백틱 처리) + Test plan 체크리스트 구조

---

## 🔒 의도된 설계 — 수정 금지

| 항목 | 이유 |
|------|------|
| `vm_password` 평문 반환 | overview-tab 복사용, 의도된 설계 |
| Next.js 미들웨어 `/api` 우회 | 백엔드 자체 JWT 인증 |
| Proxmox `verify_ssl=False` | 내부망 + 자체 서명 인증서 |
| Proxmox 180초 타임아웃 | VM 클론·스냅샷 장시간 작업 |
| CORS `allow_headers=["*"]` | 동일 도메인 운영 |

---

## 🐛 이슈 등록 컨벤션

코드 리뷰(⚠/✗) 발견 시 등록 방식:

- **PR 코멘트**: 특정 파일·라인에 pinpoint 가능한 항목 → 인라인 코멘트, 라인 특정 불가 → 일반 코멘트
- **GitHub 이슈**: PR 범위 밖이거나 PR이 없는 경우
  - 제목: `[code-review] 한국어 요약`
  - 라벨: ✗ Error → `bug` / ⚠ Warning → `enhancement`
- **[deferred] 이슈**: `/review-pr` 중 현재 PR 범위는 아니지만 추후 처리할 항목
  - 제목: `[deferred] 한국어 요약`

등록 여부는 `/code-review` 실행 후 사용자에게 확인 후 진행.

---

## 🧪 테스트

전체 테스트(`pytest tests/`) 매번 실행 금지 — 변경 파일 관련 테스트만 선별 실행. 관련 테스트 없으면 생략 가능.

---

## 🤖 에이전트 & 슬래시 커맨드

에이전트: `feature-builder` (구현/버그) · `code-reviewer` (리뷰) · `build-verifier` (빌드) · `test-runner` (pytest) · `failure-analyst` (실패 분석) · `lint-fixer` (린트)

슬래시 커맨드: `/commit` · `/new-branch` · `/code-review` · `/format` · `/new-api` · `/review-pr` · `/security-checklist` · `/test` · `/plan-deep-dive`

---

## 🛡 보안

- 파일 경로: `Path.resolve()` 후 허용 디렉터리 하위 검증
- 인증 필요 엔드포인트: `Depends(get_current_user)` 주입
- 역할 기반 접근 제어는 서버측 검증 (프론트 UI 숨김으로 대체 불가)
- 민감 필드 응답 노출 금지 (`vm_password` 예외)
- `HTTPException` 직접 사용 (서브클래스 생성 X)

---

## 🖥 인프라

- 도메인: `gsmsv.site` (웹) · `ssh.gsmsv.site` (포트포워딩) · `service.gsmsv.site` (Vultr VPC)
- Proxmox 노드: `.env`의 `NODE_1/2/3_*`, 프로젝트 오너 전용: `settings.PROJECT_NODE_NAME` (기본 `gsmgpu3`)
- VM 티어: BASIC / STANDARD / ADVANCED / PROJECT_CUSTOM
- 업로드: `uploads/avatars/` (Docker volume `gsmsv_uploads`)
