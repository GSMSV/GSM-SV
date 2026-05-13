#!/bin/bash
# PostToolUse hook — 파일 편집 후 포맷팅 + 문법 검사

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

if [ ! -f "$FILE" ]; then
    exit 0
fi

# ── Python: ruff 포맷팅 + 린트 수정 + 문법 검사 ──────────────────────
if echo "$FILE" | grep -q "\.py$"; then
    venv/bin/ruff format "$FILE" 2>/dev/null
    venv/bin/ruff check --fix "$FILE" 2>/dev/null
    RESULT=$(python3 -m py_compile "$FILE" 2>&1)
    if [ $? -ne 0 ]; then
        echo ""
        echo "⚠️  Python 문법 오류 감지: $FILE"
        echo "$RESULT"
        echo ""
        echo "→ 위 오류를 수정한 뒤 다시 저장하세요."
    fi
    exit 0
fi

# ── TypeScript: 타입 검사 ────────────────────────────────────────────
if echo "$FILE" | grep -qE "\.(ts|tsx)$"; then
    FRONTEND_DIR=$(echo "$FILE" | grep -oE ".*/frontend")
    if [ -n "$FRONTEND_DIR" ] && [ -f "$FRONTEND_DIR/tsconfig.json" ]; then
        RESULT=$(cd "$FRONTEND_DIR" && npx tsc --noEmit 2>&1)
        if [ $? -ne 0 ]; then
            echo ""
            echo "⚠️  TypeScript 타입 오류 감지: $FILE"
            echo "$RESULT" | head -20
            echo ""
            echo "→ 위 오류를 수정한 뒤 다시 저장하세요."
        fi
    fi
    exit 0
fi

exit 0
