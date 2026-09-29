"""스냅샷 HTTP 경로의 소유권·개수 제한·중복 이름 회귀 테스트."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_current_user
from api.routes import vmcontrol
from core.database import Base, get_db
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm


@pytest.fixture
def snapshot_api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    owner = User(email="snapshot-owner@gsm.hs.kr", hashed_password="hashed", role=UserRole.USER)
    stranger = User(email="snapshot-stranger@gsm.hs.kr", hashed_password="hashed", role=UserRole.USER)
    server = Server(
        name="snapshot-node", ip_address="192.0.2.10", port=8006,
        api_user="root@pam", api_password="test-password",
    )
    session.add_all([owner, stranger, server])
    session.flush()
    vm = Vm(
        hypervisor_vmid=200, name="snapshot-vm", server_id=server.id,
        owner_id=owner.id, internal_ip="192.0.2.20",
    )
    session.add(vm)
    session.commit()

    app = FastAPI()
    app.include_router(vmcontrol.router, prefix="/api/v1/vm")
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: owner
    proxmox = MagicMock()
    monkeypatch.setattr(vmcontrol, "get_proxmox_for_server", lambda _server: proxmox)

    with TestClient(app) as client:
        yield client, app, owner, stranger, proxmox
    session.close()
    engine.dispose()


URL = "/api/v1/vm/snapshot-node/vms/200/snapshots"


def test_other_users_vm_is_hidden_and_proxmox_is_not_called(snapshot_api):
    client, app, _, stranger, proxmox = snapshot_api
    app.dependency_overrides[get_current_user] = lambda: stranger

    response = client.post(URL, json={"name": "manual-new"})

    assert response.status_code == 404  # 소유권 정보 노출 방지를 위한 의도된 정책
    assert "VM 200" in response.json()["detail"]
    proxmox.nodes.assert_not_called()


def test_missing_vm_returns_404_without_proxmox_call(snapshot_api):
    client, _, _, _, proxmox = snapshot_api

    response = client.post(URL.replace("/200/", "/999/"), json={"name": "manual-new"})

    assert response.status_code == 404
    assert "VM 999" in response.json()["detail"]
    proxmox.nodes.assert_not_called()


@pytest.mark.parametrize(
    ("existing", "detail"),
    [
        (["manual-one", "manual-two"], "수동 스냅샷은 최대 2개"),
        (["auto-daily-one", "auto-daily-two", "auto-daily-three"], "스냅샷은 최대 3개"),
    ],
)
def test_snapshot_limit_returns_400_without_creating(snapshot_api, existing, detail):
    client, _, _, _, proxmox = snapshot_api
    qemu = proxmox.nodes.return_value.qemu.return_value
    qemu.snapshot.get.return_value = [{"name": "current"}] + [
        {"name": name} for name in existing
    ]

    response = client.post(URL, json={"name": "manual-new"})

    assert response.status_code == 400
    assert detail in response.json()["detail"]
    qemu.snapshot.post.assert_not_called()


def test_owned_vm_creates_snapshot_via_http(snapshot_api):
    client, _, _, _, proxmox = snapshot_api
    qemu = proxmox.nodes.return_value.qemu.return_value
    qemu.snapshot.get.return_value = [{"name": "current"}]
    qemu.snapshot.post.return_value = "UPID:snapshot"

    response = client.post(URL, json={"name": "manual-new"})

    assert response.status_code == 200
    assert response.json()["task"] == "UPID:snapshot"
    qemu.snapshot.post.assert_called_once_with(
        snapname="manual-new", description="", vmstate=0
    )


def test_duplicate_name_returns_400_without_creating(snapshot_api):
    client, _, _, _, proxmox = snapshot_api
    qemu = proxmox.nodes.return_value.qemu.return_value
    qemu.snapshot.get.return_value = [{"name": "current"}, {"name": "manual-one"}]

    response = client.post(URL, json={"name": "manual-one"})

    assert response.status_code == 400
    assert response.json()["detail"] == "이미 존재하는 스냅샷 이름입니다."
    qemu.snapshot.post.assert_not_called()
