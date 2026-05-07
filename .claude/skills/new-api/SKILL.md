---
name: new-api
description: FastAPI 엔드포인트를 end-to-end로 구현합니다 — 모델 → 서비스 → 라우터 → 프론트엔드 API 함수. GSMSV 프로젝트 컨벤션을 따릅니다.
---

# New API Implementation Flow (GSMSV)

## Directory Structure

```
api/routes/{domain}.py        # 라우터
services/{domain}_service.py  # 서비스 로직
models/{Domain}.py            # SQLAlchemy 모델 (기존 재사용)
frontend/lib/api.ts           # 프론트엔드 API 함수
frontend/lib/types.ts         # 타입 정의
```

## Step 1 — Service Function

```python
# services/{domain}_service.py
def create_{resource}(
    db: Session,
    user: User,
    data: Create{Resource}Request,
) -> {Resource}Response:
    # 권한 검증
    if user.role not in [UserRole.ADMIN, UserRole.PROJECT_OWNER]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    
    # 비즈니스 로직
    item = {Resource}(
        field1=data.field1,
        user_id=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    
    return {Resource}Response.model_validate(item)
```

## Step 2 — Pydantic Schemas

```python
# api/routes/{domain}.py 상단 또는 별도 schemas 파일

class Create{Resource}Request(BaseModel):
    field1: str
    field2: Optional[str] = None

class {Resource}Response(BaseModel):
    id: int
    field1: str
    
    model_config = ConfigDict(from_attributes=True)
```

## Step 3 — Router Endpoint

```python
# api/routes/{domain}.py
router = APIRouter(prefix="/{resources}", tags=["{domain}"])

@router.post("", response_model={Resource}Response, status_code=201)
async def create_{resource}(
    request: Create{Resource}Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {domain}_service.create_{resource}(db, current_user, request)

@router.get("/{id}", response_model={Resource}Response)
async def get_{resource}(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = {domain}_service.get_{resource}(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="리소스를 찾을 수 없습니다.")
    return item
```

## Step 4 — Frontend API Function

```typescript
// frontend/lib/api.ts
export async function create{Resource}(data: Create{Resource}Request): Promise<{Resource}Response> {
  const res = await fetch(`${API_BASE}/{resources}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

## Step 5 — Type Definitions

```typescript
// frontend/lib/types.ts
export interface {Resource} {
  id: number
  field1: string
  field2?: string
}

export interface Create{Resource}Request {
  field1: string
  field2?: string
}
```

## Checklist

- [ ] 서비스 함수 구현 (권한 검증 포함)
- [ ] Pydantic 요청/응답 스키마 작성
- [ ] 라우터 엔드포인트 등록
- [ ] `main.py` 에 라우터 include 확인
- [ ] 프론트엔드 API 함수 추가
- [ ] TypeScript 타입 정의 추가
- [ ] HTTP 상태 코드 정확 (GET 200, POST 201)
- [ ] 인증 의존성 (`Depends(get_current_user)`) 포함
- [ ] 역할 기반 접근 제어 적용 시 명시
