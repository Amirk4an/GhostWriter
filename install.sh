#!/usr/bin/env bash
# Ghost Writer — установка одной командой для macOS и Linux.
#
# Использование:
#   curl -sSL https://raw.githubusercontent.com/Amirk4an/GhostWriter/main/install.sh | bash
#
# Скрипт:
#   - определяет ОС;
#   - скачивает последний релиз с GitHub (https://github.com/Amirk4an/GhostWriter/releases/latest);
#   - macOS:   распаковывает GhostWriter.app в /Applications (или ~/Applications, если нет прав);
#   - Linux:   распаковывает onedir в ~/.local/share/GhostWriter и кладёт симлинк в ~/.local/bin;
#   - снимает quarantine-атрибут на macOS, создаёт .desktop-файл на Linux.

set -euo pipefail

# --- Конфигурация (white-label: при форке менять только GH_OWNER/GH_REPO/APP_NAME) ---
GH_OWNER="${GHOSTWRITER_GH_OWNER:-Amirk4an}"
GH_REPO="${GHOSTWRITER_GH_REPO:-GhostWriter}"
APP_NAME="${GHOSTWRITER_APP_NAME:-GhostWriter}"

ASSET_MACOS="${APP_NAME}-macOS.zip"
ASSET_LINUX="${APP_NAME}-Linux.tar.gz"
RELEASE_BASE_URL="https://github.com/${GH_OWNER}/${GH_REPO}/releases/latest/download"

# --- Утилиты вывода ---
_color() {
    local code="$1"; shift
    if [ -t 1 ]; then
        printf '\033[%sm%s\033[0m\n' "$code" "$*"
    else
        printf '%s\n' "$*"
    fi
}
info()  { _color "1;36" "==> $*"; }
ok()    { _color "1;32" "✓ $*"; }
warn()  { _color "1;33" "! $*"; }
err()   { _color "1;31" "✗ $*" >&2; }

die() {
    err "$*"
    exit 1
}

# --- Очистка временной папки ---
TMP_DIR=""
cleanup() {
    if [ -n "${TMP_DIR}" ] && [ -d "${TMP_DIR}" ]; then
        rm -rf "${TMP_DIR}"
    fi
}
trap cleanup EXIT INT TERM

# --- Проверка обязательных команд ---
require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Не найдена команда '$1'. Установите её и повторите."
}

# --- Скачивание с прогрессом ---
download() {
    local url="$1"
    local output="$2"
    info "Скачивание: ${url}"
    if ! curl -fL --retry 3 --retry-delay 2 -o "${output}" "${url}"; then
        die "Не удалось скачать ${url}. Проверьте интернет-соединение и наличие релиза в GitHub."
    fi
}

# ============================================================
# macOS
# ============================================================
install_macos() {
    require_cmd curl
    require_cmd unzip

    local zip_path="${TMP_DIR}/${ASSET_MACOS}"
    download "${RELEASE_BASE_URL}/${ASSET_MACOS}" "${zip_path}"

    # Выбор каталога установки: /Applications (системный) или ~/Applications (пользовательский).
    local install_dir="/Applications"
    if [ ! -w "${install_dir}" ]; then
        warn "Нет прав на запись в ${install_dir}. Попробуем установить в ~/Applications."
        install_dir="${HOME}/Applications"
        mkdir -p "${install_dir}"
    fi

    local target_app="${install_dir}/${APP_NAME}.app"
    if [ -d "${target_app}" ]; then
        info "Удаляю предыдущую установку: ${target_app}"
        rm -rf "${target_app}"
    fi

    info "Распаковка ${ASSET_MACOS} в ${install_dir}"
    unzip -q "${zip_path}" -d "${install_dir}"

    if [ ! -d "${target_app}" ]; then
        die "После распаковки не найден ${target_app}. Архив повреждён или имеет неожиданную структуру."
    fi

    # Снимаем quarantine, иначе macOS Gatekeeper выдаст «Приложение повреждено» для unsigned билда.
    info "Снимаю quarantine-атрибут (xattr -cr)"
    xattr -cr "${target_app}" 2>/dev/null || warn "xattr вернул ошибку — возможно, потребуется ручной запуск через Privacy & Security."

    ok "${APP_NAME} установлен в ${target_app}"
    cat <<EOF

Что дальше:
  1. Откройте ${APP_NAME} из Launchpad или Finder.
  2. Если macOS пишет, что приложение нельзя открыть, перейдите:
     System Settings → Privacy & Security → нажмите «Open Anyway» рядом с ${APP_NAME}.
  3. Выдайте права в System Settings → Privacy & Security:
     - Microphone     — для записи голоса;
     - Accessibility  — для глобального хоткея и автовставки текста;
     - Automation     — для управления System Events (вставка Cmd+V).

Документация: https://github.com/${GH_OWNER}/${GH_REPO}/blob/main/docs/INSTALL.md
EOF
}

# ============================================================
# Linux
# ============================================================
install_linux() {
    require_cmd curl
    require_cmd tar

    local tar_path="${TMP_DIR}/${ASSET_LINUX}"
    download "${RELEASE_BASE_URL}/${ASSET_LINUX}" "${tar_path}"

    local share_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/${APP_NAME}"
    local bin_dir="${HOME}/.local/bin"
    local app_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"

    if [ -d "${share_dir}" ]; then
        info "Удаляю предыдущую установку: ${share_dir}"
        rm -rf "${share_dir}"
    fi
    mkdir -p "${share_dir}" "${bin_dir}" "${app_dir}"

    info "Распаковка ${ASSET_LINUX} в ${share_dir}"
    # tar.gz содержит каталог GhostWriter/ — распаковываем в родителя share_dir и переименовываем при необходимости.
    local extract_root
    extract_root="$(dirname "${share_dir}")"
    tar -xzf "${tar_path}" -C "${extract_root}"

    # Если внутри архива лежал каталог не с тем именем — нормализуем.
    if [ ! -x "${share_dir}/${APP_NAME}" ] && [ -x "${share_dir}/GhostWriter" ]; then
        :  # каталог уже совпадает, ничего не делаем
    elif [ ! -d "${share_dir}" ]; then
        die "Не найден каталог приложения в ${share_dir} после распаковки."
    fi

    chmod +x "${share_dir}/${APP_NAME}" 2>/dev/null || true

    # Симлинк в ~/.local/bin для запуска по имени.
    local bin_link="${bin_dir}/${APP_NAME}"
    ln -sf "${share_dir}/${APP_NAME}" "${bin_link}"

    # Файл .desktop для меню приложений (best-effort).
    local desktop_file="${app_dir}/${APP_NAME}.desktop"
    cat > "${desktop_file}" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Comment=Voice dictation with global hotkey
Exec=${share_dir}/${APP_NAME}
Icon=${share_dir}/_internal/assets/icons/app_icon.png
Categories=Utility;AudioVideo;
Terminal=false
StartupNotify=false
EOF
    chmod 644 "${desktop_file}"

    ok "${APP_NAME} установлен в ${share_dir}"
    cat <<EOF

Что дальше:
  1. Запуск: '${APP_NAME}' (если '${bin_dir}' в PATH) или '${share_dir}/${APP_NAME}'.
  2. Для аудиозахвата нужен PortAudio. Если приложение не видит микрофон, установите:
       Debian/Ubuntu:  sudo apt install libportaudio2
       Fedora:         sudo dnf install portaudio
       Arch:           sudo pacman -S portaudio
  3. Меню приложений увидит ярлык после следующей перелогинки или через 'update-desktop-database ${app_dir}'.

EOF

    case ":${PATH}:" in
        *":${bin_dir}:"*) : ;;
        *) warn "${bin_dir} не находится в \$PATH. Добавьте строку в ~/.bashrc или ~/.zshrc:"
           printf '    export PATH="%s:$PATH"\n' "${bin_dir}" ;;
    esac

    cat <<EOF
Документация: https://github.com/${GH_OWNER}/${GH_REPO}/blob/main/docs/INSTALL.md
EOF
}

# ============================================================
# Точка входа
# ============================================================
main() {
    info "Установка ${APP_NAME}"

    TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t ghostwriter)"

    local os_name
    os_name="$(uname -s)"
    case "${os_name}" in
        Darwin)
            install_macos
            ;;
        Linux)
            install_linux
            ;;
        *)
            die "Неподдерживаемая ОС: ${os_name}. Скрипт работает только на macOS и Linux."
            ;;
    esac

    ok "Готово."
}

main "$@"
