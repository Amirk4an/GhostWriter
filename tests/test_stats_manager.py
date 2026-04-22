"""Тесты локальной статистики ``stats.json``."""

from __future__ import annotations

from pathlib import Path

from app.core.stats_manager import StatsManager, _estimate_time_saved_seconds, wav_audio_duration_seconds


def test_estimate_time_saved() -> None:
    # 40 слов при 40 WPM = 60 с «набора»; диктовка 15 с → 45 с выигрыша
    assert abs(_estimate_time_saved_seconds(40, 15.0, 40.0) - 45.0) < 1e-6
    assert _estimate_time_saved_seconds(0, 10.0, 40.0) == 0.0


def test_stats_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "stats.json"
    sm = StatsManager(path, typing_wpm=40.0)
    assert sm.load_snapshot().dictation_sessions == 0

    sm.record_successful_dictation(
        word_count=10,
        char_count=55,
        recorded_ms=5000.0,
        audio_seconds=3.0,
        llm_used=True,
    )
    snap = sm.load_snapshot()
    assert snap.dictation_sessions == 1
    assert snap.total_words == 10
    assert snap.total_chars == 55
    assert snap.total_audio_seconds == 3.0
    assert snap.llm_runs == 1
    assert len(snap.active_dates) == 1

    sm2 = StatsManager(path)
    snap2 = sm2.load_snapshot()
    assert snap2.total_words == 10


def test_wav_duration_minimal_wav(tmp_path: Path) -> None:
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    dur = wav_audio_duration_seconds(buf.getvalue())
    assert dur is not None
    assert abs(dur - 1.0) < 0.05


def test_snapshot_from_dict_normalizes_dates(tmp_path: Path) -> None:
    sm = StatsManager(tmp_path / "unused.json")
    snap = sm._snapshot_from_dict(  # noqa: SLF001
        {
            "active_dates": ["2026-04-01", "2026-04-01", "2026-04-02"],
        }
    )
    assert snap.active_dates == ["2026-04-01", "2026-04-02"]
