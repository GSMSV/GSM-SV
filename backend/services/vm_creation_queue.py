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
    """?쒓컙???뺣젹??媛?ν븳 VM ?앹꽦 ?묒뾽 ID瑜?留뚮뱺??"""
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
    """?ъ떆????泥섎━ 以묒씠???묒뾽源뚯? ?ㅼ떆 ?湲곗뿴濡??섎룎由곕떎."""
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
        _vm_creation_queue.put(job.id)

    if pending_jobs:
        db.commit()

    return pending_jobs


def validate_vm_creation_request(db: Session, current_user: User, vm_config: VMCreate) -> Server:
    """?먯뿉 ?ｊ린 ?꾩뿉 理쒖냼?쒖쓽 ?좉?利앸쭔 ?섑뻾?쒕떎."""
    if not vm_config.node_name:
        raise HTTPException(status_code=400, detail="node_name??吏?뺥빐 二쇱꽭??")

    if current_user.role == UserRole.USER and vm_config.node_name == settings.PROJECT_NODE_NAME:
        raise HTTPException(
            status_code=403,
            detail="?쇰컲 ?ъ슜?먮뒗 ?꾨줈?앺듃 ?꾩슜 ?몃뱶??VM???앹꽦?????놁뒿?덈떎.",
        )

    if vm_config.tier == VMTier.PROJECT_CUSTOM and current_user.role not in (
        UserRole.ADMIN,
        UserRole.PROJECT_OWNER,
    ):
        raise HTTPException(
            status_code=403,
            detail="?꾨줈?앺듃 而ㅼ뒪? ?곗뼱???꾨줈?앺듃 ?ㅻ꼫留??ъ슜?????덉뒿?덈떎.",
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
                    "?앹꽦 ?湲?吏꾪뻾 以묒씤 ?묒뾽???ы븿?섏뿬 "
                    f"?앹꽦 媛?ν븳 理쒕? VM 媛쒖닔({settings.MAX_VMS_PER_USER}媛?瑜?珥덇낵?덉뒿?덈떎."
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
            detail=f"?몃뱶 '{vm_config.node_name}'??瑜? 李얠쓣 ???녾굅??鍮꾪솢???곹깭?낅땲??",
        )
    return server


def enqueue_vm_creation(db: Session, current_user: User, vm_config: VMCreate) -> VMCreationJobResponse:
    """VM ?앹꽦 ?붿껌???먯뿉 ?ｊ퀬 ?묒뾽 ?뺣낫瑜?諛섑솚?쒕떎."""
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
        raise HTTPException(status_code=404, detail="VM ?앹꽦 ?묒뾽??李얠쓣 ???놁뒿?덈떎.")

    if current_user.role != UserRole.ADMIN and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="VM ?앹꽦 ?묒뾽??李얠쓣 ???놁뒿?덈떎.")

    return _serialize_job(job, position=_get_queue_position(db, job))


def process_vm_creation_job(job_id: str) -> None:
    """?먯뿉??爰쇰궦 ?⑥씪 ?묒뾽??泥섎━?쒕떎."""
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
            logger.info("[vm-queue] ?묒뾽 %s???대? ?ㅻⅨ ?뚯빱媛 泥섎━?덇굅???곹깭媛 蹂寃쎈맖", job_id)
            return
        job_db.commit()

        job = job_db.query(VmCreationJob).filter(VmCreationJob.id == job_id).first()
        if not job:
            logger.warning("[vm-queue] ?묒뾽??李얠쓣 ???놁쓬: %s", job_id)
            return

        payload = job.payload
        user = work_db.query(User).filter(User.id == job.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="?묒뾽 ?뚯쑀?먮? 李얠쓣 ???놁뒿?덈떎.")

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
        logger.info("[vm-queue] ?묒뾽 ?꾨즺: %s -> VMID %s", job_id, job.vmid)
    except Exception as exc:
        logger.exception("[vm-queue] ?묒뾽 ?ㅽ뙣: %s", job_id)
        try:
            job_db.rollback()
            job = job_db.query(VmCreationJob).filter(VmCreationJob.id == job_id).first()
            if job:
                job.status = VMCreationJobStatus.FAILED.value
                job.finished_at = now_kst()
                job.error_message = getattr(exc, "detail", None) or str(exc)
                job.message = "VM ?앹꽦???ㅽ뙣?덉뒿?덈떎."
                job_db.commit()
        except Exception:
            job_db.rollback()
            logger.exception("[vm-queue] ?ㅽ뙣 ?곹깭 湲곕줉 以??ㅻ쪟: %s", job_id)
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
                logger.exception("[vm-queue] ?뚯빱 猷⑦봽?먯꽌 ?덉쇅 諛쒖깮: %s", exc)
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
                    "[vm-queue] DB?먯꽌 %d媛쒖쓽 ?湲?/?ㅽ뻾 ?묒뾽???먯뿉 ?ъ쟻?ы뻽?듬땲??",
                    len(queued_jobs),
                )
        except Exception as exc:
            logger.exception("[vm-queue] ?湲??묒뾽 ?ъ쟻??以??ㅻ쪟 諛쒖깮: %s", exc)
        finally:
            db.close()
            db = None

        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="vm-creation-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.info("[vm-queue] VM ?앹꽦 ?뚯빱 ?쒖옉")


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
            logger.info("[vm-queue] VM ?앹꽦 ?뚯빱 醫낅즺")
        else:
            logger.warning("[vm-queue] VM ?앹꽦 ?뚯빱媛 ?꾩쭅 ?ㅽ뻾 以묒엯?덈떎 (??꾩븘??.")
