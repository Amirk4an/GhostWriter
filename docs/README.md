# Документация Ghost Writer (VoiceFlow WL)

Технический индекс документации. Основной обзор продукта и быстрый старт находятся в корневом [`../README.md`](../README.md).

| Документ | Содержание |
|----------|------------|
| [../README.md](../README.md) | Главная точка входа: обзор, быстрый старт, сборка, troubleshooting и ограничения платформ. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Пайплайн диктовки и дневника, модули `app/core`, `app/providers`, `app/platform`, `app/ui`, процессы и очереди. |
| [CONFIGURATION.md](CONFIGURATION.md) | Все ключи `config/config.json`, `stt_local`, секреты, переменные окружения, различия macOS / Windows / Linux. |
| [../assets/models/README.md](../assets/models/README.md) | Офлайн-веса faster-whisper для режима `stt_local.model_source: bundle`. |

## Связь с кодом

- Конфигурация: `app/core/config_manager.py` (`AppConfig`, `_validate`).
- Пути данных пользователя: `app/platform/paths.py` (`default_app_support_dir`, `single_instance_hint_path`).
- Точка входа процесса: `main.py` → `app/main_runtime.py` → `run_voiceflow_application`.
- Спецификация сборки: `GhostWriter.spec` (в корне репозитория).
