"""_collect_discord_daily_report / _format_discord_daily_message 단위 테스트."""

import pytest
from datetime import timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.security import get_password_hash
from core.timezone import now_kst
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm

TEST_DB_URL = "sqlite:///./test_discord_daily_report.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


def _make_server(db, name="gsmgpu1"):
    server = Server(
        name=name,
        ip_address="10.0.0.1",
        port=8006,
        api_user="root@pam",
        api_password="dummy",
        is_active=True,
    )
    db.add(server)
    db.commit()
    return server


def _make_user(db, email="hong@gsm.hs.kr"):
    user = User(
        email=email,
        hashed_password=get_password_hash("Pass1!aa"),
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


class TestCollectDiscordDailyReport:
    def test_includes_node_usage(self, db):
        """활성 서버의 CPU/RAM/Disk 사용률을 nodes에 포함."""
        _make_server(db, "gsmgpu1")
        now = now_kst()

        from main import _collect_discord_daily_report
        with patch(
            "main.get_server_resource_usage",
            return_value={"cpu_pct": 23.0, "ram_pct": 61.0, "disk_pct": 44.0, "free_ram_mb": 1000},
        ):
            report = _collect_discord_daily_report(db, now)

        assert len(report["nodes"]) == 1
        assert report["nodes"][0]["name"] == "gsmgpu1"
        assert report["nodes"][0]["cpu_pct"] == 23.0
        assert report["nodes"][0]["ok"] is True

    def test_node_marked_not_ok_when_usage_high(self, db):
        """CPU/RAM 90% 이상이면 ok=False."""
        _make_server(db, "gsmgpu2")
        now = now_kst()

        from main import _collect_discord_daily_report
        with patch(
            "main.get_server_resource_usage",
            return_value={"cpu_pct": 95.0, "ram_pct": 50.0, "disk_pct": 30.0, "free_ram_mb": 1000},
        ):
            report = _collect_discord_daily_report(db, now)

        assert report["nodes"][0]["ok"] is False

    def test_node_query_failure_marked_not_ok(self, db):
        """get_server_resource_usage 예외 시 cpu_pct=None, ok=False."""
        _make_server(db, "gsmgpu3")
        now = now_kst()

        from main import _collect_discord_daily_report
        with patch("main.get_server_resource_usage", side_effect=Exception("연결 실패")):
            report = _collect_discord_daily_report(db, now)

        assert report["nodes"][0]["cpu_pct"] is None
        assert report["nodes"][0]["ok"] is False

    def test_includes_vm_expiring_within_3_days(self, db):
        """3일 이내 만료 VM을 days_left와 함께 포함."""
        user = _make_user(db)
        server = _make_server(db, "gsmgpu1")
        now = now_kst()
        db.add(Vm(
            hypervisor_vmid=101,
            name="vm-042",
            server_id=server.id,
            owner_id=user.id,
            expires_at=now + timedelta(days=3),
        ))
        db.commit()

        from main import _collect_discord_daily_report
        with patch(
            "main.get_server_resource_usage",
            return_value={"cpu_pct": 10.0, "ram_pct": 10.0, "disk_pct": 10.0, "free_ram_mb": 1000},
        ):
            report = _collect_discord_daily_report(db, now)

        assert len(report["vms"]) == 1
        assert report["vms"][0]["name"] == "vm-042"
        assert report["vms"][0]["owner_email"] == "hong@gsm.hs.kr"
        assert report["vms"][0]["days_left"] == 3

    def test_excludes_vm_expiring_after_3_days(self, db):
        """3일 이후 만료 VM은 제외."""
        server = _make_server(db, "gsmgpu1")
        now = now_kst()
        db.add(Vm(
            hypervisor_vmid=102,
            name="vm-far",
            server_id=server.id,
            expires_at=now + timedelta(days=5),
        ))
        db.commit()

        from main import _collect_discord_daily_report
        with patch(
            "main.get_server_resource_usage",
            return_value={"cpu_pct": 10.0, "ram_pct": 10.0, "disk_pct": 10.0, "free_ram_mb": 1000},
        ):
            report = _collect_discord_daily_report(db, now)

        assert report["vms"] == []

    def test_vm_without_owner_shows_placeholder(self, db):
        """소유자 없는 VM은 owner_email '(소유자 없음)'으로 표시."""
        server = _make_server(db, "gsmgpu1")
        now = now_kst()
        db.add(Vm(
            hypervisor_vmid=103,
            name="vm-no-owner",
            server_id=server.id,
            owner_id=None,
            expires_at=now + timedelta(days=1),
        ))
        db.commit()

        from main import _collect_discord_daily_report
        with patch(
            "main.get_server_resource_usage",
            return_value={"cpu_pct": 10.0, "ram_pct": 10.0, "disk_pct": 10.0, "free_ram_mb": 1000},
        ):
            report = _collect_discord_daily_report(db, now)

        assert report["vms"][0]["owner_email"] == "(소유자 없음)"


class TestFormatDiscordDailyMessage:
    def test_formats_node_status_with_ok_icon(self):
        report = {
            "nodes": [{"name": "gsmgpu1", "cpu_pct": 23.0, "ram_pct": 61.0, "disk_pct": 44.0, "ok": True}],
            "vms": [],
        }
        from main import _format_discord_daily_message
        now = now_kst()

        message = _format_discord_daily_message(report, now)

        assert "gsmgpu1" in message
        assert "CPU 23.0%" in message
        assert "✅" in message

    def test_formats_node_status_with_warning_icon_when_not_ok(self):
        report = {
            "nodes": [{"name": "gsmgpu2", "cpu_pct": 95.0, "ram_pct": 50.0, "disk_pct": 30.0, "ok": False}],
            "vms": [],
        }
        from main import _format_discord_daily_message
        now = now_kst()

        message = _format_discord_daily_message(report, now)

        assert "⚠️" in message

    def test_formats_query_failure_with_red_icon(self):
        report = {
            "nodes": [{"name": "gsmgpu3", "cpu_pct": None, "ram_pct": None, "disk_pct": None, "ok": False}],
            "vms": [],
        }
        from main import _format_discord_daily_message
        now = now_kst()

        message = _format_discord_daily_message(report, now)

        assert "🔴" in message

    def test_omits_vm_section_when_no_expiring_vms(self):
        report = {"nodes": [], "vms": []}
        from main import _format_discord_daily_message
        now = now_kst()

        message = _format_discord_daily_message(report, now)

        assert "[만료 예정 VM]" not in message

    def test_includes_vm_expiry_section(self):
        now = now_kst()
        report = {
            "nodes": [],
            "vms": [{"name": "vm-042", "owner_email": "hong@gsm.hs.kr", "days_left": 3, "expires_at": now + timedelta(days=3)}],
        }
        from main import _format_discord_daily_message

        message = _format_discord_daily_message(report, now)

        assert "[만료 예정 VM]" in message
        assert "vm-042" in message
        assert "hong@gsm.hs.kr" in message
        assert "D-3" in message


class TestSendDiscordMessage:
    @pytest.mark.asyncio
    async def test_posts_content_to_webhook_when_configured(self, monkeypatch):
        from unittest.mock import AsyncMock
        import main

        monkeypatch.setattr(main.settings, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")

        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("main.httpx.AsyncClient", return_value=mock_client):
            await main._send_discord_message("test content")

        mock_client.post.assert_called_once_with(
            "https://discord.com/api/webhooks/test", json={"content": "test content"}
        )

    @pytest.mark.asyncio
    async def test_skips_when_webhook_not_configured(self, monkeypatch):
        import main

        monkeypatch.setattr(main.settings, "DISCORD_WEBHOOK_URL", "")

        with patch("main.httpx.AsyncClient") as mock_client_cls:
            await main._send_discord_message("test content")

        mock_client_cls.assert_not_called()
