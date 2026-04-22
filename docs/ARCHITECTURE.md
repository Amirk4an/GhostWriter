# Архитектура Ghost Writer

## Обзор пайплайна

Ghost Writer работает как конвейер:

1. Пользователь нажимает глобальный хоткей (**pynput**).
2. `AudioEngine` записывает аудио.
3. STT-провайдер делает транскрипцию.
4. `LLMProcessor` (если включён) редактирует/чистит текст.
5. `OutputController` вставляет текст в активное приложение: на macOS — буфер обмена + AppleScript/System Events и pynput; на Windows и прочих ОС — `pyperclip` + Ctrl+V через pynput (на Windows перед вставкой вызывается восстановление переднего окна через `user32`, см. `app/platform/windows/focus.py`).
6. При успешной диктовке опционально пишутся **история** (`HistoryManager` → SQLite) и **статистика** (`StatsManager` → JSON).
7. `StatusBridge` публикует статусы в трей и опционально в плавающий pill (`multiprocessing.Queue`).
8. Вторая очередь **`pill_command_queue`** передаётся в процесс pill: команды (например `open_dashboard`) читаются лёгким потоком в основном процессе и приводят к запуску **отдельного процесса** дашборда: `multiprocessing.Process(target=dashboard_process.run_dashboard_process, args=(path_to_config.json, focus_queue))` — только `dashboard_process` + `main_dashboard` (без повторного импорта `main`; важно для собранного `.app`, где `subprocess` + `sys.executable` снова запускали бы ядро).

Точка входа процесса: **`main.py`** (тонкая оболочка: `spawn`, `freeze_support`). Вся сборка приложения — **`app/main_runtime.run_voiceflow_application`**.

## Компоненты

### `app/core`

- `app_controller.py` — оркестратор жизненного цикла диктовки, command mode, hands-free/latch, взаимодействие со статусами.
- `audio_engine.py` — микрофон, буфер, WAV для STT, оценка уровня сигнала.
- `config_manager.py` — загрузка/валидация `config/config.json`, слой секретов (`.env.secrets`, `.env`, окружение), точечные патчи из UI (`audio_input_device`, `enable_history`).
- `provider_factory.py` — сборка STT/LLM-провайдеров из конфига.
- `llm_processor.py` — system prompt и постобработка текста.
- `interfaces.py` — контракты провайдеров и адаптеров вывода.
- `history_manager.py` — SQLite-история диктовок (дашборд читает в режиме WAL).
- `stats_manager.py` — локальный `stats.json` (сессии, слова, оценка «сэкономленного времени»).
- `glossary_manager.py` — пользовательский глоссарий из JSON.
- `mic_meter_controller.py` — вспомогательная логика для индикации/метра микрофона в UI.
- `hotkey_spec.py` — разбор и нормализация спецификаций хоткеев.
- `logging_config.py` — `setup_logging()`: stderr + при `sys.frozen` файл лога (на macOS — `~/Library/Logs/GhostWriter/app.log`, на Windows и прочих — рядом с пользовательскими данными, см. `_frozen_log_file`).

### `app/providers`

- `faster_whisper_provider.py` — локальная транскрипция (в т.ч. стриминг, VAD по конфигу).
- `openai_whisper_provider.py` — транскрипция через OpenAI API.
- `openai_llm_provider.py` — LLM через OpenAI API.

### `app/platform`

- `hotkey_listener.py` — глобальные клавиши (диктовка и command mode).
- `output_controller.py` — вставка текста через буфер обмена и эмуляцию ввода.
- `paths.py` — единый каталог пользовательских данных (`default_app_support_dir`: macOS Application Support, Windows `%APPDATA%`, прочие — `~/.ghostwriter` и т.д.).
- `windows/` — опциональные вызовы только на `win32`: фокус перед вставкой (`focus.py`), политика окна дашборда (`ctk_window_policy.py`, `WS_EX_TOOLWINDOW`).
- `macos_focus.py`, `macos_ax_selection.py`, `macos_accessibility.py` — интеграции macOS (фокус, выделение, подсказки по TCC).
- `single_instance.py` — второй экземпляр: на Unix — неблокирующий `flock` на файле в каталоге поддержки; на Windows — именованный mutex (`CreateMutexW`).
- `gui_availability.py` — проверки окружения (в т.ч. `GHOSTWRITER_HEADLESS`, предупреждения про Apple CLT Python).
- `audio_devices.py` — перечисление/утилиты устройств ввода PortAudio.

### `app/ui`

- `tray_app.py` — иконка в трее и окно настроек: на **macOS** при успешном импорте — **rumps** (NSMenu), иначе и на других ОС — **pystray**; окна — **CustomTkinter**.
- `floating_pill.py` / `floating_pill_native.py` — плавающий индикатор статуса (процесс pill) и варианты отрисовки.
- `pill_ipc.py` — формат команд pill → основной процесс.
- `pill_process_entry.py` — точка входа `Process` для pill (без импорта `main`).
- `dashboard_child_main.py` (CLI-точка) / `dashboard_process.py` / `main_dashboard.py` — дашборд в отдельном `Process`; путь к `config.json` и очередь фокуса передаются аргументами.
- `status_bridge.py` — единый шлюз статусов в pill.
- `ctk_macos_theme.py`, `macos_ctk_dock.py` — оформление CustomTkinter под macOS.

## Потоки и процессы

- Основной процесс Python обслуживает hotkey, STT, LLM и вывод.
- При `floating_pill_enabled` и отсутствии headless-режима запускается дочерний `multiprocessing.Process` для отрисовки pill.
- Дашборд (кнопка на pill или пункт **Dashboard** в меню трея) запускается `multiprocessing.Process` с `target=run_dashboard_process`; если процесс уже жив, в очередь может уйти команда поднять окно (`DASHBOARD_FOCUS_RAISE`).

## Конфигурация и секреты

- Runtime-конфиг: `config/config.json`.
- Секреты: пользовательский `.env.secrets` в каталоге поддержки приложения (на macOS см. `ConfigManager`), при разработке — локальный `.env` или окружение; минимум `OPENAI_API_KEY` для OpenAI-режимов.
- Подробно: `docs/CONFIGURATION.md`.
