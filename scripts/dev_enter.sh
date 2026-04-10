#!/usr/bin/env bash
set -euo pipefail

# One-command entry for WSL Python + Ollama workflow.
# Usage:
#   source scripts/dev_enter.sh
#   source scripts/dev_enter.sh /home/<user>/projects/soulmate

# This script must be sourced so that .venv activation persists
# in the current shell.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "[error] Please source this script (do not run with 'bash')."
  echo "Example:"
  echo "  source scripts/dev_enter.sh /home/yjh/projects/soulmate"
  exit 1
fi

PROJECT_DIR="${1:-$HOME/projects/soulmate}"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  echo "Pass path explicitly: source scripts/dev_enter.sh /path/to/project"
  exit 1
fi

cd "$PROJECT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "[setup] creating .venv ..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

WIN_HOST="$(ip route | awk '/default/ {print $3; exit}')"
if [[ -z "${WIN_HOST:-}" ]]; then
  echo "[error] cannot detect Windows host IP from WSL routing table."
  exit 1
fi

export OLLAMA_HOST="${WIN_HOST}:11434"

if ! python -c "import ollama" >/dev/null 2>&1; then
  echo "[setup] installing python package: ollama"
  python -m pip install --upgrade pip
  python -m pip install ollama
fi

echo "[ok] project: $(pwd)"
echo "[ok] python : $(which python)"
python --version
echo "[ok] pip    : $(python -m pip -V)"
echo "[ok] OLLAMA_HOST=${OLLAMA_HOST}"

echo "[check] testing Ollama API ..."
if curl -fsS "http://${OLLAMA_HOST}/api/tags" >/dev/null; then
  echo "[ok] Ollama API reachable."
else
  echo "[warn] Ollama API not reachable at http://${OLLAMA_HOST}"
  echo "       Ensure Ollama is running on Windows and firewall allows TCP 11434."
fi

cat <<'EOF'

Next:
  python init_db.py
  python -m app.main --model qwen3:8b-q4_K_M

EOF

