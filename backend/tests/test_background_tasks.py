"""_notify_admins_background_failure 단위 테스트."""

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.security import get_password_hash
from models.user import User, UserRole
from models.notification import Notification

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


from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


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


from models.vm import Vm
from models.server import Server


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


def _make_vm(db, name, server, expires_at):
    v = Vm(hypervisor_vmid=100, name=name, server_id=server.id,
           allocated_ram_mb=2048, allocated_cores=2, expires_at=expires_at)
    db.add(v)
    db.flush()
    return v


class TestSendAdminExpiryNotifications:
    """_send_admin_expiry_notifications 단위 테스트."""

    def test_vms_within_7_days_sends_list(self, db):
        """7일 이내 만료 VM 있으면 목록 포함 메시지 발송."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        admin = _make_admin(db, "admin@gsm.hs.kr")
        _make_vm(db, "vm-alpha", server, now + timedelta(days=3, hours=4))
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        notifs = db.query(Notification).filter(Notification.user_id == admin.id).all()
        assert len(notifs) == 1
        assert "만료 임박 VM 1개" in notifs[0].message
        assert "vm-alpha(3일 4시간)" in notifs[0].message
        assert notifs[0].type == "info"

    def test_no_vms_sends_empty_message(self, db):
        """7일 이내 만료 VM 없으면 '만료 임박 VM 없음' 발송."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        admin = _make_admin(db, "admin2@gsm.hs.kr")
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        notifs = db.query(Notification).filter(Notification.user_id == admin.id).all()
        assert len(notifs) == 1
        assert notifs[0].message == "만료 임박 VM 없음"

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
        notif = db.query(Notification).filter(Notification.user_id == admin.id).first()
        assert notif.message == "만료 임박 VM 없음"

    def test_vm_beyond_7_days_excluded(self, db):
        """8일 후 만료 VM은 포함 안 됨."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        server = _make_server(db)
        admin = _make_admin(db, "admin4@gsm.hs.kr")
        _make_vm(db, "far-vm", server, now + timedelta(days=8))
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        notif = db.query(Notification).filter(Notification.user_id == admin.id).first()
        assert notif.message == "만료 임박 VM 없음"

    def test_multiple_admins_each_get_one_notification(self, db):
        """ADMIN 2명이면 각자 알림 1개씩."""
        from main import _send_admin_expiry_notifications
        now = datetime(2026, 5, 26, 12, 0, 0)
        _make_admin(db, "a1@gsm.hs.kr")
        _make_admin(db, "a2@gsm.hs.kr")
        db.commit()

        _send_admin_expiry_notifications(db, now)

        db.expire_all()
        assert db.query(Notification).count() == 2
