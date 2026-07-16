from schemas.vm_schema import VMTier

# VM 티어별 리소스 정의
TIER_SPECS = {
    VMTier.BASIC:    {"memory": 2048, "cores": 1, "disk": 20},
    VMTier.STANDARD: {"memory": 4096, "cores": 2, "disk": 20},
    # 프로젝트 오너 전용 (최대 4 vCPU, 16GB RAM, 40GB SSD)
    VMTier.PROJECT_CUSTOM: {"memory": 16384, "cores": 4, "disk": 40},
}

AUTO_SNAP_PREFIX = "auto-daily"
PROVISIONING_UPTIME_THRESHOLD_SECONDS = 180
