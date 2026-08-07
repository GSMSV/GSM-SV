"""VM 삭제 시 연결된 HTTPS 라우트 자동 정리"""
from unittest.mock import MagicMock, patch

from models.https_route import HttpsRoute
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm
from services.vm_service import delete_vm


def _make_mock_proxmox():
    proxmox = MagicMock()
    node = proxmox.nodes.return_value
    node.qemu.return_value.status.current.get.return_value = {"status": "stopped"}
    node.qemu.return_value.delete.return_value = None
    return proxmox


def _make_user_server_vm(db):
    user = User(email="cleanup@gsm.hs.kr", hashed_password="h", role=UserRole.USER, is_active=True)
    server = Server(
        name="test-node",
        ip_address="192.168.1.10",
        port=8006,
        api_user="root@pam",
        api_password="password",
        is_active=True,
        gateway_ip="",
        gateway_user="",
        gateway_password="",
        base_port=21000,
    )
    db.add_all([user, server])
    db.commit()
    db.refresh(user)
    db.refresh(server)
    vm = Vm(
        hypervisor_vmid=500,
        name="cleanup-vm",
        server_id=server.id,
        owner_id=user.id,
        internal_ip="10.0.0.170",
    )
    db.add(vm)
    db.commit()
    db.refresh(vm)
    return user, server, vm


class TestVmDeleteCleansHttpsRoutes:
    @patch("services.vm_service.manage_iptables", return_value=True)
    @patch("services.vm_service.caddy_service.delete_route", return_value=True)
    @patch("services.vm_service.get_proxmox_for_server")
    def test_delete_vm_calls_caddy_delete_for_each_route_and_removes_rows(
        self, mock_proxmox_fn, mock_delete_route, mock_iptables, db
    ):
        mock_proxmox_fn.return_value = _make_mock_proxmox()
        user, server, vm = _make_user_server_vm(db)
        db.add(HttpsRoute(vm_id=vm.id, subdomain="one", internal_port=80, caddy_synced=True))
        db.add(HttpsRoute(vm_id=vm.id, subdomain="two", internal_port=81, caddy_synced=True))
        db.commit()

        delete_vm(db, vm)
        db.commit()

        assert mock_delete_route.call_count == 2
        called_subdomains = {c.args[0] for c in mock_delete_route.call_args_list}
        assert called_subdomains == {"one", "two"}
        assert db.query(HttpsRoute).filter(HttpsRoute.vm_id == vm.id).count() == 0
        assert db.query(Vm).filter(Vm.id == vm.id).first() is None

    @patch("services.vm_service.manage_iptables", return_value=True)
    @patch("services.vm_service.caddy_service.delete_route", return_value=False)
    @patch("services.vm_service.get_proxmox_for_server")
    def test_delete_vm_succeeds_even_if_caddy_delete_fails(
        self, mock_proxmox_fn, mock_delete_route, mock_iptables, db
    ):
        mock_proxmox_fn.return_value = _make_mock_proxmox()
        user, server, vm = _make_user_server_vm(db)
        db.add(HttpsRoute(vm_id=vm.id, subdomain="one", internal_port=80, caddy_synced=True))
        db.commit()

        delete_vm(db, vm)
        db.commit()

        assert db.query(Vm).filter(Vm.id == vm.id).first() is None
        assert db.query(HttpsRoute).count() == 0
