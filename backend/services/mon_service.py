from sqlalchemy.orm import Session
from models.server import Server
from services.proxmox_client import get_proxmox_for_server
from fastapi import HTTPException
import logging
from typing import Iterable

logger = logging.getLogger(__name__)

def update_server_stats(db: Session, server: Server):
    """특정 서버(Proxmox Node)에 비동기로 접속하여 잔여 RAM 용량을 조회하고 DB를 업데이트합니다."""
    try:
        proxmox = get_proxmox_for_server(server)
        node_status = proxmox.nodes(server.name).status.get()

        total_memory = node_status.get('memory', {}).get('total', 0)
        used_memory = node_status.get('memory', {}).get('used', 0)
        free_ram_mb = (total_memory - used_memory) // (1024 * 1024)

        server.last_free_ram_mb = free_ram_mb
        db.commit()
        return free_ram_mb
    except Exception as e:
        logger.exception(f"서버 {server.name} 상태 업데이트 실패: {e}")
        try:
            db.rollback()
            server.last_free_ram_mb = 0
            db.commit()
        except Exception as db_err:
            logger.exception(f"서버 {server.name} RAM 상태 초기화 실패: {db_err}")
        return None


def get_server_resource_usage(server: Server) -> dict:
    """서버의 CPU·RAM·SSD 사용률(%)을 실시간 조회해 반환합니다."""
    proxmox = get_proxmox_for_server(server)
    node_status = proxmox.nodes(server.name).status.get()

    memory = node_status.get('memory', {})
    total_mem = memory.get('total', 0)
    used_mem = memory.get('used', 0)
    ram_pct = round(used_mem / total_mem * 100, 1) if total_mem else 0.0

    cpu_pct = round(node_status.get('cpu', 0) * 100, 1)

    disk_used = 0
    disk_total = 0
    try:
        storages = proxmox.nodes(server.name).storage.get()
        for st in storages:
            if st.get("type") == "lvmthin":
                disk_used += st.get("used", 0)
                disk_total += st.get("total", 0)
    except Exception:
        pass
    disk_pct = round(disk_used / disk_total * 100, 1) if disk_total else None

    return {"ram_pct": ram_pct, "cpu_pct": cpu_pct, "disk_pct": disk_pct}

def get_best_server(
    db: Session,
    required_ram_mb: int,
    *,
    allowed_nodes: Iterable[str] | None = None,
    excluded_nodes: Iterable[str] | None = None,
) -> Server:
    """
    요구되는 RAM(MB)를 감당할 수 있으면서, 가장 여유 자원이 많은 서버를 찾습니다.
    (Resource-Based Auto Provisioning)
    """
    # 1. 활성화된 모든 서버 목록 가져오기
    query = db.query(Server).filter(Server.is_active == True)
    if allowed_nodes is not None:
        allowed_set = {node for node in allowed_nodes if node is not None}
        if allowed_set:
            query = query.filter(Server.name.in_(allowed_set))
        else:
            query = query.filter(Server.id == -1)
    if excluded_nodes is not None:
        excluded_set = {node for node in excluded_nodes if node is not None}
        if excluded_set:
            query = query.filter(~Server.name.in_(excluded_set))
    active_servers = query.all()
    
    if not active_servers:
        if allowed_nodes is not None or excluded_nodes is not None:
            raise HTTPException(status_code=503, detail="요청 가능한 활성 서버가 없습니다.")
        raise HTTPException(status_code=500, detail="사용 가능한 활성 서버가 없습니다.")
    
    # 2. (옵션) 실시간에 가깝게 하기 위해 할당 전 모든 서버의 RAM 상태를 1회 갱신 (트래픽이 적을 때 유효)
    # 트래픽이 많다면 이 부분은 백그라운드 스케줄러(ex: Celery, APScheduler)로 빼는 것이 좋습니다.
    for server in active_servers:
        update_server_stats(db, server)
        
    # 3. 요구사항을 충족(required_ram_mb 이상 여유)하는 서버들만 필터링
    capable_servers = [s for s in active_servers if s.last_free_ram_mb >= required_ram_mb]
    
    if not capable_servers:
        raise HTTPException(
            status_code=507, 
            detail=f"요청한 RAM({required_ram_mb}MB)을 할당할 여유 자원을 가진 서버가 없습니다."
        )
    
    # 4. 여유 RAM이 가장 많은 서버(가장 한가한 녀석) 선택 후 반환
    # (Python 내장 함수 max를 활용하여 last_free_ram_mb 기준으로 정렬)
    best_server = max(capable_servers, key=lambda s: s.last_free_ram_mb)
    
    return best_server
