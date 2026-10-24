"""
VM 생성 시 클론 대상 스토리지 선택 테스트

- 노드별 후보 스토리지 설정(NODE_{N}_CLONE_STORAGES) 파싱
- 후보 중 사용률 80% 미만·디스크가 들어갈 수 있는 곳에서 남은 용량이 가장 큰 스토리지 선택
- create_vm의 클론 인자·SSD 검사·실패 정리

Proxmox/SSH/iptables는 mock으로 대체, DB는 conftest의 SQLite 사용.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from proxmoxer.core import ResourceException

from core.config import Settings, settings
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm
from schemas.vm_schema import VMTier
from services.mon_service import select_clone_storage
from services.vm_service import _wait_for_clone, create_vm

GIB = 1024 ** 3


# ── Fixture / 헬퍼 ────────────────────────────────────────────

@pytest.fixture
def user(db):
    u = User(
        email="clone-storage@gsm.hs.kr",
        hashed_password="hashed",
        role=UserRole.USER,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def server(db):
    s = Server(
        name="test-node",
        ip_address="192.168.1.10",
        port=8006,
        api_user="root@pam",
        api_password="password",
        ssh_user="root",
        ssh_password="sshpass",
        is_active=True,
        gateway_ip="192.168.1.1",
        gateway_user="admin",
        gateway_password="gwpass",
        base_port=21000,
        last_free_ram_mb=16000,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _storage(name, *, total_gib=1000, used_gib=0, avail_gib=None, active=1, enabled=1,
             content="images,rootdir"):
    """Proxmox GET /nodes/{node}/storage 응답 항목 하나"""
    st = {
        "storage": name,
        "type": "lvmthin",
        "total": total_gib * GIB,
        "used": used_gib * GIB,
        "active": active,
        "enabled": enabled,
        "content": content,
    }
    st["avail"] = (avail_gib if avail_gib is not None else total_gib - used_gib) * GIB
    return st


def _storage_proxmox(storages):
    proxmox = MagicMock()
    proxmox.nodes.return_value.storage.get.return_value = storages
    return proxmox


def _make_mock_proxmox(vmid=200):
    """create_vm용 Proxmox API mock"""
    proxmox = MagicMock()
    proxmox.cluster.nextid.get.return_value = str(vmid)
    node = proxmox.nodes.return_value
    node.qemu.return_value.clone.post.return_value = None
    node.qemu.return_value.config.get.return_value = {"name": "test"}
    node.qemu.return_value.status.current.get.return_value = {"status": "stopped"}
    return proxmox


SERVER = SimpleNamespace(name="gsmgpu3")


# ── 설정 파싱 ─────────────────────────────────────────────────

class TestGetCloneStorages:

    def test_parses_trims_and_dedupes_in_order(self, monkeypatch):
        monkeypatch.setattr(settings, "NODE_1_NAME", "node-a")
        monkeypatch.setattr(settings, "NODE_1_CLONE_STORAGES", " extra-ssd, local-lvm,,extra-ssd ")

        assert settings.get_clone_storages("node-a") == ["extra-ssd", "local-lvm"]

    def test_empty_value_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(settings, "NODE_1_NAME", "node-a")
        monkeypatch.setattr(settings, "NODE_1_CLONE_STORAGES", "")

        assert settings.get_clone_storages("node-a") == []

    def test_unknown_node_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(settings, "NODE_1_NAME", "node-a")
        monkeypatch.setattr(settings, "NODE_1_CLONE_STORAGES", "local-lvm")

        assert settings.get_clone_storages("no-such-node") == []
        assert settings.get_clone_storages("") == []


# ── 스토리지 선택 ─────────────────────────────────────────────

class TestSelectCloneStorage:

    @patch("services.mon_service.get_proxmox_for_server")
    def test_picks_largest_avail(self, mock_proxmox_fn):
        mock_proxmox_fn.return_value = _storage_proxmox([
            _storage("local-lvm", total_gib=1000, used_gib=600),  # 400GiB 남음
            _storage("extra-ssd", total_gib=1000, used_gib=100),  # 900GiB 남음
        ])

        assert select_clone_storage(SERVER, ["local-lvm", "extra-ssd"], 20) == "extra-ssd"

    @patch("services.mon_service.get_proxmox_for_server")
    def test_tie_prefers_first_candidate(self, mock_proxmox_fn):
        mock_proxmox_fn.return_value = _storage_proxmox([
            _storage("local-lvm", total_gib=1000, used_gib=100),
            _storage("extra-ssd", total_gib=1000, used_gib=100),
        ])

        assert select_clone_storage(SERVER, ["local-lvm", "extra-ssd"], 20) == "local-lvm"

    @patch("services.mon_service.get_proxmox_for_server")
    def test_usage_at_threshold_is_excluded_even_with_larger_avail(self, mock_proxmox_fn):
        mock_proxmox_fn.return_value = _storage_proxmox([
            _storage("big", total_gib=5000, used_gib=4000),        # 80% — 1000GiB 남아도 제외
            _storage("small", total_gib=500, used_gib=100),        # 20%, 400GiB 남음
        ])

        assert select_clone_storage(SERVER, ["big", "small"], 20) == "small"

    @pytest.mark.parametrize("disk_gb", [20, 40])
    @patch("services.mon_service.get_proxmox_for_server")
    def test_avail_smaller_than_disk_is_excluded(self, mock_proxmox_fn, disk_gb):
        mock_proxmox_fn.return_value = _storage_proxmox([
            _storage("tight", total_gib=1000, used_gib=0, avail_gib=disk_gb - 1),
            _storage("roomy", total_gib=1000, used_gib=0, avail_gib=disk_gb),
        ])

        assert select_clone_storage(SERVER, ["tight", "roomy"], disk_gb) == "roomy"

    @pytest.mark.parametrize("bad", [
        _storage("bad", active=0),
        _storage("bad", enabled=0),
        _storage("bad", content="iso,backup"),
        _storage("bad", total_gib=0),
    ])
    @patch("services.mon_service.get_proxmox_for_server")
    def test_unusable_storage_is_excluded(self, mock_proxmox_fn, bad):
        mock_proxmox_fn.return_value = _storage_proxmox([bad, _storage("good", total_gib=100, used_gib=50)])

        assert select_clone_storage(SERVER, ["bad", "good"], 20) == "good"

    @patch("services.mon_service.get_proxmox_for_server")
    def test_missing_storage_name_is_skipped(self, mock_proxmox_fn):
        mock_proxmox_fn.return_value = _storage_proxmox([_storage("local-lvm", total_gib=1000, used_gib=100)])

        assert select_clone_storage(SERVER, ["extra-sdd", "local-lvm"], 20) == "local-lvm"

    @patch("services.mon_service.get_proxmox_for_server")
    def test_no_usable_candidate_raises_507(self, mock_proxmox_fn):
        mock_proxmox_fn.return_value = _storage_proxmox([
            _storage("local-lvm", total_gib=1000, used_gib=810),   # 81%
            _storage("extra-ssd", total_gib=100, used_gib=0, avail_gib=10),
        ])

        with pytest.raises(HTTPException) as exc_info:
            select_clone_storage(SERVER, ["local-lvm", "extra-ssd"], 20)

        assert exc_info.value.status_code == 507
        assert "extra-ssd" not in exc_info.value.detail

    @patch("services.mon_service.get_proxmox_for_server")
    def test_missing_avail_uses_total_minus_used(self, mock_proxmox_fn):
        no_avail = _storage("no-avail", total_gib=1000, used_gib=100)  # 900GiB 남음
        del no_avail["avail"]
        mock_proxmox_fn.return_value = _storage_proxmox([
            no_avail,
            _storage("with-avail", total_gib=1000, used_gib=500),     # 500GiB 남음
        ])

        assert select_clone_storage(SERVER, ["with-avail", "no-avail"], 20) == "no-avail"

    @pytest.mark.parametrize("response", [None, {"data": []}, "error"])
    @patch("services.mon_service.get_proxmox_for_server")
    def test_non_list_response_raises_503(self, mock_proxmox_fn, response):
        mock_proxmox_fn.return_value = _storage_proxmox(response)

        with pytest.raises(HTTPException) as exc_info:
            select_clone_storage(SERVER, ["local-lvm"], 20)

        assert exc_info.value.status_code == 503

    @patch("services.mon_service.get_proxmox_for_server")
    def test_storage_lookup_failure_raises_503(self, mock_proxmox_fn):
        proxmox = MagicMock()
        proxmox.nodes.return_value.storage.get.side_effect = Exception("connection refused")
        mock_proxmox_fn.return_value = proxmox

        with pytest.raises(HTTPException) as exc_info:
            select_clone_storage(SERVER, ["extra-ssd"], 20)

        assert exc_info.value.status_code == 503


# ── create_vm ────────────────────────────────────────────────

@patch("services.vm_service._delete_snippet")
@patch("services.vm_service._upload_snippet")
@patch("services.vm_service.manage_iptables", return_value=True)
@patch("services.vm_service.get_proxmox_for_server")
@patch("services.vm_service._allocate_internal_ip", return_value="10.0.0.100")
class TestCreateVmCloneStorage:

    def test_configured_node_passes_selected_storage(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, db, user, server
    ):
        proxmox = _make_mock_proxmox(200)
        mock_proxmox_fn.return_value = proxmox

        with patch.object(Settings, "get_clone_storages", return_value=["local-lvm", "extra-ssd"]), \
             patch("services.mon_service.select_clone_storage", return_value="extra-ssd") as mock_select:
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        mock_select.assert_called_once_with(server, ["local-lvm", "extra-ssd"], 20)
        clone_kwargs = proxmox.nodes.return_value.qemu.return_value.clone.post.call_args.kwargs
        assert clone_kwargs["storage"] == "extra-ssd"
        assert clone_kwargs["full"] == 1

    def test_unconfigured_node_clones_without_storage(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, db, user, server
    ):
        proxmox = _make_mock_proxmox(200)
        mock_proxmox_fn.return_value = proxmox

        with patch.object(Settings, "get_clone_storages", return_value=[]), \
             patch("services.mon_service.select_clone_storage") as mock_select:
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        mock_select.assert_not_called()
        clone_kwargs = proxmox.nodes.return_value.qemu.return_value.clone.post.call_args.kwargs
        assert "storage" not in clone_kwargs

    def test_configured_node_ignores_summed_disk_usage(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, db, user, server
    ):
        """합산 SSD가 80% 이상이어도 후보 스토리지가 조건을 만족하면 생성된다"""
        mock_proxmox_fn.return_value = _make_mock_proxmox(200)
        usage = {"ram_pct": 10.0, "cpu_pct": 10.0, "disk_pct": 95.0, "free_ram_mb": 99999}

        with patch("services.mon_service.get_server_resource_usage", return_value=usage), \
             patch.object(Settings, "get_clone_storages", return_value=["extra-ssd"]), \
             patch("services.mon_service.select_clone_storage", return_value="extra-ssd"):
            result = create_vm(db, user, VMTier.BASIC, node_name="test-node")

        assert result["success"] is True

    def test_unconfigured_node_keeps_summed_disk_check(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, db, user, server
    ):
        mock_proxmox_fn.return_value = _make_mock_proxmox(200)
        usage = {"ram_pct": 10.0, "cpu_pct": 10.0, "disk_pct": 95.0, "free_ram_mb": 99999}

        with (
            patch("services.mon_service.get_server_resource_usage", return_value=usage),
            patch.object(Settings, "get_clone_storages", return_value=[]),
            pytest.raises(HTTPException) as exc_info,
        ):
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        assert exc_info.value.status_code == 507

    def test_selection_failure_leaves_nothing_behind(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, db, user, server
    ):
        proxmox = _make_mock_proxmox(200)
        mock_proxmox_fn.return_value = proxmox
        no_space = HTTPException(status_code=507, detail="선택한 사양의 VM을 만들 SSD 공간이 부족합니다.")

        with (
            patch.object(Settings, "get_clone_storages", return_value=["extra-ssd"]),
            patch("services.mon_service.select_clone_storage", side_effect=no_space),
            pytest.raises(HTTPException) as exc_info,
        ):
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        assert exc_info.value.status_code == 507
        assert db.query(Vm).count() == 0
        mock_alloc.assert_not_called()
        proxmox.nodes.return_value.qemu.return_value.clone.post.assert_not_called()

    def test_project_custom_disk_size_is_required_size(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, db, server
    ):
        mock_proxmox_fn.return_value = _make_mock_proxmox(200)
        owner = User(email="owner@gsm.hs.kr", hashed_password="hashed", role=UserRole.PROJECT_OWNER, is_active=True)
        db.add(owner)
        db.commit()

        with patch.object(Settings, "get_clone_storages", return_value=["extra-ssd"]), \
             patch("services.mon_service.select_clone_storage", return_value="extra-ssd") as mock_select:
            create_vm(db, owner, VMTier.PROJECT_CUSTOM, node_name="test-node", custom_disk=40)

        assert mock_select.call_args.args[2] == 40


# ── 실패 정리 ─────────────────────────────────────────────────

@patch("services.vm_service.time.sleep")
@patch("services.vm_service._delete_snippet")
@patch("services.vm_service._upload_snippet")
@patch("services.vm_service.manage_iptables", return_value=True)
@patch("services.vm_service.get_proxmox_for_server")
@patch("services.vm_service._allocate_internal_ip", return_value="10.0.0.100")
class TestCloneFailureCleanup:

    def test_clone_task_failure_deletes_proxmox_vm(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, mock_sleep, db, user, server
    ):
        """_wait_for_clone의 HTTPException(클론 실패)도 Proxmox VM을 지우고 원래 예외를 올린다"""
        proxmox = _make_mock_proxmox(200)
        mock_proxmox_fn.return_value = proxmox
        clone_failed = HTTPException(status_code=500, detail="VM 200 클론 실패: storage error")

        with (
            patch("services.vm_service._wait_for_clone", side_effect=clone_failed),
            pytest.raises(HTTPException) as exc_info,
        ):
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        assert exc_info.value is clone_failed
        proxmox.nodes.return_value.qemu.return_value.delete.assert_called_once_with(purge=1)
        assert db.query(Vm).count() == 0

    def test_clone_failure_skips_delete_when_vm_is_gone(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, mock_sleep, db, user, server
    ):
        proxmox = _make_mock_proxmox(200)
        proxmox.nodes.return_value.qemu.return_value.status.current.get.side_effect = ResourceException(
            500, "Internal Server Error", "Configuration file 'nodes/test-node/qemu-server/200.conf' does not exist"
        )
        mock_proxmox_fn.return_value = proxmox
        clone_failed = HTTPException(status_code=500, detail="VM 200 클론 실패: storage error")

        with (
            patch("services.vm_service._wait_for_clone", side_effect=clone_failed),
            pytest.raises(HTTPException),
        ):
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        proxmox.nodes.return_value.qemu.return_value.delete.assert_not_called()
        mock_sleep.assert_not_called()

    @pytest.mark.parametrize("check_error", [
        ResourceException(503, "Service Unavailable", ""),
        ResourceException(401, "Unauthorized", "authentication failure"),
        ConnectionError("connection reset"),
    ])
    def test_unconfirmed_existence_still_deletes(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, mock_sleep,
        db, user, server, check_error,
    ):
        """'VM 없음'이 확인되지 않은 오류(권한·일시 오류·연결 오류)면 삭제를 시도한다"""
        proxmox = _make_mock_proxmox(200)
        proxmox.nodes.return_value.qemu.return_value.status.current.get.side_effect = check_error
        mock_proxmox_fn.return_value = proxmox
        clone_failed = HTTPException(status_code=500, detail="VM 200 클론에 실패했습니다.")

        with (
            patch("services.vm_service._wait_for_clone", side_effect=clone_failed),
            pytest.raises(HTTPException),
        ):
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        proxmox.nodes.return_value.qemu.return_value.delete.assert_called_once_with(purge=1)

    def test_clone_post_failure_does_not_delete(
        self, mock_alloc, mock_proxmox_fn, mock_iptables, mock_upload, mock_del_snippet, mock_sleep, db, user, server
    ):
        """clone.post 자체가 실패하면(클론 시작 전) 남의 VM일 수 있으므로 지우지 않는다"""
        proxmox = _make_mock_proxmox(200)
        proxmox.nodes.return_value.qemu.return_value.clone.post.side_effect = Exception("VMID 200 already exists")
        mock_proxmox_fn.return_value = proxmox

        with pytest.raises(HTTPException) as exc_info:
            create_vm(db, user, VMTier.BASIC, node_name="test-node")

        assert exc_info.value.status_code == 500
        proxmox.nodes.return_value.qemu.return_value.delete.assert_not_called()
        assert db.query(Vm).count() == 0


# ── 클론 실패 메시지 ──────────────────────────────────────────

class TestWaitForCloneMessage:

    def test_failed_task_detail_hides_proxmox_error(self):
        """Proxmox 오류 원문(스토리지·볼륨 이름 포함 가능)은 사용자 메시지에 넣지 않는다"""
        proxmox = MagicMock()
        proxmox.nodes.return_value.tasks.return_value.status.get.return_value = {
            "status": "stopped",
            "exitstatus": "clone failed: lvcreate 'extra-ssd/vm-200-disk-0' error",
        }

        with pytest.raises(HTTPException) as exc_info:
            _wait_for_clone(proxmox, "test-node", 200, upid="UPID:test")

        assert exc_info.value.status_code == 500
        assert "extra-ssd" not in exc_info.value.detail
        assert "lvcreate" not in exc_info.value.detail
