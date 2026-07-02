import logging
import os
import queue
import time
import threading
from itertools import count
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from core.timezone import now_kst
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm
from models.vm_creation_job import VmCreationJob
from schemas.vm_schema import VMCreate, VMCreationJobResponse, VMCreationJobStatus, VMOs, VMTier
from services.vm_service import create_vm

logger = logging.getLogger(__name__)

_QUEUE_STOP_SENTINEL = "__STOP__"
_vm_creation_queue: "queue.Queue[str]" = queue.Queue()
_worker_thread: Optional[threading.Thread] = None
_worker_lock = threading.Lock()
_worker_stop_event = threading.Event()
_job_id_counter = count()


def _next_job_id() -> str:
    """타임스탬프 기반의 유일한 VM 생성 작업 ID를 생성한다."""
    return f"{time.time_ns():019d}-{os.getpid():05d}-{next(_job_id_counter):06d}"


def _serialize_job(job: VmCreationJob, position: int | None = None) -> VMCreationJobResponse:
    return VMCreationJobResponse(
        job_id=job.id,
        status=VMCreationJobStatus(job.status),
        position=position,
        requested_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        vmid=job.vmid,
        node_name=job.node_name,
        message=job.message,
        error_message=job.error_message,
        result=job.result,
    )


def _get_queue_position(db: Session, job: VmCreationJob) -> int | None:
    if job.status != VMCreationJobStatus.QUEUED.value:
        return None
    return (
        db.query(VmCreationJob)
        .filter(
            VmCreationJob.status == VMCreationJobStatus.QUEUED.value,
            or_(
                VmCreationJob.queued_at < job.queued_at,
                and_(
                    VmCreationJob.queued_at == job.queued_at,
                    VmCreationJob.id <= job.id,
                ),
            ),
        )
        .count()
    )


def _recover_pending_jobs(db: Session) -> list[VmCreationJob]:
    """재시작 후 미처리 상태인 작업들을 다시 큐로 되돌린다."""
    pending_jobs = (
        db.query(VmCreationJob)
        .filter(
            VmCreationJob.status.in_([
                VMCreationJobStatus.QUEUED.value,
                VMCreationJobStatus.RUNNING.value,
            ]),
        )
        .order_by(VmCreationJob.queued_at.asc(), VmCreationJob.id.asc())
        .all()
    )

    for job in pending_jobs:
        if job.status == VMCreationJobStatus.RUNNING.value:
            job.status = VMCreationJobStatus.QUEUED.value
            job.started_at = None
            job.attempts += 1
        _vm_creation_queue.put(job.id)

    if pending_jobs:
        db.commit()

    return pending_jobs


def validate_vm_creation_request(db: Session, current_user: User, vm_config: VMCreate) -> Server:
    """큐에 넣기 전에 기본적인 유효성 검증을 수행한다."""
    if not vm_config.node_name:
        raise HTTPException(status_code=400, detail="node_name을 지정해 주세요.")

    if current_user.role == UserRole.USER and vm_config.node_name == settings.PROJECT_NODE_NAME:
        raise HTTPException(
            status_code=403,
            detail="일반 사용자는 프로젝트 전용 노드에 VM을 생성할 수 없습니다.",
        )

    if vm_config.tier == VMTier.PROJECT_CUSTOM and current_user.role not in (
        UserRole.ADMIN,
        UserRole.PROJECT_OWNER,
    ):
        raise HTTPException(
            status_code=403,
            detail="프로젝트 티어는 프로젝트 오너만 사용할 수 있습니다.",
        )

    if current_user.role == UserRole.USER:
        user_vm_count = db.query(Vm).filter(Vm.owner_id == current_user.id).count()
        active_jobs_count = db.query(VmCreationJob).filter(
            VmCreationJob.user_id == current_user.id,
            VmCreationJob.status.in_([
                VMCreationJobStatus.QUEUED.value,
                VMCreationJobStatus.RUNNING.value,
            ]),
        ).count()
        if user_vm_count + active_jobs_count >= settings.MAX_VMS_PER_USER:
            raise HTTPException(
                status_code=409,
                detail=(
                    "생성 대기/실행 중인 작업을 포함하여 "
                    f"생성 가능한 최대 VM 개수({settings.MAX_VMS_PER_USER}개)를 초과합니다."
                ),
            )

    server = (
        db.query(Server)
        .filter(Server.name == vm_config.node_name, Server.is_active.is_(True))
        .first()
    )
    if not server:
        raise HTTPException(
            status_code=404,
            detail=f"노드 '{vm_config.node_name}'을(를) 찾을 수 없거나 비활성 상태입니다.",
        )
    return server


def enqueue_vm_creation(db: Session, current_user: User, vm_config: VMCreate) -> VMCreationJobResponse:
    """VM 생성 요청을 큐에 넣고 작업 정보를 반환한다."""
    validate_vm_creation_request(db, current_user, vm_config)

    job = VmCreationJob(
        id=_next_job_id(),
        user_id=current_user.id,
        status=VMCreationJobStatus.QUEUED.value,
        tier=vm_config.tier.value,
        os=vm_config.os.value,
        node_name=vm_config.node_name,
        requested_name=vm_config.name,
    )
    job.payload = vm_config.model_dump(mode="json")
    db.add(job)
    db.commit()
    db.refresh(job)

    _vm_creation_queue.put(job.id)
    return _serialize_job(job, position=_get_queue_position(db, job))


def get_vm_creation_job(db: Session, job_id: str, current_user: User) -> VMCreationJobResponse:
    job = db.query(VmCreationJob).filter(VmCreationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="VM 생성 작업을 찾을 수 없습니다.")

    if current_user.role != UserRole.ADMIN and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="VM 생성 작업을 찾을 수 없습니다.")

    return _serialize_job(job, position=_get_queue_position(db, job))


def process_vm_creation_job(job_id: str) -> None:
    """큐에서 가져온 단일 작업을 처리한다."""
    job_db = SessionLocal()
    work_db = SessionLocal()
    try:
        claimed_at = now_kst()
        claimed_rows = (
            job_db.query(VmCreationJob)
            .filter(
                VmCreationJob.id == job_id,
                VmCreationJob.status == VMCreationJobStatus.QUEUED.value,
            )
            .update(
                {
                    VmCreationJob.status: VMCreationJobStatus.RUNNING.value,
                    VmCreationJob.started_at: claimed_at,
                    VmCreationJob.attempts: VmCreationJob.attempts + 1,
                },
                synchronize_session=False,
            )
        )
        if claimed_rows == 0:
            job_db.rollback()
            logger.info("[vm-queue] 작업 %s는 이미 다른 워커가 처리했거나 상태가 변경됨", job_id)
            return
        job_db.commit()

        job = job_db.query(VmCreationJob).filter(VmCreationJob.id == job_id).first()
        if not job:
            logger.warning("[vm-queue] 작업을 찾을 수 없음: %s", job_id)
            return

        # 멱등성 보장: vmid가 이미 설정된 경우 VM이 이미 생성된 것으로 간주
        if job.vmid is not None:
            logger.warning("[vm-queue] 작업 %s에 vmid %s가 이미 설정되어 있음, 중복 생성 방지", job_id, job.vmid)
            job.status = VMCreationJobStatus.COMPLETED.value
            job.finished_at = now_kst()
            job_db.commit()
            return

        payload = job.payload
        user = work_db.query(User).filter(User.id == job.user_id).first()
        if not user:
            raise RuntimeError(f"작업 사용자를 찾을 수 없습니다: user_id={job.user_id}")

        result = create_vm(
            db=work_db,
            current_user=user,
            tier=VMTier(payload["tier"]),
            os=VMOs(payload["os"]),
            node_name=payload.get("node_name"),
            name=payload.get("name"),
            custom_cores=payload.get("custom_cores"),
            custom_memory=payload.get("custom_memory"),
            custom_disk=payload.get("custom_disk"),
        )

        job.status = VMCreationJobStatus.COMPLETED.value
        job.finished_at = now_kst()
        job.vmid = result.get("vmid")
        job.node_name = result.get("assigned_node") or job.node_name
        job.message = result.get("message")
        job.result = result
        job.error_message = None
        job_db.commit()
        logger.info("[vm-queue] 작업 완료: %s -> VMID %s", job_id, job.vmid)
    except Exception as exc:
        logger.exception("[vm-queue] 작업 실패: %s", job_id)
        try:
            job_db.rollback()
            job = job_db.query(VmCreationJob).filter(VmCreationJob.id == job_id).first()
            if job:
                job.status = VMCreationJobStatus.FAILED.value
                job.finished_at = now_kst()
                job.error_message = getattr(exc, "detail", None) or str(exc)
                job.message = "VM 생성에 실패했습니다."
                job_db.commit()
        except Exception:
            job_db.rollback()
            logger.exception("[vm-queue] 실패 상태 기록 중 오류: %s", job_id)
    finally:
        work_db.close()
        job_db.close()


def _worker_loop() -> None:
    while not _worker_stop_event.is_set():
        try:
            job_id = _vm_creation_queue.get(timeout=1)
        except queue.Empty:
            continue

        try:
            if job_id == _QUEUE_STOP_SENTINEL:
                return
            try:
                process_vm_creation_job(job_id)
            except Exception as exc:
                logger.exception("[vm-queue] 워커 루프에서 예외 발생: %s", exc)
        finally:
            _vm_creation_queue.task_done()


def start_vm_creation_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_stop_event.clear()

        db = SessionLocal()
        try:
            queued_jobs = _recover_pending_jobs(db)
            if queued_jobs:
                logger.info(
                    "[vm-queue] DB에서 %d개의 대기/실행 작업을 큐에 적재했습니다",
                    len(queued_jobs),
                )
        except Exception as exc:
            logger.exception("[vm-queue] 대기 작업 적재 중 오류 발생: %s", exc)
        finally:
            db.close()
            db = None

        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="vm-creation-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.info("[vm-queue] VM 생성 워커 시작")


def stop_vm_creation_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if not _worker_thread or not _worker_thread.is_alive():
            return
        _worker_stop_event.set()
        _vm_creation_queue.put(_QUEUE_STOP_SENTINEL)
        _worker_thread.join(timeout=5)
        if not _worker_thread.is_alive():
            _worker_thread = None
            logger.info("[vm-queue] VM 생성 워커 종료")
        else:
            logger.warning("[vm-queue] VM 생성 워커가 여전히 실행 중입니다 (강제 종료).")
