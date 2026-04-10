#!/usr/bin/env bash
set -u

# Command-level smoke test for SoulMate CLI.
# Usage:
#   bash scripts/smoke_test.sh
#   bash scripts/smoke_test.sh qwen3:8b-q4_K_M smoke_user

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODEL="${1:-qwen3:8b-q4_K_M}"
TEST_USER="${2:-smoke}"
export SOULMATE_SMOKE_USER="$TEST_USER"

PASS_COUNT=0
FAIL_COUNT=0

log_step() {
  echo
  echo "== $1 =="
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  echo "[ok] $1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  echo "[fail] $1"
}

run_cmd() {
  local name="$1"
  shift
  if "$@"; then
    pass "$name"
  else
    fail "$name"
  fi
}

run_capture_contains() {
  local name="$1"
  local pattern="$2"
  shift 2
  local output
  if output="$("$@" 2>&1)"; then
    if printf "%s" "$output" | grep -Eq "$pattern"; then
      pass "$name"
    else
      echo "$output"
      fail "$name (pattern not found: $pattern)"
    fi
  else
    echo "$output"
    fail "$name"
  fi
}

log_step "Project"
echo "[info] project: ${PROJECT_DIR}"
cd "$PROJECT_DIR" || exit 1

if [[ ! -f "app/main.py" ]]; then
  echo "[fatal] app/main.py not found. Run this script inside project/."
  exit 1
fi

log_step "Python Environment"
run_cmd "python command exists" command -v python
run_cmd "python version" python -V
run_cmd "import ollama package" python -c "import ollama"

if [[ -z "${OLLAMA_HOST:-}" ]]; then
  WIN_HOST="$(ip route | awk '/default/ {print $3; exit}')"
  if [[ -n "${WIN_HOST:-}" ]]; then
    export OLLAMA_HOST="${WIN_HOST}:11434"
    echo "[info] OLLAMA_HOST was empty, auto-set to ${OLLAMA_HOST}"
  fi
fi

if [[ -n "${OLLAMA_HOST:-}" ]]; then
  run_cmd "Ollama API /api/tags reachable" curl -fsS "http://${OLLAMA_HOST}/api/tags"
else
  fail "OLLAMA_HOST is empty"
fi

log_step "CLI Basics"
run_cmd "python -m app.main --help" python -m app.main --help
run_cmd "python init_db.py" python init_db.py

log_step "Single Ask"
run_capture_contains \
  "single ask returns AI or empty warning" \
  "AI>|\\[warn\\] empty response from model" \
  python -m app.main --model "$MODEL" --user "$TEST_USER" --ask "这是一次smoke test，请简短回复"

log_step "DB Sanity"
run_cmd "sqlite tables exist via Python" python - <<'PY'
from app.db.sqlite_store import get_connection

required = {"users", "sessions", "messages"}
with get_connection() as conn:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
tables = {r[0] for r in rows}
missing = required - tables
if missing:
    raise SystemExit(f"missing tables: {sorted(missing)}")
print("tables ok")
PY

run_cmd "latest session exists for smoke user" python - <<'PY'
import os
from app.db.sqlite_store import get_connection, get_or_create_user, get_latest_session_id

test_user = os.getenv("SOULMATE_SMOKE_USER", "smoke")
with get_connection() as conn:
    uid = get_or_create_user(conn, test_user)
    sid = get_latest_session_id(conn, uid)
if sid is None:
    raise SystemExit("no latest session")
print(f"latest session: {sid}")
PY

log_step "Summary"
echo "[summary] pass=${PASS_COUNT} fail=${FAIL_COUNT}"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
exit 0
