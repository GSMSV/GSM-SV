"""https_gateway API — 소유자 검증, 개수 제한, 중복 서브도메인, Caddy 실패 허용"""
import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from models.https_route import HttpsRoute
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm
from schemas.https_schema import HttpsRouteCreate
from api.routes.https_gateway import add_https_route, delete_https_route, get_https_routes


def _make_user_and_vm(db, email="https-api@gsm.hs.kr", vmid=400, internal_ip="10.0.0.160"):
    user = User(email=email, hashed_password="h", role=UserRole.USER, is_active=True)
    server = db.query(Server).filter(Server.name == "test-node").first()
    if server is None:
        server = Server(
            name="test-node",
            ip_address="192.168.1.10",
            port=8006,
            api_user="root@pam",
            api_password="password",
            is_active=True,
            gateway_ip="192.168.1.1",
            gateway_user="admin",
            gateway_password="gwpass",
            base_port=21000,
        )
        db.add(server)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(server)
    vm = Vm(
        hypervisor_vmid=vmid,
        name="https-api-vm",
        server_id=server.id,
        owner_id=user.id,
        internal_ip=internal_ip,
    )
    db.add(vm)
    db.commit()
    db.refresh(vm)
    return user, vm


class TestAddHttpsRoute:
    @patch("api.routes.https_gateway.caddy_service.add_route", return_value=True)
    def test_success_saves_and_syncs(self, mock_add, db):
        user, vm = _make_user_and_vm(db)
        body = HttpsRouteCreate(subdomain="myapp", internal_port=8080)

        result = asyncio.run(
            add_https_route("test-node", vm.hypervisor_vmid, body, db=db, current_user=user)
        )

        assert result["subdomain"] == "myapp"
        assert result["full_domain"] == "myapp.https.gsmsv.site"
        assert result["caddy_synced"] is True
        mock_add.assert_called_once_with("myapp", "10.0.0.160", 8080)
        assert db.query(HttpsRoute).filter(HttpsRoute.vm_id == vm.id).count() == 1

    @patch("api.routes.https_gateway.caddy_service.add_route", return_value=False)
    def test_caddy_failure_still_saves_route(self, mock_add, db):
        user, vm = _make_user_and_vm(db)
        body = HttpsRouteCreate(subdomain="myapp", internal_port=8080)

        result = asyncio.run(
            add_https_route("test-node", vm.hypervisor_vmid, body, db=db, current_user=user)
        )

        assert result["caddy_synced"] is False
        assert db.query(HttpsRoute).filter(HttpsRoute.vm_id == vm.id).count() == 1

    @patch("api.routes.https_gateway.caddy_service.add_route", return_value=True)
    def test_exceeds_max_per_vm(self, mock_add, db):
        user, vm = _make_user_and_vm(db)
        db.add(HttpsRoute(vm_id=vm.id, subdomain="one", internal_port=80, caddy_synced=True))
        db.add(HttpsRoute(vm_id=vm.id, subdomain="two", internal_port=81, caddy_synced=True))
        db.commit()

        body = HttpsRouteCreate(subdomain="three", internal_port=82)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                add_https_route("test-node", vm.hypervisor_vmid, body, db=db, current_user=user)
            )
        assert exc_info.value.status_code == 409

    @patch("api.routes.https_gateway.caddy_service.add_route", return_value=True)
    def test_duplicate_subdomain_across_vms_rejected(self, mock_add, db):
        user1, vm1 = _make_user_and_vm(db, email="owner1@gsm.hs.kr", vmid=401)
        user2, vm2 = _make_user_and_vm(db, email="owner2@gsm.hs.kr", vmid=402, internal_ip="10.0.0.161")

        asyncio.run(
            add_https_route(
                "test-node", vm1.hypervisor_vmid,
                HttpsRouteCreate(subdomain="shared", internal_port=80),
                db=db, current_user=user1,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                add_https_route(
                    "test-node", vm2.hypervisor_vmid,
                    HttpsRouteCreate(subdomain="shared", internal_port=80),
                    db=db, current_user=user2,
                )
            )
        assert exc_info.value.status_code == 409

    def test_no_internal_ip_rejected(self, db):
        user, vm = _make_user_and_vm(db, internal_ip=None)
        body = HttpsRouteCreate(subdomain="myapp", internal_port=8080)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                add_https_route("test-node", vm.hypervisor_vmid, body, db=db, current_user=user)
            )
        assert exc_info.value.status_code == 400


class TestDeleteHttpsRoute:
    @patch("api.routes.https_gateway.caddy_service.delete_route", return_value=True)
    def test_deletes_db_row_and_calls_caddy(self, mock_delete, db):
        user, vm = _make_user_and_vm(db)
        route = HttpsRoute(vm_id=vm.id, subdomain="myapp", internal_port=8080, caddy_synced=True)
        db.add(route)
        db.commit()
        db.refresh(route)

        result = asyncio.run(
            delete_https_route("test-node", vm.hypervisor_vmid, route.id, db=db, current_user=user)
        )

        assert result["success"] is True
        mock_delete.assert_called_once_with("myapp")
        assert db.query(HttpsRoute).filter(HttpsRoute.id == route.id).first() is None

    def test_not_owner_returns_404(self, db):
        owner, vm = _make_user_and_vm(db, email="owner@gsm.hs.kr", vmid=410)
        other = User(email="other@gsm.hs.kr", hashed_password="h", role=UserRole.USER, is_active=True)
        db.add(other)
        db.commit()
        db.refresh(other)

        route = HttpsRoute(vm_id=vm.id, subdomain="myapp", internal_port=8080)
        db.add(route)
        db.commit()
        db.refresh(route)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                delete_https_route("test-node", vm.hypervisor_vmid, route.id, db=db, current_user=other)
            )
        assert exc_info.value.status_code == 404


class TestGetHttpsRoutes:
    def test_lists_vm_routes(self, db):
        user, vm = _make_user_and_vm(db)
        db.add(HttpsRoute(vm_id=vm.id, subdomain="myapp", internal_port=8080, caddy_synced=True))
        db.commit()

        result = asyncio.run(
            get_https_routes("test-node", vm.hypervisor_vmid, db=db, current_user=user)
        )

        assert result["vmid"] == vm.hypervisor_vmid
        assert len(result["routes"]) == 1
        assert result["routes"][0]["subdomain"] == "myapp"
