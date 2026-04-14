# Web / Electron UI

Папка `web` содержит UI-оболочку Ghost Writer:

- Electron main process (`electron/main.cjs`).
- React-виджет (`src`), отрисовываемый поверх окон.

По умолчанию Electron открывает **два окна** без рамки:

1. **Панель** (~1080×700 px): сайдбар (транскрипция, LLM, контексты, история, справка, настройки) и контент. Запись с микрофона на панели не показывается — только обзор и статус бэкенда.
2. **Капсула-виджет** (~140×56 px, поверх всех окон): только микрофон и passthrough кликов вне капсулы. Позиция сохраняется в `userData` / `overlay-compact-position.json`.

Оба окна грузят один Vite-сборщик; виджет открывается с hash `#ghostSurface=widget`. Перетаскивание панели — шапка сайдбара и узкая полоска над контентом (`-webkit-app-region: drag`). Настройки темы синхронизируются между окнами через `localStorage` в мок-слое `ghostIpc`. Режим `applyGhostShellLayout(..., 'compact')` для панели оставлен как резерв под IPC.

## Скрипты

- `npm start` / `npm run dev` — запуск Vite + Electron в dev-режиме.
- `npm run start:ui-only` — запуск только UI без старта Python backend.
- `npm run build` — TypeScript build + Vite build.
- `npm run start:dist` — запуск Electron c собранным `dist`.
- `npm run lint` — запуск ESLint.

## Как это связано с backend

По умолчанию Electron:

1. Поднимает локальный TCP-сервер статусов.
2. Запускает Python backend (`main.py`) из корня проекта.
3. Передаёт статусы из Python в React через IPC.

Ключевые env-переменные:

- `GHOST_WRITER_PYTHON` — путь к Python-интерпретатору (опционально).
- `GHOST_WRITER_UI_ONLY=1` — не запускать Python backend.
- `ELECTRON_DEV=1` — dev-режим загрузки через Vite URL.

## Локальная разработка

Из корня проекта:

```bash
npm --prefix web install
npm --prefix web start
```

