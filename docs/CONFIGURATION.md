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
| `model_provider` | `openai` — нативный OpenAI SDK; иначе LLM через **LiteLLM** (`groq`, `anthropic`, `gemini`, `google`, `openrouter`, `ollama`, `mistral`, `cohere` — нижний регистр). |
| `whisper_backend` | `local` (faster-whisper), `openai`, `groq`, `deepgram`. |
| `whisper_model` | Имя модели API: `whisper-1` (OpenAI), `whisper-large-v3-turbo` (Groq), `nova-2` (Deepgram) и т.д. |
| `local_whisper_model` | Имя модели/каталога для faster-whisper. |
| `llm_model` | Для `openai` — имя модели чата (например `gpt-4o-mini`). Для LiteLLM — короткое имя модели **без** префикса провайдера (например `llama-3.1-8b-instant` для `groq`) или полный идентификатор с `/` (например `openai/gpt-4o-mini` для OpenRouter). Внутри `LiteLLMLLMProvider` короткое имя преобразуется в `<provider>/<model>`, при `model_provider=google` используется префикс `gemini`. |
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
| `journal_system_prompt` | Дефолт: `Пользователь диктует мысль для личного дневника. Верни один JSON-объект с ключами: "title" (краткий заголовок), "tags" (массив из 2–3 коротких строк-тегов для сортировки), "advice" (короткий совет или инсайт по теме), "refined_text" (исправленная от опечаток оригинальная мысль, без добавления новых фактов). Только JSON, без markdown и пояснений.` |
| `command_mode_system_prompt` | Дефолт: `Ты редактируешь выделенный текст по голосовой команде пользователя. Верни только итоговый текст, который должен заменить выделение целиком, без пояснений и кавычек.` |
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

План по кроссплатформенности и этапы Windows-реализации описаны в [`../README.md`](../README.md) в разделе `Known Limitations / Roadmap`.

## user_glossary.json

Путь задаётся ключом `user_glossary_path` (по умолчанию `user_glossary.json`).
Загрузчик (`app/core/glossary_manager.py`) поддерживает 3 формата:

1. JSON-объект `{"исходный_термин": "замена"}`.
2. Массив пар: `[["исходный_термин", "замена"]]`.
3. Массив объектов: `[{"from": "исходный_термин", "to": "замена"}]`.

Минимальный валидный пример:

```json
{
  "GPT чат": "ChatGPT",
  "пайтон": "Python"
}
```

Расширенный пример:

```json
[
  ["опен ай", "OpenAI"],
  {"from": "дипграм", "to": "Deepgram"}
]
```

Правила обработки:

- Пустые ключи (`from`) и нестроковые значения игнорируются.
- Замены сортируются по длине исходного термина (длинные применяются первыми).
- Для «словесных» ключей применяется матч по границам слова (без частичных вхождений), для остальных — обычный `replace`.

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

## Переменные окружения и секреты

Приоритет чтения секретов (см. `ConfigManager`): файл **`.env.secrets`** в каталоге поддержки приложения, затем локальный **`.env`**, затем переменные окружения процесса.

> Примечание: для полей и дефолтов источником истины остаётся `app/core/config_manager.py`, но ключевые значения по умолчанию продублированы в этой документации для прозрачности.

### Таблица: провайдер → переменная секрета

| Роль | Значение в конфиге | Переменная (`.env.secrets`) |
|------|--------------------|-----------------------------|
| LLM | `model_provider` = `openai` | `OPENAI_API_KEY` |
| LLM | `groq` | `GROQ_API_KEY` |
| LLM | `anthropic` | `ANTHROPIC_API_KEY` |
| LLM | `google` / `gemini` | `GEMINI_API_KEY` |
| LLM | `openrouter` | `OPENROUTER_API_KEY` |
| LLM | `mistral` | `MISTRAL_API_KEY` |
| LLM | `cohere` | `COHERE_API_KEY` |
| LLM | `ollama` | ключ не обязателен (локальный сервер по умолчанию) |
| STT | `whisper_backend` = `openai` | `OPENAI_API_KEY` |
| STT | `groq` | `GROQ_API_KEY` |
| STT | `deepgram` | `DEEPGRAM_API_KEY` |
| STT | `local` | — |

После сохранения настроек в дашборде основной процесс получает **`RELOAD_CONFIG`**: конфиг и **провайдеры STT/LLM пересоздаются** без полного перезапуска приложения.

### Проверка подключения API (Dashboard)

В дашборде используется `app/core/api_selftest.py`:

- LLM: минимальный вызов к текущему провайдеру (`OpenAI` напрямую или `LiteLLM`).
- STT: проверка ключа через легковесные endpoint'ы (`/models` для OpenAI/Groq, `/v1/projects` для Deepgram).

Эти проверки не требуют записи аудио и нужны для быстрой диагностики секретов/доступности API.

### Прочее

| Переменная | Назначение |
|------------|------------|
| `GHOSTWRITER_HEADLESS=1` | Не поднимать Tk/CustomTkinter (pill, дашборд из рантайма). Для cron/launchd без дисплея. |

## Рекомендации

- Слабое железо — модели `tiny` / `base` для локального whisper.
- Облачные режимы — сеть и валидные ключи по таблице выше.
- Правки **`config.json`** на диске: используйте кнопку «Перечитать» в дашборде или сохранение из Settings — основной процесс подхватит конфиг и провайдеры; полный перезапуск нужен только для смены зависимостей окружения или кода.
