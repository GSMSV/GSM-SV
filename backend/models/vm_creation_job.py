import json
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base
from core.timezone import now_kst


class VmCreationJob(Base):
    __tablename__ = "vm_creation_jobs"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    tier = Column(String(32), nullable=False)
    os = Column(String(32), nullable=False)
    node_name = Column(String(128), nullable=True, index=True)
    requested_name = Column(String(128), nullable=True)
    queued_at = Column(DateTime(timezone=True), default=now_kst, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    vmid = Column(Integer, nullable=True, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    payload_json = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    user = relationship("User")

    @property
    def payload(self) -> dict:
        return json.loads(self.payload_json) if self.payload_json else {}

    @payload.setter
    def payload(self, value: dict) -> None:
        self.payload_json = json.dumps(value, ensure_ascii=False)

    @property
    def result(self) -> dict | None:
        return json.loads(self.result_json) if self.result_json else None

    @result.setter
    def result(self, value: dict | None) -> None:
        self.result_json = json.dumps(value, ensure_ascii=False, default=str) if value is not None else None
