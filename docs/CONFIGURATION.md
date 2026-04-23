# Конфигурация Ghost Writer

Файл по умолчанию: **`config/config.json`**. Источник истины для обязательных ключей и значений по умолчанию — **`app/core/config_manager.py`** (`AppConfig`, метод `_validate`).

См. также: [ARCHITECTURE.md](ARCHITECTURE.md) · [../README.md](../README.md)

## Обязательные поля JSON

При отсутствии любого из перечисленных ключей старт приложения завершится ошибкой валидации:

| Ключ | Описание |
|------|-----------|
| `app_name` | Имя в UI и трее (white-label). |
| `primary_color` | HEX цвета для pill/дашборда. |
| `hotkey` | Хоткей диктовки (например `f8`); нормализация: нижний регистр, без пробелов. |
| `system_prompt` | Базовый промпт LLM-постобработки. |
| `model_provider` | Сейчас ожидается `openai` (нижний регистр при чтении). |
| `whisper_backend` | `local` или `openai`. |
| `whisper_model` | Имя модели API (например `whisper-1`). |
| `local_whisper_model` | Имя модели/каталога для faster-whisper. |
| `llm_model` | Идентификатор модели чата OpenAI. |
| `llm_enabled` | `true` / `false` — включать ли постобработку LLM. |
| `sample_rate` | Гц, обычно `16000`. |
| `channels` | Чаще `1` (моно). |
| `chunk_size` | Размер чанка записи (сэмплы). |
| `max_parallel_jobs` | ≥ 1 после валидации. |

## Блок `stt_local` (опционально)

Параметры локального **faster-whisper** (CTranslate2):

| Поле | Значения |
|------|-----------|
| `model_source` | `cache` — HF-кэш; `bundle` — `assets/models/<local_whisper_model>/`; `custom_path` — свой каталог. |
| `custom_model_path` | Обязателен при `custom_path`. |
| `device` | Например `cpu`, `cuda` (зависит от сборки CTranslate2). |
| `compute_type` | Например `int8`, `float16`. |

Если блок отсутствует или не объект — по умолчанию: `cache`, пустой путь, `cpu`, `int8`.

## Опциональные поля

| Ключ | По умолчанию / заметки |
|------|-------------------------|
| `audio_input_device` | `null` — устройство по умолчанию PortAudio; иначе целый индекс. |
| `floating_pill_enabled` | `true` |
| `command_mode_hotkey` | `""` — command mode выключен, если пусто. |
| `journal_hotkey` | `""` — отдельный хоткей дневника выключен. Формат как у `hotkey` / `command_mode_hotkey`. Некорректная строка приводит к отключению с предупреждением в логе. |
| `journal_system_prompt` | Системный промпт для JSON-ответа LLM (`title`, `tags`, `advice`, `refined_text`); см. значение по умолчанию в `AppConfig`. |
| `command_mode_system_prompt` | Текст по умолчанию в `AppConfig` в коде. |
| `app_context_prompts` | `{}` или объект; ключи — подстроки/имена приложений с macOS. |
| `user_glossary_path` | `user_glossary.json` |
| `hands_free_enabled` | `true` |
| `short_tap_max_ms` | `220`, минимум `50` |
| `latch_arm_window_ms` | `450`, минимум `100` |
| `latch_stop_double_down_ms` | `450`, минимум `100` |
| `streaming_stt_enabled` | `false` |
| `whisper_mode_boost_input` | `false` |
| `language` | Если ключа нет — **`ru`**. `null`, `""`, `auto`, `detect`, `multi` → автоопределение (`None` для STT). |
| `enable_history` | `true` |

## Пути данных и секретов

Функция **`default_app_support_dir`** в `app/platform/paths.py`:

- **macOS:** `~/Library/Application Support/GhostWriter/`
- **Windows:** `%APPDATA%\GhostWriter\`
- **прочие Unix:** `~/.ghostwriter/` (имя из `support_subdir`: `GhostWriter` → `.ghostwriter`)

Там же лежат **`history.db`** (таблицы `dictations` и **`journal_entries`** для дневника), **`stats.json`**, **`.env.secrets`**, на Unix — **`single_instance.lock`**. На Windows второй экземпляр блокируется **mutex**, не файлом.

### White-label

Имя подкаталога **`GhostWriter`** в коде передаётся как `support_subdir` в менеджеры путей и single-instance. Для полного переименования продукта нужно согласованно заменить эту строку в **`paths.py`**, **`single_instance.py`**, **`logging_config.py`** (подкаталог логов на macOS) и при необходимости в `GhostWriter.spec` / `Info.plist`.

## Поведение на разных ОС

### Command mode (редактирование выделения по голосу)

Чтение выделения — **только macOS** (`macos_ax_selection.py`). На Windows и Linux command mode **недоступен**, пока не реализованы нативные аналоги.

### Трей

**rumps** на macOS при успешном импорте; иначе **pystray** (в т.ч. Windows).

### Глобальные хоткеи (Windows)

**pynput**; при проблемах см. раздел «Рекомендации» в [../README.md](../README.md#устранение-неполадок).

## Пример `config.json`

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

1. **macOS:** **Конфиденциальность → Микрофон** для терминала/IDE или для бандла приложения.
2. **Windows 10/11:** **Параметры → Конфиденциальность и безопасность → Микрофон**.
3. **`audio_input_device`** в JSON — индекс PortAudio или `null`.
4. В логах после записи смотрите **`peak`** / **`rms`**.

## Переменные окружения

### Приоритет `OPENAI_API_KEY`

1. `.env.secrets` в каталоге поддержки приложения.
2. `.env` рядом с `config.json` или в текущей рабочей директории.
3. Переменные окружения процесса.

### Прочее

| Переменная | Назначение |
|------------|------------|
| `GHOSTWRITER_HEADLESS=1` | Не поднимать Tk/CustomTkinter (pill, дашборд из рантайма). Для cron/launchd без дисплея. |

## Рекомендации

- Слабое железо — модели `tiny` / `base`.
- OpenAI-режимы — сеть и валидный ключ.
- После правок **`config.json`** перезапустите процесс приложения.
