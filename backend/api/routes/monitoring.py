import asyncio
import logging
import threading
import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.database import get_db
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm
from schemas.monitoring_schema import NodeStatsResponse
from services.proxmox_client import get_proxmox_for_server

logger = logging.getLogger(__name__)
router = APIRouter()
_NODE_STATS_TTL = 30
_node_stats_cache: dict[int, tuple[float, tuple, dict]] = {}
_node_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_cached_node_stats(server: Server) -> dict:
    """Cache only a node's metrics, never the user-filtered aggregate response."""
    with _locks_guard:
        node_lock = _node_locks.setdefault(server.id, threading.Lock())

    # Serialize misses for this node, without holding up other nodes.
    with node_lock:
        identity = (server.name, server.ip_address, server.port, server.api_user)
        cached = _node_stats_cache.get(server.id)
        if cached and cached[0] > time.monotonic() and cached[1] == identity:
            return cached[2].copy()

        try:
            proxmox = get_proxmox_for_server(server)
            node_status = proxmox.nodes(server.name).status.get()
            cpu_usage = node_status.get("cpu", 0) * 100
            memory = node_status.get("memory", {})
            total_ram_gb = memory.get("total", 0) / (1024**3)
            used_ram_gb = memory.get("used", 0) / (1024**3)
            stats = {
                "status": "online",
                "cpu_usage_percent": round(cpu_usage, 1),
                "ram_total_gb": round(total_ram_gb, 1),
                "ram_used_gb": round(used_ram_gb, 1),
                "ram_free_gb": round(total_ram_gb - used_ram_gb, 1),
                "uptime_seconds": node_status.get("uptime", 0),
            }
        except Exception as exc:  # noqa: BLE001 - retain the endpoint's offline fallback
            logger.error("[monitoring] 노드 %s 조회 실패: %s", server.name, exc)
            stats = {"status": "offline", "error": "노드에 연결할 수 없습니다."}

        # Start the TTL after network I/O, including failed lookups.
        _node_stats_cache[server.id] = (time.monotonic() + _NODE_STATS_TTL, identity, stats)
        return stats.copy()


@router.get("/nodes", response_model=NodeStatsResponse)
async def get_system_stats(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    활성 서버(Node)의 리소스 취합 조회.
    ADMIN/PROJECT_OWNER: 전체 노드 조회 / USER: 본인 VM이 위치한 노드만 조회
    """
    query = db.query(Server).filter(Server.is_active == True)
    if current_user.role not in (UserRole.ADMIN, UserRole.PROJECT_OWNER):
        user_server_ids = (
            db.query(Vm.server_id)
            .filter(Vm.owner_id == current_user.id)
            .distinct()
            .scalar_subquery()
        )
        query = query.filter(Server.id.in_(user_server_ids))
    servers = query.all()
    if not servers:
        return {"message": "등록된 활성 서버가 없습니다.", "stats": {}}

    all_stats = {}

    for server in servers:
        all_stats[server.name] = await asyncio.to_thread(_get_cached_node_stats, server)

    return {"stats": all_stats}
