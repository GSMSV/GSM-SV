#!/bin/bash
# PreToolCall hook — 위험한 Bash 명령 차단
# Claude Code가 Bash 도구를 실행하기 전에 호출됩니다.
# stdin으로 JSON을 받고, stdout으로 결정(approve/block)을 출력합니다.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null)

# ── 1. main 브랜치 force push 차단 ──────────────────────────────────
if echo "$COMMAND" | grep -qE "git push.*(--force|-f).*\bmain\b|git push.*\bmain\b.*(--force|-f)"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "⛔ main 브랜치에 force push는 금지되어 있습니다.\n→ develop 브랜치에 push한 뒤 GitHub PR을 통해 main에 머지하세요."
}
EOF
    exit 0
fi

# ── 2. main 브랜치 직접 push 차단 (develop → main은 GitHub에서만) ──
# git push origin main, git push origin HEAD:main 등
if echo "$COMMAND" | grep -qE "git push\s+(origin\s+)?(\w+:)?main\b" && \
   ! echo "$COMMAND" | grep -qE "git push.*develop|git push.*origin main:develop"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "⛔ main 브랜치에 직접 push는 금지되어 있습니다.\n→ develop 브랜치에 push하고 GitHub에서 PR을 통해 머지하세요."
}
EOF
    exit 0
fi

# ── 3. 소스 디렉터리 rm -rf 차단 ─────────────────────────────────────
if echo "$COMMAND" | grep -qE "rm\s+-rf?\s+.*(api|services|frontend|models|core|schemas)/"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "⛔ 소스 디렉터리에 대한 rm -rf는 금지되어 있습니다.\n파일 삭제가 필요하면 특정 파일을 명시해주세요."
}
EOF
    exit 0
fi

# ── 4. git reset --hard on main 차단 ─────────────────────────────────
if echo "$COMMAND" | grep -qE "git reset --hard" && \
   git branch --show-current 2>/dev/null | grep -q "^main$"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "⛔ main 브랜치에서 git reset --hard는 금지되어 있습니다.\ndevelop 또는 feature 브랜치에서 작업하세요."
}
EOF
    exit 0
fi

# ── 통과 ─────────────────────────────────────────────────────────────
echo '{"decision": "approve"}'
exit 0
