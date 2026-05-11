---
name: format
description: Run code formatting in GSMSV — ruff for Python, ESLint for TypeScript. Use after large edits or when formatting is needed.
---

Run GSMSV project formatting:

## Python (ruff)

1. Ruff format + lint autofix:
   ```bash
   ruff format . && ruff check . --fix
   ```

2. Review results and report modified files

## TypeScript (ESLint + tsc)

1. ESLint autofix:
   ```bash
   cd frontend && npx eslint . --ext .ts,.tsx --fix
   ```

2. Type check (no changes, just verify):
   ```bash
   cd frontend && npx tsc --noEmit
   ```

3. Review results

## Unfixed items

If errors remain that cannot be auto-fixed, output the error messages and guide which items need manual fixes.
