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


class TestAddRoute:
    @patch("services.caddy_service.requests.post")
    def test_success_posts_correct_payload(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)

        result = add_route("myapp", "10.0.0.150", 8080)

        assert result is True
        args, kwargs = mock_post.call_args
        assert "routes" in args[0]
        payload = kwargs["json"]
        assert payload["@id"] == "route-myapp"
        assert payload["match"][0]["host"] == ["myapp.https.gsmsv.site"]
        assert payload["handle"][0]["upstreams"][0]["dial"] == "10.0.0.150:8080"

    @patch("services.caddy_service.requests.post", side_effect=Exception("connection refused"))
    def test_failure_returns_false_without_raising(self, mock_post):
        result = add_route("myapp", "10.0.0.150", 8080)
        assert result is False


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
