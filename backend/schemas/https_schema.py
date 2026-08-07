from pydantic import BaseModel, Field, field_validator

from services.caddy_service import validate_subdomain


class HttpsRouteCreate(BaseModel):
    subdomain: str
    internal_port: int = Field(..., ge=1, le=65535)

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain_field(cls, v: str) -> str:
        return validate_subdomain(v)
