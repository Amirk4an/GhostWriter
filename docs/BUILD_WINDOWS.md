# Сборка на Windows

Инструкция по подготовке окружения, сборке через PyInstaller и проверке артефакта на **Windows**. Общие требования и типовые проблемы — в [BUILD_CROSS_PLATFORM.md](BUILD_CROSS_PLATFORM.md).

## 1) Подготовка окружения

Из корня репозитория в **PowerShell**:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

В **cmd**:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

Проверка:

```powershell
py --version
```

## 2) Предсборочная проверка

```powershell
python main.py
```

Если приложение стартует и появляется трей, можно переходить к сборке.

## 3) Сборка через PyInstaller

Из корня проекта:

```powershell
pyinstaller GhostWriter.spec --clean
```

**Результат:** каталог **`dist\GhostWriter\`** с исполняемым файлом **`dist\GhostWriter\GhostWriter.exe`** (onedir, без `.app`).

## 4) Проверка артефакта

Запуск:

```powershell
.\dist\GhostWriter\GhostWriter.exe
```

**Что проверить:**

- одноэкземплярность (второй запуск не поднимает вторую копию);
- горячая клавиша диктовки работает;
- вставка `Ctrl+V` в целевое приложение выполняется корректно.

## 5) Установщик Inno Setup (опционально)

Чтобы собрать один файл `**Output\GhostWriter_Setup.exe`**, установите [Inno Setup](https://jrsoftware.org/isinfo.php), откройте в компиляторе файл `**GhostWriter_installer.iss`** из корня репозитория и выполните сборку. Подробнее: [README.md](../README.md#установщик-windows-inno-setup).

## 6) Права и настройки системы

- Включите доступ классических приложений к микрофону: **Параметры → Конфиденциальность и безопасность → Микрофон**.
- Если глобальный хоткей конфликтует с другим ПО, проверьте фоновые хуки клавиатуры.

