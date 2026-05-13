---
name: test
description: Run pytest tests and report results. Decide test scope by context and analyze failures in detail. Run the full suite only when necessary.
allowed-tools: Bash(python:*)
---

Run tests following these steps:

## Steps

1. **Decide test scope**:
   - Specific file/module mentioned: run only related test files (recommended)
   - Specific feature area changed: run tests for that domain
   - Full run explicitly requested: run all tests

2. **Run tests**:

   ```bash
   # Related tests only (recommended)
   python -m pytest tests/test_{module}.py -v 2>&1

   # Specific function
   python -m pytest tests/test_{module}.py::test_{function_name} -v 2>&1

   # Full suite (only when necessary)
   python -m pytest tests/ -v 2>&1
   ```

3. **Analyze results**:
   - Show the test summary
   - On failure: show error messages and traceback, analyze root cause
   - On success: confirm number of tests passed

4. **Report**:
   - Total tests run
   - Passed/failed counts
   - If failures, suggest fixes

Do not claim success without running tests.
