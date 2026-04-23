# Архитектура Ghost Writer

Документ описывает поток данных и основные модули. Детали ключей конфигурации — в [CONFIGURATION.md](CONFIGURATION.md).

## Точка входа и процессы

1. **`main.py`** — только инициализация `multiprocessing`: `freeze_support()`, `set_start_method("spawn", force=True)`, проверка `multiprocessing.parent_process()` (дочерние процессы сразу выходят без импорта тяжёлого стека), затем `run_voiceflow_application()` из `app/main_runtime.py`.

2. **`app/main_runtime.run_voiceflow_application`** — единственное место сборки зависимостей рантайма: `ConfigManager`, фабрика провайдеров, `AudioEngine`, `ClipboardOutputController`, `AppController`, опционально очереди pill, поток обработки `pill_command_queue`, `PynputHotkeyListener`, `TrayApplication`, обработчики `SIGINT`/`SIGTERM`, корректное завершение дочерних `Process`.

3. **Корень файлов приложения** — в `main_runtime._project_root_dir()`: при `sys.frozen` и `sys._MEIPASS` (PyInstaller) конфиг и ресурсы читаются из распакованного бандла; иначе — родительский каталог относительно `app/main_runtime.py` (корень репозитория при разработке).

## Обзор пайплайна диктовки

1. Пользователь нажимает глобальный хоткей (**pynput**, `PynputHotkeyListener`).
2. **`AudioEngine`** записывает PCM в буфер и при необходимости формирует WAV для STT.
3. **STT-провайдер** (`FasterWhisperProvider` или `OpenAIWhisperProvider` через `ProviderFactory`) выполняет транскрипцию (в т.ч. стриминг при включённой опции в конфиге).
4. **`LLMProcessor`** при `llm_enabled` применяет system prompt (контекст активного приложения из `macos_focus` / глоссарий / `app_context_prompts`).
5. **`ClipboardOutputController`** вставляет результат: на **macOS** — буфер обмена + AppleScript/System Events и pynput; на **Windows** — pyperclip + поднятие переднего окна (`windows/focus.py`) + Ctrl+V; на прочих ОС — по возможности аналогично без AppleScript.
6. При успехе опционально **`HistoryManager`** (SQLite) и **`StatsManager`** (JSON).
7. **`StatusBridge`** публикует коды статуса в трей и при наличии — в очередь pill.
8. **`pill_command_queue`**: команда `open_dashboard` в отдельном потоке приводит к **`multiprocessing.Process(target=run_dashboard_process, args=(config_json_path, focus_queue))`**. Дочерний процесс **не** импортирует корневой `main` — это важно для собранного `.app`, где повторный запуск бинарника через `subprocess` поднял бы второе ядро.

## Компоненты `app/core`

| Модуль | Назначение |
|--------|------------|
| `app_controller.py` | Жизненный цикл диктовки, hands-free/latch, command mode, reload конфига, связь со статусами и менеджерами истории/статистики. |
| `audio_engine.py` | Захват с `sounddevice`, чанки, WAV, метрики `peak`/`rms` в логах. |
| `config_manager.py` | JSON-конфиг, валидация, секреты, `patch_audio_input_device`, `patch_enable_history`. |
| `provider_factory.py` | Создание STT/LLM по `AppConfig`. |
| `llm_processor.py` | Вызов LLM с промптами. |
| `interfaces.py` | Абстракции провайдеров и вывода. |
| `history_manager.py` | SQLite, WAL, лимит записей. |
| `stats_manager.py` | `stats.json`, оценка «сэкономленного времени». |
| `glossary_manager.py` | Пользовательский JSON-глоссарий. |
| `mic_meter_controller.py` | Логика метра/индикации микрофона для UI. |
| `hotkey_spec.py` | Парсинг строк хоткеев. |
| `logging_config.py` | `setup_logging()`: stderr + файл при `sys.frozen`. |

## Компоненты `app/providers`

- **`faster_whisper_provider.py`** — локальный inference, VAD из пакета, опционально streaming.
- **`openai_whisper_provider.py`** — API транскрипции.
- **`openai_llm_provider.py`** — чат-комплишены OpenAI.

## Компоненты `app/platform`

| Модуль | Назначение |
|--------|------------|
| `paths.py` | `default_app_support_dir`, `single_instance_hint_path` — единая база путей данных. |
| `hotkey_listener.py` | Слушатель pynput для диктовки и command mode. |
| `output_controller.py` | Вставка текста, платформенные ветки. |
| `single_instance.py` | Unix: `flock` на lock-файле; Windows: `CreateMutexW`. |
| `gui_availability.py` | `GHOSTWRITER_HEADLESS`, предупреждения про окружение. |
| `audio_devices.py` | Список устройств PortAudio. |
| `macos_*.py` | Фокус, AX selection, accessibility-подсказки. |
| `windows/focus.py` | Восстановление HWND переднего окна перед Ctrl+V. |
| `windows/ctk_window_policy.py` | Поведение окна дашборда (toolwindow и т.п.). |

## Компоненты `app/ui`

- **`tray_app.py`** — macOS: **rumps** при успешном импорте; иначе **pystray**; окна на **CustomTkinter**.
- **`floating_pill.py`**, **`floating_pill_native.py`** — процесс pill и варианты UI.
- **`pill_ipc.py`**, **`pill_process_entry.py`** — IPC и точка входа `Process` для pill.
- **`dashboard_process.py`**, **`main_dashboard.py`**, **`dashboard_child_main.py`** — дашборд в отдельном процессе.
- **`status_bridge.py`** — унификация статусов для трея и pill.
- **`ctk_macos_theme.py`**, **`macos_ctk_dock.py`** — внешний вид под macOS.

## Конфигурация и секреты

- Файл: **`config/config.json`** (в бандле копируется через `GhostWriter.spec`).
- Секреты: `.env.secrets` в каталоге поддержки + слой `.env` и `os.environ` — см. `ConfigManager`.
- Подробности полей: [CONFIGURATION.md](CONFIGURATION.md).

## Сборка

- Спецификация: **`GhostWriter.spec`** в корне (комментарии внутри файла про `SPECPATH`, `BUNDLE` только на Darwin).
- Скрипт: **`build.py`** — альтернативный путь вызова PyInstaller с постобработкой plist на macOS.

Общий чеклист для разработчика — в [../README.md](../README.md#сборка-pyinstaller).
