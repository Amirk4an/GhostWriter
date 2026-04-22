"""
Точка входа CLI для дашборда (отладка без полного приложения).

Запуск из каталога проекта::

    python3 -m app.ui.dashboard_child_main /абсолютный/путь/config.json

В штатном режиме дашборд поднимается из ``main.py`` через ``multiprocessing.Process``
(``run_dashboard_process`` в ``dashboard_process.py``), чтобы не повторно запускать ядро.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """
    Читает путь к ``config.json`` из ``argv[1]`` и открывает дашборд.

    Args:
        argv: Аргументы командной строки (по умолчанию ``sys.argv``).

    Returns:
        Код выхода процесса (0 при нормальном завершении UI).
    """
    argv = argv if argv is not None else sys.argv
    if len(argv) < 2:
        print("Использование: python3 -m app.ui.dashboard_child_main <путь-к-config.json>", file=sys.stderr)
        return 2
    from app.platform.gui_availability import skip_tkinter_gui

    if skip_tkinter_gui():
        print(
            "Дашборд не запущен: установлена переменная GHOSTWRITER_HEADLESS (нет GUI-сессии).",
            file=sys.stderr,
        )
        return 0
    from app.ui.dashboard_process import run_dashboard_app

    run_dashboard_app(argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
