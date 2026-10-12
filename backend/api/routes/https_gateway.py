import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_vm_with_owner_check
from core.config import settings
from core.database import get_db
from models.https_route import HttpsRoute
from models.user import User
from schemas.https_schema import HttpsRouteCreate
from services import caddy_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize(route: HttpsRoute) -> dict:
    return {
        "id": route.id,
        "subdomain": route.subdomain,
        "full_domain": f"{route.subdomain}.{settings.CADDY_HTTPS_DOMAIN_SUFFIX}",
        "internal_port": route.internal_port,
        "caddy_synced": route.caddy_synced,
        "created_at": route.created_at,
    }


@router.get("/{node}/{vmid}/routes")
async def get_https_routes(
    node: str,
    vmid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """VM의 HTTPS 라우트 목록 조회 (소유자 또는 관리자)"""
    vm = get_vm_with_owner_check(db, vmid, current_user, node=node)
    routes = db.query(HttpsRoute).filter(HttpsRoute.vm_id == vm.id).all()
    return {"vmid": vmid, "routes": [_serialize(r) for r in routes]}


@router.post("/{node}/{vmid}/routes", status_code=status.HTTP_201_CREATED)
async def add_https_route(
    node: str,
    vmid: int,
    body: HttpsRouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """HTTPS 서브도메인 라우트 추가 — DB 저장 + Caddy Admin API 등록(실패해도 저장은 유지)"""
    vm = get_vm_with_owner_check(db, vmid, current_user, node=node)

    if not vm.internal_ip:
        raise HTTPException(status_code=400, detail="VM에 내부 IP가 할당되지 않았습니다.")

    route_count = db.query(HttpsRoute).filter(HttpsRoute.vm_id == vm.id).count()
    if route_count >= settings.MAX_HTTPS_ROUTES_PER_VM:
        raise HTTPException(
            status_code=409,
            detail=f"VM당 HTTPS 라우트는 최대 {settings.MAX_HTTPS_ROUTES_PER_VM}개까지 추가할 수 있습니다.",
        )

    https_route = HttpsRoute(
        vm_id=vm.id,
        subdomain=body.subdomain,
        internal_port=body.internal_port,
        caddy_synced=False,
    )
    db.add(https_route)
    try:
        db.commit()
        db.refresh(https_route)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="이미 사용 중인 서브도메인입니다.")
    except Exception as e:
        db.rollback()
        logger.error(f"[https_gateway] DB 저장 실패: {e}")
        raise HTTPException(status_code=500, detail="라우트 저장에 실패했습니다.")

    synced = caddy_service.add_route(body.subdomain, vm.internal_ip, body.internal_port)
    if synced != https_route.caddy_synced:
        https_route.caddy_synced = synced
        db.commit()
        db.refresh(https_route)

    return _serialize(https_route)


@router.delete("/{node}/{vmid}/routes/{route_id}", status_code=status.HTTP_200_OK)
async def delete_https_route(
    node: str,
    vmid: int,
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """HTTPS 라우트 삭제 — Caddy Admin API 제거 + DB 삭제 (Caddy 실패해도 DB는 삭제)"""
    vm = get_vm_with_owner_check(db, vmid, current_user, node=node)

    https_route = (
        db.query(HttpsRoute)
        .filter(HttpsRoute.id == route_id, HttpsRoute.vm_id == vm.id)
        .first()
    )
    if not https_route:
        raise HTTPException(status_code=404, detail="라우트를 찾을 수 없습니다.")

    if not caddy_service.delete_route(https_route.subdomain):
        logger.error(f"[https_gateway] Caddy 라우트 삭제 실패, DB만 정리 — {https_route.subdomain}")

    subdomain = https_route.subdomain
    db.delete(https_route)
    db.commit()
    return {"success": True, "message": f"라우트 '{subdomain}' 삭제 완료"}
