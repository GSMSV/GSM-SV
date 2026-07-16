"""
DevFest 이후 인스턴스 정책 변경 테스트

- 티어: BASIC/STANDARD 스펙, 만료 7일
- 연장: 만료 7일 전부터 +14일
- purpose: 필수 입력·수정
"""
import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.timezone import now_kst
from core.database import Base
from core.constants import TIER_SPECS
from models.user import User, UserRole
from models.server import Server
from models.vm import Vm
from schemas.vm_schema import VMCreate, VMPurposeUpdate, VMTier
from services.vm_service import create_vm

TEST_DB_URL = "sqlite:///./test_vm_policy.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def user(db):
    u = User(
        email="policy-user@gsm.hs.kr",
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


def _make_mock_proxmox(vmid=200):
    proxmox = MagicMock()
    proxmox.cluster.nextid.get.return_value = str(vmid)
    node = proxmox.nodes.return_value
    node.qemu.return_value.clone.post.return_value = None
    node.qemu.return_value.config.get.return_value = {"name": "test"}
    node.qemu.return_value.config.put.return_value = None
    node.qemu.return_value.resize.put.return_value = None
    node.qemu.return_value.status.start.post.return_value = None
    node.qemu.return_value.status.current.get.return_value = {"status": "running"}
    return proxmox


# ── 티어 스펙 ─────────────────────────────────────────────────

class TestTierSpecs:
    def test_basic_standard_specs(self):
        assert TIER_SPECS[VMTier.BASIC] == {"memory": 2048, "cores": 1, "disk": 20}
        assert TIER_SPECS[VMTier.STANDARD] == {"memory": 4096, "cores": 2, "disk": 20}
        assert TIER_SPECS[VMTier.PROJECT_CUSTOM] == {"memory": 16384, "cores": 4, "disk": 40}

    def test_removed_tiers_rejected(self):
        with pytest.raises(ValidationError):
            VMCreate(tier="micro", purpose="테스트")
        with pytest.raises(ValidationError):
            VMCreate(tier="large", purpose="테스트")


# ── 만료 7일 ─────────────────────────────────────────────────

class TestExpiry7Days:
    @patch("services.vm_service._delete_snippet")
    @patch("services.vm_service._upload_snippet")
    @patch("services.vm_service.manage_iptables", return_value=True)
    @patch("services.vm_service.get_proxmox_for_server")
    @patch("services.vm_service._allocate_internal_ip", return_value="10.0.0.100")
    def test_user_vm_expires_in_7_days(
        self, mock_alloc, mock_proxmox_fn, mock_iptables,
        mock_upload, mock_del_snippet, db, user, server
    ):
        mock_proxmox_fn.return_value = _make_mock_proxmox(200)

        before = now_kst().replace(tzinfo=None)
        create_vm(db, user, VMTier.BASIC, node_name="test-node", purpose="과제 서버")
        after = now_kst().replace(tzinfo=None)

        vm = db.query(Vm).filter(Vm.hypervisor_vmid == 200).first()
        assert vm.purpose == "과제 서버"
        # SQLite는 naive datetime으로 저장되므로 naive 기준으로 비교
        expires_at = vm.expires_at.replace(tzinfo=None)
        assert before + timedelta(days=7) <= expires_at <= after + timedelta(days=7)


# ── 연장 (만료 7일 전부터 +14일) ─────────────────────────────

class TestExtendVm:
    def _make_vm(self, db, user, server, expires_at):
        vm = Vm(
            hypervisor_vmid=300,
            name="extend-vm",
            server_id=server.id,
            owner_id=user.id,
            expires_at=expires_at,
        )
        db.add(vm)
        db.commit()
        db.refresh(vm)
        return vm

    def test_extend_rejected_before_window(self, db, user, server):
        """만료까지 7일 초과 남으면 400."""
        from fastapi import HTTPException
        from api.routes.vmcontrol import extend_vm

        # SQLite는 naive datetime으로 저장되므로 now_kst도 naive로 패치
        now = now_kst().replace(tzinfo=None)
        self._make_vm(db, user, server, now + timedelta(days=10))

        with patch("api.routes.vmcontrol.now_kst", return_value=now):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(extend_vm("test-node", 300, db=db, current_user=user))
        assert exc_info.value.status_code == 400
        assert "만료 7일 전부터" in exc_info.value.detail

    def test_extend_adds_14_days(self, db, user, server):
        """만료 7일 이내면 expires_at + 14일."""
        from api.routes.vmcontrol import extend_vm

        now = now_kst().replace(tzinfo=None)
        original = now + timedelta(days=5)
        vm = self._make_vm(db, user, server, original)

        with patch("api.routes.vmcontrol.now_kst", return_value=now):
            result = asyncio.run(extend_vm("test-node", 300, db=db, current_user=user))

        assert result["success"] is True
        assert "14일" in result["message"]
        db.refresh(vm)
        assert vm.expires_at == original + timedelta(days=14)


# ── purpose 검증·수정 ────────────────────────────────────────

class TestPurpose:
    def test_purpose_required(self):
        with pytest.raises(ValidationError):
            VMCreate(tier=VMTier.BASIC)

    def test_purpose_blank_rejected(self):
        with pytest.raises(ValidationError):
            VMCreate(tier=VMTier.BASIC, purpose="   ")

    def test_purpose_too_long_rejected(self):
        with pytest.raises(ValidationError):
            VMCreate(tier=VMTier.BASIC, purpose="a" * 101)

    def test_purpose_stripped(self):
        vm = VMCreate(tier=VMTier.BASIC, purpose="  웹 서버 실습  ")
        assert vm.purpose == "웹 서버 실습"

    def test_update_purpose_endpoint(self, db, user, server):
        from api.routes.vmcontrol import update_vm_purpose

        vm = Vm(
            hypervisor_vmid=400,
            name="purpose-vm",
            server_id=server.id,
            owner_id=user.id,
            purpose="이전 목적",
        )
        db.add(vm)
        db.commit()

        result = asyncio.run(update_vm_purpose(
            "test-node", 400, VMPurposeUpdate(purpose="새 목적"),
            db=db, current_user=user,
        ))

        assert result == {"success": True, "purpose": "새 목적"}
        db.refresh(vm)
        assert vm.purpose == "새 목적"

    def test_update_purpose_other_user_404(self, db, user, server):
        from fastapi import HTTPException
        from api.routes.vmcontrol import update_vm_purpose

        other = User(
            email="other@gsm.hs.kr",
            hashed_password="hashed",
            role=UserRole.USER,
            is_active=True,
        )
        db.add(other)
        vm = Vm(
            hypervisor_vmid=401,
            name="other-vm",
            server_id=server.id,
            owner_id=user.id,
        )
        db.add(vm)
        db.commit()
        db.refresh(other)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(update_vm_purpose(
                "test-node", 401, VMPurposeUpdate(purpose="탈취 시도"),
                db=db, current_user=other,
            ))
        assert exc_info.value.status_code == 404
