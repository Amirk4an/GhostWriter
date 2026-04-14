# Ghost Writer (VoiceFlow WL)

Диктовка с глобальным хоткеем: запись с микрофона → STT (локальный **faster-whisper** или **OpenAI Whisper**) → опциональная постобработка через LLM → вставка текста в активное приложение. Есть режим **Python-only** (трей и плавающий индикатор) и режим **Electron + React** с единым UI (панель с сайдбаром и экраном транскрипции; подробности в [web/README.md](web/README.md)).

Подробнее о пайплайне и модулях: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Настройки и переменные окружения: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Требования

- **macOS** (в репозитории есть зависимости под Darwin для доступности и ввода).
- **Python 3.9+** (в проекте есть `.venv`; при необходимости создайте свой).
- **Node.js** и **npm** (для папки `web`: Vite, Electron, скрипты запуска).

## Быстрый старт

1. Клонируйте репозиторий и перейдите в корень проекта.

2. Python-зависимости:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Секреты для OpenAI (если используете облачные STT/LLM). В корне создайте файл `.env`:

   ```bash
   OPENAI_API_KEY=sk-...
   ```

4. Установите npm-зависимости **обязательно в `web/`** (иначе при `npm start` не найдётся `concurrently` и другие dev-утилиты):

   ```bash
   npm --prefix web install
   ```

5. Запуск **Electron + Vite + Python backend** из корня:

   ```bash
   npm start
   ```

   Эквивалент: `npm --prefix web start`. Скрипты и переменные окружения для UI описаны в [web/README.md](web/README.md).

### Только Python (без Electron)

```bash
source .venv/bin/activate
python main.py
```

Используется трей и при необходимости плавающий pill из Python. Конфиг: `config/config.json`.

### Сборка фронта

```bash
npm --prefix web run build
npm --prefix web run start:dist
```

### Сборка macOS-приложения (.app)

Сначала соберите бинарник Python в корневой каталог `dist/`, затем упакуйте Electron (артефакты — `web/release/`, в том числе `.app`, `.dmg` и `.zip`):

```bash
bash build_backend.sh
npm --prefix web run build:app
```

## Структура репозитория

| Путь | Назначение |
|------|------------|
| `main.py` | Точка входа Python: хоткей, аудио, провайдеры, вывод, трей. |
| `app/` | Ядро, платформенный слой, провайдеры STT/LLM, UI-мост статусов. |
| `config/` | `config.json`, пользовательский глоссарий и т.п. |
| `web/` | Electron (main/preload), React UI, Vite. |
| `tests/` | Pytest. |

## Разработка и тесты

```bash
source .venv/bin/activate
pytest
```

```bash
npm --prefix web run lint
```

## Устранение неполадок

### `sh: concurrently: command not found`

Зависимости `web/` не установлены или установлены в другом каталоге. Выполните из корня проекта:

```bash
npm --prefix web install
```

Затем снова `npm start`.

### `command not found: compdef` при входе в shell (OpenClaw)

Сообщение относится к **`~/.openclaw/completions/openclaw.zsh`**: в конце файла вызывается `compdef`, которая доступна только после инициализации системы completions в Zsh.

**Варианты:**

- Убедитесь, что **до** `source` этого файла выполняется `compinit`, например в `~/.zshrc`:

  ```bash
  autoload -Uz compinit
  compinit
  ```

  (часто это уже делает Oh My Zsh / Prezto; если completions отключены — включите их или перенесите `source` строки OpenClaw ниже блока с `compinit`).

- Либо не подключайте сгенерированный completion-скрипт вручную, если вы не используете Zsh completions — используйте способ установки completions из документации OpenClaw для вашей оболочки.

Это не ошибка самого Ghost Writer и на запуск приложения из этого репозитория не влияет.

## Лицензия и вклад

При добавлении лицензии или гайдлайнов для контрибьюторов дополните этот раздел в репозитории.
