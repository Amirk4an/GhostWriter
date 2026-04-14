"""Управление white-label конфигурацией приложения."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

from dotenv import load_dotenv


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

    def get_secret(self, key: str) -> str:
        """Возвращает секрет из переменных окружения."""
        value = os.getenv(key)
        if not value:
            raise RuntimeError(f"Не найден секрет '{key}' в окружении")
        return value

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

        return AppConfig(
            app_name=str(raw["app_name"]),
            primary_color=str(raw["primary_color"]),
            hotkey=str(raw["hotkey"]).lower().replace(" ", ""),
            system_prompt=str(raw["system_prompt"]),
            model_provider=str(raw["model_provider"]).lower(),
            whisper_backend=str(raw["whisper_backend"]).lower(),
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
        )
