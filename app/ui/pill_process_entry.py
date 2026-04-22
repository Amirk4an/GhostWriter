"""
Точка входа дочернего процесса плавающего pill (multiprocessing spawn).

Модуль не импортирует ``main`` и не поднимает ядро: только ленивый запуск UI pill.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing.queues import Queue as MPQueue


def run_floating_pill_process(
    pill_queue: "MPQueue",
    pill_command_queue: "MPQueue",
    app_name: str,
    primary_color: str,
) -> None:
    """
    Запускает цикл pill в отдельном процессе (Tk/AppKit только здесь).

    Команды с шестерёнки уходят в ``pill_command_queue`` и обрабатываются **основным**
    процессом (``main_runtime``): открытие дашборда или поднятие уже открытого окна.

    Args:
        pill_queue: Очередь статусов в pill.
        pill_command_queue: Очередь команд из pill в основной процесс.
        app_name: Имя приложения из конфига.
        primary_color: Акцентный цвет из конфига.
    """
    from app.ui.floating_pill import run_floating_pill_loop_mp

    run_floating_pill_loop_mp(pill_queue, pill_command_queue, app_name, primary_color)
