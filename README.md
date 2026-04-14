# Ghost Writer

Desktop-приложение для голосового ввода: захват аудио, распознавание речи (локально или через OpenAI), опциональная LLM-обработка текста и вставка результата в активное поле ввода.

## Возможности

- Глобальный хоткей для старта/остановки диктовки.
- STT через `faster-whisper` (локально) или `openai/whisper-1`.
- Опциональная постобработка текста через LLM (OpenAI).
- Контекстные промпты для разных приложений (Slack, Mail, Cursor и т.д.).
- Два UI-режима: системный tray (Python) или overlay-виджет (Electron + React).

## Технологии

- Backend: Python 3.10+, `sounddevice`, `pynput`, `pyperclip`, `openai`, `faster-whisper`.
- UI (desktop shell): Electron.
- UI (виджет): React + TypeScript + Vite.

## Требования

- macOS (основной целевой сценарий проекта).
- Python 3.10+.
- Node.js 18+ и npm (для запуска Electron UI).
- API-ключ OpenAI для режимов, использующих OpenAI.

## Быстрый старт (Python-only режим)

1. Создайте виртуальное окружение:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
2. Установите зависимости:
  - `pip install -r requirements.txt`
3. Создайте `.env` из примера:
  - `cp .env.example .env`
4. Укажите `OPENAI_API_KEY` в `.env`.
5. Проверьте настройки в `config/config.json`.
6. Запустите приложение:
  - `python main.py`

## Запуск через Electron (рекомендуемый UI)

1. Подготовьте Python-зависимости, как в разделе выше.
2. Установите зависимости Electron/React (из корня репозитория):
  - `npm --prefix web install`
3. Запустите единое приложение:
  - `npm start`

Electron поднимет UI и автоматически запустит Python backend (`main.py`) в фоне.

## Тесты

- Запуск тестов:
  - `pytest`

## Структура проекта

- `app/core` — оркестрация приложения, конфиг, интерфейсы, фабрика провайдеров.
- `app/providers` — STT/LLM-провайдеры.
- `app/platform` — платформенные адаптеры (хоткеи, фокус, вставка текста).
- `app/ui` — Python UI-компоненты и статусы.
- `web` — Electron + React UI.
- `config/config.json` — основная runtime-конфигурация.
- `config/user_glossary.json` — пользовательский словарь терминов.

## Документация

- Архитектура: `docs/ARCHITECTURE.md`
- Конфигурация: `docs/CONFIGURATION.md`

## Важные заметки для macOS

- Нужно выдать Accessibility permissions приложению/терминалу для глобальных хоткеев и эмуляции ввода.
- Для локальной транскрипции (`faster-whisper`) нужны дополнительные CPU/GPU ресурсы.

