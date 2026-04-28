"""
Главное окно-дашборд (CustomTkinter): боковое меню и вкладки Home / Dictionary / History / Journal / Settings.

В дочернем процессе используется только ``ConfigManager`` (своя память, конфиг с диска).
Никаких вызовов Tk/CustomTkinter на уровне модуля: импорт ``customtkinter`` и виджеты
создаются только внутри ``MainDashboard.__init__`` после появления корневого ``CTk``.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from app.core.api_selftest import test_llm_connection, test_stt_connection
from app.core.provider_credentials import (
    ALLOWED_MODEL_PROVIDERS,
    ALLOWED_WHISPER_BACKENDS,
    all_known_secret_env_names,
    iter_needed_secret_names,
)

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager

LOGGER = logging.getLogger(__name__)

# Порядок в меню model_provider (остальные из ALLOWED_MODEL_PROVIDERS добавятся в конец).
_MODEL_PROVIDER_MENU_ORDER = (
    "openai",
    "groq",
    "anthropic",
    "gemini",
    "google",
    "openrouter",
    "ollama",
    "mistral",
    "cohere",
)

# Пресеты llm_model по провайдеру (пользователь может оставить своё значение из config — оно подмешивается в меню).
_LLM_MODEL_PRESETS: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
    "groq": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-flash"],
    "google": ["gemini-2.0-flash", "gemini-1.5-flash"],
    "openrouter": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
    "ollama": ["llama3.1", "mistral"],
    "mistral": ["mistral-small-latest", "mistral-large-latest"],
    "cohere": ["command-r-plus"],
}

_WHISPER_MODEL_HINTS = (
    "local: не используется для API. openai: whisper-1. groq: whisper-large-v3-turbo. deepgram: nova-2."
)


def _mask_secret(value: str | None, visible_tail: int = 4) -> str:
    """Маскирует секрет для отображения (ключи только из окружения)."""
    if not value:
        return "не задан"
    v = value.strip()
    if len(v) <= visible_tail:
        return "••••"
    return "•" * max(8, len(v) - visible_tail) + v[-visible_tail:]


class MainDashboard:
    """
    Собирает UI дашборда внутри переданного корня ``CTk``.

    ``StringVar``, шрифты и прочие объекты Tk создаются только здесь, после того как
    в процессе уже создан ``root = ctk.CTk()``.
    """

    def __init__(
        self,
        root: Any,
        config_manager: "ConfigManager",
        host_command_queue: Any | None = None,
    ) -> None:
        if getattr(root, "_gw_dashboard_mounted", False):
            return
        root._gw_dashboard_mounted = True  # noqa: SLF001

        import customtkinter as ctk

        from app.platform.audio_devices import list_audio_input_devices, validate_audio_input_index
        from app.ui.ctk_macos_theme import preferred_ui_font
        from app.ui.hotkey_capture import bind_hotkey_capture
        from app.ui.pill_ipc import reload_config_message

        cfg = config_manager.config
        self._host_command_queue = host_command_queue
        title_font = preferred_ui_font(18, "bold", master=root)
        body_font = preferred_ui_font(13, master=root)
        small_font = preferred_ui_font(11, master=root)

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(
            root,
            fg_color=("#2C2C2E", "#2C2C2E"),
            corner_radius=0,
            width=220,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        brand = ctk.CTkLabel(
            sidebar,
            text=cfg.app_name,
            font=title_font,
            text_color=("#F2F2F7", "#F2F2F7"),
        )
        brand.pack(anchor="w", padx=18, pady=(24, 8))

        main_area = ctk.CTkFrame(root, fg_color=("#1C1C1E", "#1C1C1E"), corner_radius=0)
        main_area.grid(row=0, column=1, sticky="nsew")
        main_area.grid_columnconfigure(0, weight=1)
        main_area.grid_rowconfigure(0, weight=1)

        pages: dict[str, ctk.CTkFrame] = {}
        nav_buttons: list[ctk.CTkButton] = []
        current_page: list[str] = ["home"]

        from app.core.mic_meter_controller import DashboardMicMeter

        mic_meter = DashboardMicMeter()
        root._gw_mic_meter = mic_meter  # noqa: SLF001 — остановка при закрытии окна дашборда

        home = ctk.CTkScrollableFrame(main_area, fg_color="transparent")
        pages["home"] = home
        home.grid_columnconfigure(0, weight=1)

        from app.core.stats_manager import REFERENCE_EPIC_WORDS, StatsManager, default_stats_json_path

        _stats_json_path = default_stats_json_path()

        def _format_ru_int(n: int) -> str:
            return f"{int(n):,}".replace(",", " ")

        def _format_saved_time(sec: float) -> str:
            s = max(0, int(round(sec)))
            if s < 60:
                return f"{s} с"
            h, r = divmod(s, 3600)
            m, se = divmod(r, 60)
            parts: list[str] = []
            if h:
                parts.append(f"{h} ч")
            if m or h:
                parts.append(f"{m} мин")
            parts.append(f"{se} с")
            return " ".join(parts)

        def _format_audio_minutes(sec: float) -> str:
            if sec < 60:
                return f"{sec:.1f} с"
            return f"{sec / 60.0:.1f} мин"

        def refresh_home_stats() -> None:
            snap = StatsManager(_stats_json_path).load_snapshot()
            home_saved_lbl.configure(text=_format_saved_time(snap.total_time_saved_seconds))
            home_words_lbl.configure(text=_format_ru_int(snap.total_words))
            home_chars_lbl.configure(text=_format_ru_int(snap.total_chars))
            home_sessions_lbl.configure(text=_format_ru_int(snap.dictation_sessions))
            home_days_lbl.configure(text=_format_ru_int(snap.active_days_count))
            home_audio_lbl.configure(text=_format_audio_minutes(snap.total_audio_seconds))
            home_llm_lbl.configure(text=_format_ru_int(snap.llm_runs))
            epic = snap.total_words / float(REFERENCE_EPIC_WORDS) if REFERENCE_EPIC_WORDS else 0.0
            if epic >= 0.05:
                home_epic_lbl.configure(
                    text=(
                        f"≈ {epic:.1f} условного «тома» крупного романа "
                        f"(~{REFERENCE_EPIC_WORDS // 1000} тыс. слов)"
                    )
                )
            else:
                home_epic_lbl.configure(text="")

        def _stat_value_card(parent: Any, title: str, value_font: Any) -> tuple[Any, Any]:
            card = ctk.CTkFrame(
                parent,
                fg_color=("#2C2C2E", "#2C2C2E"),
                corner_radius=14,
                border_width=1,
                border_color=("#48484A", "#48484A"),
            )
            ctk.CTkLabel(card, text=title, font=small_font, text_color="#AEAEB2").pack(
                anchor="w", padx=14, pady=(12, 4)
            )
            val = ctk.CTkLabel(card, text="—", font=value_font, text_color="#F2F2F7")
            val.pack(anchor="w", padx=14, pady=(0, 12))
            return card, val

        section_font = preferred_ui_font(14, "bold", master=root)
        hero_value_font = preferred_ui_font(22, "bold", master=root)
        mid_value_font = preferred_ui_font(18, "bold", master=root)

        ctk.CTkLabel(home, text="Ценность для вас", font=section_font, text_color="#F2F2F7").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        value_row = ctk.CTkFrame(home, fg_color="transparent")
        value_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        value_row.grid_columnconfigure((0, 1, 2), weight=1, uniform="stat")

        card_saved, home_saved_lbl = _stat_value_card(value_row, "Сэкономлено времени*", hero_value_font)
        card_saved.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        card_words, home_words_lbl = _stat_value_card(value_row, "Слов надиктовано", mid_value_font)
        card_words.grid(row=0, column=1, sticky="nsew", padx=6)
        card_sess, home_sessions_lbl = _stat_value_card(value_row, "Сессий диктовки", mid_value_font)
        card_sess.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        home_epic_lbl = ctk.CTkLabel(
            home,
            text="",
            font=small_font,
            text_color="#8E8E93",
            wraplength=900,
            justify="left",
        )
        home_epic_lbl.grid(row=2, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(
            home,
            text=(
                "*Оценка: время набора при ~40 слов/мин минус длительность записи голоса. "
                "Не учитывает правки после вставки."
            ),
            font=small_font,
            text_color="#636366",
            wraplength=900,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(0, 14))

        ctk.CTkLabel(home, text="Активность", font=section_font, text_color="#F2F2F7").grid(
            row=4, column=0, sticky="w", pady=(0, 8)
        )
        act_row = ctk.CTkFrame(home, fg_color="transparent")
        act_row.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        act_row.grid_columnconfigure((0, 1), weight=1, uniform="act")
        card_days, home_days_lbl = _stat_value_card(act_row, "Дней с диктовкой", mid_value_font)
        card_days.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        card_chars, home_chars_lbl = _stat_value_card(act_row, "Символов всего", mid_value_font)
        card_chars.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        ctk.CTkLabel(home, text="Технический контроль", font=section_font, text_color="#F2F2F7").grid(
            row=6, column=0, sticky="w", pady=(0, 8)
        )
        tech_row = ctk.CTkFrame(home, fg_color="transparent")
        tech_row.grid(row=7, column=0, sticky="ew", pady=(0, 12))
        tech_row.grid_columnconfigure((0, 1), weight=1, uniform="tech")
        card_audio, home_audio_lbl = _stat_value_card(tech_row, "Аудио на STT (накопленно)", body_font)
        card_audio.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        card_llm, home_llm_lbl = _stat_value_card(tech_row, "Проходов через LLM", body_font)
        card_llm.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        style_card = ctk.CTkFrame(
            home,
            fg_color=("#2C2C2E", "#2C2C2E"),
            corner_radius=14,
            border_width=1,
            border_color=("#48484A", "#48484A"),
        )
        style_card.grid(row=8, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(style_card, text="Style", font=title_font, text_color="#F2F2F7").pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        ctk.CTkLabel(
            style_card,
            text="Настройка стиля написания появится здесь (заглушка).",
            font=body_font,
            text_color="#AEAEB2",
            wraplength=640,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        dictionary = ctk.CTkFrame(main_area, fg_color="transparent")
        pages["dictionary"] = dictionary
        ctk.CTkLabel(
            dictionary,
            text="Dictionary",
            font=title_font,
            text_color="#F2F2F7",
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            dictionary,
            text="Словарь и пользовательский глоссарий — в разработке.",
            font=body_font,
            text_color="#AEAEB2",
            wraplength=700,
            justify="left",
        ).pack(anchor="w")

        import pyperclip

        from app.core.history_manager import HistoryManager, default_history_db_path
        from app.core.journal_manager import JournalManager

        _history_db_path = default_history_db_path()
        history_store_ui = HistoryManager(_history_db_path)
        history_store_ui.init_schema()
        journal_store_ui = JournalManager(_history_db_path)
        journal_store_ui.init_schema()

        history = ctk.CTkScrollableFrame(main_area, fg_color="transparent")
        pages["history"] = history
        history.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(history, text="История диктовок", font=title_font, text_color="#F2F2F7").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        ctk.CTkLabel(
            history,
            text=(
                "Последние 50 записей. Данные только на этом компьютере (SQLite). "
                f"Файл: {_history_db_path}"
            ),
            font=small_font,
            text_color="#8E8E93",
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        history_cards_host = ctk.CTkFrame(history, fg_color="transparent")
        history_cards_host.grid(row=2, column=0, sticky="ew")

        def _format_history_timestamp(iso_ts: str) -> str:
            from datetime import date, datetime

            try:
                ts = datetime.fromisoformat(iso_ts)
            except ValueError:
                return iso_ts[:19]
            local = ts.astimezone() if ts.tzinfo else ts
            today = date.today()
            if local.date() == today:
                return f"Сегодня, {local.strftime('%H:%M')}"
            if (today - local.date()).days == 1:
                return f"Вчера, {local.strftime('%H:%M')}"
            return local.strftime("%d.%m.%Y %H:%M")

        def _copy_clipboard_safe(text: str) -> None:
            try:
                pyperclip.copy(text)
            except Exception:
                LOGGER.warning("Не удалось скопировать в буфер обмена", exc_info=True)

        def refresh_history_ui() -> None:
            if not root.winfo_exists():
                return
            for w in history_cards_host.winfo_children():
                w.destroy()
            try:
                recs = history_store_ui.list_recent(50)
            except Exception:
                LOGGER.exception("Чтение истории диктовок")
                recs = []
            if not recs:
                ctk.CTkLabel(
                    history_cards_host,
                    text="Пока нет записей. После успешной диктовки текст появится здесь.",
                    font=body_font,
                    text_color="#AEAEB2",
                ).pack(anchor="w", pady=12)
                return
            for rec in recs:
                card = ctk.CTkFrame(
                    history_cards_host,
                    fg_color=("#2C2C2E", "#2C2C2E"),
                    corner_radius=12,
                    border_width=1,
                    border_color=("#48484A", "#48484A"),
                )
                card.pack(fill="x", pady=(0, 10), padx=2)
                target = rec.target_app.strip() or "—"
                head = f"{_format_history_timestamp(rec.created_at)}  ·  {target}"
                ctk.CTkLabel(card, text=head, font=small_font, text_color="#8E8E93").pack(
                    anchor="w", padx=12, pady=(10, 4)
                )
                body = rec.final_text or ""
                preview = body if len(body) <= 520 else body[:520] + "…"
                ctk.CTkLabel(
                    card,
                    text=preview,
                    font=body_font,
                    text_color="#E5E5EA",
                    wraplength=700,
                    justify="left",
                ).pack(anchor="w", padx=12, pady=(0, 8))
                btn_row = ctk.CTkFrame(card, fg_color="transparent")
                btn_row.pack(fill="x", padx=8, pady=(0, 10))
                ctk.CTkButton(
                    btn_row,
                    text="Копировать итог",
                    width=150,
                    height=32,
                    font=body_font,
                    fg_color=("#3A3A3C", "#3A3A3C"),
                    command=lambda t=rec.final_text: _copy_clipboard_safe(t),
                ).pack(side="left", padx=4)
                ctk.CTkButton(
                    btn_row,
                    text="Копировать сырой",
                    width=150,
                    height=32,
                    font=body_font,
                    fg_color=("#3A3A3C", "#3A3A3C"),
                    command=lambda t=rec.raw_text: _copy_clipboard_safe(t),
                ).pack(side="left", padx=4)

        journal = ctk.CTkFrame(main_area, fg_color="transparent")
        pages["journal"] = journal
        journal.grid_columnconfigure(0, weight=0, minsize=220)
        journal.grid_columnconfigure(1, weight=1)
        journal.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(journal, text="Ежедневник", font=title_font, text_color="#F2F2F7").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        ctk.CTkLabel(
            journal,
            text=f"Записи в том же файле SQLite: {_history_db_path}",
            font=small_font,
            text_color="#8E8E93",
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        journal_filter_var = ctk.StringVar(value="Все")

        def _journal_ts_label(iso_ts: str) -> str:
            from datetime import date, datetime

            try:
                ts = datetime.fromisoformat(iso_ts)
            except ValueError:
                return iso_ts[:19]
            local = ts.astimezone() if ts.tzinfo else ts
            today = date.today()
            if local.date() == today:
                return f"Сегодня {local.strftime('%H:%M')}"
            if (today - local.date()).days == 1:
                return f"Вчера {local.strftime('%H:%M')}"
            return local.strftime("%d.%m.%Y %H:%M")

        journal_sidebar = ctk.CTkScrollableFrame(journal, fg_color=("#2C2C2E", "#2C2C2E"), corner_radius=12)
        journal_sidebar.grid(row=3, column=0, sticky="nsew", padx=(0, 10), pady=(0, 0))

        journal_detail_host = ctk.CTkScrollableFrame(journal, fg_color=("#2C2C2E", "#2C2C2E"), corner_radius=12)
        journal_detail_host.grid(row=3, column=1, sticky="nsew")
        journal_detail_host.grid_columnconfigure(0, weight=1)

        journal_selected_id: list[int | None] = [None]

        title_var = ctk.StringVar(value="")
        tags_edit_var = ctk.StringVar(value="")

        def _journal_filter_values() -> list[str]:
            tags = ["Все"] + journal_store_ui.list_distinct_tags(limit=80)
            return tags

        journal_filter_menu = ctk.CTkOptionMenu(
            journal,
            values=_journal_filter_values(),
            variable=journal_filter_var,
            font=body_font,
            width=200,
            fg_color=("#3A3A3C", "#3A3A3C"),
            button_color=("#48484A", "#48484A"),
        )
        journal_filter_menu.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

        def refresh_journal_filter_menu() -> None:
            journal_filter_menu.configure(values=_journal_filter_values())
            cur = journal_filter_var.get()
            if cur not in journal_filter_menu.cget("values"):
                journal_filter_var.set("Все")

        advice_box = ctk.CTkTextbox(journal_detail_host, font=body_font, height=72, wrap="word")
        refined_box = ctk.CTkTextbox(journal_detail_host, font=body_font, height=140, wrap="word")
        raw_box = ctk.CTkTextbox(journal_detail_host, font=body_font, height=100, wrap="word")

        def _clear_journal_detail_form() -> None:
            journal_selected_id[0] = None
            title_var.set("")
            tags_edit_var.set("")
            for box in (advice_box, refined_box, raw_box):
                box.configure(state="normal")
                box.delete("1.0", "end")
                box.configure(state="disabled")

        def _load_journal_detail(entry_id: int) -> None:
            ent = journal_store_ui.get(entry_id)
            if ent is None:
                _clear_journal_detail_form()
                return
            journal_selected_id[0] = entry_id
            title_var.set(ent.title)
            tags_edit_var.set(", ".join(ent.tags_list()))
            for box in (advice_box, refined_box, raw_box):
                box.configure(state="normal")
                box.delete("1.0", "end")
            advice_box.insert("1.0", ent.advice)
            refined_box.insert("1.0", ent.refined_text)
            raw_box.insert("1.0", ent.raw_text)
            for box in (advice_box, refined_box, raw_box):
                box.configure(state="normal")

        def refresh_journal_sidebar() -> None:
            if not root.winfo_exists():
                return
            for w in journal_sidebar.winfo_children():
                w.destroy()
            tag_sel = journal_filter_var.get().strip()
            filt: str | None = None if tag_sel in ("", "Все") else tag_sel
            try:
                items = journal_store_ui.list_recent(limit=200, tag_filter=filt)
            except Exception:
                LOGGER.exception("Чтение дневника")
                items = []
            if not items:
                ctk.CTkLabel(
                    journal_sidebar,
                    text="Пока нет записей. Используйте journal hotkey в приложении.",
                    font=body_font,
                    text_color="#AEAEB2",
                    wraplength=200,
                    justify="left",
                ).pack(anchor="w", padx=8, pady=12)
                _clear_journal_detail_form()
                return
            for ent in items:
                line = f"{ent.title or 'Без названия'}\n{_journal_ts_label(ent.created_at)}"

                def _make_pick(eid: int) -> object:
                    return lambda: _load_journal_detail(eid)

                btn = ctk.CTkButton(
                    journal_sidebar,
                    text=line,
                    font=small_font,
                    anchor="w",
                    height=56,
                    fg_color=("#3A3A3C", "#3A3A3C"),
                    hover_color=("#48484A", "#48484A"),
                    command=_make_pick(ent.id),
                )
                btn.pack(fill="x", padx=6, pady=4)

        def on_journal_filter_change(_choice: str) -> None:
            refresh_journal_sidebar()

        journal_filter_menu.configure(command=on_journal_filter_change)

        def save_journal_edits() -> None:
            eid = journal_selected_id[0]
            if eid is None:
                return
            raw_tags = [t.strip() for t in tags_edit_var.get().split(",") if t.strip()][:10]
            try:
                journal_store_ui.update(
                    eid,
                    title=title_var.get().strip(),
                    tags=raw_tags,
                    advice=advice_box.get("1.0", "end").strip(),
                    refined_text=refined_box.get("1.0", "end").strip(),
                    raw_text=raw_box.get("1.0", "end").strip(),
                )
            except Exception:
                LOGGER.exception("Сохранение записи дневника")
                return
            refresh_journal_filter_menu()
            refresh_journal_sidebar()
            _load_journal_detail(eid)

        row_d = 0
        ctk.CTkLabel(journal_detail_host, text="Заголовок", font=small_font, text_color="#AEAEB2").grid(
            row=row_d, column=0, sticky="w", padx=12, pady=(12, 2)
        )
        row_d += 1
        ctk.CTkEntry(journal_detail_host, textvariable=title_var, font=body_font).grid(
            row=row_d, column=0, sticky="ew", padx=12, pady=(0, 8)
        )
        row_d += 1
        ctk.CTkLabel(journal_detail_host, text="Теги (через запятую)", font=small_font, text_color="#AEAEB2").grid(
            row=row_d, column=0, sticky="w", padx=12, pady=(0, 2)
        )
        row_d += 1
        ctk.CTkEntry(journal_detail_host, textvariable=tags_edit_var, font=body_font).grid(
            row=row_d, column=0, sticky="ew", padx=12, pady=(0, 8)
        )
        row_d += 1
        ctk.CTkLabel(journal_detail_host, text="Совет", font=small_font, text_color="#AEAEB2").grid(
            row=row_d, column=0, sticky="w", padx=12, pady=(0, 2)
        )
        row_d += 1
        advice_box.grid(row=row_d, column=0, sticky="ew", padx=12, pady=(0, 8))
        row_d += 1
        ctk.CTkLabel(journal_detail_host, text="Текст заметки", font=small_font, text_color="#AEAEB2").grid(
            row=row_d, column=0, sticky="w", padx=12, pady=(0, 2)
        )
        row_d += 1
        refined_box.grid(row=row_d, column=0, sticky="ew", padx=12, pady=(0, 8))
        row_d += 1
        ctk.CTkLabel(journal_detail_host, text="Сырой транскрипт", font=small_font, text_color="#AEAEB2").grid(
            row=row_d, column=0, sticky="w", padx=12, pady=(0, 2)
        )
        row_d += 1
        raw_box.grid(row=row_d, column=0, sticky="ew", padx=12, pady=(0, 8))
        row_d += 1
        ctk.CTkButton(
            journal_detail_host,
            text="Сохранить изменения",
            font=body_font,
            height=36,
            fg_color=("#3A3A3C", "#3A3A3C"),
            command=save_journal_edits,
        ).grid(row=row_d, column=0, sticky="w", padx=12, pady=(0, 16))
        _clear_journal_detail_form()

        settings = ctk.CTkScrollableFrame(main_area, fg_color="transparent")
        pages["settings"] = settings
        settings.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(settings, text="Settings", font=title_font, text_color="#F2F2F7").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )

        sec_title_font = preferred_ui_font(15, "bold", master=root)

        def _settings_section_card(row: int, title: str) -> Any:
            card = ctk.CTkFrame(
                settings,
                fg_color=("#2C2C2E", "#2C2C2E"),
                corner_radius=14,
                border_width=1,
                border_color=("#48484A", "#48484A"),
            )
            card.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            ctk.CTkLabel(card, text=title, font=sec_title_font, text_color="#F2F2F7").pack(
                anchor="w", padx=16, pady=(14, 6)
            )
            return card

        hotkeys_card = _settings_section_card(1, "⌨️ Управление (хоткеи)")
        ctk.CTkLabel(
            hotkeys_card,
            text="Кликните в поле и нажмите сочетание. Escape — очистить поле. Вставка из буфера: Cmd/Ctrl+V.",
            font=small_font,
            text_color="#8E8E93",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        var_hotkey = ctk.StringVar(value=cfg.hotkey or "")
        var_journal_hk = ctk.StringVar(value=cfg.journal_hotkey or "")
        var_cmd_hk = ctk.StringVar(value=cfg.command_mode_hotkey or "")

        def _hotkey_field(parent: Any, label: str, var: Any) -> None:
            row_f = ctk.CTkFrame(parent, fg_color="transparent")
            row_f.pack(fill="x", padx=16, pady=(0, 8))
            ctk.CTkLabel(row_f, text=label, font=body_font, text_color="#E5E5EA").pack(anchor="w")
            ent = ctk.CTkEntry(row_f, textvariable=var, font=body_font, height=32)
            ent.pack(fill="x", pady=(4, 0))
            bind_hotkey_capture(ent, var.set)

        _hotkey_field(hotkeys_card, "Основной хоткей (dictation)", var_hotkey)
        _hotkey_field(hotkeys_card, "Дневник (journal_hotkey)", var_journal_hk)
        _hotkey_field(hotkeys_card, "Командный режим (command_mode_hotkey)", var_cmd_hk)

        ai_card = _settings_section_card(2, "🧠 ИИ и промпты")
        llm_sw = ctk.CTkSwitch(ai_card, text="Включить LLM (llm_enabled)", font=body_font, progress_color=("#34C759", "#34C759"))
        if cfg.llm_enabled:
            llm_sw.select()
        else:
            llm_sw.deselect()
        llm_sw.pack(anchor="w", padx=16, pady=(0, 10))

        _mp_menu_values = [p for p in _MODEL_PROVIDER_MENU_ORDER if p in ALLOWED_MODEL_PROVIDERS] + sorted(
            ALLOWED_MODEL_PROVIDERS - set(_MODEL_PROVIDER_MENU_ORDER)
        )
        _mp_init = cfg.model_provider if cfg.model_provider in ALLOWED_MODEL_PROVIDERS else "openai"
        model_provider_var = ctk.StringVar(value=_mp_init)
        ctk.CTkLabel(ai_card, text="Провайдер LLM (model_provider)", font=small_font, text_color="#AEAEB2").pack(
            anchor="w", padx=16
        )
        model_provider_menu = ctk.CTkOptionMenu(
            ai_card,
            values=_mp_menu_values,
            variable=model_provider_var,
            font=body_font,
            width=220,
            fg_color=("#3A3A3C", "#3A3A3C"),
            button_color=("#48484A", "#48484A"),
        )
        model_provider_menu.pack(anchor="w", padx=16, pady=(4, 8))

        ctk.CTkLabel(ai_card, text="Модель LLM (llm_model)", font=small_font, text_color="#AEAEB2").pack(anchor="w", padx=16)
        llm_model_var = ctk.StringVar(value=cfg.llm_model or "gpt-4o-mini")

        def _llm_preset_list_for(provider: str) -> list[str]:
            base = list(_LLM_MODEL_PRESETS.get(provider, []))
            cur = (llm_model_var.get() or "").strip()
            if cur and cur not in base:
                base.insert(0, cur)
            return base if base else [cur or "gpt-4o-mini"]

        llm_model_menu = ctk.CTkOptionMenu(
            ai_card,
            values=_llm_preset_list_for(_mp_init),
            variable=llm_model_var,
            font=body_font,
            width=320,
            fg_color=("#3A3A3C", "#3A3A3C"),
            button_color=("#48484A", "#48484A"),
        )
        llm_model_menu.pack(anchor="w", padx=16, pady=(4, 10))

        def _on_model_provider_change(_: str | None = None) -> None:
            prov = model_provider_var.get().strip().lower()
            vals = _llm_preset_list_for(prov)
            llm_model_menu.configure(values=vals)
            if vals and llm_model_var.get() not in vals:
                llm_model_var.set(str(vals[0]))

        model_provider_menu.configure(command=_on_model_provider_change)
        ctk.CTkLabel(ai_card, text="system_prompt", font=small_font, text_color="#AEAEB2").pack(anchor="w", padx=16)
        system_prompt_box = ctk.CTkTextbox(ai_card, height=110, font=body_font, wrap="word")
        system_prompt_box.pack(fill="x", padx=16, pady=(4, 8))
        system_prompt_box.insert("1.0", cfg.system_prompt)
        ctk.CTkLabel(ai_card, text="journal_system_prompt", font=small_font, text_color="#AEAEB2").pack(
            anchor="w", padx=16
        )
        journal_prompt_box = ctk.CTkTextbox(ai_card, height=110, font=body_font, wrap="word")
        journal_prompt_box.pack(fill="x", padx=16, pady=(4, 12))
        journal_prompt_box.insert("1.0", cfg.journal_system_prompt)

        stt_card = _settings_section_card(3, "🎙 Распознавание (Speech-to-Text)")
        ctk.CTkLabel(stt_card, text="Движок (whisper_backend)", font=small_font, text_color="#AEAEB2").pack(
            anchor="w", padx=16
        )
        _wb_values = sorted(ALLOWED_WHISPER_BACKENDS)
        whisper_var = ctk.StringVar(
            value=cfg.whisper_backend if cfg.whisper_backend in ALLOWED_WHISPER_BACKENDS else "local"
        )
        ctk.CTkOptionMenu(
            stt_card,
            values=_wb_values,
            variable=whisper_var,
            font=body_font,
            width=200,
            fg_color=("#3A3A3C", "#3A3A3C"),
            button_color=("#48484A", "#48484A"),
        ).pack(anchor="w", padx=16, pady=(4, 4))
        ctk.CTkLabel(
            stt_card,
            text=(
                "После «Сохранить» основной процесс перечитывает конфиг и пересоздаёт STT/LLM "
                "(перезапуск приложения не нужен)."
            ),
            font=small_font,
            text_color="#8E8E93",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 6))
        ctk.CTkLabel(stt_card, text="Модель STT (whisper_model)", font=small_font, text_color="#AEAEB2").pack(
            anchor="w", padx=16
        )
        whisper_model_var = ctk.StringVar(value=cfg.whisper_model or "")
        ctk.CTkEntry(stt_card, textvariable=whisper_model_var, font=body_font, height=32).pack(
            fill="x", padx=16, pady=(4, 4)
        )
        ctk.CTkLabel(
            stt_card,
            text=_WHISPER_MODEL_HINTS,
            font=small_font,
            text_color="#8E8E93",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        ctk.CTkLabel(stt_card, text="Язык (language)", font=small_font, text_color="#AEAEB2").pack(anchor="w", padx=16)
        _lang_init = "auto" if cfg.language is None else cfg.language
        if _lang_init not in ("ru", "en", "auto"):
            _lang_init = "ru"
        lang_var = ctk.StringVar(value=_lang_init)
        ctk.CTkOptionMenu(
            stt_card,
            values=["ru", "en", "auto"],
            variable=lang_var,
            font=body_font,
            width=200,
            fg_color=("#3A3A3C", "#3A3A3C"),
            button_color=("#48484A", "#48484A"),
        ).pack(anchor="w", padx=16, pady=(4, 12))

        ui_card = _settings_section_card(4, "Внешний вид")
        pill_sw = ctk.CTkSwitch(
            ui_card,
            text="Плавающий индикатор (floating_pill_enabled)",
            font=body_font,
            progress_color=("#34C759", "#34C759"),
        )
        if cfg.floating_pill_enabled:
            pill_sw.select()
        else:
            pill_sw.deselect()
        pill_sw.pack(anchor="w", padx=16, pady=(0, 12))
        ctk.CTkLabel(
            ui_card,
            text="Смена pill вступит в силу после перезапуска приложения.",
            font=small_font,
            text_color="#8E8E93",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        def sync_settings_widgets() -> None:
            c = config_manager.config
            var_hotkey.set(c.hotkey or "")
            var_journal_hk.set(c.journal_hotkey or "")
            var_cmd_hk.set(c.command_mode_hotkey or "")
            if c.llm_enabled:
                llm_sw.select()
            else:
                llm_sw.deselect()
            mp = c.model_provider if c.model_provider in ALLOWED_MODEL_PROVIDERS else "openai"
            model_provider_var.set(mp)
            llm_model_var.set(c.llm_model or "gpt-4o-mini")
            vals = _llm_preset_list_for(mp)
            llm_model_menu.configure(values=vals)
            if vals and llm_model_var.get() not in vals:
                llm_model_var.set(str(vals[0]))
            system_prompt_box.configure(state="normal")
            system_prompt_box.delete("1.0", "end")
            system_prompt_box.insert("1.0", c.system_prompt)
            journal_prompt_box.configure(state="normal")
            journal_prompt_box.delete("1.0", "end")
            journal_prompt_box.insert("1.0", c.journal_system_prompt)
            wb = c.whisper_backend if c.whisper_backend in ALLOWED_WHISPER_BACKENDS else "local"
            whisper_var.set(wb)
            whisper_model_var.set(c.whisper_model or "")
            li = "auto" if c.language is None else c.language
            if li not in ("ru", "en", "auto"):
                li = "ru"
            lang_var.set(li)
            if c.floating_pill_enabled:
                pill_sw.select()
            else:
                pill_sw.deselect()

        save_row = ctk.CTkFrame(settings, fg_color="transparent")
        save_row.grid(row=9, column=0, sticky="ew", pady=(4, 4))
        save_feedback = ctk.CTkLabel(save_row, text="", font=body_font, text_color="#34C759")

        def on_save_settings() -> None:
            try:
                lang_v = lang_var.get().strip().lower()
                updates = {
                    "hotkey": var_hotkey.get().strip().lower().replace(" ", ""),
                    "journal_hotkey": var_journal_hk.get().strip().lower().replace(" ", ""),
                    "command_mode_hotkey": var_cmd_hk.get().strip().lower().replace(" ", ""),
                    "llm_enabled": bool(llm_sw.get()),
                    "model_provider": model_provider_var.get().strip().lower(),
                    "llm_model": llm_model_var.get().strip(),
                    "system_prompt": system_prompt_box.get("1.0", "end").strip(),
                    "journal_system_prompt": journal_prompt_box.get("1.0", "end").strip(),
                    "whisper_backend": whisper_var.get().strip().lower(),
                    "whisper_model": whisper_model_var.get().strip(),
                    "language": lang_v,
                    "floating_pill_enabled": bool(pill_sw.get()),
                }
                config_manager.update_and_save(updates)
                sync_settings_widgets()
                sync_secrets_panel()
                if self._host_command_queue is not None:
                    try:
                        self._host_command_queue.put_nowait(reload_config_message())
                    except Exception:
                        LOGGER.warning("Не удалось отправить RELOAD_CONFIG в основной процесс", exc_info=True)
                save_feedback.configure(
                    text="Настройки сохранены и отправлены в основной процесс",
                    text_color="#34C759",
                )

                def _clear_fb() -> None:
                    try:
                        if root.winfo_exists():
                            save_feedback.configure(text="")
                    except Exception:
                        pass

                root.after(5000, _clear_fb)
            except Exception as exc:
                save_feedback.configure(text=f"Ошибка: {exc}", text_color="#FF453A")

        ctk.CTkButton(
            save_row,
            text="Сохранить изменения",
            font=body_font,
            height=40,
            width=220,
            corner_radius=10,
            fg_color=("#0A84FF", "#0A84FF"),
            hover_color=("#0066CC", "#0066CC"),
            command=on_save_settings,
        ).pack(side="left", padx=(0, 12), pady=4)
        save_feedback.pack(side="left", pady=4)

        mic_card = ctk.CTkFrame(
            settings,
            fg_color=("#2C2C2E", "#2C2C2E"),
            corner_radius=14,
            border_width=1,
            border_color=("#48484A", "#48484A"),
        )
        mic_card.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        mic_title_font = preferred_ui_font(15, "bold", master=root)
        ctk.CTkLabel(mic_card, text="Микрофон", font=mic_title_font, text_color="#F2F2F7").pack(
            anchor="w", padx=16, pady=(14, 6)
        )

        devices, _default_in = list_audio_input_devices()
        labels: list[str] = ["По умолчанию (системный)"]
        values: list[str | None] = [None]
        for d in devices:
            labels.append(f"{d['index']}: {d['name']}")
            values.append(str(d["index"]))

        def label_for_device_index() -> str:
            cur = config_manager.config.audio_input_device
            if cur is None:
                return labels[0]
            for lab, val in zip(labels, values):
                if val is not None and int(val) == int(cur):
                    return lab
            return labels[0]

        mic_var = ctk.StringVar(value=label_for_device_index())

        def on_mic_pick(choice: str) -> None:
            idx: int | None = None
            for lab, val in zip(labels, values):
                if lab == choice:
                    idx = int(val) if val is not None else None
                    break
            if idx is not None:
                try:
                    validate_audio_input_index(idx)
                except ValueError as err:
                    LOGGER.warning("%s", err)
                    return
            try:
                config_manager.patch_audio_input_device(idx)
            except Exception:
                LOGGER.exception("Не удалось записать микрофон в config.json")
                return
            restart_mic_meter_if_settings()

        mic_menu = ctk.CTkOptionMenu(
            mic_card,
            values=labels,
            variable=mic_var,
            command=on_mic_pick,
            font=body_font,
            fg_color=("#3A3A3C", "#3A3A3C"),
            button_color=("#48484A", "#48484A"),
            button_hover_color=("#5C5C5E", "#5C5C5E"),
        )
        mic_menu.pack(anchor="w", padx=16, pady=(0, 6))

        ctk.CTkLabel(
            mic_card,
            text="Уровень сигнала (превью)",
            font=small_font,
            text_color="#AEAEB2",
        ).pack(anchor="w", padx=16, pady=(4, 2))

        mic_level_bar = ctk.CTkProgressBar(
            mic_card,
            width=280,
            height=12,
            corner_radius=6,
            fg_color=("#3A3A3C", "#3A3A3C"),
            progress_color=("#34C759", "#34C759"),
        )
        mic_level_bar.set(0.0)
        mic_level_bar.pack(anchor="w", padx=16, pady=(0, 4))

        mic_meter_status = ctk.CTkLabel(
            mic_card,
            text="",
            font=small_font,
            text_color="#FF9F0A",
            wraplength=720,
            justify="left",
        )
        mic_meter_status.pack(anchor="w", padx=16, pady=(0, 6))

        _meter_ui_after: list[Any] = [None]

        def _cancel_meter_ui_tick() -> None:
            aid = _meter_ui_after[0]
            if aid is not None:
                try:
                    root.after_cancel(aid)
                except Exception:
                    pass
                _meter_ui_after[0] = None

        def update_meter_ui() -> None:
            _meter_ui_after[0] = None
            if not root.winfo_exists():
                return
            if current_page[0] != "settings":
                return
            target = mic_meter.get_level()
            try:
                cur = float(mic_level_bar.get())
            except Exception:
                cur = 0.0
            smoothed = cur + (target - cur) * 0.3
            mic_level_bar.set(smoothed)
            err = mic_meter.get_last_error()
            if err:
                mic_meter_status.configure(text=err, text_color="#FF9F0A")
            else:
                mic_meter_status.configure(text="", text_color="#8E8E93")
            _meter_ui_after[0] = root.after(50, update_meter_ui)

        def restart_mic_meter_if_settings() -> None:
            if current_page[0] != "settings":
                return
            mic_meter.start_metering(device=config_manager.config.audio_input_device)

        ctk.CTkLabel(
            mic_card,
            text=(
                "Запись в основном приложении подхватит устройство после "
                "«Reload configuration» в меню трея или перезапуска."
            ),
            font=small_font,
            text_color="#8E8E93",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        privacy_card = ctk.CTkFrame(
            settings,
            fg_color=("#2C2C2E", "#2C2C2E"),
            corner_radius=14,
            border_width=1,
            border_color=("#48484A", "#48484A"),
        )
        privacy_card.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        privacy_title_font = preferred_ui_font(15, "bold", master=root)
        ctk.CTkLabel(
            privacy_card,
            text="История и приватность",
            font=privacy_title_font,
            text_color="#F2F2F7",
        ).pack(anchor="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            privacy_card,
            text="История хранится только локально. Отключите, если не хотите сохранять тексты на диск.",
            font=small_font,
            text_color="#8E8E93",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        hist_sw = ctk.CTkSwitch(
            privacy_card,
            text="Сохранять историю диктовок",
            font=body_font,
            progress_color=("#34C759", "#34C759"),
        )
        if config_manager.config.enable_history:
            hist_sw.select()
        else:
            hist_sw.deselect()
        hist_sw.pack(anchor="w", padx=16, pady=(0, 10))

        def on_hist_switch() -> None:
            try:
                config_manager.patch_enable_history(bool(hist_sw.get()))
            except Exception:
                LOGGER.exception("Не удалось записать enable_history в config.json")

        hist_sw.configure(command=on_hist_switch)

        def sync_history_switch() -> None:
            if bool(hist_sw.get()) != bool(config_manager.config.enable_history):
                if config_manager.config.enable_history:
                    hist_sw.select()
                else:
                    hist_sw.deselect()

        def on_clear_history() -> None:
            try:
                history_store_ui.clear_all()
                refresh_history_ui()
            except Exception:
                LOGGER.exception("Очистка истории диктовок")

        ctk.CTkButton(
            privacy_card,
            text="Очистить всю историю на этом Mac",
            font=body_font,
            height=34,
            corner_radius=10,
            fg_color=("#5C2C2C", "#5C2C2C"),
            hover_color=("#7A3838", "#7A3838"),
            command=on_clear_history,
        ).pack(anchor="w", padx=16, pady=(0, 14))

        api_card = ctk.CTkFrame(
            settings,
            fg_color=("#2C2C2E", "#2C2C2E"),
            corner_radius=14,
            border_width=1,
            border_color=("#48484A", "#48484A"),
        )
        api_card.grid(row=7, column=0, sticky="ew", pady=(0, 12))
        api_title_font = preferred_ui_font(15, "bold", master=root)
        ctk.CTkLabel(api_card, text="API-ключи", font=api_title_font, text_color="#F2F2F7").pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        ctk.CTkLabel(
            api_card,
            text=(
                "Ключ сохраняется в .env.secrets в каталоге поддержки приложения "
                "(рядом со stats.json), не внутри .app и не в config.json. "
                "Для разработки по-прежнему можно использовать локальный .env или переменные окружения."
            ),
            font=small_font,
            text_color="#8E8E93",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        secrets_path_lbl = ctk.CTkLabel(
            api_card,
            text=f"Файл: {config_manager.secrets_env_path()}",
            font=small_font,
            text_color="#8E8E93",
            wraplength=720,
            justify="left",
        )
        secrets_path_lbl.pack(anchor="w", padx=16, pady=(0, 6))

        secrets_rows_host = ctk.CTkFrame(api_card, fg_color="transparent")
        secrets_rows_host.pack(fill="x", padx=16, pady=(0, 6))

        _all_secret_names = all_known_secret_env_names()
        _needed_init = iter_needed_secret_names(
            model_provider=cfg.model_provider,
            whisper_backend=cfg.whisper_backend,
            llm_enabled=cfg.llm_enabled,
        )
        _pick_init = _needed_init[0] if _needed_init else (_all_secret_names[0] if _all_secret_names else "OPENAI_API_KEY")
        if _all_secret_names and _pick_init not in _all_secret_names:
            _pick_init = _all_secret_names[0]
        secret_target_var = ctk.StringVar(value=_pick_init)

        pick_row = ctk.CTkFrame(api_card, fg_color="transparent")
        pick_row.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(pick_row, text="Сохранить значение в переменную", font=small_font, text_color="#AEAEB2").pack(
            side="left", padx=(0, 10)
        )
        secret_pick_menu = ctk.CTkOptionMenu(
            pick_row,
            values=_all_secret_names or ["OPENAI_API_KEY"],
            variable=secret_target_var,
            font=body_font,
            width=220,
            fg_color=("#3A3A3C", "#3A3A3C"),
            button_color=("#48484A", "#48484A"),
        )
        secret_pick_menu.pack(side="left")

        api_input_row = ctk.CTkFrame(api_card, fg_color="transparent")
        api_input_row.pack(fill="x", padx=16, pady=(0, 6))

        api_entry = ctk.CTkEntry(
            api_input_row,
            show="*",
            width=320,
            placeholder_text="Вставьте ключ и нажмите «Сохранить»",
            font=body_font,
        )
        api_entry.pack(side="left", padx=(0, 10))

        api_save_status = ctk.CTkLabel(api_card, text="", font=small_font, text_color="#34C759")
        api_save_status.pack(anchor="w", padx=16, pady=(0, 6))

        secret_source_lbl = ctk.CTkLabel(api_card, text="", font=small_font, text_color="#8E8E93")
        secret_source_lbl.pack(anchor="w", padx=16, pady=(0, 6))

        def _secret_source_text(key_name: str) -> str:
            source = config_manager.secret_source(key_name)
            if source == "secrets_file":
                return "Источник: .env.secrets (управляется из приложения)"
            if source == "local_env":
                return "Источник: локальный .env (режим разработки)"
            if source == "environment":
                return "Источник: переменная окружения процесса"
            return "Источник: ключ не найден"

        def _delete_secret(key_name: str, *, everywhere: bool) -> None:
            try:
                config_manager.delete_secret(key_name, everywhere=everywhere)
                if secret_target_var.get().strip() == key_name:
                    api_entry.delete(0, "end")
                sync_secrets_panel()
                if everywhere:
                    api_save_status.configure(
                        text=(
                            f"{key_name} удалён из .env.secrets, локальных .env и текущих переменных "
                            "окружения процесса."
                        ),
                        text_color="#8E8E93",
                    )
                else:
                    api_save_status.configure(
                        text=f"{key_name} удалён из .env.secrets и из текущей сессии приложения.",
                        text_color="#8E8E93",
                    )
            except Exception as exc:
                api_save_status.configure(text=f"Ошибка удаления: {exc}", text_color="#FF453A")

        def _render_secrets_rows() -> None:
            for w in secrets_rows_host.winfo_children():
                w.destroy()
            names = all_known_secret_env_names()
            required_names = set(
                iter_needed_secret_names(
                    model_provider=config_manager.config.model_provider,
                    whisper_backend=config_manager.config.whisper_backend,
                    llm_enabled=config_manager.config.llm_enabled,
                )
            )
            has_any = False
            for name in names:
                value = config_manager.peek_secret(name)
                if not value and name not in required_names:
                    continue
                has_any = True
                row = ctk.CTkFrame(secrets_rows_host, fg_color="transparent")
                row.pack(fill="x", pady=(0, 4))
                ctk.CTkLabel(
                    row,
                    text=f"{name}: {_mask_secret(value)}",
                    font=body_font,
                    text_color="#E5E5EA" if value else "#AEAEB2",
                    anchor="w",
                ).pack(side="left", padx=(0, 10))
                if value:
                    ctk.CTkButton(
                        row,
                        text="Удалить (.env.secrets)",
                        font=body_font,
                        width=170,
                        height=30,
                        corner_radius=10,
                        fg_color=("#5C2C2C", "#5C2C2C"),
                        hover_color=("#7A3838", "#7A3838"),
                        command=lambda k=name: _delete_secret(k, everywhere=False),
                    ).pack(side="left", padx=(0, 8))
                    ctk.CTkButton(
                        row,
                        text="Удалить везде",
                        font=body_font,
                        width=130,
                        height=30,
                        corner_radius=10,
                        fg_color=("#7A5A2C", "#7A5A2C"),
                        hover_color=("#8A6A34", "#8A6A34"),
                        command=lambda k=name: _delete_secret(k, everywhere=True),
                    ).pack(side="left")
            if not has_any:
                ctk.CTkLabel(
                    secrets_rows_host,
                    text="Для текущих настроек облачные ключи не обязательны (или LLM выключен).",
                    font=body_font,
                    text_color="#AEAEB2",
                    justify="left",
                    anchor="w",
                ).pack(anchor="w")

        def sync_secrets_panel() -> None:
            _render_secrets_rows()
            secrets_path_lbl.configure(text=f"Файл: {config_manager.secrets_env_path()}")
            cur = secret_target_var.get()
            names = all_known_secret_env_names()
            secret_pick_menu.configure(values=names or ["OPENAI_API_KEY"])
            if cur not in names and names:
                secret_target_var.set(names[0])
            secret_source_lbl.configure(text=_secret_source_text(secret_target_var.get().strip()))

        def on_save_api_secret() -> None:
            raw = api_entry.get().strip()
            key_name = secret_target_var.get().strip()
            try:
                config_manager.set_secret(key_name, raw)
                api_entry.delete(0, "end")
                sync_secrets_panel()
                if raw:
                    api_save_status.configure(
                        text=f"Сохранено в {key_name}. Основной процесс подхватит при следующем запросе.",
                        text_color="#34C759",
                    )
                else:
                    api_save_status.configure(
                        text=f"Значение {key_name} удалено из файла секретов (если было).",
                        text_color="#8E8E93",
                    )
            except Exception as exc:
                api_save_status.configure(text=f"Ошибка: {exc}", text_color="#FF453A")

        ctk.CTkButton(
            api_input_row,
            text="Сохранить",
            font=body_font,
            width=110,
            height=34,
            corner_radius=10,
            fg_color=("#3A3A3C", "#3A3A3C"),
            command=on_save_api_secret,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            api_input_row,
            text="Очистить поле",
            font=body_font,
            width=120,
            height=34,
            corner_radius=10,
            fg_color=("#48484A", "#48484A"),
            command=lambda: api_entry.delete(0, "end"),
        ).pack(side="left")

        secret_pick_menu.configure(command=lambda _: sync_secrets_panel())
        sync_secrets_panel()

        test_conn_row = ctk.CTkFrame(api_card, fg_color="transparent")
        test_conn_row.pack(fill="x", padx=16, pady=(4, 10))
        connection_test_lbl = ctk.CTkLabel(
            test_conn_row,
            text="",
            font=small_font,
            text_color="#8E8E93",
            wraplength=720,
            justify="left",
            anchor="w",
        )
        connection_test_lbl.pack(fill="x", pady=(6, 0))

        def _run_llm_test_bg() -> None:
            connection_test_lbl.configure(text="Проверка LLM…", text_color="#AEAEB2")

            def work() -> None:
                ok, msg = test_llm_connection(config_manager, config_manager.config)
                color = "#34C759" if ok else "#FF453A"

                def apply() -> None:
                    try:
                        if root.winfo_exists():
                            connection_test_lbl.configure(text=f"LLM: {msg}", text_color=color)
                    except Exception:
                        pass

                root.after(0, apply)

            threading.Thread(target=work, daemon=True).start()

        def _run_stt_test_bg() -> None:
            connection_test_lbl.configure(text="Проверка STT…", text_color="#AEAEB2")

            def work() -> None:
                ok, msg = test_stt_connection(config_manager, config_manager.config)
                color = "#34C759" if ok else "#FF453A"

                def apply() -> None:
                    try:
                        if root.winfo_exists():
                            connection_test_lbl.configure(text=f"STT: {msg}", text_color=color)
                    except Exception:
                        pass

                root.after(0, apply)

            threading.Thread(target=work, daemon=True).start()

        ctk.CTkButton(
            test_conn_row,
            text="Проверить LLM",
            font=body_font,
            width=140,
            height=32,
            corner_radius=10,
            fg_color=("#3A3A3C", "#3A3A3C"),
            command=_run_llm_test_bg,
        ).pack(side="left", padx=(0, 8), pady=(0, 0))
        ctk.CTkButton(
            test_conn_row,
            text="Проверить STT",
            font=body_font,
            width=140,
            height=32,
            corner_radius=10,
            fg_color=("#3A3A3C", "#3A3A3C"),
            command=_run_stt_test_bg,
        ).pack(side="left", padx=(0, 8), pady=(0, 0))

        reload_row = ctk.CTkFrame(settings, fg_color="transparent")
        reload_row.grid(row=8, column=0, sticky="w", pady=12)

        def reload_cfg() -> None:
            try:
                config_manager.reload()
                sync_settings_widgets()
                mic_var.set(label_for_device_index())
                sync_history_switch()
                sync_secrets_panel()
                restart_mic_meter_if_settings()
                if current_page[0] == "history":
                    refresh_history_ui()
                if current_page[0] == "journal":
                    refresh_journal_filter_menu()
                    refresh_journal_sidebar()
            except Exception:
                LOGGER.exception("reload из дашборда")

        ctk.CTkButton(
            reload_row,
            text="Перечитать config.json с диска",
            font=body_font,
            height=34,
            corner_radius=10,
            fg_color=("#3A3A3C", "#3A3A3C"),
            command=reload_cfg,
        ).pack(side="left", padx=(0, 8))

        def show_page(name: str) -> None:
            prev = current_page[0]
            if prev == "settings" and name != "settings":
                _cancel_meter_ui_tick()
                mic_meter.stop_metering()
            current_page[0] = name
            for p in pages.values():
                p.grid_remove()
            pages[name].grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            for b in nav_buttons:
                b.configure(fg_color="transparent")
            idx = {"home": 0, "dictionary": 1, "history": 2, "journal": 3, "settings": 4}[name]
            nav_buttons[idx].configure(fg_color=("#3A3A3C", "#3A3A3C"))
            if name == "settings":
                restart_mic_meter_if_settings()
                update_meter_ui()
            if name == "home":
                refresh_home_stats()
            if name == "history":
                refresh_history_ui()
            if name == "journal":
                refresh_journal_filter_menu()
                refresh_journal_sidebar()

        def nav_cmd(key: str) -> Any:
            return lambda: show_page(key)

        b_home = ctk.CTkButton(
            sidebar,
            text="Home",
            font=body_font,
            anchor="w",
            height=40,
            fg_color="transparent",
            command=nav_cmd("home"),
        )
        b_home.pack(fill="x", padx=10, pady=4)
        nav_buttons.append(b_home)

        b_dict = ctk.CTkButton(
            sidebar,
            text="Dictionary",
            font=body_font,
            anchor="w",
            height=40,
            fg_color="transparent",
            command=nav_cmd("dictionary"),
        )
        b_dict.pack(fill="x", padx=10, pady=4)
        nav_buttons.append(b_dict)

        b_hist = ctk.CTkButton(
            sidebar,
            text="История",
            font=body_font,
            anchor="w",
            height=40,
            fg_color="transparent",
            command=nav_cmd("history"),
        )
        b_hist.pack(fill="x", padx=10, pady=4)
        nav_buttons.append(b_hist)

        b_journal = ctk.CTkButton(
            sidebar,
            text="Ежедневник",
            font=body_font,
            anchor="w",
            height=40,
            fg_color="transparent",
            command=nav_cmd("journal"),
        )
        b_journal.pack(fill="x", padx=10, pady=4)
        nav_buttons.append(b_journal)

        b_set = ctk.CTkButton(
            sidebar,
            text="Settings",
            font=body_font,
            anchor="w",
            height=40,
            fg_color="transparent",
            command=nav_cmd("settings"),
        )
        b_set.pack(fill="x", padx=10, pady=4)
        nav_buttons.append(b_set)

        show_page("home")


def mount_main_dashboard(
    root: Any,
    config_manager: "ConfigManager",
    host_command_queue: Any | None = None,
) -> None:
    """
    Совместимая обёртка: монтирует дашборд в корневое окно.

    Args:
        root: Уже созданный ``ctk.CTk()``.
        config_manager: Менеджер конфигурации процесса дашборда.
        host_command_queue: Опционально — очередь в основной процесс (IPC после сохранения настроек).
    """
    MainDashboard(root, config_manager, host_command_queue=host_command_queue)
