# Конфигурация Ghost Writer

Основной конфиг хранится в `config/config.json`.

## Обязательные поля

- `app_name` — имя приложения в UI.
- `primary_color` — основной цвет (hex).
- `hotkey` — hotkey диктовки (например, `f8`).
- `system_prompt` — базовый промпт постобработки текста.
- `model_provider` — провайдер LLM (сейчас используется `openai`).
- `whisper_backend` — backend STT: `local` или `openai`.
- `whisper_model` — модель OpenAI Whisper (например, `whisper-1`).
- `local_whisper_model` — локальная модель faster-whisper (`tiny`, `base`, `small`, ...).
- `llm_model` — модель LLM (например, `gpt-4o-mini`).
- `llm_enabled` — включить/выключить LLM-постобработку.
- `sample_rate` — частота дискретизации микрофона.
- `channels` — число каналов.
- `chunk_size` — размер аудио-чанка.
- `max_parallel_jobs` — макс. количество задач обработки.

## Опциональные поля

- `audio_input_device` — индекс устройства ввода PortAudio (`null` = вход по умолчанию ОС). В **Electron** тот же параметр можно менять в интерфейсе: **Настройки → Распознавание речи → Микрофон** (список приходит из Python / `sounddevice`).
- `floating_pill_enabled` — включение плавающего индикатора.
- `command_mode_hotkey` — хоткей режима редактирования выделенного текста.
- `command_mode_system_prompt` — отдельный промпт для command mode.
- `app_context_prompts` — словарь промптов по имени приложения.
- `user_glossary_path` — путь к JSON-словарю терминов.
- `hands_free_enabled` — режим "без рук".
- `short_tap_max_ms` — лимит короткого тапа.
- `latch_arm_window_ms` — окно для "latch" режима.
- `latch_stop_double_down_ms` — таймаут двойного нажатия для остановки.
- `streaming_stt_enabled` — включение стримингового STT.
- `whisper_mode_boost_input` — усиление тихого входа в whisper-режиме.
- `language` — язык распознавания (`ru`, `en`, и т.п.) или `null` для автоопределения.

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
  "llm_model": "gpt-4o-mini",
  "llm_enabled": false,
  "sample_rate": 16000,
  "channels": 1,
  "chunk_size": 1024,
  "language": "ru",
  "max_parallel_jobs": 1,
  "audio_input_device": 1
}
```

## Переменные окружения

Минимально в `.env`:

- `OPENAI_API_KEY=...`

Для Electron-интеграции (обычно выставляются автоматически):

- `GHOST_WRITER_ELECTRON_UI=1`
- `GHOST_WRITER_PUSH_STATUS_HOST=127.0.0.1`
- `GHOST_WRITER_PUSH_STATUS_PORT=<port>`
- `GHOST_WRITER_PYTHON=<path-to-python>` (опционально, для явного выбора Python)
- `GHOST_WRITER_UI_ONLY=1` (запуск только UI без Python backend)

## Рекомендации по настройке

- Для слабых машин используйте меньшую локальную модель (`tiny`/`base`).
- Если используете OpenAI STT/LLM, проверьте доступ к сети и валидность API-ключа.
- После изменения `config/config.json` перезапустите приложение.

