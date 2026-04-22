"""Точка входа VoiceFlow WL — запуск из консоли: python3 main.py (на macOS часто нет команды python)."""

from __future__ import annotations

import sys


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    multiprocessing.set_start_method("spawn", force=True)

    # Страховка: не поднимать трей и ядро в дочернем контексте, если блок __main__ выполнился бы ошибочно.
    if multiprocessing.parent_process() is not None:
        sys.exit(0)

    from app.main_runtime import run_voiceflow_application

    run_voiceflow_application()
