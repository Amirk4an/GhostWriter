"""Локальная статистика использования (white-label): JSON в каталоге поддержки приложения."""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

LOGGER = logging.getLogger(__name__)

STATS_FILE_NAME = "stats.json"
STATS_SCHEMA_VERSION = 1
# Средняя скорость набора текста для оценки «сэкономленного времени» (слов в минуту).
DEFAULT_TYPING_WPM = 40.0
# Условный объём «крупного романа» для наглядного сравнения на главной.
REFERENCE_EPIC_WORDS = 300_000


def default_stats_json_path(*, support_subdir: str = "GhostWriter") -> Path:
    """
    Путь к ``stats.json`` рядом с single-instance lock (white-label: тот же ``support_subdir``).

    На macOS: ``~/Library/Application Support/<subdir>/stats.json``.
    В остальных ОС: ``~/.<subdir_lower>/stats.json``.
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / support_subdir / STATS_FILE_NAME
    safe = support_subdir.strip().lower().replace(" ", "_") or "ghostwriter"
    return Path.home() / f".{safe}" / STATS_FILE_NAME


@dataclass
class StatsSnapshot:
    """Снимок счётчиков для UI и отчётов."""

    version: int = STATS_SCHEMA_VERSION
    dictation_sessions: int = 0
    total_words: int = 0
    total_chars: int = 0
    total_audio_seconds: float = 0.0
    total_time_saved_seconds: float = 0.0
    llm_runs: int = 0
    active_dates: list[str] = field(default_factory=list)

    @property
    def active_days_count(self) -> int:
        """Число календарных дней, в которые была хотя бы одна успешная сессия."""
        return len(self.active_dates)


def _today_iso() -> str:
    return date.today().isoformat()


def _estimate_time_saved_seconds(word_count: int, dictation_seconds: float, typing_wpm: float) -> float:
    """
    Оценка сэкономленного времени: время набора при средней скорости минус время диктовки.

    Args:
        word_count: Слов в итоговом тексте.
        dictation_seconds: Длительность записи (сек), без STT/LLM.
        typing_wpm: Средняя скорость печати (слов/мин).
    """
    if word_count <= 0 or typing_wpm <= 0:
        return 0.0
    typing_seconds = (word_count / typing_wpm) * 60.0
    return max(0.0, typing_seconds - max(0.0, dictation_seconds))


def wav_audio_duration_seconds(wav_bytes: bytes) -> float | None:
    """Длительность PCM из WAV-байтов (как у ``AudioEngine``), либо ``None`` при ошибке."""
    if len(wav_bytes) < 64:
        return None
    import io
    import wave

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate <= 0 or frames <= 0:
                return None
            return frames / float(rate)
    except Exception:
        return None


class StatsManager:
    """Потокобезопасная запись и чтение ``stats.json``."""

    def __init__(self, json_path: Path, *, typing_wpm: float = DEFAULT_TYPING_WPM) -> None:
        """
        Args:
            json_path: Абсолютный путь к файлу статистики.
            typing_wpm: Средняя скорость печати для метрики «сэкономлено времени».
        """
        self._path = json_path
        self._typing_wpm = typing_wpm
        self._lock = RLock()

    @classmethod
    def with_default_path(cls, *, support_subdir: str = "GhostWriter", typing_wpm: float = DEFAULT_TYPING_WPM) -> StatsManager:
        """Фабрика с путём по умолчанию для каталога поддержки приложения."""
        path = default_stats_json_path(support_subdir=support_subdir)
        return cls(path, typing_wpm=typing_wpm)

    def load_snapshot(self) -> StatsSnapshot:
        """Читает файл с диска; при отсутствии или ошибке возвращает нулевой снимок."""
        with self._lock:
            return self._read_snapshot_locked()

    def record_successful_dictation(
        self,
        *,
        word_count: int,
        char_count: int,
        recorded_ms: float,
        audio_seconds: float | None,
        llm_used: bool,
    ) -> None:
        """
        Увеличивает счётчики после успешной диктовки (текст вставлен / выведен без ошибки вставки).

        Args:
            word_count: Слов в итоговом тексте.
            char_count: Символов в итоговом тексте.
            recorded_ms: Длительность удержания записи (мс), с ``AudioEngine``.
            audio_seconds: Длительность по WAV или ``None`` (тогда из ``recorded_ms``).
            llm_used: Был ли вызван облачный/локальный LLM (провайдер включён).
        """
        dictation_sec = max(0.0, float(recorded_ms) / 1000.0)
        audio_sec = float(audio_seconds) if audio_seconds is not None else dictation_sec
        saved = _estimate_time_saved_seconds(word_count, dictation_sec, self._typing_wpm)

        with self._lock:
            snap = self._read_snapshot_locked()
            if snap.version != STATS_SCHEMA_VERSION:
                snap.version = STATS_SCHEMA_VERSION
            snap.dictation_sessions += 1
            snap.total_words += max(0, int(word_count))
            snap.total_chars += max(0, int(char_count))
            snap.total_audio_seconds += max(0.0, audio_sec)
            snap.total_time_saved_seconds += saved
            if llm_used:
                snap.llm_runs += 1
            today = _today_iso()
            if today not in snap.active_dates:
                snap.active_dates.append(today)
                snap.active_dates.sort()
                if len(snap.active_dates) > 400:
                    snap.active_dates = snap.active_dates[-366:]
            self._atomic_write_locked(snap)

    def _read_snapshot_locked(self) -> StatsSnapshot:
        if not self._path.is_file():
            return StatsSnapshot()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.warning("Не удалось прочитать stats.json, используем пустую статистику", exc_info=True)
            return StatsSnapshot()
        return self._snapshot_from_dict(data)

    def _snapshot_from_dict(self, data: dict[str, Any]) -> StatsSnapshot:
        dates = data.get("active_dates") or []
        if isinstance(dates, list):
            norm_dates = sorted({str(d) for d in dates if d})
        else:
            norm_dates = []
        return StatsSnapshot(
            version=int(data.get("version", STATS_SCHEMA_VERSION)),
            dictation_sessions=int(data.get("dictation_sessions", 0)),
            total_words=int(data.get("total_words", 0)),
            total_chars=int(data.get("total_chars", 0)),
            total_audio_seconds=float(data.get("total_audio_seconds", 0.0)),
            total_time_saved_seconds=float(data.get("total_time_saved_seconds", 0.0)),
            llm_runs=int(data.get("llm_runs", 0)),
            active_dates=norm_dates,
        )

    def _atomic_write_locked(self, snap: StatsSnapshot) -> None:
        import os

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(snap)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(prefix="stats_", suffix=".json", dir=str(self._path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(text)
            os.replace(tmp, self._path)
        except Exception:
            LOGGER.exception("Не удалось записать stats.json")
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass
