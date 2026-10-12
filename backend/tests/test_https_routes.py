"""HttpsRoute 모델 — 생성·조회·Vm relationship 테스트"""
from models.https_route import HttpsRoute
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm


def _make_user_and_vm(db, subdomain_owner_email="https-owner@gsm.hs.kr"):
    user = User(email=subdomain_owner_email, hashed_password="h", role=UserRole.USER, is_active=True)
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
    db.add_all([user, server])
    db.commit()
    db.refresh(user)
    db.refresh(server)
    vm = Vm(
        hypervisor_vmid=300,
        name="https-test-vm",
        server_id=server.id,
        owner_id=user.id,
        internal_ip="10.0.0.150",
    )
    db.add(vm)
    db.commit()
    db.refresh(vm)
    return user, vm


class TestHttpsRouteModel:
    def test_create_and_query_via_vm_relationship(self, db):
        user, vm = _make_user_and_vm(db)

        route = HttpsRoute(vm_id=vm.id, subdomain="myapp", internal_port=8080)
        db.add(route)
        db.commit()
        db.refresh(route)

        assert route.id is not None
        assert route.caddy_synced is False
        assert route.created_at is not None

        db.refresh(vm)
        assert len(vm.https_routes) == 1
        assert vm.https_routes[0].subdomain == "myapp"

    def test_subdomain_globally_unique(self, db):
        from sqlalchemy.exc import IntegrityError
        import pytest

        user, vm = _make_user_and_vm(db)
        db.add(HttpsRoute(vm_id=vm.id, subdomain="dup", internal_port=80))
        db.commit()

        db.add(HttpsRoute(vm_id=vm.id, subdomain="dup", internal_port=81))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
