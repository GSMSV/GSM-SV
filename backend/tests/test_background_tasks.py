"""_notify_admins_background_failure 단위 테스트."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.security import get_password_hash
from core.timezone import KST
from models.notification import Notification
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm

TEST_DB_URL = "sqlite:///./test_background_tasks.db"
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


def _call_notify(task_name: str, failures: int):
    from main import _notify_admins_background_failure
    with patch("main.SessionLocal", return_value=TestSession()):
        _notify_admins_background_failure(task_name, failures)


class TestNotifyAdminsBackgroundFailure:
    def test_creates_notification_for_each_admin(self, db):
        """ADMIN 유저 수만큼 Notification 생성."""
        for email in ("a@gsm.hs.kr", "b@gsm.hs.kr"):
            db.add(User(
                email=email,
                hashed_password=get_password_hash("Pass1!aa"),
                role=UserRole.ADMIN,
                is_active=True,
            ))
        db.commit()

        from main import _notify_admins_background_failure
        with patch("main.SessionLocal", return_value=db):
            _notify_admins_background_failure("expire", 5)

        db.expire_all()
        notifs = db.query(Notification).all()
        assert len(notifs) == 2
        assert all("expire" in n.message for n in notifs)
        assert all("5회" in n.message for n in notifs)

    def test_no_notification_when_no_admin(self, db):
        """ADMIN이 없으면 Notification 생성 안 됨."""
        db.add(User(
            email="user@gsm.hs.kr",
            hashed_password=get_password_hash("Pass1!aa"),
            role=UserRole.USER,
            is_active=True,
        ))
        db.commit()

        from main import _notify_admins_background_failure
        with patch("main.SessionLocal", return_value=db):
            _notify_admins_background_failure("expire", 5)

        assert db.query(Notification).count() == 0

    def test_db_error_triggers_rollback_and_warning(self, db):
        """DB 오류 시 rollback 후 logger.warning 호출, 예외 전파 없음."""
        db.add(User(
            email="admin@gsm.hs.kr",
            hashed_password=get_password_hash("Pass1!aa"),
            role=UserRole.ADMIN,
            is_active=True,
        ))
        db.commit()

        from main import _notify_admins_background_failure
        broken_session = TestSession()
        broken_session.commit = lambda: (_ for _ in ()).throw(Exception("DB error"))

        import logging
        with patch("main.SessionLocal", return_value=broken_session), \
             patch.object(logging.getLogger("main"), "warning") as mock_warn:
            _notify_admins_background_failure("expire", 5)  # 예외 전파 없어야 함

        assert mock_warn.called
        broken_session.close()

    def test_inactive_admin_excluded(self, db):
        """is_active=False인 ADMIN에게는 알림 발송 안 됨."""
        db.add(User(
            email="inactive@gsm.hs.kr",
            hashed_password=get_password_hash("Pass1!aa"),
            role=UserRole.ADMIN,
            is_active=False,
        ))
        db.commit()

        from main import _notify_admins_background_failure
        with patch("main.SessionLocal", return_value=db):
            _notify_admins_background_failure("expire", 5)

        assert db.query(Notification).count() == 0


class TestNextNotifySleepSeconds:
    """_next_notify_sleep_seconds 순수 함수 단위 테스트."""

    def _now(self, hour, minute=0):
        return datetime(2026, 5, 26, hour, minute, 0, tzinfo=KST)

    def test_next_hour_today(self):
        """현재 05:30 → 다음 06:00까지 30분."""
        from main import _next_notify_sleep_seconds
        now = self._now(5, 30)
        secs = _next_notify_sleep_seconds(now, [0, 6, 12, 18])
        assert secs == 30 * 60

    def test_next_is_tomorrow(self):
        """현재 19:00 → 다음 00:00(익일)까지 5시간."""
        from main import _next_notify_sleep_seconds
        now = self._now(19, 0)
        secs = _next_notify_sleep_seconds(now, [0, 6, 12, 18])
        assert secs == 5 * 3600

    def test_exact_boundary_skipped(self):
        """현재 정확히 06:00 → 다음 12:00까지 6시간."""
        from main import _next_notify_sleep_seconds
        now = self._now(6, 0)
        secs = _next_notify_sleep_seconds(now, [0, 6, 12, 18])
        assert secs == 6 * 3600


def _make_server(db):
    s = Server(name="pve-test", ip_address="10.0.0.1", port=8006, api_user="root")
    s.api_password = "pw"
    db.add(s)
    db.flush()
    return s


def _make_admin(db, email):
    u = User(email=email, hashed_password=get_password_hash("Pass1!aa"),
             role=UserRole.ADMIN, is_active=True)
    db.add(u)
    db.flush()
    return u


def _make_vm(db, name, server, expires_at, owner=None, vmid=100):
    v = Vm(hypervisor_vmid=vmid, name=name, server_id=server.id,
           allocated_ram_mb=2048, allocated_cores=2, expires_at=expires_at,
           owner_id=owner.id if owner else None)
    db.add(v)
    db.flush()
    return v


class TestSendAdminExpiryNotifications:
    """_send_admin_expiry_notifications 단위 테스트."""

    def test_vms_within_3_days_sends_list(self, db):
        """3일 이내 만료 VM 있으면 목록 포함 메시지 발송."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        admin = _make_admin(db, "admin@gsm.hs.kr")
        _make_vm(db, "vm-alpha", server, now + timedelta(days=2, hours=4))
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        notifs = db.query(Notification).filter(Notification.user_id == admin.id).all()
        assert len(notifs) == 1
        assert "만료 임박 VM 1개" in notifs[0].message
        assert "vm-alpha(2일 4시간)" in notifs[0].message
        assert notifs[0].type == "info"

    def test_no_vms_sends_no_notification(self, db):
        """3일 이내 만료 VM 없으면 알림 발송 안 함."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        admin = _make_admin(db, "admin2@gsm.hs.kr")
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        assert db.query(Notification).filter(Notification.user_id == admin.id).count() == 0

    def test_expired_vm_excluded(self, db):
        """이미 만료된 VM(expires_at <= now)은 포함 안 됨."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        admin = _make_admin(db, "admin3@gsm.hs.kr")
        _make_vm(db, "expired-vm", server, now - timedelta(hours=1))
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        assert db.query(Notification).filter(Notification.user_id == admin.id).count() == 0

    def test_vm_beyond_3_days_excluded(self, db):
        """4일 후 만료 VM은 포함 안 됨."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        admin = _make_admin(db, "admin4@gsm.hs.kr")
        _make_vm(db, "far-vm", server, now + timedelta(days=4))
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        assert db.query(Notification).filter(Notification.user_id == admin.id).count() == 0

    def test_multiple_admins_each_get_one_notification(self, db):
        """ADMIN 2명이면 각자 알림 1개씩."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        _make_admin(db, "a1@gsm.hs.kr")
        _make_admin(db, "a2@gsm.hs.kr")
        _make_vm(db, "vm-soon", server, now + timedelta(days=3))
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        assert db.query(Notification).count() == 2

    def test_duplicate_same_day_notification_skipped(self, db):
        """같은 날 이미 만료 임박 알림을 받은 ADMIN에게 중복 발송하지 않는다."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        admin = _make_admin(db, "dup-admin@gsm.hs.kr")
        _make_vm(db, "vm-soon", server, now + timedelta(days=3))
        db.add(Notification(
            user_id=admin.id,
            type="info",
            message="만료 임박 VM 1개: old-vm(1일 0시간)",
            created_at=now.replace(hour=1),
        ))
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        assert db.query(Notification).filter(Notification.user_id == admin.id).count() == 1


def _mock_proxmox(status="running"):
    m = MagicMock()
    m.nodes.return_value.qemu.return_value.status.current.get.return_value = {
        "status": status
    }
    return m


def _stop_post(m):
    return m.nodes.return_value.qemu.return_value.status.stop.post


class TestProcessGraceVms:
    """_process_grace_vms 단위 테스트 — 만료 3일 유예 정지 + 알림."""

    def test_grace_vm_stopped_and_notified(self, db):
        """만료 직후 VM은 삭제 없이 정지되고 '3일 후 완전 삭제' 알림 1건 발송."""
        from main import _process_grace_vms
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        owner = _make_admin(db, "owner@gsm.hs.kr")
        _make_vm(db, "grace-vm", server, now - timedelta(hours=1), owner=owner)
        db.commit()

        proxmox = _mock_proxmox("running")
        with patch("services.proxmox_client.get_proxmox_for_server", return_value=proxmox):
            _process_grace_vms(db, now)

        _stop_post(proxmox).assert_called_once()
        db.expire_all()
        assert db.query(Vm).count() == 1  # 삭제되지 않음
        notifs = db.query(Notification).filter(Notification.user_id == owner.id).all()
        assert len(notifs) == 1
        assert "3일 후 완전 삭제" in notifs[0].message
        assert "'grace-vm'" in notifs[0].message

    def test_notification_not_duplicated_on_rerun(self, db):
        """같은 유예 기간 내 루프 재실행 시 알림이 중복 생성되지 않는다."""
        from main import _process_grace_vms
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        owner = _make_admin(db, "owner2@gsm.hs.kr")
        _make_vm(db, "rerun-vm", server, now - timedelta(hours=1), owner=owner)
        db.commit()

        proxmox = _mock_proxmox("stopped")
        with patch("services.proxmox_client.get_proxmox_for_server", return_value=proxmox):
            _process_grace_vms(db, now)
            _process_grace_vms(db, now + timedelta(hours=1))

        db.expire_all()
        assert db.query(Notification).filter(Notification.user_id == owner.id).count() == 1

    def test_already_stopped_vm_not_stopped_again(self, db):
        """이미 정지된 VM에는 stop 호출하지 않는다."""
        from main import _process_grace_vms
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        owner = _make_admin(db, "owner3@gsm.hs.kr")
        _make_vm(db, "stopped-vm", server, now - timedelta(hours=1), owner=owner)
        db.commit()

        proxmox = _mock_proxmox("stopped")
        with patch("services.proxmox_client.get_proxmox_for_server", return_value=proxmox):
            _process_grace_vms(db, now)

        _stop_post(proxmox).assert_not_called()

    def test_vm_past_grace_excluded(self, db):
        """만료 3일 경과 VM은 유예 대상이 아니다 (삭제 단계에서 처리)."""
        from main import _process_grace_vms
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        owner = _make_admin(db, "owner4@gsm.hs.kr")
        _make_vm(db, "old-vm", server, now - timedelta(days=3, hours=1), owner=owner)
        db.commit()

        proxmox = _mock_proxmox("running")
        with patch("services.proxmox_client.get_proxmox_for_server", return_value=proxmox):
            _process_grace_vms(db, now)

        _stop_post(proxmox).assert_not_called()
        assert db.query(Notification).count() == 0

    def test_extended_vm_excluded(self, db):
        """연장 등으로 expires_at이 미래인 VM은 유예 대상이 아니다."""
        from main import _process_grace_vms
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        owner = _make_admin(db, "owner5@gsm.hs.kr")
        _make_vm(db, "future-vm", server, now + timedelta(days=30), owner=owner)
        db.commit()

        proxmox = _mock_proxmox("running")
        with patch("services.proxmox_client.get_proxmox_for_server", return_value=proxmox):
            _process_grace_vms(db, now)

        _stop_post(proxmox).assert_not_called()
        assert db.query(Notification).count() == 0

    def test_owner_none_stops_without_notification(self, db):
        """소유자 없는 VM도 정지는 되고 알림만 생략된다."""
        from main import _process_grace_vms
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        _make_vm(db, "orphan-vm", server, now - timedelta(hours=1))
        db.commit()

        proxmox = _mock_proxmox("running")
        with patch("services.proxmox_client.get_proxmox_for_server", return_value=proxmox):
            _process_grace_vms(db, now)

        _stop_post(proxmox).assert_called_once()
        assert db.query(Notification).count() == 0

    def test_substring_vm_name_not_suppressed(self, db):
        """다른 VM('app2') 알림이 있어도 이름이 부분 문자열인 VM('app')의 알림은 발송된다."""
        from main import _process_grace_vms
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        owner = _make_admin(db, "owner6@gsm.hs.kr")
        _make_vm(db, "app", server, now - timedelta(hours=1), owner=owner)
        db.add(Notification(
            user_id=owner.id,
            type="error",
            message="VM 'app2'이(가) 만료되어 정지되었습니다. 3일 후 완전 삭제됩니다.",
            created_at=now,
        ))
        db.commit()

        proxmox = _mock_proxmox("stopped")
        with patch("services.proxmox_client.get_proxmox_for_server", return_value=proxmox):
            _process_grace_vms(db, now)

        db.expire_all()
        assert (
            db.query(Notification)
            .filter(Notification.message.contains("'app'"))
            .count()
            == 1
        )
