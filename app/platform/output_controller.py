"""Вывод текста через буфер обмена и эмуляцию вставки."""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import subprocess
import time
from pathlib import Path

import pyperclip
from pynput.keyboard import Controller, Key

from app.core.interfaces import OutputAdapter
from app.platform.macos_accessibility import macos_accessibility_trust_breakdown
from app.platform.macos_focus import get_macos_frontmost_app_name

LOGGER = logging.getLogger(__name__)

def _darwin_stderr_indicates_system_events_denied(stderr: str) -> bool:
    """True, если stderr osascript/System Events указывает на запрет отправки нажатий (типично 1002)."""
    if not stderr:
        return False
    low = stderr.casefold()
    if "1002" in stderr:
        return True
    if "not allowed to send" in low or "not allowed to assist" in low:
        return True
    if "не разрешена" in low or "не разрешено" in low:
        return True
    return False


def _paste_debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, object]) -> None:
    """NDJSON-отладка (без секретов), сессия ee7e85."""
    try:
        _log_path = "/Users/krasikov/projects/ghostwriter/.cursor/debug-ee7e85.log"
        Path(_log_path).parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "sessionId": "ee7e85",
            "runId": os.environ.get("GHOST_DEBUG_RUN_ID", "run1"),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(_log_path, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


_MACOS_PASTE_DENIED_HINT = (
    "macOS не разрешила автоматическую вставку (Cmd+V) для процесса Ghost Writer "
    "(тот интерпретатор Python / Terminal, из которого запущен main.py). "
    "Нужны два разных типа доступа: (1) «Универсальный доступ» — для этого же процесса; "
    "(2) если в логе ошибка System Events 1002 — «Автоматизация»: разрешите этому процессу "
    "управлять «System Events». Текст уже в буфере обмена — нажмите Cmd+V в поле ввода вручную."
)


def _darwin_paste_target_already_frontmost(target_app: str) -> bool:
    """True, если приложение с именем target_app уже на переднем плане (без учёта регистра)."""
    current = get_macos_frontmost_app_name()
    if not current:
        return False
    return target_app.strip().casefold() == current.strip().casefold()


def _darwin_use_process_targeted_paste(app_name: str) -> bool:
    """True для приложений на Electron (и похожих), где фокус поля легко теряется и activate помогает."""
    n = app_name.strip().casefold()
    if "cursor" in n or "windsurf" in n or "trae" in n:
        return True
    if n == "code" or "visual studio code" in n:
        return True
    if "chrome" in n or "obsidian" in n:
        return True
    return False


class ClipboardOutputController(OutputAdapter):
    """Вставляет текст в активное приложение через clipboard+paste."""

    def __init__(self) -> None:
        self._keyboard = Controller()
        self._last_darwin_paste_result: tuple[bool, str] | None = None

    def take_last_darwin_paste_result(self) -> tuple[bool, str] | None:
        """После `output_text` на macOS: (успех вставки, подсказка при неуспехе). Одноразовое чтение."""
        r = self._last_darwin_paste_result
        self._last_darwin_paste_result = None
        return r

    def copy_to_clipboard_without_paste(self, text: str) -> None:
        """Помещает текст в буфер без эмуляции вставки (например для тестов или ручной вставки)."""
        if not text:
            return
        if platform.system() == "Darwin":
            self._copy_to_clipboard_macos(text)
        else:
            pyperclip.copy(text)

    def set_last_darwin_paste_result(self, ok: bool, message: str = "") -> None:
        """Фиксирует результат вставки вручную (например после тестовой подмены адаптера вывода)."""
        self._last_darwin_paste_result = (ok, message)

    def output_text(self, text: str, paste_target_app: str | None = None) -> None:
        if not text:
            return

        if platform.system() == "Darwin":
            self._copy_to_clipboard_macos(text)
            time.sleep(0.14)
        else:
            pyperclip.copy(text)
            time.sleep(0.1)

        if platform.system() == "Darwin":
            if paste_target_app:
                LOGGER.info("Вставка в приложение с фокусом при записи: %s", paste_target_app)
            ok = self._darwin_activate_and_paste(paste_target_app)
            hint = _MACOS_PASTE_DENIED_HINT
            if not ok:
                bd = macos_accessibility_trust_breakdown()
                if bd.get("merged") is False:
                    hint += (
                        " Система сообщает, что для этого процесса нет доверия «Универсальный доступ» "
                        f"(исполняемый файл: {sys.executable}). "
                        "Включите именно его в настройках или снимите галочку и включите снова после обновления сборки."
                    )
            self._last_darwin_paste_result = (ok, "" if ok else hint)
            if not ok:
                LOGGER.error(
                    "Автовставка Cmd+V на macOS не удалась (см. ERROR выше: pynput/osascript). "
                    "Типично: «Универсальный доступ» для процесса, из которого запущен Ghost Writer, "
                    "и при ошибке System Events — «Автоматизация» → System Events.",
                )
            LOGGER.info(
                "Текст в буфере (%d симв.). Если в поле пусто — кликните в поле и Cmd+V.",
                len(text),
            )
            return

        try:
            with self._keyboard.pressed(Key.ctrl):
                self._keyboard.tap("v")
        except Exception as error:  # noqa: BLE001
            LOGGER.error(
                "Эмуляция Ctrl+V не удалась: %s",
                error,
                exc_info=True,
            )
            LOGGER.info(
                "Текст в буфере (%d симв.). Вставьте Ctrl+V вручную.",
                len(text),
            )

    def _copy_to_clipboard_macos_osascript(self, text: str) -> bool:
        """Копирует текст через AppleScript (NSString в pasteboard) — корректная кириллица в Notes и др. Cocoa.

        Сырой stdin в pbcopy иногда даёт «кракозябры» (UTF-8 читают как Latin-1). argv в osascript
        передаётся в Unicode и совпадает с тем, что ожидают нативные поля ввода.

        Args:
            text: Строка для буфера обмена.

        Returns:
            True, если буфер установлен без ошибки.
        """
        if len(text) > 200_000:
            return False
        script = (
            "on run argv\n"
            "  set the clipboard to item 1 of argv\n"
            "end run\n"
        )
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-e", script, "--", text],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode != 0:
                err = (result.stderr or "").strip()
                if err:
                    LOGGER.debug("osascript clipboard: %s", err[:300])
                return False
            return True
        except (OSError, subprocess.TimeoutExpired) as error:
            LOGGER.debug("osascript clipboard ошибка: %s", error)
            return False

    def _copy_to_clipboard_macos(self, text: str) -> None:
        """Копирует текст в буфер: AppleScript (предпочтительно для UTF-8), затем pbcopy, затем pyperclip."""
        if self._copy_to_clipboard_macos_osascript(text):
            return
        _utf8_env = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "LC_CTYPE": "en_US.UTF-8"}
        try:
            subprocess.run(
                ["pbcopy"],
                input=text.encode("utf-8"),
                check=True,
                timeout=10,
                env=_utf8_env,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            LOGGER.debug("pbcopy не сработал, pyperclip: %s", error)
            pyperclip.copy(text)

    def _run_osascript_meta(self, script: str, argv: list[str]) -> tuple[bool, str, str]:
        """Запуск osascript; возвращает (успех по returncode==0, stderr, stdout)."""
        cmd = ["/usr/bin/osascript", "-e", script]
        if argv:
            cmd.append("--")
            cmd.extend(argv)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            err = (result.stderr or "").strip()
            out = (result.stdout or "").strip()
            ok = result.returncode == 0
            if not ok:
                if err or out:
                    LOGGER.warning("osascript stderr: %s", err or out)
            elif err:
                LOGGER.debug("osascript (stderr при коде 0): %s", err)
            return ok, err, out
        except (OSError, subprocess.TimeoutExpired) as error:
            LOGGER.warning("osascript ошибка: %s", error)
            return False, str(error), ""

    def _run_osascript(self, script: str, argv: list[str]) -> bool:
        ok, _, _ = self._run_osascript_meta(script, argv)
        return ok

    def _darwin_paste_via_system_events_process(self, process_name: str) -> bool:
        """Cmd+V через System Events с явным frontmost процесса (имя как в «tell process»)."""
        script = (
            "on run argv\n"
            "  set pn to item 1 of argv\n"
            '  tell application "System Events"\n'
            "    tell process pn\n"
            "      set frontmost to true\n"
            "      delay 0.18\n"
            "    end tell\n"
            "    key code 9 using command down\n"
            "  end tell\n"
            "end run\n"
        )
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-e", script, "--", process_name],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            err = (result.stderr or "").strip()[:400]
            ok = result.returncode == 0
            if not ok and err:
                LOGGER.debug("process paste stderr: %s", err)
            return ok
        except (OSError, subprocess.TimeoutExpired) as error:
            LOGGER.debug("osascript process paste: %s", error)
            return False

    def _darwin_try_pynput_cmd_v(self) -> tuple[bool, str | None]:
        """Одна попытка Cmd+V через pynput. Возвращает (успех без исключения, имя исключения или None)."""
        try:
            time.sleep(0.05)
            with self._keyboard.pressed(Key.cmd):
                self._keyboard.tap("v")
            return True, None
        except Exception as error:  # noqa: BLE001
            LOGGER.error("pynput Cmd+V не удался: %s", error, exc_info=True)
            return False, type(error).__name__

    def _darwin_activate_and_paste(self, app_name: str | None) -> bool:
        """Активирует цель через AppleScript, затем вставка: при неуверенном отказе AX — ранний pynput; иначе System Events и запасной pynput при ошибке 1002.

        keystroke внутри tell process в AppleScript даёт код 0 без реальной вставки в Electron (Cursor);
        глобальный key code 9 (Cmd+V) после activate обычно срабатывает.
        Если System Events возвращает 1002 (osascript не может слать нажатия), успешный pynput от этого процесса
        всё равно принимается как успех вставки — это обход отказа AppleScript при наличии «Универсальный доступ».
        """
        if app_name:
            # Повторный activate того же приложения после долгого STT часто сбрасывает фокус
            # с поля заметки на список/поиск (Notes, Mail и т.д.) — Cmd+V уходит не туда.
            # Для Electron (Cursor, VS Code и т.д.) наоборот: окно уже спереди, но фокус в поле
            # мог потеряться — пропуск activate ухудшает вставку; всегда делаем tell … activate.
            skip_activate = _darwin_paste_target_already_frontmost(app_name) and not _darwin_use_process_targeted_paste(
                app_name
            )
            if skip_activate:
                LOGGER.info(
                    "Вставка: «%s» уже на переднем плане — пропускаем activate, чтобы не сбить фокус в поле ввода.",
                    app_name,
                )
                time.sleep(0.1)
            else:
                if _darwin_paste_target_already_frontmost(app_name) and _darwin_use_process_targeted_paste(app_name):
                    LOGGER.info(
                        "Вставка: «%s» уже на переднем плане — принудительная активация (Electron), "
                        "чтобы восстановить фокус в поле ввода.",
                        app_name,
                    )
                script_activate = (
                    "on run argv\n"
                    "  set procName to item 1 of argv\n"
                    "  tell application procName to activate\n"
                    "  delay 0.6\n"
                    "end run"
                )
                activated = self._run_osascript(script_activate, [app_name])
                if not activated:
                    LOGGER.warning("osascript не смог активировать «%s»", app_name)
        else:
            time.sleep(0.12)

        time.sleep(0.1)

        bd_ax = macos_accessibility_trust_breakdown()
        ax_trusted = bd_ax.get("merged")
        # region agent log
        _paste_debug_log(
            "P7",
            "output_controller.py:_darwin_activate_and_paste",
            "проверка AX trusted перед вставкой",
            {
                "target": app_name or "",
                "ax_pyobjc": bd_ax.get("pyobjc"),
                "ax_ctypes": bd_ax.get("ctypes"),
                "ax_merged": ax_trusted,
                "ax_merged_repr": "true"
                if ax_trusted is True
                else ("false" if ax_trusted is False else "none"),
                "executable_tail": (sys.executable or "")[-120:],
            },
        )
        # endregion
        # Ранний pynput только при явном True от AX: при merged=None pynput часто «молча» не вставляет,
        # но не бросает исключение — раньше это давало ложный успех и пропуск реальных путей (osascript).
        # Для Electron-IDE ранний pynput не используем: он часто «успешен» без исключения, но не вставляет
        # в поле — ниже нужен tell process + System Events.
        if ax_trusted is True and not (app_name and _darwin_use_process_targeted_paste(app_name)):
            early_ok, early_exc = self._darwin_try_pynput_cmd_v()
            if early_ok:
                # region agent log
                _paste_debug_log(
                    "P5",
                    "output_controller.py:_darwin_activate_and_paste",
                    "paste path: ранний pynput до System Events (AX trusted)",
                    {"target": app_name or "", "branch": "pynput_early", "ax_merged": ax_trusted},
                )
                # endregion
                return True
            # region agent log
            _paste_debug_log(
                "P6",
                "output_controller.py:_darwin_activate_and_paste",
                "ранний pynput не удался, продолжаем osascript",
                {"target": app_name or "", "branch": "early_pynput_failed", "exc": early_exc or ""},
            )
            # endregion

        # Cursor/VS Code: «голый» key code без привязки к процессу часто завершается с кодом 0, но текст не вставляется.
        if (
            app_name
            and _darwin_use_process_targeted_paste(app_name)
            and _darwin_paste_target_already_frontmost(app_name)
        ):
            if self._darwin_paste_via_system_events_process(app_name):
                return True

        script_keycode_paste = (
            'tell application "System Events"\n'
            "\tdelay 0.2\n"
            "\tkey code 9 using command down\n"
            "end tell"
        )
        keycode_ok, keycode_err, _kc_out = self._run_osascript_meta(script_keycode_paste, [])
        if keycode_ok:
            # region agent log
            _paste_debug_log(
                "P2",
                "output_controller.py:_darwin_activate_and_paste",
                "paste path: keycode System Events ok",
                {"target": app_name or "", "branch": "keycode"},
            )
            # endregion
            return True

        system_events_denied = _darwin_stderr_indicates_system_events_denied(keycode_err)

        pyn_ok, pyn_exc = self._darwin_try_pynput_cmd_v()
        pynput_exc_name: str | None = pyn_exc

        # Без явного доверия AX нельзя считать «pynput без исключения» успехом вставки: CGEventPost
        # часто просто не доставляет нажатие в другое приложение.
        # При отказе System Events (1002) дальнейший osascript с тем же API не поможет; если
        # pynput не выбросил исключение и AX доверен — считаем вставку через него.
        if pyn_ok and system_events_denied and ax_trusted is True:
            # region agent log
            _paste_debug_log(
                "P3b",
                "output_controller.py:_darwin_activate_and_paste",
                "paste path: pynput после отказа System Events (1002)",
                {
                    "target": app_name or "",
                    "branch": "pynput_after_se_denied",
                    "keycode_stderr_tail": keycode_err[:220],
                },
            )
            # endregion
            return True

        # Если System Events не сообщила об отказе (1002 и т.п.), а pynput отработал без
        # исключения — не используем результат последующего osascript с activate цели:
        # он часто падает по автоматизации приложения при уже успешной вставке через pynput.
        # Только при явном AX trusted — иначе это ложный успех (буфер заполнен, в поле пусто).
        if pyn_ok and not system_events_denied and ax_trusted is True:
            # region agent log
            _paste_debug_log(
                "P3",
                "output_controller.py:_darwin_activate_and_paste",
                "paste path: pynput ok, skip global activate fallback",
                {
                    "target": app_name or "",
                    "branch": "pynput_short_circuit",
                    "keycode_stderr_tail": keycode_err[:220],
                },
            )
            # endregion
            return True

        script_global_v = (
            "on run argv\n"
            "  set procName to item 1 of argv\n"
            "  tell application procName to activate\n"
            "  delay 0.7\n"
            '  tell application "System Events" to keystroke "v" using command down\n'
            "end run"
        )
        if app_name:
            ok, global_err, _ = self._run_osascript_meta(script_global_v, [app_name])
            if not ok:
                tail = (global_err or "").strip()[:800]
                LOGGER.error(
                    "osascript: activate «%s» + Cmd+V (global fallback) не удался: %s",
                    app_name,
                    tail or "(пустой stderr, см. WARNING выше от osascript)",
                )
            # region agent log
            _paste_debug_log(
                "P4",
                "output_controller.py:_darwin_activate_and_paste",
                "paste path: global activate+keystroke result",
                {
                    "branch": "global_v_activate",
                    "ok": ok,
                    "target": app_name,
                    "system_events_denied": system_events_denied,
                    "pynput_exc": pynput_exc_name or "",
                    "keycode_stderr_tail": keycode_err[:220],
                },
            )
            # endregion
            return ok
        script_se = (
            'tell application "System Events"\n'
            "\tdelay 0.12\n"
            '\tkeystroke "v" using command down\n'
            "end tell"
        )
        ok_se, se_err, _ = self._run_osascript_meta(script_se, [])
        if not ok_se:
            tail = (se_err or "").strip()[:800]
            LOGGER.error(
                "osascript: только System Events Cmd+V не удался: %s",
                tail or "(пустой stderr)",
            )
        # region agent log
        _paste_debug_log(
            "P4",
            "output_controller.py:_darwin_activate_and_paste",
            "paste path: System Events keystroke-only result",
            {
                "branch": "system_events_keystroke_only",
                "ok": ok_se,
                "target": "",
                "system_events_denied": system_events_denied,
                "pynput_exc": pynput_exc_name or "",
                "keycode_stderr_tail": keycode_err[:220],
            },
        )
        # endregion
        return ok_se
