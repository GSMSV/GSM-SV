import logging
import re

import requests

from core.config import settings

logger = logging.getLogger(__name__)

RESERVED_SUBDOMAINS = {"admin", "api", "www", "status", "app", "mail", "ftp", "gsmsv"}
_SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_ADMIN_API_TIMEOUT = 5


def validate_subdomain(subdomain: str) -> str:
    """DNS 라벨 규격(RFC 1123 소문자·숫자·하이픈, 1~63자) + 예약어 검증"""
    if not _SUBDOMAIN_PATTERN.match(subdomain):
        raise ValueError("서브도메인은 영문 소문자·숫자·하이픈만 가능하며 1~63자입니다.")
    if subdomain in RESERVED_SUBDOMAINS:
        raise ValueError(f"'{subdomain}'은(는) 예약된 서브도메인입니다.")
    return subdomain


def _route_id(subdomain: str) -> str:
    return f"route-{subdomain}"


def add_route(subdomain: str, internal_ip: str, internal_port: int) -> bool:
    """Caddy Admin API에 reverse_proxy 라우트 등록. 실패해도 예외를 던지지 않고 False 반환"""
    full_domain = f"{subdomain}.{settings.CADDY_HTTPS_DOMAIN_SUFFIX}"
    delete_route(subdomain)  # 고아 라우트 선점 해제 — 실패해도 무시(항상 bool 반환, 예외 없음)
    payload = {
        "@id": _route_id(subdomain),
        "match": [{"host": [full_domain]}],
        "handle": [{
            "handler": "reverse_proxy",
            "upstreams": [{"dial": f"{internal_ip}:{internal_port}"}],
        }],
    }
    try:
        resp = requests.post(
            f"{settings.CADDY_ADMIN_API_URL}/config/apps/http/servers/srv0/routes",
            json=payload,
            timeout=_ADMIN_API_TIMEOUT,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"[caddy] 라우트 추가 실패 ({full_domain}): {e}")
        return False


def delete_route(subdomain: str) -> bool:
    """Caddy Admin API에서 라우트 삭제. 이미 없는 라우트(400)도 목표 상태 달성으로 간주해 True"""
    try:
        resp = requests.delete(
            f"{settings.CADDY_ADMIN_API_URL}/id/{_route_id(subdomain)}",
            timeout=_ADMIN_API_TIMEOUT,
        )
        if resp.status_code == 400:
            return True
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"[caddy] 라우트 삭제 실패 ({subdomain}): {e}")
        return False
