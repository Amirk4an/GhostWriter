# Документация Ghost Writer (VoiceFlow WL)

Технический индекс документации. Основной обзор продукта и быстрый старт находятся в корневом `[../README.md](../README.md)`.


| Документ                                                 | Содержание                                                                                                      |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| [../README.md](../README.md)                             | Главная точка входа: обзор, быстрый старт, сборка, troubleshooting и ограничения платформ.                      |
| [BUILD_CROSS_PLATFORM.md](BUILD_CROSS_PLATFORM.md)       | Указатель: общие требования, типовые проблемы, релизный чеклист; ссылки на платформенные инструкции ниже.       |
| [BUILD_macOS.md](BUILD_macOS.md)                         | Сборка и проверка артефакта на macOS.                                                                           |
| [BUILD_WINDOWS.md](BUILD_WINDOWS.md)                     | Сборка и проверка на Windows; Inno Setup.                                                                       |
| [BUILD_LINUX.md](BUILD_LINUX.md)                         | Сборка и проверка на Linux.                                                                                     |
| [ARCHITECTURE.md](ARCHITECTURE.md)                       | Пайплайн диктовки и дневника, модули `app/core`, `app/providers`, `app/platform`, `app/ui`, процессы и очереди. |
| [CONFIGURATION.md](CONFIGURATION.md)                     | Все ключи `config/config.json`, `stt_local`, секреты, переменные окружения, различия macOS / Windows / Linux.   |
| [../assets/models/README.md](../assets/models/README.md) | Офлайн-веса faster-whisper для режима `stt_local.model_source: bundle`.                                         |


## Связь с кодом

- Конфигурация: `app/core/config_manager.py` (`AppConfig`, `_validate`).
- Пути данных пользователя: `app/platform/paths.py` (`default_app_support_dir`, `single_instance_hint_path`).
- Точка входа процесса: `main.py` → `app/main_runtime.py` → `run_voiceflow_application`.
- Спецификация сборки: `GhostWriter.spec` (в корне репозитория).