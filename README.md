# Ghost Writer (VoiceFlow WL)

Диктовка с глобальным хоткеем: запись с микрофона → STT (локальный **faster-whisper** или **OpenAI Whisper**) → опциональная постобработка через LLM → вставка текста в активное приложение. Запуск из консоли: `python3 main.py` (на macOS команды `python` часто нет в `PATH`). В трее — статус и меню; опционально плавающий индикатор (pill) и отдельный **Dashboard** (история, статистика, ключ API).

Подробности: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), все ключи конфига: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Требования

- **macOS** — основная целевая платформа (TCC, вставка через AppleScript/System Events, трей через **rumps** при наличии).
- **Windows** — поддерживается на уровне путей (`%APPDATA%\GhostWriter\`), single-instance mutex, трей **pystray**, вставка **Ctrl+V** и поднятие переднего окна (`app/platform/windows/`). Глобальные хоткеи — **pynput**; command mode чтения выделения пока только на macOS (см. `docs/CONFIGURATION.md`).
- **Python 3.9+** (в репозитории удобно держать виртуальное окружение `.venv` в корне).

Каталог пользовательских данных (история, статистика, `.env.secrets`, лог собранного приложения на Windows/Linux) задаётся в `app/platform/paths.py` (`default_app_support_dir`).

### Автовставка

- **macOS (Cmd+V):** чтобы система разрешила программную вставку (**pynput** / System Events), в **Системные настройки → Конфиденциальность и безопасность → Универсальный доступ** включите переключатель для **того же приложения**, из которого запущен Ghost Writer (часто **Terminal**, **Cursor**, **iTerm** или интерпретатор **Python**). При ошибке автоматизации (**1002**) может понадобиться разрешить управление **System Events**. Если текст в поле не попал — он уже в буфере обмена, нажмите **Cmd+V** вручную.
- **Windows (Ctrl+V):** перед вставкой поднимается переднее окно (`app/platform/windows/focus.py`). При сбоях проверьте, что целевое приложение допускает вставку из буфера; текст дублируется через **pyperclip** так же, как на macOS.

## Быстрый старт

1. Клонируйте репозиторий и перейдите в корень проекта.

2. Зависимости Python:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Секреты для OpenAI (если используете облачные STT/LLM). Удобнее всего задать ключ на вкладке **Settings** дашборда — файл `.env.secrets` окажется в каталоге поддержки приложения (на macOS: `~/Library/Application Support/GhostWriter/`, на Windows: `%APPDATA%\GhostWriter\`). При разработке можно положить `.env` в корень репозитория или рядом с `config/config.json`:

   ```bash
   OPENAI_API_KEY=sk-...
   ```

4. Запуск:

   ```bash
   source .venv/bin/activate
   python3 main.py
   ```

Конфигурация: `config/config.json`. После ручного редактирования JSON перезапустите приложение (часть полей дашборд может менять сам — см. код `ConfigManager`).

## Структура репозитория

| Путь | Назначение |
|------|------------|
| `main.py` | Точка входа: `multiprocessing.freeze_support()`, режим `spawn`, вызов `run_voiceflow_application()`. |
| `app/main_runtime.py` | Сборка пайплайна: конфиг, провайдеры STT/LLM, аудио, вывод, `AppController`, дочерние процессы pill и дашборда, хоткеи, трей, обработка сигналов. |
| `app/core/` | Оркестратор (`app_controller`), аудио, конфиг, фабрика провайдеров, LLM, интерфейсы, **история** (`history_manager`), **статистика** (`stats_manager`), глоссарий, логирование. |
| `app/providers/` | Реализации STT и LLM (faster-whisper, OpenAI). |
| `app/platform/` | Глобальные клавиши, вывод в систему, `paths.py` (каталог данных), интеграции ОС, один экземпляр: `flock` на Unix или именованный mutex на Windows (`single_instance.py`). |
| `app/ui/` | Трей, pill, дашборд (отдельные процессы), мост статусов. |
| `config/` | `config.json`, пользовательский глоссарий и связанные данные. |
| `tests/` | Pytest. |
| `GhostWriter.spec` | Сборка PyInstaller (данные faster-whisper/VAD, `assets/models` и т.д.). |

## Разработка и тесты

```bash
source .venv/bin/activate
pytest
```

## Сборка .app (PyInstaller)

Сборка из корня репозитория (после `pip install -r requirements.txt` и установки `pyinstaller`):

```bash
pyinstaller GhostWriter.spec --clean
```

В [`GhostWriter.spec`](GhostWriter.spec) в `Analysis(..., datas=...)` через `collect_data_files('faster_whisper')` подключаются ресурсы **faster-whisper**, в том числе **VAD** (`silero_vad_v6.onnx`). Без этого локальный STT с `vad_filter=True` в собранном `.app` падает с `NoSuchFile` для ONNX.

В `BUNDLE` заданы ключи `Info.plist`: **LSUIElement** (основное приложение без иконки в Dock), описания для **микрофона**, **Apple Events** и **универсального доступа** (запросы TCC). Иконка бандла: положите `icon.icns` в корень и укажите `icon='icon.icns'` в `BUNDLE`, если нужна своя иконка.

Офлайн-веса faster-whisper: блок **`stt_local`** в `config.json` (см. [docs/CONFIGURATION.md](docs/CONFIGURATION.md)) и каталог **`assets/models/`** — при сборке, если папка есть, она попадает в `datas`. Подробности в [assets/models/README.md](assets/models/README.md).

Второй экземпляр блокируется так: на **macOS / Linux** — неблокирующий **`flock`** на файле `single_instance.lock` в каталоге данных (`default_app_support_dir`, см. `app/platform/paths.py`); на **Windows** — именованный **mutex** в сессии пользователя (`Local\\GhostWriter_<subdir>`). Сообщения в stderr при отказе — в `app/main_runtime.py`.

### Логи собранного приложения

При запуске из **PyInstaller** (`sys.frozen`) логи дублируются в файл на диске (см. `app/core/logging_config.py`):

- **macOS:** `~/Library/Logs/GhostWriter/app.log`
- **Windows и прочие:** `%APPDATA%\GhostWriter\app.log` (или `~/.ghostwriter/app.log` на Unix без отдельного каталога Logs — как в `_frozen_log_file()`)

Удобно для отладки windowed-сборки, когда stderr недоступен. Запуск бинарника из терминала даёт тот же вывод в консоль:

```bash
./dist/GhostWriter.app/Contents/MacOS/GhostWriter
```

## Данные на диске

Каталог задаётся **`default_app_support_dir`** в `app/platform/paths.py` (параметр white-label `support_subdir`, по умолчанию `GhostWriter`):

| Платформа | Типичный путь |
|-----------|----------------|
| macOS | `~/Library/Application Support/GhostWriter/` |
| Windows | `%APPDATA%\GhostWriter\` |
| Linux и прочие Unix | `~/.ghostwriter/` |

В нём обычно лежат:

- `.env.secrets` — ключи API (запись из дашборда);
- `history.db` — локальная история диктовок (SQLite), если `enable_history` в конфиге;
- `stats.json` — агрегированная статистика для дашборда;
- `single_instance.lock` — файловый lock второго экземпляра (Unix; на Windows эксклюзивность — через mutex, не через этот файл);
- при **frozen**-сборке на не-macOS — также **`app.log`** рядом с данными (см. выше).

## Устранение неполадок

### Микрофон не записывает

В режиме **консоли** (`python3 main.py`): на **macOS** в **Конфиденциальность и безопасность → Микрофон** включите доступ для **Terminal** (или IDE), из которой запущен процесс. На **Windows 10/11** — **Параметры → Конфиденциальность → Микрофон** для классических и UWP-приложений.

В режиме **собранного .app** (macOS): разрешите микрофон для **GhostWriter** (или имени вашего бандла) — запрос текста подставляется из `Info.plist` при сборке. Проверьте **Звук → Ввод** и при необходимости поле `audio_input_device` в `config.json` (индекс устройства PortAudio; `null` — устройство по умолчанию).

### Глобальный хоткей не срабатывает

Нужны **Универсальный доступ** и при необходимости **Мониторинг ввода** для того же процесса: при запуске из терминала — для **Terminal** / **Python**; при запуске **.app** — для приложения из бандла. На клавиатурах Mac для **F8** иногда нужно **Fn+F8**.

### `command not found: compdef` при входе в shell (OpenClaw)

Сообщение относится к **`~/.openclaw/completions/openclaw.zsh`**: в конце файла вызывается `compdef`, которая доступна только после инициализации completions в Zsh. Это не ошибка Ghost Writer.

## Лицензия и вклад

При добавлении лицензии или гайдлайнов для контрибьюторов дополните этот раздел в репозитории.
