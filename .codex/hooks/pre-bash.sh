#!/bin/bash
# PreToolUse hook: block risky Bash commands.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null)

if echo "$COMMAND" | grep -qE "git push.*(--force|-f).*\bmain\b|git push.*\bmain\b.*(--force|-f)"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "main 브랜치에 force push는 금지되어 있습니다.\n→ develop 브랜치에 push한 뒤 GitHub PR을 통해 main에 머지하세요."
}
EOF
    exit 0
fi

if echo "$COMMAND" | grep -qE "git push\s+(origin\s+)?(\w+:)?main\b" && \
   ! echo "$COMMAND" | grep -qE "git push.*develop|git push.*origin main:develop"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "main 브랜치에 직접 push는 금지되어 있습니다.\n→ develop 브랜치에 push하고 GitHub에서 PR을 통해 머지하세요."
}
EOF
    exit 0
fi

if echo "$COMMAND" | grep -qE "rm\s+-rf?\s+.*(api|services|frontend|models|core|schemas)\b"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "소스 디렉터리에 대한 rm -rf는 금지되어 있습니다.\n파일 삭제가 필요하면 특정 파일을 명시해주세요."
}
EOF
    exit 0
fi

if echo "$COMMAND" | grep -qE "git reset --hard" && \
   git branch --show-current 2>/dev/null | grep -q "^main$"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "main 브랜치에서 git reset --hard는 금지되어 있습니다.\ndevelop 또는 feature 브랜치에서 작업하세요."
}
EOF
    exit 0
fi

echo '{"decision": "approve"}'
exit 0
