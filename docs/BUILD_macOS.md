# Сборка на macOS

Инструкция по подготовке окружения, сборке через PyInstaller и проверке артефакта на **macOS**. Общие требования и типовые проблемы — в [BUILD_CROSS_PLATFORM.md](BUILD_CROSS_PLATFORM.md).

## 1) Подготовка окружения

Из корня репозитория:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

Проверка версии Python:

```bash
python3 --version
```

## 2) Предсборочная проверка

Убедитесь, что проект запускается в dev-режиме:

```bash
python3 main.py
```

Если приложение стартует и появляется трей, можно переходить к сборке.

## 3) Сборка через PyInstaller

Из корня проекта:

```bash
pyinstaller GhostWriter.spec --clean
```

**Результат:** каталог `dist/GhostWriter/` и пакет приложения `**dist/GhostWriter.app`**.

## 4) Проверка артефакта

Запуск из терминала (удобно для отладки):

```bash
./dist/GhostWriter.app/Contents/MacOS/GhostWriter
```

**Что проверить:**

- приложение появляется в трее;
- запись с микрофона работает;
- текст вставляется в активное окно;
- нет критических ошибок в логе.

## 5) Права доступа

- В **Privacy & Security** выдайте:
  - **Microphone**
  - **Accessibility** (для автовставки и глобальных хоткеев)
- При запуске из IDE или терминала права выдаются именно этой программе (Terminal, Cursor, iTerm и т.д.).

