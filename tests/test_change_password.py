"""비밀번호 변경 (PUT /auth/change-password) 동작 검증 테스트."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base, get_db
from core.security import create_access_token, get_password_hash, verify_password
from models.user import User, UserRole

TEST_DB_URL = "sqlite:///./test_change_password.db"
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


@pytest.fixture
def app(db):
    from api.routes import auth as auth_route

    test_app = FastAPI()
    test_app.include_router(auth_route.router, prefix="/api/v1/auth")

    def override_db():
        try:
            yield db
        finally:
            pass

    test_app.dependency_overrides[get_db] = override_db
    return test_app


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _make_user(db, email="user@gsm.hs.kr", password="OldPass1!", oauth=False):
    u = User(
        email=email,
        hashed_password="" if oauth else get_password_hash(password),
        role=UserRole.USER,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth_cookie(user_id: int) -> dict:
    return {"access_token": create_access_token(subject=str(user_id))}


class TestChangePassword:
    def test_success(self, client, db):
        user = _make_user(db, password="OldPass1!")
        res = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass2@"},
            cookies=_auth_cookie(user.id),
        )
        assert res.status_code == 200, res.text
        db.refresh(user)
        assert verify_password("NewPass2@", user.hashed_password)
        assert not verify_password("OldPass1!", user.hashed_password)

    def test_wrong_current_password(self, client, db):
        user = _make_user(db, password="OldPass1!")
        res = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "WrongPass1!", "new_password": "NewPass2@"},
            cookies=_auth_cookie(user.id),
        )
        assert res.status_code == 400
        assert "현재 비밀번호" in res.json()["detail"]

    def test_weak_new_password(self, client, db):
        user = _make_user(db, password="OldPass1!")
        res = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "weak"},
            cookies=_auth_cookie(user.id),
        )
        assert res.status_code == 400
        assert "8자" in res.json()["detail"]

    def test_oauth_user_blocked(self, client, db):
        user = _make_user(db, oauth=True)
        res = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "anything", "new_password": "NewPass2@"},
            cookies=_auth_cookie(user.id),
        )
        assert res.status_code == 400
        assert "OAuth" in res.json()["detail"]

    def test_unauthenticated(self, client):
        res = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass2@"},
        )
        assert res.status_code == 401

    def test_long_ascii_password_72plus(self, client, db):
        """72바이트 초과 ASCII 비밀번호 → 400."""
        user = _make_user(db, password="OldPass1!")
        long_pw = "Aa1!" + "x" * 70  # 74 bytes
        res = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": long_pw},
            cookies=_auth_cookie(user.id),
        )
        assert res.status_code == 400, res.text
        assert "72바이트" in res.json()["detail"]

    def test_unicode_password_long_bytes(self, client, db):
        """한글 포함 + 72바이트 초과 비밀번호 → 400."""
        user = _make_user(db, password="OldPass1!")
        unicode_pw = "Aa1!" + "한" * 30  # 4 + 90 = 94 bytes
        res = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": unicode_pw},
            cookies=_auth_cookie(user.id),
        )
        assert res.status_code == 400
        assert "72바이트" in res.json()["detail"]

    def test_dual_role_account_login_after_change(self, client, db):
        """같은 이메일에 USER와 PROJECT_OWNER 계정이 모두 있는 경우 — 모두 갱신되어야 한다.

        password-reset/confirm과 동일한 정책: 같은 이메일의 모든 활성 row 일괄 갱신.
        """
        _make_user(db, email="dup@gsm.hs.kr", password="OldPass1!")
        po_row = User(
            email="dup@gsm.hs.kr",
            hashed_password=get_password_hash("OldPass1!"),
            role=UserRole.PROJECT_OWNER,
            is_active=True,
        )
        db.add(po_row)
        db.commit()
        db.refresh(po_row)

        change = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass2@"},
            cookies=_auth_cookie(po_row.id),
        )
        assert change.status_code == 200

        # 양쪽 role 모두 새 비밀번호로 로그인 가능해야 함
        login_user = client.post(
            "/api/v1/auth/login",
            data={"username": "dup@gsm.hs.kr", "password": "NewPass2@"},
        )
        login_po = client.post(
            "/api/v1/auth/login?login_role=project_owner",
            data={"username": "dup@gsm.hs.kr", "password": "NewPass2@"},
        )
        assert login_user.status_code == 200, login_user.text
        assert login_po.status_code == 200, login_po.text

        # 옛 비밀번호로는 양쪽 모두 실패
        old_user = client.post(
            "/api/v1/auth/login",
            data={"username": "dup@gsm.hs.kr", "password": "OldPass1!"},
        )
        old_po = client.post(
            "/api/v1/auth/login?login_role=project_owner",
            data={"username": "dup@gsm.hs.kr", "password": "OldPass1!"},
        )
        assert old_user.status_code == 401
        assert old_po.status_code == 401

    def test_db_direct_plaintext_password_login(self, client, db):
        """hashed_password 컬럼에 비-bcrypt 형식이 들어 있어도 500이 아닌 401."""
        u = User(
            email="direct@gsm.hs.kr",
            hashed_password="Pass1!aa",  # 평문 (bcrypt 해시 아님)
            role=UserRole.USER,
            is_active=True,
        )
        db.add(u)
        db.commit()

        res = client.post(
            "/api/v1/auth/login",
            data={"username": "direct@gsm.hs.kr", "password": "Pass1!aa"},
        )
        assert res.status_code == 401, res.text

    def test_db_direct_change_then_login(self, client, db):
        """DB에 올바른 bcrypt 해시를 직접 삽입한 정상 케이스 → 변경 → 새 비번 로그인."""
        u = User(
            email="dbgood@gsm.hs.kr",
            hashed_password=get_password_hash("OldPass1!"),
            role=UserRole.USER,
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)

        change = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass2@"},
            cookies=_auth_cookie(u.id),
        )
        assert change.status_code == 200, change.text

        new_login = client.post(
            "/api/v1/auth/login",
            data={"username": "dbgood@gsm.hs.kr", "password": "NewPass2@"},
        )
        assert new_login.status_code == 200, new_login.text

    def test_change_password_updates_all_role_rows_at_db_level(self, client, db):
        """DB 레벨에서 같은 이메일의 모든 활성 row가 새 해시로 갱신되는지 직접 확인."""
        old_hash = get_password_hash("OldPass1!")
        u_user = User(
            email="multi@gsm.hs.kr",
            hashed_password=old_hash,
            role=UserRole.USER,
            is_active=True,
        )
        u_po = User(
            email="multi@gsm.hs.kr",
            hashed_password=old_hash,
            role=UserRole.PROJECT_OWNER,
            is_active=True,
        )
        db.add_all([u_user, u_po])
        db.commit()
        db.refresh(u_user)
        db.refresh(u_po)

        change = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass2@"},
            cookies=_auth_cookie(u_po.id),
        )
        assert change.status_code == 200

        db.expire_all()
        u_user_reloaded = db.query(User).filter_by(id=u_user.id).first()
        u_po_reloaded = db.query(User).filter_by(id=u_po.id).first()
        assert verify_password("NewPass2@", u_po_reloaded.hashed_password)
        assert verify_password("NewPass2@", u_user_reloaded.hashed_password), (
            "USER row도 함께 갱신되어야 함 (재설정과 동일한 정책)"
        )

    def test_login_with_new_password_after_change(self, client, db):
        """변경 → 새 비밀번호 로그인 성공, 옛 비밀번호 로그인 실패."""
        user = _make_user(db, email="login@gsm.hs.kr", password="OldPass1!")

        change = client.put(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass2@"},
            cookies=_auth_cookie(user.id),
        )
        assert change.status_code == 200, change.text

        new_login = client.post(
            "/api/v1/auth/login",
            data={"username": "login@gsm.hs.kr", "password": "NewPass2@"},
        )
        assert new_login.status_code == 200, new_login.text

        old_login = client.post(
            "/api/v1/auth/login",
            data={"username": "login@gsm.hs.kr", "password": "OldPass1!"},
        )
        assert old_login.status_code == 401
