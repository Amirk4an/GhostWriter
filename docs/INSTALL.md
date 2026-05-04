# Установка одной командой

Эта страница — для **конечного пользователя**: одна команда в терминале/PowerShell ставит готовое приложение без Python, виртуальных окружений и сборки. Если вы разработчик и хотите собрать проект из исходников — см. [BUILD_CROSS_PLATFORM.md](BUILD_CROSS_PLATFORM.md).

## Требования

- Доступ в интернет (скрипт скачивает релиз с GitHub).
- Минимум 500 МБ свободного места на диске.
- **macOS 12+**, **Windows 10/11**, **Linux** (любой современный с PulseAudio/PipeWire).

## Приватный репозиторий GitHub

Если репозиторий **не публичный**, ссылки `raw.githubusercontent.com` и `releases/latest/download/...` для анонимного `curl` возвращают **404**. В терминале это часто выглядит как `bash: line 1: 404:: command not found` — в `bash` попадает текст ответа «Not Found», а не сам скрипт.

**Не выполняйте** `curl ... | bash`, пока не убедитесь, что первые строки ответа — это код shell (начинается с `#!/` или `#`).

**Вариант A — сделать репозиторий public** (тогда команды ниже по разделам macOS/Linux/Windows работают как в инструкции).

**Вариант B — оставить private и использовать токен** (Classic PAT: scope `repo`, или Fine-grained: **Contents** и **Metadata** на репозиторий; для `gh auth token` обычно достаточно уже залогиненного `gh`).

### macOS / Linux (приватный репо)

```bash
export GITHUB_TOKEN="$(gh auth token)"   # или вставьте свой PAT
curl -sSL \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/Amirk4an/GhostWriter/contents/install.sh?ref=main" | bash
```

Скрипт установки сам подхватит `GITHUB_TOKEN` (или `GH_TOKEN`) и скачает zip/tar.gz релиза через **GitHub API**.

### Windows (приватный репо)

```powershell
$env:GITHUB_TOKEN = gh auth token   # или ваш PAT
iex (irm -Headers @{
    Authorization = "Bearer $($env:GITHUB_TOKEN)"
    Accept          = 'application/vnd.github.raw'
} "https://api.github.com/repos/Amirk4an/GhostWriter/contents/install.ps1?ref=main")
```

## macOS

```bash
curl -sSL https://raw.githubusercontent.com/Amirk4an/GhostWriter/main/install.sh | bash
```

**Что происходит:**

1. Скачивается `GhostWriter-macOS.zip` из [последнего релиза](https://github.com/Amirk4an/GhostWriter/releases/latest).
2. Распаковывается `GhostWriter.app` в `/Applications` (или в `~/Applications`, если нет прав).
3. Снимается quarantine-атрибут (`xattr -cr`), чтобы Gatekeeper не ругался.

**После установки:**

1. Запустите **GhostWriter** из Launchpad.
2. **Если macOS пишет «приложение нельзя открыть, потому что разработчик не подтверждён»:**
   - Откройте **Системные настройки → Конфиденциальность и безопасность**.
   - Внизу страницы нажмите **«Открыть всё равно»** напротив строки про GhostWriter.
   - При следующем запуске подтвердите ещё раз — это нормально для приложения без Apple Developer ID.
3. Выдайте права в **Системные настройки → Конфиденциальность и безопасность**:
   - **Микрофон** — для записи голоса;
   - **Универсальный доступ (Accessibility)** — для глобальных горячих клавиш и автовставки;
   - **Автоматизация** — разрешить управление **System Events** (используется для `Cmd+V`).

## Windows

Запустите **PowerShell** (не cmd) и вставьте:

```powershell
iex (irm https://raw.githubusercontent.com/Amirk4an/GhostWriter/main/install.ps1)
```

**Что происходит:**

1. Скачивается `GhostWriter-Windows-Setup.exe` (Inno Setup) из [последнего релиза](https://github.com/Amirk4an/GhostWriter/releases/latest).
2. Запускается тихая установка: `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`.
3. Появляется запрос UAC — подтвердите.
4. Файлы кладутся в `C:\Program Files\Ghost Writer\`, ярлык — в меню «Пуск».
5. Временный установщик удаляется.

**После установки:**

1. Запустите **Ghost Writer** из меню «Пуск».
2. Если SmartScreen покажет **«Неизвестный издатель»** (это ожидаемо для unsigned-билда):
   - нажмите **«Подробнее»**;
   - затем **«Выполнить в любом случае»**.
3. Разрешите доступ к микрофону: **Параметры → Конфиденциальность и безопасность → Микрофон → Разрешить доступ настольных приложений**.

## Linux

```bash
curl -sSL https://raw.githubusercontent.com/Amirk4an/GhostWriter/main/install.sh | bash
```

**Что происходит:**

1. Скачивается `GhostWriter-Linux.tar.gz` из [последнего релиза](https://github.com/Amirk4an/GhostWriter/releases/latest).
2. Распаковывается в `~/.local/share/GhostWriter/`.
3. Создаётся симлинк `~/.local/bin/GhostWriter` (запуск по имени из терминала).
4. Создаётся файл `.desktop` в `~/.local/share/applications/` для меню приложений.

**После установки:**

1. Если `~/.local/bin` есть в `PATH`, просто наберите `GhostWriter`. Иначе скрипт покажет команду для добавления.
2. Установите системные зависимости аудио (если ещё не установлены):
   ```bash
   # Debian / Ubuntu
   sudo apt install libportaudio2

   # Fedora
   sudo dnf install portaudio

   # Arch
   sudo pacman -S portaudio
   ```
3. Для появления ярлыка в меню приложений может потребоваться `update-desktop-database ~/.local/share/applications/` или перелогинка.

## Первая настройка

После запуска приложение само создаст пользовательский каталог:

- **macOS:** `~/Library/Application Support/GhostWriter/`
- **Windows:** `%APPDATA%\GhostWriter\`
- **Linux:** `~/.ghostwriter/`

Туда будут писаться: история, статистика, `.env.secrets` (с API-ключами провайдеров) и часть логов. Ввод API-ключей — в дашборде на вкладке **Settings**. Полный список настроек — [docs/CONFIGURATION.md](CONFIGURATION.md).

## Удаление

### macOS

```bash
rm -rf /Applications/GhostWriter.app
# Или из ~/Applications, если ставили туда:
rm -rf ~/Applications/GhostWriter.app
# Опционально - удалить пользовательские данные:
rm -rf ~/Library/Application\ Support/GhostWriter
```

### Windows

**Параметры → Приложения → Ghost Writer → Удалить.**

Опционально (удалить пользовательские данные):

```powershell
Remove-Item -Recurse -Force "$env:APPDATA\GhostWriter"
```

### Linux

```bash
rm -rf ~/.local/share/GhostWriter
rm -f  ~/.local/bin/GhostWriter
rm -f  ~/.local/share/applications/GhostWriter.desktop
# Опционально - удалить пользовательские данные:
rm -rf ~/.ghostwriter
```

## Обновление

Просто запустите команду установки заново — install.sh / install.ps1 заменят старую версию на актуальную из последнего релиза. Пользовательские данные (`history`, `stats`, `.env.secrets`) при этом не удаляются: они хранятся отдельно (см. «Первая настройка»).

## Если что-то не работает

- **macOS:** «приложение повреждено» — снова выполните `xattr -cr /Applications/GhostWriter.app` и запустите через **«Открыть всё равно»** в Privacy & Security.
- **Windows:** установщик не запускается — проверьте, что вы открыли **PowerShell** (а не cmd), и подтвердили UAC. Лог установки лежит в `%TEMP%\GhostWriter_Install_*.log`.
- **Linux:** «нет звука / нет микрофона» — проверьте `pactl list sources` и установите `libportaudio2`.

Подробное руководство по запуску, настройке провайдеров STT/LLM и сценариям — в корневом [README.md](../README.md) и [CONFIGURATION.md](CONFIGURATION.md).
