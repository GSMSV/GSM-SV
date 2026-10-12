"""caddy_service — subdomain 검증 + Caddy Admin API 호출(mock)"""
import pytest
from unittest.mock import MagicMock, patch

from services.caddy_service import validate_subdomain, add_route, delete_route


class TestValidateSubdomain:
    def test_accepts_valid_subdomain(self):
        assert validate_subdomain("my-app123") == "my-app123"

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError, match="영문 소문자"):
            validate_subdomain("MyApp")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="영문 소문자"):
            validate_subdomain("my_app")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="영문 소문자"):
            validate_subdomain("a" * 64)

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="영문 소문자"):
            validate_subdomain("")

    def test_rejects_reserved_word(self):
        with pytest.raises(ValueError, match="예약된 서브도메인"):
            validate_subdomain("admin")


def _make_get_mock(existing_routes):
    # json=lambda가 매번 새 리스트를 반환하게 해서, add_route()의 routes.insert(0, ...)가
    # 테스트가 들고 있는 원본 existing_routes를 제자리 변형하지 않도록 함
    return MagicMock(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: list(existing_routes) if existing_routes is not None else None,
    )


class TestAddRoute:
    @patch("services.caddy_service.requests.delete")
    @patch("services.caddy_service.requests.patch")
    @patch("services.caddy_service.requests.get")
    def test_success_prepends_via_get_then_patch(self, mock_get, mock_patch, mock_delete):
        existing = [{"@id": "route-other", "match": [{"host": ["other.https.gsmsv.site"]}]}]
        mock_get.return_value = _make_get_mock(existing)
        mock_patch.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        mock_delete.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)

        result = add_route("myapp", "10.0.0.150", 8080)

        assert result is True
        mock_delete.assert_called_once()
        mock_get.assert_called_once()
        assert mock_get.call_args[0][0].endswith("/routes")

        args, kwargs = mock_patch.call_args
        assert args[0].endswith("/routes")
        new_routes = kwargs["json"]
        assert new_routes[0]["@id"] == "route-myapp"
        assert new_routes[0]["match"][0]["host"] == ["myapp.https.gsmsv.site"]
        assert new_routes[0]["handle"][0]["upstreams"][0]["dial"] == "10.0.0.150:8080"
        assert new_routes[0]["terminal"] is True
        assert new_routes[1] == existing[0]  # 기존 라우트는 뒤로 밀림, 유지됨

    @patch("services.caddy_service.requests.delete")
    @patch("services.caddy_service.requests.patch")
    @patch("services.caddy_service.requests.get")
    def test_empty_routes_array_handled(self, mock_get, mock_patch, mock_delete):
        mock_get.return_value = _make_get_mock(None)  # 라우트가 아예 없으면 null
        mock_patch.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        mock_delete.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)

        result = add_route("myapp", "10.0.0.150", 8080)

        assert result is True
        new_routes = mock_patch.call_args[1]["json"]
        assert len(new_routes) == 1
        assert new_routes[0]["@id"] == "route-myapp"

    @patch("services.caddy_service.requests.delete")
    @patch("services.caddy_service.requests.get", side_effect=Exception("connection refused"))
    def test_failure_returns_false_without_raising(self, mock_get, mock_delete):
        mock_delete.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        result = add_route("myapp", "10.0.0.150", 8080)
        assert result is False

    @patch("services.caddy_service.requests.delete")
    @patch("services.caddy_service.requests.patch")
    @patch("services.caddy_service.requests.get")
    def test_deletes_existing_route_before_get(self, mock_get, mock_patch, mock_delete):
        calls = []
        mock_get.side_effect = lambda *a, **k: calls.append("get") or _make_get_mock([])
        mock_patch.side_effect = lambda *a, **k: calls.append("patch") or MagicMock(status_code=200, raise_for_status=lambda: None)
        mock_delete.side_effect = lambda *a, **k: calls.append("delete") or MagicMock(status_code=200, raise_for_status=lambda: None)

        result = add_route("myapp", "10.0.0.150", 8080)

        assert result is True
        assert calls == ["delete", "get", "patch"]
        args, _ = mock_delete.call_args
        assert args[0].endswith("/id/route-myapp")


class TestDeleteRoute:
    @patch("services.caddy_service.requests.delete")
    def test_success_calls_correct_id(self, mock_delete):
        mock_delete.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)

        result = delete_route("myapp")

        assert result is True
        args, _ = mock_delete.call_args
        assert args[0].endswith("/id/route-myapp")

    @patch("services.caddy_service.requests.delete")
    def test_missing_route_still_returns_true(self, mock_delete):
        mock_delete.return_value = MagicMock(status_code=400)
        result = delete_route("already-gone")
        assert result is True

    @patch("services.caddy_service.requests.delete", side_effect=Exception("timeout"))
    def test_failure_returns_false_without_raising(self, mock_delete):
        result = delete_route("myapp")
        assert result is False
