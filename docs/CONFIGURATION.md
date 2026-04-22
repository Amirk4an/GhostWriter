# Конфигурация Ghost Writer

Основной конфиг хранится в `config/config.json`. Загрузка и значения по умолчанию для отсутствующих ключей — в `app/core/config_manager.py` (`AppConfig`, метод `_validate`).

## Обязательные поля

В JSON **должны** присутствовать ключи (иначе `ConfigManager` выбросит ошибку при старте):

- `app_name` — имя приложения в UI.
- `primary_color` — основной цвет (hex).
- `hotkey` — хоткей диктовки (например, `f8`); при чтении нормализуется к нижнему регистру, пробелы убираются.
- `system_prompt` — базовый промпт постобработки текста.
- `model_provider` — провайдер LLM (сейчас используется `openai`).
- `whisper_backend` — backend STT: `local` или `openai`.
- `whisper_model` — модель OpenAI Whisper (например, `whisper-1`).
- `local_whisper_model` — локальная модель faster-whisper (`tiny`, `base`, `small`, …) или имя каталога весов при `stt_local.model_source: bundle`.
- `llm_model` — модель LLM (например, `gpt-4o-mini`).
- `llm_enabled` — включить/выключить LLM-постобработку.
- `sample_rate` — частота дискретизации микрофона.
- `channels` — число каналов.
- `chunk_size` — размер аудио-чанка.
- `max_parallel_jobs` — макс. количество задач обработки (в валидации не меньше 1).

## Блок `stt_local` (опционально)

Источник весов и параметры **CTranslate2** для локального faster-whisper:

- `model_source`: `cache` (скачивание в кэш Hugging Face при первом использовании), `bundle` (каталог `assets/models/<local_whisper_model>/` внутри бандла PyInstaller или в корне репозитория при разработке), `custom_path` (абсолютный путь к каталогу весов).
- `custom_model_path` — обязателен при `model_source: custom_path`.
- `device` — например `cpu` (рекомендуется для предсказуемости на macOS).
- `compute_type` — например `int8` или `float16` (подбирается под целевое железо).

Если блок `stt_local` отсутствует или не объект, используются значения по умолчанию: `cache`, пустой путь, `cpu`, `int8`.

## Опциональные поля

- `audio_input_device` — индекс устройства ввода PortAudio (`null` = вход по умолчанию ОС). Индексы на разных машинах различаются: для переносимости чаще оставляют `null` и при необходимости меняют значение вручную в `config.json` после проверки списка устройств в системе или в логах.
- `floating_pill_enabled` — включение плавающего индикатора (по умолчанию `true`, если ключ отсутствует).
- `command_mode_hotkey` — хоткей режима редактирования выделенного текста.
- `command_mode_system_prompt` — отдельный промпт для command mode.
- `app_context_prompts` — словарь промптов по имени приложения (должен быть JSON-объектом).
- `user_glossary_path` — путь к JSON-словарю терминов (по умолчанию `user_glossary.json`).
- `hands_free_enabled` — режим «без рук».
- `short_tap_max_ms` — лимит короткого тапа (не ниже 50 при отсутствии/меньшем значении).
- `latch_arm_window_ms` — окно для latch (не ниже 100).
- `latch_stop_double_down_ms` — таймаут двойного нажатия для остановки (не ниже 100).
- `streaming_stt_enabled` — включение стримингового STT.
- `whisper_mode_boost_input` — усиление тихого входа в whisper-режиме.
- `language` — язык распознавания (`ru`, `en`, …). Особые случаи:
  - если ключа **нет** в JSON, по умолчанию используется **`ru`**;
  - `null`, пустая строка или значения `auto` / `detect` / `multi` (без учёта регистра) трактуются как **автоопределение** (внутри приложения — `None` для провайдера).
- `enable_history` — сохранять историю успешных диктовок в локальную SQLite. По умолчанию `true`; при `false` новые записи не пишутся (уже сохранённые остаются, пока не очистите историю в дашборде).

Пути к БД истории, `stats.json`, `.env.secrets` и файловому lock второго экземпляра задаётся функцией `default_app_support_dir` в `app/platform/paths.py`:

- **macOS:** `~/Library/Application Support/GhostWriter/`
- **Windows:** `%APPDATA%\GhostWriter\` (обычно `C:\Users\<user>\AppData\Roaming\GhostWriter\`)
- **прочие Unix:** `~/.ghostwriter/` (имя каталога из `support_subdir`, по умолчанию `GhostWriter` → `.ghostwriter`).

На Windows второй экземпляр блокируется **именованным mutex** в сессии пользователя (не отдельным файлом); сообщение в консоли при отказе см. в `main_runtime.py`.

### Command mode (редактирование выделения)

Чтение выделенного текста в активном поле реализовано через **Accessibility API только на macOS** (`macos_ax_selection.py`). На **Windows и Linux** `get_focused_selected_text` возвращает `None`, поэтому command mode там **пока недоступен**, пока не будет отдельной реализации (например UI Automation на Windows).

### Системный трей

На macOS по умолчанию используется **rumps** (нативное меню); при недоступности и на **Windows** — **pystray** (контекстное меню по правому клику на иконку в области уведомлений).

### Глобальные хоткеи (Windows)

Слушатель строится на **pynput**. На Windows при отсутствии срабатывания проверьте, не требуется ли запуск от имени администратора для низкоуровневого перехвата в отдельных средах; в типичной пользовательской сессии права обычно достаточны.

## Пример

```json
{
  "app_name": "Ghost Writer",
  "primary_color": "#2A5BCC",
  "hotkey": "f8",
  "command_mode_hotkey": "",
  "floating_pill_enabled": true,
  "hands_free_enabled": true,
  "short_tap_max_ms": 220,
  "latch_arm_window_ms": 450,
  "latch_stop_double_down_ms": 450,
  "streaming_stt_enabled": true,
  "whisper_mode_boost_input": false,
  "system_prompt": "Ты — профессиональный редактор...",
  "command_mode_system_prompt": "Ты редактируешь выделенный текст...",
  "app_context_prompts": {
    "Slack": "Стиль: неформальный, короткие фразы, как в чате."
  },
  "user_glossary_path": "user_glossary.json",
  "model_provider": "openai",
  "whisper_backend": "local",
  "whisper_model": "whisper-1",
  "local_whisper_model": "small",
  "stt_local": {
    "model_source": "cache",
    "custom_model_path": "",
    "device": "cpu",
    "compute_type": "int8"
  },
  "llm_model": "gpt-4o-mini",
  "llm_enabled": false,
  "sample_rate": 16000,
  "channels": 1,
  "chunk_size": 1024,
  "language": "ru",
  "max_parallel_jobs": 1,
  "audio_input_device": null,
  "enable_history": true
}
```

## Диагностика микрофона

1. Откройте **Системные настройки → Конфиденциальность и безопасность → Микрофон** и включите доступ для **Terminal** (или IDE), из которой запущен `python3 main.py`.
2. В `config/config.json` для `audio_input_device` задайте осмысленный индекс или `null` (см. выше про индексы PortAudio).
3. В логах при остановке записи пишутся оценки `peak` / `rms` — по ним видно, был ли ненулевой сигнал.

## Переменные окружения и API-ключ

Приоритет чтения `OPENAI_API_KEY` (и других секретов через `ConfigManager`):

1. Файл **`.env.secrets`** в каталоге поддержки приложения (см. раздел про пути выше: на Windows — под `%APPDATA%\GhostWriter\`, на macOS — `~/Library/Application Support/GhostWriter/`). Туда же пишет вкладка **Settings** дашборда.
2. Локальный **`.env`** рядом с `config.json` или в текущем каталоге (удобно при разработке).
3. Переменные окружения процесса.

В `.env` при разработке обычно достаточно:

- `OPENAI_API_KEY=...` — для облачных режимов OpenAI (STT/LLM).

Дополнительно (не в `.env` обязательно, можно задать в `launchd`/shell):

- `GHOSTWRITER_HEADLESS=1` — не поднимать окна Tk/CustomTkinter (дашборд, pill на Tk). Нужно для **cron**, **launchd без Aqua** и других фоновых процессов без доступа к оконному серверу; иначе возможен `Tcl_Panic` в `TkpInit`. В этом режиме pill отключается, дашборд не стартует из рантайма.

## Рекомендации по настройке

- Для слабых машин используйте меньшую локальную модель (`tiny`/`base`).
- Если используете OpenAI STT/LLM, проверьте доступ к сети и валидность API-ключа.
- После изменения `config/config.json` перезапустите приложение.
