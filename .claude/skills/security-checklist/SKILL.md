---
name: security-checklist
description: Validate security risks — hardcoded secrets, Path Traversal, SQL Injection, JWT validation, sensitive logging, and role-based access control. Run before merging auth/API changes.
allowed-tools: Bash(grep:*)
---

# Security Checklist (GSMSV)

## Checklist Items

### 1. Hardcoded secrets
- [ ] No API keys, secrets, or passwords in code?
- [ ] Environment variables or `.env` files used instead?

```bash
grep -r "password.*=.*['\"]" --include="*.py" api/ services/
grep -r "secret.*=.*['\"]" --include="*.py" api/ services/
grep -r "API_KEY\|SECRET_KEY" --include="*.ts" --include="*.tsx" frontend/
```

### 2. Path Traversal
- [ ] `Path.resolve()` used when building file paths?
- [ ] Validates path is under an allowed directory?
- [ ] Blocks `../` or absolute path input?

```bash
grep -r "Path(" --include="*.py" api/ services/
grep -r "os.path\|open(" --include="*.py" api/ services/
```

### 3. SQL Injection
- [ ] Uses ORM (SQLAlchemy)?
- [ ] If raw SQL is used, parameters are bound?
- [ ] Avoids building SQL with string formatting?

### 4. JWT validation
- [ ] Verifies JWT signature?
- [ ] Checks expiration?
- [ ] Identifies user from token claims (not request body user_id)?

### 5. Logging
- [ ] No passwords, tokens, or secrets in logs?
- [ ] Appropriate log levels used?

```bash
grep -r "logger\.\|print(" --include="*.py" api/ services/ | grep -i "password\|token\|secret"
```

### 6. Role-based access control
- [ ] Auth-required endpoints include `Depends(get_current_user)`?
- [ ] Role checks (USER/PROJECT_OWNER/ADMIN) happen server-side?
- [ ] Access is not enforced only by hiding frontend UI?
- [ ] Access to other users' resources is blocked/validated?

### 7. CORS
- [ ] CORS includes only allowed origins?
- [ ] If `*` wildcard is used, is there a deliberate reason? (allowed if intentional)

## Report Format

For each item:
- ✓ Pass
- ⚠ Warning (recommendation)
- ✗ Error (must fix)

Final summary: `{n} items — {p} passed, {w} warnings, {e} errors`
