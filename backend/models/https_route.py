from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from core.database import Base


class HttpsRoute(Base):
    __tablename__ = "https_routes"

    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=False, index=True)
    subdomain = Column(String, nullable=False, unique=True, index=True)
    internal_port = Column(Integer, nullable=False)
    caddy_synced = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
