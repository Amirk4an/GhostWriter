# Кроссплатформенная сборка Ghost Writer

Эта инструкция описывает корректную сборку приложения из исходников на **macOS**, **Windows** и **Linux**.

## 1) Общие требования

- Python `3.9+`
- Доступ в интернет для установки зависимостей
- Рекомендуется собирать в чистом виртуальном окружении `.venv`
- Сборку выполняйте из корня репозитория (`.../ghostwriter`)

Проверка:

```bash
python3 --version
```

Для Windows:

```powershell
py --version
```

## 2) Подготовка окружения

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

### Windows (cmd)

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

## 3) Предсборочная проверка

Перед сборкой убедитесь, что проект запускается в dev-режиме:

```bash
python3 main.py
```

Windows:

```powershell
python main.py
```

Если приложение стартует и появляется трей, можно переходить к сборке.

## 4) Сборка через PyInstaller

Во всех ОС используйте одну и ту же команду из корня проекта:

```bash
pyinstaller GhostWriter.spec --clean
```

Результат:

- **macOS**: `dist/GhostWriter/` и `dist/GhostWriter.app`
- **Windows**: `dist/GhostWriter/` и исполняемый файл `dist\GhostWriter\GhostWriter.exe`
- **Linux**: `dist/GhostWriter/` и бинарник внутри каталога

## 5) Проверка артефакта после сборки

### macOS

Запуск из терминала (полезно для отладки):

```bash
./dist/GhostWriter.app/Contents/MacOS/GhostWriter
```

Что проверить:

- приложение появляется в трее;
- запись с микрофона работает;
- текст вставляется в активное окно;
- нет критических ошибок в логе.

### Windows

Запуск:

```powershell
.\dist\GhostWriter\GhostWriter.exe
```

Что проверить:

- одноэкземплярность (второй запуск не поднимает вторую копию);
- горячая клавиша диктовки работает;
- вставка `Ctrl+V` в целевое приложение выполняется корректно.

### Linux

Запуск бинарника из `dist/GhostWriter/` и базовая проверка:

- старт приложения без traceback;
- доступ к микрофону;
- корректная работа хоткея и вывода текста (с учетом ограничений платформы).

## 6) Платформенные требования и права доступа

### macOS

- Выдайте права в **Privacy & Security**:
  - **Microphone**
  - **Accessibility** (для автовставки и глобальных хоткеев)
- При запуске из IDE/терминала права должны быть выданы именно этой программе (Terminal/Cursor/iTerm).

### Windows

- Включите доступ классических приложений к микрофону:
  - `Параметры -> Конфиденциальность и безопасность -> Микрофон`
- Если глобальный хоткей конфликтует с другим ПО, проверьте фоновые хуки клавиатуры.

### Linux

- Убедитесь, что установлен и активен стек аудио (PulseAudio/PipeWire + PortAudio).
- Проверяйте права текущего пользователя на доступ к аудиоустройствам.

## 7) Частые проблемы сборки

- `ModuleNotFoundError` в runtime:
  - удалите `build/` и `dist/`, повторите сборку с `--clean`;
  - проверьте, что сборка выполнена в активированном `.venv` с установленными зависимостями.
- Приложение запускается, но нет записи:
  - проверьте права на микрофон и `audio_input_device` в `config/config.json`.
- Не работает автовставка на macOS:
  - проверьте Accessibility для процесса, от имени которого запущен app.

## 8) Релизный чеклист

Перед публикацией сборки:

1. Очистить старые артефакты `build/` и `dist/`.
2. Выполнить свежую сборку на целевой ОС.
3. Проверить запуск и базовый сценарий диктовки.
4. Проверить наличие нужных ресурсов в `dist` (включая `assets/models`, если используется локальный STT из бандла).
5. Зафиксировать версию и дату сборки в вашем release-процессе.

