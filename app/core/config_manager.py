"""Управление white-label конфигурацией приложения."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

from dotenv import dotenv_values, load_dotenv, set_key, unset_key

from app.core.hotkey_spec import parse_hotkey_spec
from app.core.provider_credentials import ALLOWED_MODEL_PROVIDERS, ALLOWED_WHISPER_BACKENDS

LOGGER = logging.getLogger(__name__)

# Ключи, которые дашборд может массово записать в ``config.json`` (остальные игнорируются).
DASHBOARD_PATCHABLE_KEYS = frozenset(
    {
        "hotkey",
        "journal_hotkey",
        "command_mode_hotkey",
        "llm_enabled",
        "llm_model",
        "model_provider",
        "system_prompt",
        "journal_system_prompt",
        "whisper_backend",
        "whisper_model",
        "language",
        "floating_pill_enabled",
    }
)


@dataclass
class AppConfig:
    """Структура конфигурации приложения."""

    app_name: str
    primary_color: str
    hotkey: str
    system_prompt: str
    model_provider: str
    whisper_backend: str
    whisper_model: str
    local_whisper_model: str
    llm_model: str
    llm_enabled: bool
    sample_rate: int
    channels: int
    chunk_size: int
    language: str | None
    max_parallel_jobs: int
    audio_input_device: int | None = None
    floating_pill_enabled: bool = True
    command_mode_hotkey: str = ""
    app_context_prompts: dict[str, str] = field(default_factory=dict)
    user_glossary_path: str = "user_glossary.json"
    hands_free_enabled: bool = True
    short_tap_max_ms: int = 220
    latch_arm_window_ms: int = 450
    latch_stop_double_down_ms: int = 450
    command_mode_system_prompt: str = (
        "Ты редактируешь выделенный текст по голосовой команде пользователя. "
        "Верни только итоговый текст, который должен заменить выделение целиком, без пояснений и кавычек."
    )
    streaming_stt_enabled: bool = False
    whisper_mode_boost_input: bool = False
    # Локальный faster-whisper: источник весов и параметры CTranslate2 (см. ``stt_local`` в JSON).
    local_whisper_model_source: str = "cache"
    local_whisper_custom_path: str = ""
    local_whisper_device: str = "cpu"
    local_whisper_compute_type: str = "int8"
    enable_history: bool = True
    journal_hotkey: str = ""
    journal_system_prompt: str = (
        "Пользователь диктует мысль для личного дневника. Верни один JSON-объект с ключами: "
        '"title" (краткий заголовок), "tags" (массив из 2–3 коротких строк-тегов для сортировки), '
        '"advice" (короткий совет или инсайт по теме), "refined_text" (исправленная от опечаток '
        "оригинальная мысль, без добавления новых фактов). Только JSON, без markdown и пояснений."
    )


SECRETS_FILE_NAME = ".env.secrets"


def default_secrets_env_path(*, support_subdir: str = "GhostWriter") -> Path:
    """
    Путь к изменяемому файлу секретов (рядом со ``stats.json`` / ``history.db``).

    См. ``app.platform.paths.default_app_support_dir``.
    """
    from app.platform.paths import default_app_support_dir

    return default_app_support_dir(support_subdir=support_subdir) / SECRETS_FILE_NAME


class ConfigManager:
    """Загружает конфиг и секреты, поддерживает reload во время работы."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._lock = RLock()
        self._config: AppConfig | None = None
        load_dotenv()
        self.reload()

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def config(self) -> AppConfig:
        """Возвращает актуальную конфигурацию."""
        with self._lock:
            if self._config is None:
                raise RuntimeError("Конфигурация не загружена")
            return self._config

    def reload(self) -> AppConfig:
        """Перезагружает конфигурацию из файла."""
        with self._lock:
            raw_data = self._read_json()
            self._config = self._validate(raw_data)
            return self._config

    def patch_audio_input_device(self, device: int | None) -> AppConfig:
        """Записывает ``audio_input_device`` в ``config.json`` и обновляет кэш.

        Args:
            device: Индекс PortAudio или ``None`` (вход по умолчанию ОС).

        Returns:
            Актуальная конфигурация после записи.
        """
        with self._lock:
            raw_data = self._read_json()
            if device is None:
                raw_data["audio_input_device"] = None
            else:
                raw_data["audio_input_device"] = int(device)
            self._write_json(raw_data)
            self._config = self._validate(raw_data)
            return self._config

    def patch_enable_history(self, enabled: bool) -> AppConfig:
        """Записывает ``enable_history`` в ``config.json`` (история диктовок в SQLite)."""
        with self._lock:
            raw_data = self._read_json()
            raw_data["enable_history"] = bool(enabled)
            self._write_json(raw_data)
            self._config = self._validate(raw_data)
            return self._config

    def update_and_save(self, new_values: dict[str, Any]) -> AppConfig:
        """
        Читает ``config.json``, обновляет разрешённые ключи, валидирует целиком и атомарно сохраняет.

        Неизвестные ключи из ``new_values`` пропускаются (с предупреждением в логе).

        Args:
            new_values: Плоский словарь ключ → значение для записи.

        Returns:
            Актуальный ``AppConfig`` после успешной валидации и записи.

        Raises:
            RuntimeError: При ошибке валидации или пустом ``hotkey``.
        """
        with self._lock:
            raw = self._read_json()
            for key, val in new_values.items():
                if key not in DASHBOARD_PATCHABLE_KEYS:
                    LOGGER.warning("update_and_save: пропуск ключа вне белого списка: %s", key)
                    continue
                if key == "language":
                    if val is None or str(val).strip().lower() in ("", "auto", "detect", "multi"):
                        raw["language"] = None
                    else:
                        raw["language"] = str(val).strip()
                elif key in ("llm_enabled", "floating_pill_enabled"):
                    raw[key] = bool(val)
                elif key in ("system_prompt", "journal_system_prompt", "llm_model"):
                    raw[key] = str(val)
                elif key in ("hotkey", "journal_hotkey", "command_mode_hotkey"):
                    raw[key] = str(val or "").strip().lower().replace(" ", "")
                elif key == "whisper_backend":
                    raw[key] = str(val or "").strip().lower()
                elif key == "model_provider":
                    raw[key] = str(val or "").strip().lower()
                elif key == "whisper_model":
                    raw[key] = str(val or "").strip()
                else:
                    raw[key] = val

            if not str(raw.get("hotkey", "") or "").strip():
                raise RuntimeError("Поле «Основной хоткей» не может быть пустым")

            cfg = self._validate(raw)
            raw["hotkey"] = cfg.hotkey
            raw["journal_hotkey"] = cfg.journal_hotkey
            raw["command_mode_hotkey"] = cfg.command_mode_hotkey
            raw["whisper_backend"] = cfg.whisper_backend
            raw["model_provider"] = cfg.model_provider
            raw["whisper_model"] = cfg.whisper_model
            raw["language"] = cfg.language
            raw["llm_model"] = cfg.llm_model
            raw["llm_enabled"] = cfg.llm_enabled
            raw["system_prompt"] = cfg.system_prompt
            raw["journal_system_prompt"] = cfg.journal_system_prompt
            raw["floating_pill_enabled"] = cfg.floating_pill_enabled
            self._write_json(raw)
            self._config = cfg
            return cfg

    def secrets_env_path(self) -> Path:
        """Файл ``.env.secrets`` в каталоге поддержки приложения (доступен на запись вне бандла .app)."""
        return default_secrets_env_path()

    def _local_dotenv_candidates(self) -> list[Path]:
        """Пути ``.env`` для разработки: рядом с ``config.json``, затем текущий каталог."""
        return [self._config_path.parent / ".env", Path.cwd() / ".env"]

    def _read_secret_layered(self, key: str) -> str | None:
        """Читает секрет: пользовательский файл → локальный ``.env`` → ``os.environ``."""
        user_path = self.secrets_env_path()
        if user_path.is_file():
            raw = dotenv_values(user_path).get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
        for candidate in self._local_dotenv_candidates():
            if candidate.is_file():
                raw = dotenv_values(candidate).get(key)
                if raw is not None and str(raw).strip():
                    return str(raw).strip()
        v = os.getenv(key)
        if v is not None and str(v).strip():
            return str(v).strip()
        return None

    def peek_secret(self, key: str) -> str | None:
        """Возвращает секрет без исключения (для UI и проверок)."""
        return self._read_secret_layered(key)

    def get_secret(self, key: str) -> str:
        """Возвращает секрет (каждый раз с диска / окружения — актуально после записи из дашборда)."""
        value = self._read_secret_layered(key)
        if not value:
            raise RuntimeError(
                f"Не найден секрет '{key}'. Задайте его в настройках дашборда, в файле "
                f"{self.secrets_env_path()}, в локальном .env или в переменных окружения."
            )
        return value

    def set_secret(self, key: str, value: str) -> None:
        """Сохраняет секрет в пользовательский ``.env.secrets`` (не внутри бандла PyInstaller)."""
        path = self.secrets_env_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path_str = str(path)
        existed = path.is_file()
        if value.strip():
            set_key(path_str, key, value.strip())
            if not existed:
                try:
                    path.chmod(0o600)
                except OSError:
                    pass
            os.environ[key] = value.strip()
        else:
            if path.is_file():
                unset_key(path_str, key)
            os.environ.pop(key, None)

    def _read_json(self) -> dict[str, Any]:
        try:
            with self._config_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError as error:
            raise RuntimeError(f"Файл конфигурации не найден: {self._config_path}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Некорректный JSON в {self._config_path}") from error

    def _write_json(self, data: dict[str, Any]) -> None:
        """Атомарно сохраняет JSON конфигурации."""
        tmp_path = self._config_path.with_suffix(".json.tmp")
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        with tmp_path.open("w", encoding="utf-8") as file:
            file.write(payload)
        tmp_path.replace(self._config_path)

    def _parse_stt_local(self, raw: dict[str, Any]) -> tuple[str, str, str, str]:
        """
        Читает опциональный блок ``stt_local`` для локального faster-whisper.

        Returns:
            Кортеж ``(model_source, custom_model_path, device, compute_type)``.
        """
        block = raw.get("stt_local")
        if not isinstance(block, dict):
            return ("cache", "", "cpu", "int8")
        source = str(block.get("model_source", "cache") or "cache").strip().lower()
        if source not in ("cache", "bundle", "custom_path"):
            raise RuntimeError(
                f"stt_local.model_source: ожидается cache, bundle или custom_path, получено {source!r}"
            )
        custom = str(block.get("custom_model_path", "") or "").strip()
        if source == "custom_path" and not custom:
            raise RuntimeError("stt_local.custom_model_path обязателен при model_source=custom_path")
        device = str(block.get("device", "cpu") or "cpu").strip()
        compute_type = str(block.get("compute_type", "int8") or "int8").strip()
        return (source, custom, device, compute_type)

    def _parse_language(self, raw: dict[str, Any]) -> str | None:
        if "language" not in raw:
            return "ru"
        value = raw["language"]
        if value is None:
            return None
        s = str(value).strip().lower()
        if s in ("", "auto", "detect", "multi"):
            return None
        return str(value).strip()

    def _validate(self, raw: dict[str, Any]) -> AppConfig:
        required_keys = {
            "app_name",
            "primary_color",
            "hotkey",
            "system_prompt",
            "model_provider",
            "whisper_backend",
            "whisper_model",
            "local_whisper_model",
            "llm_model",
            "llm_enabled",
            "sample_rate",
            "channels",
            "chunk_size",
            "max_parallel_jobs",
        }
        missing = required_keys - raw.keys()
        if missing:
            raise RuntimeError(f"Отсутствуют ключи конфига: {sorted(missing)}")

        audio_raw = raw.get("audio_input_device", None)
        audio_input_device: int | None
        if audio_raw is None:
            audio_input_device = None
        else:
            audio_input_device = int(audio_raw)

        ctx = raw.get("app_context_prompts") or {}
        if not isinstance(ctx, dict):
            raise RuntimeError("app_context_prompts должен быть объектом JSON")
        context_prompts = {str(k): str(v) for k, v in ctx.items()}

        lw_source, lw_custom, lw_device, lw_compute = self._parse_stt_local(raw)

        journal_hotkey_raw = str(raw.get("journal_hotkey", "") or "").lower().replace(" ", "")
        journal_hotkey_effective = journal_hotkey_raw
        if journal_hotkey_raw:
            try:
                parse_hotkey_spec(journal_hotkey_raw)
            except ValueError:
                LOGGER.warning("Некорректный journal_hotkey %r — режим дневника отключён", journal_hotkey_raw)
                journal_hotkey_effective = ""

        model_provider = str(raw["model_provider"]).lower()
        if model_provider not in ALLOWED_MODEL_PROVIDERS:
            raise RuntimeError(
                f"model_provider: ожидается один из {sorted(ALLOWED_MODEL_PROVIDERS)}, получено {model_provider!r}"
            )

        whisper_backend = str(raw["whisper_backend"]).lower()
        if whisper_backend not in ALLOWED_WHISPER_BACKENDS:
            raise RuntimeError(
                f"whisper_backend: ожидается один из {sorted(ALLOWED_WHISPER_BACKENDS)}, "
                f"получено {whisper_backend!r}"
            )

        return AppConfig(
            app_name=str(raw["app_name"]),
            primary_color=str(raw["primary_color"]),
            hotkey=str(raw["hotkey"]).lower().replace(" ", ""),
            system_prompt=str(raw["system_prompt"]),
            model_provider=model_provider,
            whisper_backend=whisper_backend,
            whisper_model=str(raw["whisper_model"]),
            local_whisper_model=str(raw["local_whisper_model"]),
            llm_model=str(raw["llm_model"]),
            llm_enabled=bool(raw["llm_enabled"]),
            sample_rate=int(raw["sample_rate"]),
            channels=int(raw["channels"]),
            chunk_size=int(raw["chunk_size"]),
            language=self._parse_language(raw),
            max_parallel_jobs=max(1, int(raw["max_parallel_jobs"])),
            audio_input_device=audio_input_device,
            floating_pill_enabled=bool(raw.get("floating_pill_enabled", True)),
            command_mode_hotkey=str(raw.get("command_mode_hotkey", "") or "").lower().replace(" ", ""),
            app_context_prompts=context_prompts,
            user_glossary_path=str(raw.get("user_glossary_path", "user_glossary.json")),
            hands_free_enabled=bool(raw.get("hands_free_enabled", True)),
            short_tap_max_ms=max(50, int(raw.get("short_tap_max_ms", 220))),
            latch_arm_window_ms=max(100, int(raw.get("latch_arm_window_ms", 450))),
            latch_stop_double_down_ms=max(100, int(raw.get("latch_stop_double_down_ms", 450))),
            command_mode_system_prompt=str(
                raw.get(
                    "command_mode_system_prompt",
                    AppConfig.command_mode_system_prompt,
                )
            ),
            streaming_stt_enabled=bool(raw.get("streaming_stt_enabled", False)),
            whisper_mode_boost_input=bool(raw.get("whisper_mode_boost_input", False)),
            local_whisper_model_source=lw_source,
            local_whisper_custom_path=lw_custom,
            local_whisper_device=lw_device,
            local_whisper_compute_type=lw_compute,
            enable_history=bool(raw.get("enable_history", True)),
            journal_hotkey=journal_hotkey_effective,
            journal_system_prompt=str(
                raw.get("journal_system_prompt", AppConfig.journal_system_prompt) or AppConfig.journal_system_prompt
            ),
        )
