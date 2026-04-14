# Архитектура Ghost Writer

## Обзор пайплайна

Ghost Writer работает как конвейер:

1. Пользователь нажимает глобальный хоткей.
2. `AudioEngine` записывает аудио.
3. STT-провайдер делает транскрипцию.
4. `LLMProcessor` (если включен) редактирует/чистит текст.
5. `OutputController` вставляет текст в активное приложение.
6. `StatusBridge` публикует статусы в UI (Python pill/tray или Electron).

Точка входа конвейера: `main.py`.

## Компоненты

### `app/core`

- `app_controller.py` — оркестратор жизненного цикла диктовки.
- `audio_engine.py` — работа с микрофоном и буфером аудио.
- `config_manager.py` — загрузка/валидация `config/config.json`, доступ к `.env`.
- `provider_factory.py` — сборка нужных STT/LLM-провайдеров из конфига.
- `llm_processor.py` — применение system prompt и постобработка текста.
- `interfaces.py` — интерфейсы для провайдеров и адаптеров.

### `app/providers`

- `faster_whisper_provider.py` — локальная транскрипция.
- `openai_whisper_provider.py` — транскрипция через OpenAI API.
- `openai_llm_provider.py` — LLM-обработка текста через OpenAI API.

### `app/platform`

- `hotkey_listener.py` — глобальные клавиши.
- `output_controller.py` — вставка текста через буфер обмена/эмуляцию ввода.
- `macos_focus.py`, `macos_ax_selection.py` — macOS-специфичные интеграции.

### `app/ui`

- `tray_app.py` — иконка в трее и actions.
- `floating_pill*.py` — плавающий индикатор статуса.
- `status_bridge.py` — единый шлюз статусов.
- `status_push_client.py` — отправка статусов в Electron по TCP.

### `web` (Electron + React)

- `web/electron/main.cjs` — создание окна, запуск Python backend, IPC и глобальный шорткат UI.
- `web/src` — React-компоненты виджета и отображение статусов.

## Режимы запуска

- **Python-only**: запускается `python main.py`, используется tray/pill UI из Python.
- **Electron mode**: запускается `npm start`, Electron стартует Python-процесс и получает статусы по локальному TCP.

## Потоки и процессы

- Основной Python-процесс обслуживает hotkey/STT/LLM/output.
- Для `floating_pill` может запускаться отдельный `multiprocessing.Process`.
- В Electron-режиме есть отдельный процесс Node/Electron, который спаунит Python.

## Конфигурация и секреты

- Runtime-конфиг: `config/config.json`.
- Секреты: `.env` (минимум `OPENAI_API_KEY` для OpenAI-режимов).
- Подробно: `docs/CONFIGURATION.md`.

