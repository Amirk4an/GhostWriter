#!/usr/bin/env bash
# Сборка Python-бэкенда в один исполняемый файл (PyInstaller) в каталог dist/ репозитория.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "Не найден интерпретатор: ожидался ${ROOT}/.venv/bin/python или python3 в PATH" >&2
  exit 1
fi

exec "${PY}" -m PyInstaller --name ghost_backend --onefile --noconsole main.py
