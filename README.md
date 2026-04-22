# Ghost Writer (VoiceFlow WL)

Диктовка с глобальным хоткеем: запись с микрофона → STT (локальный **faster-whisper** или **OpenAI Whisper**) → опциональная постобработка через LLM → вставка текста в активное приложение. Запуск из консоли: `python3 main.py` (на macOS команды `python` часто нет в `PATH`). В трее — статус и меню; опционально плавающий индикатор (pill) и отдельный **Dashboard** (история, статистика, ключ API).

Подробности: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), все ключи конфига: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Требования

- **Целевая платформа — macOS** (TCC для микрофона и универсального доступа, вставка через AppleScript/System Events, меню трея через **rumps** при наличии).
- **Python 3.9+** (в репозитории удобно держать виртуальное окружение `.venv` в корне).

Часть путей к данным пользователя (история, статистика, `.env.secrets`) на несистемах Darwin повторяет логику «каталог в домашней папке» (`~/.ghostwriter/` и т.п. — см. `ConfigManager` / `HistoryManager`), но сборка и UX ориентированы на macOS.

### Автовставка (Cmd+V)

Чтобы macOS разрешила программную вставку (**pynput** / System Events), в **Системные настройки → Конфиденциальность и безопасность → Универсальный доступ** включите переключатель для **того же приложения**, из которого вы запускаете Ghost Writer (часто **Terminal**, **Cursor**, **iTerm** или интерпретатор **Python**). При ошибке автоматизации (**1002**) может понадобиться разрешить управление **System Events**. Если текст в поле не попал — он уже в буфере обмена, нажмите **Cmd+V** вручную.

## Быстрый старт

1. Клонируйте репозиторий и перейдите в корень проекта.

2. Зависимости Python:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Секреты для OpenAI (если используете облачные STT/LLM). Удобнее всего задать ключ на вкладке **Settings** дашборда — значение попадает в `~/Library/Application Support/GhostWriter/.env.secrets` на macOS. При разработке можно положить `.env` в корень репозитория или рядом с `config/config.json`:

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
| `app/platform/` | Глобальные клавиши, вывод в систему, macOS-интеграции, single-instance lock (где доступен `fcntl`). |
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

Второй экземпляр на **не-Windows** платформах с **`fcntl`** блокируется **single-instance lock**: файл `~/Library/Application Support/GhostWriter/single_instance.lock` (тот же подкаталог, что и для истории на macOS; путь в коде задан в стиле macOS и на других Unix создаётся так же — см. `app/platform/single_instance.py`). На **Windows** захват lock в коде пропускается (`try_acquire_single_instance_lock` сразу возвращает успех).

### Логи собранного приложения

При запуске из **PyInstaller** (`sys.frozen`) логи дублируются в файл:

`~/Library/Logs/GhostWriter/app.log`

Удобно для отладки двойным кликом по `.app`, когда stderr недоступен. Запуск бинарника из терминала даёт тот же вывод в консоль:

```bash
./dist/GhostWriter.app/Contents/MacOS/GhostWriter
```

## Данные на диске (macOS)

В каталоге **`~/Library/Application Support/GhostWriter/`** (имя white-label можно менять в коде констант `support_subdir`) обычно лежат:

- `.env.secrets` — ключи API (запись из дашборда);
- `history.db` — локальная история диктовок (SQLite), если `enable_history` в конфиге;
- `stats.json` — агрегированная статистика для дашборда;
- `single_instance.lock` — lock второго экземпляра.

## Устранение неполадок

### Микрофон не записывает

В режиме **консоли** (`python3 main.py`): на macOS в **Конфиденциальность и безопасность → Микрофон** включите доступ для **Terminal** (или IDE), из которой запущен процесс.

В режиме **собранного .app**: разрешите микрофон для **GhostWriter** (или имени вашего бандла) в том же разделе настроек — запрос текста подставляется из `Info.plist` при сборке. Проверьте **Звук → Ввод** и при необходимости поле `audio_input_device` в `config.json` (индекс устройства PortAudio; `null` — устройство по умолчанию).

### Глобальный хоткей не срабатывает

Нужны **Универсальный доступ** и при необходимости **Мониторинг ввода** для того же процесса: при запуске из терминала — для **Terminal** / **Python**; при запуске **.app** — для приложения из бандла. На клавиатурах Mac для **F8** иногда нужно **Fn+F8**.

### `command not found: compdef` при входе в shell (OpenClaw)

Сообщение относится к **`~/.openclaw/completions/openclaw.zsh`**: в конце файла вызывается `compdef`, которая доступна только после инициализации completions в Zsh. Это не ошибка Ghost Writer.

## Лицензия и вклад

При добавлении лицензии или гайдлайнов для контрибьюторов дополните этот раздел в репозитории.
