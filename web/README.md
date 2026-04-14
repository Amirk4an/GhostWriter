# Web / Electron UI

Папка `web` содержит UI-оболочку Ghost Writer:

- Electron main process (`electron/main.cjs`).
- React-виджет (`src`), отрисовываемый поверх окон.

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

