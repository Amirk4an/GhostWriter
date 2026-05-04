# Сборка на Linux

Инструкция по подготовке окружения, сборке через PyInstaller и проверке артефакта на **Linux**. Общие требования и типовые проблемы — в [BUILD_CROSS_PLATFORM.md](BUILD_CROSS_PLATFORM.md).

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

```bash
python3 main.py
```

Если приложение стартует и появляется трей, можно переходить к сборке.

## 3) Сборка через PyInstaller

Из корня проекта:

```bash
pyinstaller GhostWriter.spec --clean
```

**Результат:** каталог `**dist/GhostWriter/`** с бинарником внутри (onedir).

## 4) Проверка артефакта

Запуск бинарника из `dist/GhostWriter/` и базовая проверка:

- старт приложения без traceback;
- доступ к микрофону;
- корректная работа хоткея и вывода текста (с учётом ограничений платформы).

## 5) Окружение и права

- Убедитесь, что установлен и активен стек аудио (**PulseAudio** / **PipeWire** + **PortAudio**).
- Проверьте права текущего пользователя на доступ к аудиоустройствам.

