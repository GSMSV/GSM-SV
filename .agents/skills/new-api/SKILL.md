---
name: new-api
description: Implement a FastAPI endpoint end-to-end — model → service → router → frontend API function. Follow GSMSV project conventions.
---

# New API Implementation Flow (GSMSV)

## Directory Structure

```
api/routes/{domain}.py        # router
services/{domain}_service.py  # service logic
models/{Domain}.py            # SQLAlchemy model (reuse existing)
frontend/lib/api.ts           # frontend API functions
frontend/lib/types.ts         # type definitions
```

## Step 1 — Service Function

```python
# services/{domain}_service.py
def create_{resource}(
    db: Session,
    user: User,
    data: Create{Resource}Request,
) -> {Resource}Response:
    # authorization
    if user.role not in [UserRole.ADMIN, UserRole.PROJECT_OWNER]:
        raise HTTPException(status_code=403, detail="Permission denied.")
    
    # business logic
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
# top of api/routes/{domain}.py or separate schemas file

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
        raise HTTPException(status_code=404, detail="Resource not found.")
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

- [ ] Implement service function (including auth checks)
- [ ] Write Pydantic request/response schemas
- [ ] Register router endpoint
- [ ] Confirm router is included in `main.py`
- [ ] Add frontend API function
- [ ] Add TypeScript type definitions
- [ ] Correct HTTP status codes (GET 200, POST 201)
- [ ] Include auth dependency (`Depends(get_current_user)`)
- [ ] If RBAC is applied, make it explicit
