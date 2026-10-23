# VM 생성 시 클론 대상 스토리지 선택

## 배경

- gsmgpu3에 SSD를 추가하고 Proxmox에 별도 LVM-Thin 스토리지 `node3Ssd2`로 등록했다 (2026-10-21). 기존 VM 스토리지 `local-lvm`(thin pool `data`)은 거의 찬 상태다
- 백엔드는 템플릿을 클론할 때 스토리지를 지정하지 않는다 (`backend/services/vm_service.py` `create_vm()`의 `clone.post(newid, name, full=1, target)`). 2026-10-22 테스트에서 콘솔로 만든 VM의 디스크가 `local-lvm`에 생겼다. 새 SSD는 쓰이지 않는다
- 반면 VM 생성 전 SSD 80% 검사(`get_server_resource_usage`)와 대시보드 표시(`vmcontrol.py`)는 노드의 모든 `lvmthin` 스토리지를 합산한다. 그래서 검사는 낮게 나오는 합산 사용률로 통과하지만, VM은 거의 찬 `local-lvm`에 계속 쌓인다

## 목표

- 설정한 노드에서는 후보 스토리지 중 **남은 용량(GB)이 가장 큰 곳**에 VM을 만든다
- 80% 검사를 클론이 실제로 들어갈 스토리지 기준으로 한다
- 설정하지 않은 노드(gsmgpu1·2)는 지금 동작을 하나도 바꾸지 않는다

## 근거 (공식 문서)

- Proxmox VE 「Copies and Clones」(`chapter-qm.html#qm_copy_and_clone`): full clone은 "It is possible to select a Target Storage, so one can use this to migrate a VM to a totally different storage." 따라서 템플릿이 `local-lvm`에 있어도 full clone으로 다른 스토리지에 만들 수 있다
- 같은 절: "It is not possible to change the Target storage for linked clones." 백엔드는 이미 `full=1`이라 해당하지 않는다
- 같은 절: "A full clone needs to read and copy all VM image data." 디스크를 건너는 복사라 시간이 걸릴 수 있다 (아래 배포 전 확인 1번)
- `qm clone --storage`: "Target storage for full clone."
- lvmthin(7): thin pool이 가득 차면 쓰기를 기본 60초 대기시킨 뒤 에러를 돌려주고 파일 시스템이 손상될 수 있다. "Thin snapshots also keep thin pool chunks from being freed." 그래서 남은 용량 검사와 함께 80% 여유 기준을 유지한다

## 기능 요구사항

1. `.env`에 노드별 후보 스토리지 목록을 둔다. 예: `NODE_3_CLONE_STORAGES=local-lvm,node3Ssd2`
2. 목록이 있는 노드에서 VM을 만들 때, 각 후보를 아래 조건으로 거른다
   - Proxmox가 돌려준 노드 스토리지 목록에 그 이름이 있다
   - `active == 1`이고, `enabled` 값이 있으면 `1`이다
   - `content`에 `images`가 들어 있다
   - `total > 0`이고 사용률(`used / total × 100`)이 80% 미만이다
   - 남은 용량(`avail`)이 이 VM의 디스크 크기 이상이다
3. 남은 조건을 통과한 후보 중 `avail`이 가장 큰 것을 고른다. 같으면 목록에서 앞에 적힌 것을 고른다
4. 고른 스토리지를 `clone.post(..., storage=선택)`으로 넘긴다
5. 목록이 있는 노드는 기존의 합산 SSD 80% 검사를 하지 않는다 (2번의 스토리지별 검사가 대신한다). RAM·CPU 80% 검사와 가용 RAM 검사는 그대로 한다
6. 목록이 없는 노드는 지금과 똑같다: 합산 SSD 80% 검사, `storage` 인자 없이 클론
7. 대시보드(`vmcontrol.py`)와 Discord 일일 리포트(`main.py`)는 지금처럼 합산해서 보여 준다
8. 실패하면 실패 그대로 알린다. 다른 스토리지로 몰래 다시 시도하지 않는다
9. 클론을 시작한 뒤 실패하면, 예외 종류(`HTTPException` 포함)와 관계없이 Proxmox에 만들어진 VM을 정리한다 (아래 「실패 정리」)

## 결정 사항과 이유

| 항목 | 결정 | 이유 |
|---|---|---|
| 설정 위치 | `.env` 노드별 변수 | 노드 접속 정보와 같은 방식. DB 스키마를 바꾸지 않는다 (운영 DB는 `create_all`이 기존 표를 바꾸지 않아 직접 `ALTER`해야 한다) |
| 후보 범위 | `.env`에 적은 노드·스토리지만 | 모든 `lvmthin`을 자동 후보로 삼으면 `lvmthin`이 여러 개인 노드(대시보드 코드 주석: "data, vm 등 여러 파티션")의 동작까지 바뀐다 |
| 비교 기준 | 남은 용량(바이트) | 두 스토리지 크기가 달라서 사용률(%)로는 실제로 들어갈 자리를 비교할 수 없다 |
| 필요 용량 | 이 VM의 디스크 크기 전체 | thin이라 처음에는 조금만 차지하지만, 나중에 디스크 크기까지 늘어날 수 있다 |
| 80% 검사 | 후보 조건에 유지 | 남은 용량만 보면 pool이 끝까지 찬다. pool이 차면 그 위 VM 전체가 쓰기에 실패한다 (lvmthin(7)) |
| 동시 생성 | 기존 VM 생성 큐를 따른다 | 아래 「동시성」 참고 |

## 데이터 모델

- DB 스키마 변경 없음. `Server` 모델, `init_servers.py` 그대로
- `backend/core/config.py`
  - `NODE_1_CLONE_STORAGES: str = ""`, `NODE_2_CLONE_STORAGES: str = ""`, `NODE_3_CLONE_STORAGES: str = ""` 추가. 빈 문자열이면 기존 동작
  - `Settings.get_clone_storages(node_name: str) -> list[str]` 추가
    - `NODE_{i}_NAME == node_name`인 노드의 값을 쉼표로 나누고, 앞뒤 공백을 지우고, 빈 항목을 버리고, 순서를 지키며 중복을 없앤다
    - 맞는 노드가 없거나 값이 비어 있으면 `[]`
- `.env.example`에 노드마다 `NODE_{i}_CLONE_STORAGES=` 줄과 설명 주석을 추가한다 (값은 비워 둔다)

## API

- 엔드포인트·요청·응답 형식 변경 없음
- 실패 시 VM 생성 작업(`VmCreationJob`)의 `error_message`에 아래 「오류」의 메시지가 들어간다 (기존 큐 동작: `HTTPException.detail`을 그대로 기록)
- 응답과 작업 결과에 스토리지 이름을 넣지 않는다

## 비즈니스 로직

### 스토리지 선택 함수

`backend/services/mon_service.py`에 추가한다 (스토리지 조회 코드가 이미 여기 있다).

```python
def select_clone_storage(server: Server, candidates: list[str], required_disk_gb: int) -> str:
    ...
```

- `proxmox.nodes(server.name).storage.get()`을 한 번 호출한다. 예외가 나면 로그를 남기고 503을 낸다
- `required_bytes = required_disk_gb * 1024 ** 3`
- `avail`이 없으면 `total - used`로 계산한다
- 후보를 목록 순서대로 보고, 조건에 맞지 않는 후보는 이유와 함께 로그를 남긴다. 설정에 있는데 노드에 없는 이름은 설정 오류일 수 있으므로 `logger.error`로 남긴다
- 고른 스토리지와 남은 용량(GB)을 `logger.info`로 남긴다
- 80%는 `create_vm`의 기존 `THRESHOLD = 80.0`과 같은 값이어야 한다. 두 곳이 같은 상수를 보도록 `core/constants.py`에 상수로 둔다

### `create_vm()` 변경 (`backend/services/vm_service.py`)

1. `specs["disk"]`가 확정된 뒤(`custom_disk` 반영 후)의 값을 필요 용량으로 쓴다. 현재 BASIC·STANDARD 20 GB, PROJECT_CUSTOM 20~40 GB
2. 서버를 정한 뒤 `clone_storages = settings.get_clone_storages(server.name)`
3. 기존 「1-1. 자원 조회」 블록에서 `clone_storages`가 있으면 합산 `disk_pct` 검사만 건너뛴다. 이 블록의 `except Exception: ... 체크 건너뜀`은 RAM·CPU 검사에 대해서는 지금 동작을 유지한다
4. 그 블록 **바깥**에서 `clone_storages`가 있으면 `select_clone_storage(server, clone_storages, specs["disk"])`를 호출한다
   - 블록 안에 두면 조회 실패가 `except Exception`에 먹혀서 검사 없이 진행되므로 반드시 바깥에 둔다
   - VMID 선택·IP 할당·DB 커밋(3·4단계) **전에** 호출한다. 실패해도 DB 기록·VMID·Proxmox에 아무것도 남지 않게 하기 위해서다
5. 5단계 클론에서 `clone_storage`가 있을 때만 `storage=clone_storage`를 넣는다. 없으면 지금과 같은 인자로 호출한다
6. 클론 대상 스토리지를 VMID와 함께 로그로 남긴다

### 실패 정리 (`create_vm()`의 예외 처리)

지금은 `except HTTPException` 분기가 DB 레코드만 지운다. 클론 작업이 실패하거나 120초를 넘기면 `_wait_for_clone`이 `HTTPException`을 던지는데, 이때 Proxmox VM이 남는다. Proxmox VM 삭제, iptables 정리, 스니펫 삭제는 `except Exception` 분기에만 있다.

1. `except Exception` 분기의 정리 코드(Proxmox VM 삭제, iptables 삭제, 스니펫 삭제)를 함수 하나로 뺀다. 예: `_cleanup_failed_vm_resources(server, proxmox, vmid, internal_ip, *, clone_started, iptables_added)`
2. 두 분기 모두 이 함수를 부른 뒤 `_cleanup_vm_db_record`를 부른다
   - `except HTTPException`: 원래 예외를 그대로 다시 던진다 (메시지 유지)
   - `except Exception`: 지금처럼 500 "VM 생성에 실패했습니다. 잠시 후 다시 시도해주세요."
3. Proxmox VM 삭제는 `clone_started`가 참일 때만 한다. `clone.post`가 성공해 돌아온 뒤에만 참이 되므로, 남의 VM을 지울 일이 없다
4. 지우기 전에 그 VM이 Proxmox에 아직 있는지 `qemu(vmid).status.current.get()`으로 확인한다. Proxmox API가 오류(`ResourceException`)를 돌려주면 없다고 보고(클론 실패 때 Proxmox가 지운 경우), lock 대기와 삭제를 건너뛰고 info 로그만 남긴다. 연결 오류 같은 다른 예외면 있다고 보고 지금처럼 삭제를 시도한다
   - `_is_vmid_free_in_proxmox`(클러스터 `nextid` API)는 쓰지 않는다. 기존 테스트 목업은 `nextid`가 항상 "비어 있음"을 돌려주게 되어 있어서, 쓰면 기존 정리 테스트가 깨진다
   - 이유: 없는 VM이면 지금 코드는 `config.get` 실패로 3초씩 10번(30초) 기다린 뒤 삭제에도 실패해 "수동 확인 필요" 경고를 남긴다
5. lock 대기(3초 × 10번)와 `delete(purge=1)`, 실패 시 "수동 확인 필요" 경고는 지금 동작 그대로다. 클론이 아직 진행 중이라 30초 안에 lock이 풀리지 않으면 삭제에 실패하고 경고가 남는다

### 동시성

- VM 생성 요청은 큐에 들어가고, 워커 스레드 하나가 하나씩 차례로 `create_vm()`을 실행한다 (`backend/services/vm_creation_queue.py`). `create_vm()`은 클론이 끝날 때까지 기다린다
- 따라서 스토리지 선택을 `create_vm()` 안에 두면 생성 작업끼리 겹치지 않는다. 큐에 넣는 시점의 검사(`validate_vm_creation_request`)에 두지 않는다. 그러면 대기 중인 작업들이 모두 같은 예전 값을 보게 된다
- **전제: 백엔드가 프로세스 하나로 돈다.** 큐는 프로세스 메모리 안에 있어서 프로세스가 여럿이면 워커도 여럿이 된다. `backend/Dockerfile`은 `--workers` 없이 uvicorn을 실행하고 `WEB_CONCURRENCY` 기본값은 1이다. 운영 값은 배포 전에 확인한다

## 오류

| 상황 | 상태 코드 | 사용자 메시지 | 로그 |
|---|---|---|---|
| 노드 스토리지 목록 조회 실패 | 503 | VM 저장 공간 상태를 확인할 수 없습니다. 잠시 후 다시 시도해주세요. | 노드 이름, 예외 |
| 조건에 맞는 후보 없음 (설정 이름 오타·비활성·80% 이상·남은 용량 부족 포함) | 507 | 선택한 사양의 VM을 만들 SSD 공간이 부족합니다. 관리자에게 문의하세요. | 후보별 탈락 이유, 필요 용량 |
| 클론 작업 실패·타임아웃 | 기존 처리 | 기존 메시지 | 기존 로그 + 대상 스토리지 |

- 메시지에는 스토리지 이름과 용량 숫자를 넣지 않는다

## 보안

- 스토리지 이름은 `.env`에서만 온다. 요청 값으로 받지 않으므로 사용자가 Proxmox API 인자를 바꿀 수 없다
- 새 엔드포인트가 없고 권한 검사는 그대로다 (gsmgpu3은 큐 등록과 `create_vm()` 양쪽에서 `PROJECT_OWNER`·`ADMIN`만 허용)
- 사용자 메시지에 인프라 이름을 넣지 않는다

## 테스트

`backend/tests/`에 추가한다. Proxmox 호출은 mock한다. `conftest.py`가 `get_server_resource_usage`를 이미 mock하고 있으므로 스토리지 선택은 `storage.get()` 응답을 mock해서 시험한다.

### 설정

- `get_clone_storages`: 공백·빈 항목·중복 처리, 순서 유지, 값이 없는 노드와 없는 노드 이름은 `[]`

### 스토리지 선택

- 두 후보 모두 조건을 만족하면 `avail`이 큰 쪽을 고른다
- `avail`이 같으면 목록 앞쪽을 고른다
- 사용률 80% 이상이면 `avail`이 더 커도 제외한다
- `avail`이 필요 용량보다 작으면 제외한다 (20 GB, 40 GB 각각)
- `active == 0`, `enabled == 0`, `content`에 `images` 없음, 노드에 없는 이름은 제외한다
- 모두 제외되면 507
- `storage.get()` 예외면 503

### `create_vm()`

- 목록이 있는 노드: `clone.post`에 `storage`가 들어간다. 합산 `disk_pct`가 80% 이상이어도 후보가 조건을 만족하면 통과한다
- 목록이 없는 노드: `clone.post`에 `storage`가 없다. 합산 `disk_pct` 80% 이상이면 지금처럼 507
- 선택이 실패하면 `Vm` 레코드가 남지 않고 VMID 선택·클론을 호출하지 않는다
- PROJECT_CUSTOM `custom_disk=40`이면 40 GB로 검사한다

### 실패 정리

- 클론 뒤 `_wait_for_clone`이 `HTTPException`(클론 실패·타임아웃)을 던지면: Proxmox VM `delete(purge=1)`를 호출하고, DB 레코드를 지우고, 원래 `HTTPException`이 그대로 올라간다
- 같은 상황에서 VMID가 Proxmox에 이미 없으면: `delete`를 호출하지 않고 lock 대기도 하지 않는다
- `clone.post` 자체가 실패하면(`clone_started`가 거짓): Proxmox VM `delete`를 호출하지 않는다
- 클론 뒤 일반 예외(예: iptables 등록 실패)면: 지금처럼 VM·iptables·스니펫을 정리하고 500을 낸다

### 큐

- 선택 실패(507) 작업은 `FAILED`가 되고 `error_message`에 메시지가 그대로 들어간다

## 배포 전 확인

1. **클론 시간 측정 (완료).** 2026-10-22에 Proxmox 웹 UI에서 gsmgpu3의 템플릿 1000을 Full Clone, Target Storage `node3Ssd2`로 임시 VMID에 클론했더니 약 2초 걸렸다. 임시 VM은 지웠다. `_wait_for_clone`의 대기 시간 120초는 바꾸지 않는다
2. **운영 백엔드가 프로세스 하나인지** 확인한다 (`WEB_CONCURRENCY`가 없거나 1, `--workers` 없음)
3. 운영 `.env`에 `NODE_3_CLONE_STORAGES=local-lvm,node3Ssd2`를 넣고 백엔드를 재시작한다
4. 콘솔에서 gsmgpu3에 VM을 하나 만들고, Proxmox Hardware에서 Hard Disk가 `node3Ssd2:vm-…`인지 본다. 확인 뒤 콘솔에서 지운다
5. 이전 테스트로 만든 VM은 콘솔에서 지운다

## 알려진 위험

- 클론 실패·타임아웃 때 Proxmox에 VM이 남던 기존 문제는 이번 범위에서 고친다 (「실패 정리」). 다만 클론이 진행 중인 채로 타임아웃이 나서 30초 안에 lock이 풀리지 않으면 여전히 남을 수 있다. 이때는 "수동 확인 필요" 경고 로그가 남는다
- 대시보드는 합산이라 여유가 있어 보여도, 스토리지마다 따로 판단하므로 생성이 거절될 수 있다

## 되돌리기

- `.env`의 `NODE_3_CLONE_STORAGES`를 지우거나 비우고 재시작하면 예전 동작으로 돌아간다
- 이미 `node3Ssd2`에 만든 VM은 그대로 동작한다. 시작·정지·삭제·스냅샷은 VM 설정에 적힌 스토리지를 Proxmox가 따라가므로 백엔드 변경이 필요 없다

## 범위 밖

- 대시보드에 스토리지별 표시
- 기존 VM 디스크를 `node3Ssd2`로 옮기기
- gsmgpu1·2 설정
- 생성 후 디스크 크기 변경 기능 (지금은 CPU·RAM만 바꿀 수 있다)
