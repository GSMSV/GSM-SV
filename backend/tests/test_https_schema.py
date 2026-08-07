"""HttpsRouteCreate 스키마 검증"""
import pytest
from pydantic import ValidationError

from schemas.https_schema import HttpsRouteCreate


class TestHttpsRouteCreate:
    def test_valid_payload(self):
        body = HttpsRouteCreate(subdomain="myapp", internal_port=8080)
        assert body.subdomain == "myapp"
        assert body.internal_port == 8080

    def test_invalid_subdomain_raises(self):
        with pytest.raises(ValidationError):
            HttpsRouteCreate(subdomain="Invalid_Sub", internal_port=8080)

    def test_reserved_subdomain_raises(self):
        with pytest.raises(ValidationError):
            HttpsRouteCreate(subdomain="www", internal_port=8080)

    def test_port_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            HttpsRouteCreate(subdomain="myapp", internal_port=70000)
