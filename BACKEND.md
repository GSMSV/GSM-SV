# Backend Architecture & API Reference

> FastAPI + SQLAlchemy + PostgreSQL 기반 VM 신청·관리 플랫폼 백엔드

---

## 목차

1. [디렉터리 구조](#디렉터리-구조)
2. [애플리케이션 초기화](#애플리케이션-초기화)
3. [백그라운드 태스크](#백그라운드-태스크)
4. [API 엔드포인트](#api-엔드포인트)
   - [인증 (Auth)](#인증-apiv1auth)
   - [OAuth](#oauth-apiv1oauth)
   - [VM 관리 (VM Control)](#vm-관리-apiv1vm)
   - [네트워크 (Network)](#네트워크-apiv1network)
   - [방화벽 (Firewall)](#방화벽-apiv1firewall)
   - [모니터링 (Monitoring)](#모니터링-apiv1monitoring)
   - [알림 (Notifications)](#알림-apiv1notifications)
   - [FAQ](#faq-apiv1faq)
5. [서비스 레이어](#서비스-레이어)
6. [데이터베이스 모델](#데이터베이스-모델)
7. [Pydantic 스키마](#pydantic-스키마)
8. [핵심 인프라 (core/)](#핵심-인프라-core)
9. [인증 & 권한 흐름](#인증--권한-흐름)
10. [주요 설계 패턴](#주요-설계-패턴)

---

## 디렉터리 구조

```
backend/
├── main.py                          # 앱 진입점, 미들웨어, 라우터, 백그라운드 태스크
├── init_db.py                       # DB 초기화 스크립트
├── api/
│   ├── dependencies.py              # JWT 인증, RBAC 의존성
│   └── routes/
│       ├── auth.py                  # 회원가입·로그인·비밀번호·프로필
│       ├── oauth.py                 # DataGSM OAuth 2.0 + PKCE
│       ├── vmcontrol.py             # VM CRUD·전원 제어·스냅샷·메트릭
│       ├── network.py               # 포트 포워딩 조회
│       ├── firewall.py              # 방화벽 룰·커스텀 포트 CRUD
│       ├── monitoring.py            # 노드 통계
│       ├── notifications.py         # 사용자 알림
│       └── faq.py                   # FAQ 질문·답변
├── core/
│   ├── config.py                    # .env 기반 Settings 싱글톤
│   ├── security.py                  # JWT 생성·검증, bcrypt
│   ├── database.py                  # SQLAlchemy 엔진·세션·Base
│   ├── encryption.py                # Fernet 대칭 암호화
│   ├── constants.py                 # VM 티어 스펙
│   ├── timezone.py                  # KST 유틸리티
│   └── init_servers.py              # .env → DB 노드 동기화
├── models/
│   ├── user.py                      # User (ADMIN / PROJECT_OWNER / USER)
│   ├── vm.py                        # VM 메타데이터
│   ├── server.py                    # Proxmox 물리 노드
│   ├── notification.py              # 사용자 알림
│   ├── email_verification.py        # 이메일 인증 토큰
│   ├── faq_question.py              # FAQ 질문·답변
│   └── vm_port.py                   # 커스텀 포트 포워딩
├── schemas/
│   ├── user_schema.py               # 인증 요청·응답 스키마
│   ├── vm_schema.py                 # VM 생성·조작 스키마
│   └── fw_schema.py                 # 방화벽·포트 스키마
├── services/
│   ├── vm_service.py                # VM 생성·삭제 오케스트레이션
│   ├── email_service.py             # SMTP 이메일 발송
│   ├── proxmox_client.py            # Proxmox API 래퍼 (연결 캐시)
│   ├── datagsm_service.py           # DataGSM API 클라이언트
│   ├── network_service.py           # iptables 관리·포트 할당
│   └── mon_service.py               # 모니터링·메트릭 수집
└── tests/                           # pytest 테스트 스위트
```

---

## 애플리케이션 초기화

**파일:** `main.py`

### 미들웨어 & 예외 처리

| 항목 | 설정 |
|------|------|
| CORS | `settings.CORS_ORIGINS` (기본: localhost:3000, localhost:5173) |
| 허용 메서드 | GET, POST, PUT, DELETE, OPTIONS |
| 정적 파일 | `/uploads` → `uploads/` (사용자 아바타) |
| Rate Limiting | slowapi — 초과 시 429 응답 |

### 라우터 등록

| 접두사 | 파일 |
|--------|------|
| `/api/v1/auth` | `routes/auth.py` |
| `/api/v1/oauth` | `routes/oauth.py` |
| `/api/v1/vm` | `routes/vmcontrol.py` |
| `/api/v1/network` | `routes/network.py` |
| `/api/v1/firewall` | `routes/firewall.py` |
| `/api/v1/monitoring` | `routes/monitoring.py` |
| `/api/v1/notifications` | `routes/notifications.py` |
| `/api/v1/faq` | `routes/faq.py` |

### 서버 시작 순서

1. OAuth 스토어 모드 검증 (단일 워커 → memory, 다중 워커 → Redis)
2. `Base.metadata.create_all()` — 모든 테이블 생성
3. `.env` → DB 노드 동기화 (`init_servers.py`)
4. 등록된 라우트 로깅
5. 백그라운드 태스크 spawn

---

## 백그라운드 태스크

앱 시작 시 `asyncio.create_task()`로 독립 실행. 연속 5회 실패 시 관리자에게 알림 전송.

| 태스크 | 실행 주기 | 역할 |
|--------|-----------|------|
| `_expire_vms_loop()` | 1시간 | 만료 VM 삭제, 만료 15일 전 소유자 알림, 오래된 알림 정리 |
| `_iptables_weekly_backup_loop()` | 7일 | 게이트웨이 iptables 규칙 SSH 백업 |
| `_daily_snapshot_loop()` | 매일 00:00 | 오래된 auto-daily 스냅샷 삭제 후 신규 생성 (auto_snapshot=True VM) |
| `_oauth_store_cleanup_loop()` | 5분 | 만료된 PKCE/토큰 인메모리 항목 정리 |

---

## API 엔드포인트

### 인증 `/api/v1/auth`

**파일:** `api/routes/auth.py`

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| POST | `/signup` | 이메일 인증 코드 발송 (DataGSM 재학생 확인) | 불필요 |
| POST | `/signup/project/check` | 프로젝트 오너 이메일 확인 및 프로젝트 목록 조회 | 불필요 |
| POST | `/signup/project` | 프로젝트 오너 계정 신청 (관리자 승인 대기) | 불필요 |
| POST | `/verify` | 이메일 코드 검증 + 계정 생성 | 불필요 |
| POST | `/resend-code` | 인증 코드 재발송 | 불필요 |
| GET | `/pending-approvals` | 프로젝트 오너 승인 대기 목록 | **Admin** |
| POST | `/approve/{user_id}` | 프로젝트 오너 승인 | **Admin** |
| POST | `/reject/{user_id}` | 프로젝트 오너 거절 및 계정 삭제 | **Admin** |
| POST | `/login` | 이메일+비밀번호+역할 로그인 | 불필요 |
| POST | `/refresh` | refresh token으로 access token 갱신 | 불필요 |
| GET | `/me` | 현재 로그인 사용자 정보 | 필요 |
| POST | `/password-reset/request` | 비밀번호 재설정 코드 이메일 발송 | 불필요 |
| POST | `/password-reset/confirm` | 코드 + 새 비밀번호로 재설정 | 불필요 |
| PUT | `/change-password` | 로그인 상태에서 비밀번호 변경 | 필요 |
| POST | `/avatar` | 프로필 이미지 업로드 (최대 2MB, jpeg/png/webp) | 필요 |
| DELETE | `/avatar` | 프로필 이미지 삭제 | 필요 |
| POST | `/logout` | 로그아웃 (httpOnly 쿠키 초기화) | 필요 |

**주요 제약 조건:**
- 이메일+역할 복합 유니크 — 동일 이메일로 USER, PROJECT_OWNER, ADMIN 계정 독립 보유 가능
- DataGSM 재학생 여부 필수 검증
- 비밀번호 정책: 8자 이상, 영문+숫자+특수문자(!@#$%^&*...) 혼합, UTF-8 최대 72바이트
- Rate limit: signup 5회/분, login 10회/분, 비밀번호 재설정 3회/분

---

### OAuth `/api/v1/oauth`

**파일:** `api/routes/oauth.py`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/authorize` | DataGSM OAuth 흐름 시작 (PKCE S256 state 생성) |
| GET | `/callback` | DataGSM 리디렉션 수신 (code → temp_code 발급) |
| POST | `/exchange` | 프론트엔드에서 temp_code → JWT 토큰 교환 |

**OAuth 흐름 (Authorization Code + PKCE):**

```
프론트엔드           백엔드                DataGSM
    │──GET /authorize──▶│                     │
    │◀─ PKCE state ─────│                     │
    │                   │                     │
    │──────── DataGSM 로그인 리디렉션 ─────────▶│
    │◀──── callback (code) ───────────────────│
    │                   │──code+verifier─────▶│
    │                   │◀─ access_token ─────│
    │                   │── userinfo 조회 ────▶│
    │                   │◀─ 사용자 정보 ───────│
    │                   │── 계정 생성/연동     │
    │──POST /exchange───▶│                     │
    │◀─ JWT 토큰 쌍 ────│                     │
```

**인메모리 스토어 (TTL 5분):**
- `_pkce_store`: state → (code_verifier, expires_at)
- `_token_store`: temp_code → {access_token, refresh_token, expires}
- 다중 워커 환경에서는 `OAUTH_STORE_MODE=redis` 필요

---

### VM 관리 `/api/v1/vm`

**파일:** `api/routes/vmcontrol.py`

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/nodes` | 전체 Proxmox 노드 목록 및 상태 | Admin |
| GET | `/nodes/resources` | 노드별 CPU/RAM/디스크 사용량 | 인증 필요 |
| GET | `/admin/all-vms` | 모든 VM 상세 목록 (CPU/RAM 사용량 포함) | Admin |
| GET | `/my-vms` | 내 VM 전체 목록 (실시간 상태) | 인증 필요 |
| GET | `/{node}/vms` | 특정 노드의 VM 목록 | 인증 필요 |
| GET | `/{node}/vms/{vmid}/status` | VM 상세 상태 | 소유자 또는 Admin |
| GET | `/{node}/vms/{vmid}/metrics` | VM 메트릭 (CPU/RAM/디스크/네트워크) | 소유자 또는 Admin |
| PUT | `/{node}/vms/{vmid}/resize` | CPU/RAM 핫플러그 변경 | Project Owner 이상 |
| POST | `/{node}/vms/{vmid}/extend` | 만료일 30일 연장 (만료 15일 전부터 가능) | 소유자 또는 Admin |
| POST | `/{node}/vms/{vmid}/action` | 전원 제어 (start/stop/shutdown/reboot) | 소유자 또는 Admin |
| POST | `/create` | VM 생성 (티어 기반 자동 프로비저닝) | 인증 필요 |
| GET | `/{node}/vms/{vmid}/snapshots` | 스냅샷 목록 | 소유자 또는 Admin |
| POST | `/{node}/vms/{vmid}/snapshots` | 수동 스냅샷 생성 (최대 3개) | 소유자 또는 Admin |
| DELETE | `/{node}/vms/{vmid}/snapshots/{name}` | 스냅샷 삭제 | 소유자 또는 Admin |
| POST | `/{node}/vms/{vmid}/snapshots/{name}/restore` | 스냅샷 복구 | 소유자 또는 Admin |

**VM 생성 흐름 (POST /create):**

```
요청 (tier, os, node_name?)
    │
    ├─ node_name 미지정 → 여유 RAM 가장 많은 노드 자동 선택
    │
    ├─ 내부 IP 할당 (10.0.0.100-254에서 미사용 주소)
    ├─ VMID 할당 (클러스터 내 다음 가용 ID)
    ├─ cloud-init YAML 생성 → Proxmox SSH로 snippet 업로드
    ├─ Proxmox API로 VM 클론 + 설정
    ├─ iptables DNAT 규칙 추가 (SSH/HTTP/SVC 포트)
    └─ DB 저장 (만료일: 생성일 +30일, USER 한정)
```

**기본 포트 계산:**

```
SSH  : base_port + vmid
HTTP : base_port + 1000 + vmid
SVC  : base_port + 2000 + vmid
```

**VM 티어 스펙:**

| 티어 | vCPU | RAM | 디스크 |
|------|------|-----|--------|
| MICRO | 1 | 2 GB | 30 GB |
| SMALL | 2 | 4 GB | 40 GB |
| MEDIUM | 2 | 6 GB | 50 GB |
| LARGE | 4 | 8 GB | 50 GB |
| PROJECT_CUSTOM | 8 | 32 GB | 70 GB |

**Rate limit:** action 10회/분, create 5회/분

---

### 네트워크 `/api/v1/network`

**파일:** `api/routes/network.py`

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/{node}/{vmid}/ports` | VM의 외부 포트 정보 (SSH/HTTP/SVC) | 인증 필요 |

반환: 게이트웨이 공인 IP + 각 서비스별 외부 포트 번호

---

### 방화벽 `/api/v1/firewall`

**파일:** `api/routes/firewall.py`

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/{vmid}/rules` | Proxmox VM 방화벽 규칙 목록 | 소유자 또는 Admin |
| POST | `/{vmid}/rules` | 방화벽 규칙 추가 | 소유자 또는 Admin |
| DELETE | `/{vmid}/rules/{pos}` | 방화벽 규칙 삭제 (위치 기반) | 소유자 또는 Admin |
| GET | `/{node}/{vmid}/ports` | 커스텀 포트 목록 (DB) | 소유자 또는 Admin |
| POST | `/{node}/{vmid}/ports` | 커스텀 포트 추가 (30000-39999 랜덤) | 소유자 또는 Admin |
| DELETE | `/{node}/{vmid}/ports/{port_id}` | 커스텀 포트 삭제 | 소유자 또는 Admin |
| POST | `/{node}/{vmid}/ports/defaults/restore` | 기본 포트(SSH/HTTP/SVC) 복원 | 소유자 또는 Admin |

**커스텀 포트 제약:**
- VM당 최대 30개
- 외부 포트: 30000-39999 범위에서 랜덤 할당
- 프로토콜: tcp 또는 udp
- 선택적 소스 IP/CIDR 제한

---

### 모니터링 `/api/v1/monitoring`

**파일:** `api/routes/monitoring.py`

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/nodes` | 전체 활성 노드 통계 | 인증 필요 |

**반환 데이터:**
- CPU 사용률 (%)
- RAM: total_gb, used_gb, free_gb
- 업타임 (초)
- 상태: online / offline

**권한별 필터:**
- Admin / Project Owner → 전체 노드
- User → 자신의 VM이 있는 노드만

---

### 알림 `/api/v1/notifications`

**파일:** `api/routes/notifications.py`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `` | 알림 목록 (최신 50개) |
| PATCH | `/{notification_id}/read` | 단일 알림 읽음 처리 |
| POST | `/read-all` | 전체 알림 읽음 처리 |
| DELETE | `/{notification_id}` | 단일 알림 삭제 |

모든 엔드포인트 인증 필요. 알림 타입: `info` / `success` / `error`

---

### FAQ `/api/v1/faq`

**파일:** `api/routes/faq.py`

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `` | FAQ 목록 (Admin: 전체, User: 본인 질문) | 인증 필요 |
| POST | `` | 질문 등록 (최대 500자) | 인증 필요 |
| PUT | `/{question_id}/answer` | 질문 답변 작성 | Admin |
| DELETE | `/{question_id}` | 질문 삭제 (작성자 또는 Admin) | 인증 필요 |

---

## 서비스 레이어

### `services/vm_service.py`

VM 생성·삭제의 핵심 오케스트레이션 담당.

| 함수 | 역할 |
|------|------|
| `create_vm(db, user, tier, os, ...)` | VM 생성 전 과정 조율 |
| `delete_vm(db, vm, purge)` | Proxmox 삭제 + DB 삭제 + iptables 정리 |
| `_get_next_vmid(proxmox, node)` | 클러스터에서 다음 가용 VMID 조회 |
| `_allocate_internal_ip(db)` | 10.0.0.100-254 범위에서 미사용 IP 할당 |
| `_generate_userdata_yaml(password, root_password)` | Ubuntu cloud-init YAML 생성 |
| `_upload_snippet(server, filename, content)` | SSH로 Proxmox 노드에 cloud-init 파일 업로드 |
| `_generate_vm_name(user, tier, name)` | (proxmox_name, display_name) 튜플 생성 |

---

### `services/network_service.py`

게이트웨이 서버의 iptables 규칙을 SSH로 직접 관리.

| 함수 | 역할 |
|------|------|
| `calculate_ports(base_port, vmid)` | SSH/HTTP/SVC 외부 포트 계산 |
| `manage_iptables(server, vmid, vm_ip, action)` | 기본 DNAT 규칙 추가/삭제 |
| `manage_custom_iptables(...)` | 커스텀 포트 규칙 추가/삭제 |
| `allocate_random_port(db, start, end)` | 30000-39999 범위 미사용 포트 조회 |

**iptables DNAT 규칙 구조:**
```bash
# PREROUTING
-t nat -A PREROUTING -p {proto} -d {GATEWAY_PUBLIC_IP} --dport {public_port} \
  -j DNAT --to-destination {vm_ip}:{internal_port}

# FORWARD
-A FORWARD -p {proto} -d {vm_ip} --dport {internal_port} \
  -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT
```

---

### `services/proxmox_client.py`

| 함수 | 역할 |
|------|------|
| `get_proxmox_for_server(server)` | 캐시된 ProxmoxAPI 연결 반환 (TTL 5분) |

연결당 캐시, 스레드 세이프 락, 연결 고갈 방지.

---

### `services/datagsm_service.py`

| 함수 | 역할 |
|------|------|
| `lookup_student_by_email(email)` | DataGSM에서 재학생 여부 확인 |
| `lookup_projects_by_email(email)` | 이메일이 속한 프로젝트 목록 조회 |

---

### `services/email_service.py`

| 함수 | 역할 |
|------|------|
| `generate_verification_code()` | 6자리 랜덤 인증 코드 생성 |
| `send_verification_email(to_email, code)` | SMTP(Gmail, STARTTLS 587)로 HTML 이메일 발송 |

---

## 데이터베이스 모델

### `User` 테이블: `users`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer PK | |
| email | String | 로그인 식별자 |
| hashed_password | String? | bcrypt 해시 (OAuth 계정은 null) |
| role | Enum | `ADMIN` / `PROJECT_OWNER` / `USER` |
| is_active | Boolean | 계정 활성 상태 (PROJECT_OWNER는 승인 전 False) |
| oauth_provider | String? | OAuth 제공자 (예: "datagsm") |
| oauth_sub | String? | OAuth subject ID |
| name | String? | 학생 이름 |
| grade / class_num / number | Integer? | 학년·반·번호 |
| major | String? | 학과 |
| avatar_url | String? | 프로필 이미지 URL |
| project_name | String? | 프로젝트명 (PROJECT_OWNER) |
| project_reason | String? | 신청 사유 (PROJECT_OWNER) |

**유니크 제약:** `(email, role)` — 같은 이메일로 역할별 독립 계정 가능

---

### `VM` 테이블: `vms`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer PK | 내부 식별자 |
| hypervisor_vmid | Integer | Proxmox VMID (100, 101, ...) |
| name | String | 전체 이름 (프리픽스-이름) |
| display_name | String | UI 표시용 단축 이름 |
| server_id | FK → servers | 물리 노드 |
| owner_id | FK → users | VM 소유자 |
| allocated_ram_mb | Integer | RAM 할당량 |
| allocated_cores | Integer | vCPU 수 |
| internal_ip | String | 내부 IP (10.0.0.x) |
| _vm_password | String | Fernet 암호화된 초기 비밀번호 |
| created_at | DateTime(TZ) | 생성 시각 |
| expires_at | DateTime(TZ)? | 만료 시각 (USER만, 생성일 +30일) |
| auto_snapshot | Boolean | 자동 일일 스냅샷 활성화 |

`vm_password` 프로퍼티: `_vm_password` Fernet 복호화 반환 (의도된 설계 — 복사 기능용)

---

### `Server` 테이블: `servers`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer PK | |
| name | String | 노드명 (gsmgpu1, gsmgpu2, ...) |
| ip_address | String | Proxmox 관리 IP |
| port | Integer | Proxmox API 포트 (8006, 8007, ...) |
| api_user | String | Proxmox 사용자 (root@pam) |
| _api_password | String | 암호화된 Proxmox 비밀번호 |
| ssh_user / _ssh_password / ssh_port | | SSH 접속 정보 |
| is_active | Boolean | 자동 프로비저닝 대상 여부 |
| gateway_ip / gateway_user / _gateway_password | | iptables 관리 게이트웨이 |
| base_port | Integer | 포트 포워딩 베이스 (21000, 22000, ...) |
| last_free_ram_mb | Integer | 캐시된 여유 RAM (프로비저닝 노드 선택용) |

---

### 기타 모델

| 모델 | 테이블 | 주요 필드 |
|------|--------|-----------|
| `EmailVerification` | `email_verifications` | email, hashed_password, code, signup_role, expires_at, attempts |
| `Notification` | `notifications` | user_id, type (info/success/error), message, is_read, created_at |
| `FaqQuestion` | `faq_questions` | user_id, question, answer?, answered_at, created_at |
| `VmPort` | `vm_ports` | vm_id, internal_port, external_port (unique), protocol, action, source, is_default |

---

## Pydantic 스키마

### `schemas/user_schema.py`

| 스키마 | 용도 |
|--------|------|
| `UserCreate` | 일반 회원가입 요청 |
| `ProjectCheckRequest` | 프로젝트 오너 이메일 확인 |
| `ProjectSignupRequest` | 프로젝트 오너 신청 |
| `VerifyCodeRequest` | 이메일 코드 검증 |
| `Token` | JWT 응답 (access + refresh) |
| `PasswordResetRequest` | 비밀번호 재설정 요청 |
| `PasswordResetConfirm` | 비밀번호 재설정 확인 |
| `ChangePasswordRequest` | 로그인 상태 비밀번호 변경 |

---

### `schemas/vm_schema.py`

| 스키마 | 용도 |
|--------|------|
| `VMTier` | MICRO / SMALL / MEDIUM / LARGE / PROJECT_CUSTOM |
| `VMOs` | UBUNTU2204 / WINDOWS_SERVER |
| `VMActionType` | start / stop / shutdown / reboot |
| `VMAction` | 전원 제어 요청 |
| `VMResize` | CPU/RAM 핫플러그 요청 |
| `SnapshotCreateRequest` | 스냅샷 생성 요청 |
| `VMCreate` | VM 생성 요청 (tier, os, node_name?, name?, 커스텀 스펙?) |

---

### `schemas/fw_schema.py`

| 스키마 | 용도 |
|--------|------|
| `VmPortCreate` | 커스텀 포트 생성 요청 |
| `FirewallRule` | Proxmox 방화벽 규칙 |

---

## 핵심 인프라 (core/)

### `core/config.py` — 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SECRET_KEY` | (필수) | JWT 서명 키 |
| `DATABASE_URL` | sqlite:///./vm_console.db | SQLAlchemy URL |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Access token 수명 |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | 10080 | Refresh token 수명 (7일) |
| `MAX_VMS_PER_USER` | 3 | 일반 사용자 VM 최대 개수 |
| `SMTP_HOST/PORT/USER/PASSWORD` | | 이메일 발송 설정 |
| `DATAGSM_API_KEY/URL` | | 재학생 조회 API |
| `DATAGSM_CLIENT_ID/SECRET` | | OAuth 클라이언트 설정 |
| `GATEWAY_PUBLIC_IP/IP/USER/PASSWORD` | | iptables 관리 게이트웨이 |
| `NODE_{1,2,3}_{NAME,IP,PORT,...}` | | Proxmox 노드 설정 |
| `INTERNAL_SUBNET` | 10.0.0 | VM 내부 네트워크 |
| `INTERNAL_IP_START/END` | 100 / 254 | IP 할당 범위 |
| `OAUTH_STORE_MODE` | memory | `memory` 또는 `redis` |

---

### `core/security.py`

| 함수 | 역할 |
|------|------|
| `verify_password(plain, hashed)` | bcrypt 검증 |
| `get_password_hash(password)` | bcrypt 해시 생성 |
| `create_access_token(subject, expires_delta)` | JWT access token 발급 |
| `create_refresh_token(subject, expires_delta)` | JWT refresh token 발급 |

**JWT 페이로드:**
```json
{ "exp": "<timestamp>", "sub": "<user_id>", "type": "access" }
```

---

### `core/encryption.py`

Fernet 대칭 암호화. `SECRET_KEY`를 SHA256으로 파생하여 키 생성.
서버 비밀번호, VM 초기 비밀번호 저장에 사용.

---

### `api/dependencies.py`

| 함수 | 역할 |
|------|------|
| `get_current_user(request, db, bearer_token)` | 쿠키 또는 Bearer 헤더에서 JWT 파싱 → User 반환 |
| `get_current_active_admin(current_user)` | Admin 역할 검증 |
| `get_vm_with_owner_check(db, vmid, current_user, node)` | VM 소유권 검증 (IDOR 방지) |

---

## 인증 & 권한 흐름

### 토큰 발급 및 전달

```
로그인 성공
    ├─ httpOnly 쿠키 설정 (access_token, refresh_token)
    └─ JSON 응답 (access_token, refresh_token)

요청 시 토큰 조회 순서:
    1. httpOnly 쿠키 (우선)
    2. Authorization: Bearer 헤더 (폴백)

refresh_token 쿠키 경로: /api/v1/auth/refresh (제한)
```

### 역할 계층

```
ADMIN
  └─ 전체 VM 조회/관리, 회원 승인, FAQ 답변
PROJECT_OWNER
  └─ VM 리사이즈, PROJECT_CUSTOM 티어 사용
USER
  └─ 본인 VM 생성/관리 (최대 3개, 만료일 있음)
```

---

## 주요 설계 패턴

| 패턴 | 설명 |
|------|------|
| **이메일+역할 복합 키** | 동일 이메일로 역할별 독립 계정 허용 |
| **Fernet 암호화** | 서버 자격증명, VM 비밀번호를 DB에 암호화 저장 |
| **자동 노드 선택** | VM 생성 시 여유 RAM 기준 최적 노드 자동 선택 |
| **포트 공식 계산** | `base_port + offset + vmid`로 포트 충돌 없이 결정론적 할당 |
| **Cloud-Init 프로비저닝** | YAML 동적 생성 후 SSH로 Proxmox snippet 업로드 |
| **Proxmox 연결 캐싱** | 노드별 5분 TTL 캐시로 연결 고갈 방지 |
| **배경 태스크 내결함성** | 연속 5회 실패 시 Admin 알림, 각 태스크 독립 동작 |
| **RBAC 서버 측 검증** | 프론트엔드 UI 숨김은 보조 수단, 모든 권한은 서버에서 강제 |
| **Rate Limiting** | slowapi로 엔드포인트별 요청 횟수 제한 |
| **httpOnly 쿠키 우선** | XSS 방어를 위해 쿠키 우선, Bearer 헤더 폴백 |
