#!/usr/bin/env bash
# Сборка Python-бэкенда через PyInstaller в каталог dist/ghost_backend/ (onedir, без консоли).
# Режим onedir на macOS совместим с будущими версиями PyInstaller и не даёт предупреждения onefile+windowed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Удаляем прошлый вывод (в т.ч. onefile-бинарник с тем же именем, что и каталог onedir).
rm -rf "${ROOT}/dist/ghost_backend" "${ROOT}/build/ghost_backend"

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "Не найден интерпретатор: ожидался ${ROOT}/.venv/bin/python или python3 в PATH" >&2
  exit 1
fi

exec "${PY}" -m PyInstaller --name ghost_backend --onedir --noconsole main.py
