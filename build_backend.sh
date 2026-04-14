#!/usr/bin/env bash
# Сборка Python-бэкенда через PyInstaller в каталог dist/ghost_backend/ (onedir, без консоли).
# Режим onedir на macOS совместим с будущими версиями PyInstaller и не даёт предупреждения onefile+windowed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Удаляем прошлый вывод: каталог onedir, кэш сборки и .app от PyInstaller (--noconsole на macOS).
rm -rf "${ROOT}/dist/ghost_backend" "${ROOT}/dist/ghost_backend.app" "${ROOT}/build/ghost_backend"

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "Не найден интерпретатор: ожидался ${ROOT}/.venv/bin/python или python3 в PATH" >&2
  exit 1
fi

FW_ASSETS_DIR="$("${PY}" -c 'import faster_whisper,inspect,os; print(os.path.join(os.path.dirname(inspect.getfile(faster_whisper)), "assets"))')"
if [[ ! -d "${FW_ASSETS_DIR}" ]]; then
  echo "Не найден faster_whisper assets: ${FW_ASSETS_DIR}" >&2
  exit 1
fi

exec "${PY}" -m PyInstaller \
  --noconfirm \
  --name ghost_backend \
  --onedir \
  --noconsole \
  --collect-data faster_whisper \
  --add-data "${FW_ASSETS_DIR}:faster_whisper/assets" \
  main.py
