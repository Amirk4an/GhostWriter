# Ghost Writer (VoiceFlow WL)

Диктовка с глобальным хоткеем: запись с микрофона → STT (локальный **faster-whisper** или облачный **OpenAI/Groq/Deepgram**) → опциональная постобработка через LLM → вставка текста в активное приложение.

Запуск из консоли: `python3 main.py` (на macOS команды `python` часто нет в `PATH`). В трее — статус и меню; опционально плавающий индикатор (pill) и отдельный **Dashboard** (история, статистика, ключ API).

**Документация:** этот `README.md` — основная точка входа (обзор, запуск, сборка, troubleshooting). Технические детали: [docs/README.md](docs/README.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/CONFIGURATION.md](docs/CONFIGURATION.md) · [assets/models/README.md](assets/models/README.md)

## Требования

- **macOS** — основная целевая платформа (TCC, вставка через AppleScript/System Events, трей через **rumps** при наличии, **PyObjC** из `requirements.txt`).
- **Windows** — пути `%APPDATA%\GhostWriter\`, single-instance mutex, трей **pystray**, вставка **Ctrl+V** и поднятие переднего окна (`app/platform/windows/`). Глобальные хоткеи — **pynput**; command mode чтения выделения пока только на macOS (см. `docs/CONFIGURATION.md`).
- **Linux и прочие Unix** — запуск возможен (те же зависимости Python, кроме macOS-специфичных пакетов); пути данных `~/.ghostwriter/` (см. `app/platform/paths.py`). Полировка UX и автовставка ориентированы на macOS/Windows.
- **Python 3.9+**; в репозитории удобно держать `.venv` в корне.

Каталог пользовательских данных (история, статистика, `.env.secrets`, часть логов frozen-сборки) задаётся в **`app/platform/paths.py`** (`default_app_support_dir`).

### Основные зависимости Python

| Пакет | Роль |
|--------|------|
| `faster-whisper`, `numpy`, `scipy` | Локальный STT |
| `openai` | OpenAI STT/LLM |
| `litellm`, `httpx` | Единый LLM-слой для провайдеров (Groq/Anthropic/Gemini/OpenRouter/Mistral/Cohere/Ollama) и HTTP-клиент для STT-провайдеров |
| `sounddevice` | Захват аудио (PortAudio) |
| `pynput`, `pyperclip` | Глобальные клавиши и буфер обмена |
| `customtkinter`, `pillow` | UI дашборда и настроек |
| `pystray` | Трей (и fallback на macOS) |
| `rumps` (только Darwin) | Нативный трей macOS |
| `python-dotenv` | `.env` / `.env.secrets` |
| `pyobjc-*` (только Darwin) | Доступность и интеграции macOS |

Полный список версий — в [`requirements.txt`](requirements.txt). Тесты: `pytest`.

### Автовставка

- **macOS (Cmd+V):** **Системные настройки → Конфиденциальность и безопасность → Универсальный доступ** — разрешите приложение, из которого запущен Ghost Writer (**Terminal**, **Cursor**, **iTerm**, **Python**). Ошибка **1002** / System Events — проверьте права для **System Events**. При сбое текст часто уже в буфере — **Cmd+V** вручную.
- **Windows (Ctrl+V):** перед вставкой поднимается переднее окно (`app/platform/windows/focus.py`). Текст кладётся через **pyperclip**; целевое приложение должно принимать вставку из буфера.

## Known Limitations / Roadmap

### Command mode: паритет платформ

- **Сейчас:** чтение выделенного текста для voice-editing реализовано только на macOS через Accessibility API (`app/platform/macos_ax_selection.py`).
- **Windows/Linux:** режим редактирования выделения пока ограничен из-за отсутствия реализованного нативного backend-а чтения selection.

План для Windows (поэтапно):

1. **MVP fallback:** `Ctrl+C` -> чтение текста из clipboard -> обработка через LLM -> `Ctrl+V`.
2. **Надёжность пайплайна:** защита от race conditions буфера, таймауты ожидания, восстановление исходного clipboard.
3. **Edge cases:** пустое выделение, защищённые/неподдерживаемые поля ввода, приложения с нестандартными хоткеями вставки.
4. **UX-полировка:** явный статус в UI/логах при невозможности безопасно прочитать выделение.

Linux-поддержка планируется после стабилизации Windows fallback и унификации поведения command mode.

## Быстрый старт

1. Клонируйте репозиторий и перейдите в корень проекта.

2. Виртуальное окружение и зависимости:

   ```bash
   python3 -m venv .venv
   # macOS / Linux:
   source .venv/bin/activate
   # Windows (cmd):
   .venv\Scripts\activate.bat
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1

   pip install -r requirements.txt
   ```

3. Секреты провайдеров (облачные STT/LLM). Удобнее задавать их на вкладке **Settings** дашборда — запись в `.env.secrets` в каталоге поддержки (macOS: `~/Library/Application Support/GhostWriter/`, Windows: `%APPDATA%\GhostWriter\`). При разработке можно использовать `.env` в корне репозитория или рядом с `config/config.json`:

   ```bash
   # LLM/STT OpenAI
   OPENAI_API_KEY=sk-...
   # STT Groq
   GROQ_API_KEY=gsk_...
   # STT Deepgram
   DEEPGRAM_API_KEY=...
   ```

4. Запуск:

   ```bash
   python3 main.py
   ```

Конфигурация по умолчанию: **`config/config.json`**. После ручного редактирования JSON можно нажать «Перечитать» в дашборде (или сохранить настройки через Settings) — основной процесс выполнит `RELOAD_CONFIG` и пересоздаст STT/LLM-провайдеры без полного перезапуска.

## Структура репозитория

| Путь | Назначение |
|------|------------|
| `main.py` | Точка входа: `freeze_support()`, режим `spawn`, защита от дочернего процесса, вызов `run_voiceflow_application()`. |
| `app/main_runtime.py` | Сборка пайплайна: конфиг, провайдеры STT/LLM, аудио, вывод, `AppController`, процессы pill и дашборда, хоткеи, трей, сигналы `SIGINT`/`SIGTERM`. |
| `app/core/` | `app_controller`, `audio_engine`, `config_manager`, `provider_factory`, `provider_credentials`, `llm_processor`, `interfaces`, `history_manager`, `journal_manager`, `stats_manager`, `glossary_manager`, `mic_meter_controller`, `hotkey_spec`, `api_selftest`, `logging_config`. |
| `app/providers/` | STT и LLM: `faster_whisper_provider`, `openai_whisper_provider`, `groq_whisper_provider`, `deepgram_transcription_provider`, `openai_llm_provider`, `litellm_llm_provider`. |
| `app/platform/` | Хоткеи, вывод, `paths.py`, macOS/Windows-модули, `single_instance`, `gui_availability`, `audio_devices`. |
| `app/ui/` | Трей, pill, дашборд, IPC статусов. |
| `config/` | `config.json`, глоссарий и связанные файлы. |
| `tests/` | Pytest. |
| `GhostWriter.spec` | PyInstaller: `datas` (config, customtkinter, faster_whisper, `assets/models`), `hiddenimports`, на Darwin — `BUNDLE` → `GhostWriter.app`. |
| `build.py` | Альтернативный сценарий сборки через API PyInstaller + правки `Info.plist` (см. docstring в файле). |

## Разработка и тесты

```bash
source .venv/bin/activate   # или .venv\Scripts\activate на Windows
pytest
```

## Сборка (PyInstaller)

### macOS — каталог + `.app`

Из корня репозитория:

```bash
pyinstaller GhostWriter.spec --clean
```

Артефакты: `dist/GhostWriter/` (COLLECT) и **`dist/GhostWriter.app`** (BUNDLE на Darwin).

В [`GhostWriter.spec`](GhostWriter.spec) через `collect_data_files('faster_whisper')` подтягиваются ресурсы **faster-whisper**, в т.ч. **VAD** (`silero_vad_v6.onnx`). Также в `datas/hiddenimports` включены `litellm`, `tiktoken`, `tiktoken_ext` и fallback-файл `litellm/model_prices_and_context_window_backup.json` для стабильной работы LiteLLM в frozen-сборке.

`Info.plist`: **LSUIElement**, описания для микрофона, Apple Events и универсального доступа. Своя иконка: `icon.icns` в корень и `icon='icon.icns'` в `BUNDLE`.

### Windows — каталог `dist/GhostWriter/`

Та же команда `pyinstaller GhostWriter.spec --clean` на Windows формирует **onedir**-каталог без `.app` (см. комментарий в spec). Запуск: `dist\GhostWriter\GhostWriter.exe` (имя задаётся в `EXE` в spec).

Офлайн-веса: **`stt_local`** в конфиге и **`assets/models/`** — при наличии папки она попадает в `datas`. Подробнее: [assets/models/README.md](assets/models/README.md).

### Один экземпляр

- **macOS / Linux:** неблокирующий `flock` на `single_instance.lock` в `default_app_support_dir`.
- **Windows:** именованный mutex `Local\GhostWriter_<subdir>` (см. `app/platform/single_instance.py`). Тексты ошибок — `app/main_runtime.py`.

### Логи frozen-сборки (`sys.frozen`)

См. `app/core/logging_config.py` (`_frozen_log_file`):

- **macOS:** `~/Library/Logs/GhostWriter/app.log`
- **Windows:** `%APPDATA%\GhostWriter\app.log`
- **прочие Unix:** `~/.ghostwriter/app.log`

Запуск `.app` из терминала для отладки:

```bash
./dist/GhostWriter.app/Contents/MacOS/GhostWriter
```

## Данные на диске

Каталог: **`default_app_support_dir`** в `app/platform/paths.py` (white-label подкаталог по умолчанию `GhostWriter` — при переименовании продукта ищите ту же строку в коде рядом с `support_subdir`).

| Платформа | Типичный путь |
|-----------|----------------|
| macOS | `~/Library/Application Support/GhostWriter/` |
| Windows | `%APPDATA%\GhostWriter\` |
| Linux и прочие Unix | `~/.ghostwriter/` |

Содержимое: `.env.secrets`, `history.db` (если `enable_history`), `stats.json`, на Unix — `single_instance.lock`; на не-macOS frozen — ещё **`app.log`**.

## Устранение неполадок

### Микрофон не записывает

- **macOS (консоль):** микрофон для **Terminal** / IDE. **Собранный .app:** для имени бандла из `Info.plist`.
- **Windows:** **Параметры → Конфиденциальность → Микрофон** для классических приложений.
- Везде: проверьте устройство ввода в ОС и при необходимости `audio_input_device` в `config.json` (`null` — по умолчанию PortAudio).
- Если микрофон сменён через Settings дашборда: примените **Reload configuration** в меню трея (или перезапустите приложение), чтобы основной процесс начал писать с нового устройства.

### Глобальный хоткей не срабатывает

- **macOS:** **Универсальный доступ** и при необходимости **Мониторинг ввода** для того же процесса; для **F8** иногда **Fn+F8**.
- **Windows:** при отсутствии реакции проверьте конфликт с другими хуками и при необходимости запуск от администратора (редко нужно в обычной сессии).

### Проблема с single-instance lock (macOS/Linux)

Если после аварийного завершения приложение сообщает, что второй экземпляр уже запущен:

1. Убедитесь, что процесса GhostWriter действительно нет в системе.
2. Удалите файл блокировки в каталоге данных приложения:
   - macOS: `~/Library/Application Support/GhostWriter/single_instance.lock`
   - Linux: `~/.ghostwriter/single_instance.lock`
3. Запустите приложение повторно.

На Windows используется mutex, поэтому ручное удаление lock-файла обычно не требуется.

### `command not found: compdef` (OpenClaw / zsh)

Относится к **`~/.openclaw/completions/openclaw.zsh`**, не к Ghost Writer.

## Лицензия и вклад

При добавлении лицензии или гайдлайнов для контрибьюторов дополните этот раздел в репозитории.
