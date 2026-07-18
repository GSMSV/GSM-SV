import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class VMTier(str, Enum):
    BASIC = "basic"
    STANDARD = "standard"
    # 프로젝트 오너 전용 커스텀 스펙
    PROJECT_CUSTOM = "project_custom"


class VMOs(str, Enum):
    UBUNTU2204 = "ubuntu2204"
    WINDOWS_SERVER = "windows-server"


class VMActionType(str, Enum):
    START = "start"
    STOP = "stop"
    SHUTDOWN = "shutdown"
    REBOOT = "reboot"


class VMAction(BaseModel):
    """VM/컨테이너 제어 액션 모델"""

    action: VMActionType


class VMResize(BaseModel):
    """VM 사양 변경 요청 모델 (핫플러그)"""

    cores: Optional[int] = None
    memory: Optional[int] = None


class SnapshotCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    description: str = ""


class VMCreate(BaseModel):
    """VM 생성 요청 모델 - 사용자는 os, tier, node_name, purpose를 입력 (node_name·purpose 필수)"""

    tier: VMTier = VMTier.BASIC
    os: VMOs = VMOs.UBUNTU2204
    node_name: Optional[str] = None  # 큐 경로에서 필수 검증, vm_service 직접 호출 시 None 허용
    name: Optional[str] = None
    purpose: str  # 사용 목적 (모든 역할 필수)
    custom_cores: Optional[int] = None
    custom_memory: Optional[int] = None
    custom_disk: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is None:
            return v
        if len(v) > 40:
            raise ValueError("VM 이름은 40자 이하여야 합니다.")
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", v):
            raise ValueError(
                "VM 이름은 영문·숫자로 시작하고 영문·숫자·하이픈·언더스코어만 허용합니다."
            )
        return v

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("사용 목적을 입력해주세요.")
        if len(v) > 100:
            raise ValueError("사용 목적은 100자 이하여야 합니다.")
        return v


class VMPurposeUpdate(BaseModel):
    """VM 사용 목적 수정 요청 모델"""

    purpose: str

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("사용 목적을 입력해주세요.")
        if len(v) > 100:
            raise ValueError("사용 목적은 100자 이하여야 합니다.")
        return v


class VMCreationJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VMCreationJobResponse(BaseModel):
    """VM 생성 큐 작업 상태 응답."""

    job_id: str
    status: VMCreationJobStatus
    position: Optional[int] = None
    requested_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    vmid: Optional[int] = None
    node_name: Optional[str] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[dict] = None
