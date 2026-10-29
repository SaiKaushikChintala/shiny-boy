import tkinter as tk
from tkinter import ttk
from typing import Callable

from shiny.app.ui.kit import Chip, ProgressBar, Button, NavList, RoundedFrame, SearchSelect, Segmented, SlimScrollbar, Toggle, add_window_buttons, dark_title_bar
from shiny.app.ui.theme import FONT_BIG, FONT_BOLD, FONT_HEADING, FONT_MONO_SMALL, FONT_SMALL, P, dp
from shiny.core.pokemon.natures import NATURES
from shiny.hunts.registry import bots_for

TARGET_COLUMNS = (
    ("advance", "Advances", 66, "e"), ("pid", "PID", 70, "center"), ("species", "Pokémon", 80, "w"), ("level", "Lv", 32, "center"),
    ("shiny", "Shiny", 44, "center"), ("nature", "Nature", 64, "w"), ("ability", "Ability", 70, "w"), ("hp", "HP", 36, "center"),
    ("atk", "Atk", 36, "center"), ("def", "Def", 36, "center"), ("spa", "SpA", 36, "center"), ("spd", "SpD", 36, "center"),
    ("spe", "Spe", 36, "center"), ("hidden", "Hidden", 62, "w"), ("power", "Power", 44, "center"), ("gender", "Gender", 48, "center"),
    ("hit", "Hit", 30, "center"),
)

GENERATE_HINT = "Generate saves, reloads the game from its start and lists the shiny Pokémon that can be made, with their advances. Click a row to choose it; click it again to unselect. None chosen = the next shiny."
GENERATE_HINT_FROM_HERE = (
    "Generate lists the shiny Pokémon this bot can make from where the game is now (the game is paused). Click a row to choose "
    "it; click it again to unselect. None chosen = the next shiny."
)


def describe_for_card(pokemon) -> tuple[str, list[tuple[str, int]], str]:
    ivs = getattr(pokemon, "ivs", None)
    if ivs:
        order = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
        stats = [(name, ivs[name]) for name in order if name in ivs]
        return f"{pokemon.nature}   ·   PID {pokemon.personality_value:#010x}", stats, ""
    from shiny.core.rng.timer_gen12 import split_dvs

    attack, defense, speed, special = split_dvs(pokemon.dv_bytes)
    hp = (attack & 1) << 3 | (defense & 1) << 2 | (speed & 1) << 1 | (special & 1)
    note = "Gen 1 has no shiny Pokémon: these DVs are shiny once the Pokémon is traded to Gen 2." if pokemon.is_shiny and pokemon.generation == 1 else ""
    return f"DVs {pokemon.dv_bytes[0]:02x}{pokemon.dv_bytes[1]:02x}", [("HP", hp), ("Atk", attack), ("Def", defense), ("Spe", speed), ("Spc", special)], note


class BotPanel(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        on_start: Callable[[dict], None],
        on_stop: Callable[[], None],
        on_interaction: Callable[[], None],
        wraplength: int,
        on_generate: Callable[[], None],
        game=None,
    ):
        super().__init__(parent, background=P.panel)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_interaction = on_interaction
        self._on_generate = on_generate
        self._interactive: list[tk.Misc] = []
        self._nature_locked = False
        self._has_hits = False
        self._nature_before = "Any"
        self.on_targets_visible: Callable[[bool], None] | None = None
        self._running = False
        self._active_bot: str | None = None
        self._last_choices: dict[str, str] = {}

        self.bots = bots_for(game)
        self.names = list(self.bots)
        mode_card = RoundedFrame(self, radius=14, fill=P.card, outline=P.border, pad=8)
        mode_card.pack(fill="x", padx=dp(14), pady=(0, dp(10)))
        self.mode_list = NavList(mode_card.body, on_select=lambda: (self._mode_changed(), self._on_interaction()), bg=P.card)
        self.mode_list.pack(fill="x")
        self._fill_list()

        self.choice_variable = tk.StringVar()
        self.nature_variable = tk.StringVar(value="Any")
        self.fast_variable = tk.BooleanVar(value=True)
        self._build_options_card()

        self.buttons = tk.Frame(self, background=P.panel)
        self.buttons.pack(fill="x", padx=dp(14), pady=(0, dp(10)))
        self.buttons.columnconfigure((0, 1), weight=1, uniform="buttons")
        self.start_button = Button(self.buttons, "Start", self._start_pressed, kind="primary", pady=10, radius=10)
        self.start_button.grid(row=0, column=0, sticky="we", padx=(0, dp(5)))
        self.stop_button = Button(self.buttons, "Stop", self._stop_pressed, kind="danger", pady=10, radius=10)
        self.stop_button.grid(row=0, column=1, sticky="we", padx=(dp(5), 0))
        self._enable(self.stop_button, False)
        self._enable(self.start_button, False)

        self.feedback = tk.Frame(self, background=P.panel)
        self.feedback.pack(fill="x")
        self.progress = ProgressBar(self.feedback, bg=P.panel)
        self.result_card: RoundedFrame | None = None
        self.status_label = tk.Label(
            self.feedback, text="", background=P.panel, foreground=P.text, font=FONT_BOLD, anchor="w", justify="left",
            wraplength=wraplength,
        )
        self.result_label = tk.Label(
            self.feedback, text="", background=P.panel, foreground=P.text, font=FONT_BIG, anchor="w", justify="left",
            wraplength=wraplength,
        )
        self._progress_shown = False

        self._build_targets_section(wraplength)
        self._mode_changed()

    def _build_options_card(self) -> None:
        card = RoundedFrame(self, radius=14, fill=P.card, outline=P.border, pad=14)
        self.options_card = card
        body = card.body
        body.columnconfigure(1, weight=1)

        self._choice_label = tk.Label(body, text="", background=P.card, foreground=P.subtle, font=FONT_SMALL, anchor="w")
        self._choice_label.grid(row=0, column=0, sticky="w", padx=(0, dp(12)), pady=dp(4))
        self._choice_buttons = tk.Frame(body, background=P.card)
        self._choice_buttons.grid(row=0, column=1, sticky="w", pady=dp(4))

        self._nature_label = tk.Label(body, text="Nature", background=P.card, foreground=P.subtle, font=FONT_SMALL, anchor="w")
        self._nature_label.grid(row=2, column=0, sticky="w", padx=(0, dp(12)), pady=dp(4))
        self._nature_box = SearchSelect(body, self.nature_variable, ["Any", *NATURES], bg=P.card, width=200)
        self._nature_box.grid(row=2, column=1, sticky="w", pady=dp(4))
        self._nature_box.bind("<<ComboboxSelected>>", lambda _event: self._on_interaction())
        self._interactive.append(self._nature_box)

        self._box_label = tk.Label(body, text="", background=P.card, foreground=P.subtle, font=FONT_SMALL, anchor="w")
        self._box_label.grid(row=1, column=0, sticky="w", padx=(0, dp(12)), pady=dp(4))
        self._choice_box = SearchSelect(body, self.choice_variable, [], bg=P.card, width=260)
        self._choice_box.grid(row=1, column=1, sticky="we", pady=dp(4))
        self._choice_box.bind("<<ComboboxSelected>>", lambda _event: self._on_interaction())
        self._interactive.append(self._choice_box)

        fast = Toggle(body, "Fast replay (skip the long wait)", self.fast_variable, command=self._on_interaction, bg=P.card)
        fast.grid(row=4, column=0, columnspan=2, sticky="w", pady=(dp(10), 0))
        self._interactive.append(fast)

    def _build_targets_section(self, wraplength: int) -> None:
        self.targets_frame = RoundedFrame(self, radius=14, fill=P.card, outline=P.border, pad=14)
        body = self.targets_frame.body
        tk.Label(body, text="ADVANCED", background=P.card, foreground=P.subtle, font=FONT_HEADING, anchor="w").pack(fill="x", pady=(0, dp(10)))
        self.table_button = Button(body, "Generate RNG table", self._generate_from_panel, kind="secondary", pady=9, radius=10)
        self.table_button.pack(fill="x")
        self._interactive.append(self.table_button)
        self.chosen_row = tk.Frame(body, background=P.card)
        self.chosen_label = tk.Label(self.chosen_row, text="", background=P.card, foreground=P.accent_text, font=FONT_SMALL, anchor="w", justify="left", wraplength=dp(300))
        self.chosen_label.pack(side="left", fill="x", expand=True)
        self.chosen_clear = Button(self.chosen_row, "Clear", self._clear_chosen, kind="ghost", padx=10, pady=4, font=FONT_SMALL, radius=8, bg=P.card)
        self.chosen_clear.pack(side="right", padx=(dp(8), 0))
        self._interactive.append(self.chosen_clear)
        self._target_keys: dict[str, tuple[int, int]] = {}
        self._target_advances: dict[str, int] = {}
        self._note = ""
        self._table_window: tk.Toplevel | None = None
        self._hover_row = ""
        self._build_table_window()

    def _build_table_window(self) -> None:
        main = self.winfo_toplevel()
        window = tk.Toplevel(main)
        window.withdraw()
        window.title("Shiny encounters")
        window.configure(background=P.panel)
        window.transient(main)
        window.minsize(dp(960), dp(380))
        window.protocol("WM_DELETE_WINDOW", self.close_table)
        window.bind("<Escape>", lambda _event: self.close_table())
        self._table_window = window

        header = tk.Frame(window, background=P.panel)
        header.pack(fill="x", padx=dp(18), pady=(dp(16), dp(6)))
        tk.Label(header, text="Shiny encounters", background=P.panel, foreground=P.text, font=FONT_BIG).pack(side="left")
        self.table_count = tk.Label(header, text="")
        generate = Button(header, "Generate", self._generate_pressed, kind="primary", padx=16, pady=6, font=FONT_SMALL, radius=8)
        generate.pack(side="right", padx=(0, dp(8)))
        self._interactive.append(generate)
        clear = Button(header, "Clear", self._clear_pressed, kind="ghost", padx=12, pady=6, font=FONT_SMALL, radius=8)
        clear.pack(side="right", padx=(0, dp(6)))
        self._interactive.append(clear)
        self.max_advance_variable = tk.StringVar(value="200000")
        max_advance = ttk.Entry(header, textvariable=self.max_advance_variable, width=10, justify="right")
        max_advance.pack(side="right", padx=(0, dp(10)))
        self._interactive.append(max_advance)
        tk.Label(header, text="up to advance", background=P.panel, foreground=P.subtle, font=FONT_SMALL).pack(side="right", padx=(0, dp(6)))

        self.targets_hint = tk.Label(window, text="", background=P.panel, foreground=P.muted, font=FONT_SMALL, anchor="w", justify="left", wraplength=dp(900))
        header.pack_configure(pady=(dp(16), dp(10)))

        table_card = RoundedFrame(window, radius=14, fill=P.card, outline=P.border, pad=8, stretch=True)
        table_card.pack(fill="both", expand=True, padx=dp(14), pady=(0, dp(14)))
        tree_frame = table_card.body
        scroll_y = SlimScrollbar(tree_frame, bg=P.card)
        scroll_y.pack(side="right", fill="y", padx=(0, dp(4)), pady=dp(8))
        self.targets_tree = ttk.Treeview(
            tree_frame, columns=[name for name, _title, _width, _anchor in TARGET_COLUMNS], show="headings", selectmode="browse",
            height=12, yscrollcommand=scroll_y.set, takefocus=0,
        )
        for name, title, width, anchor in TARGET_COLUMNS:
            self.targets_tree.heading(name, text=title.upper(), anchor=anchor)
            self.targets_tree.column(name, width=dp(width), minwidth=dp(width), anchor=anchor, stretch=False)
        self.targets_tree.pack(side="left", fill="both", expand=True, padx=(dp(4), 0), pady=(dp(4), dp(4)))
        scroll_y.configure(command=self.targets_tree.yview)
        self.targets_tree.tag_configure("odd", background="#1a1a21")
        self.targets_tree.tag_configure("hover", background=P.card_hover)
        self.targets_tree.bind("<<TreeviewSelect>>", lambda _event: self._selection_changed())
        self.targets_tree.bind("<Button-1>", self._toggle_row)
        self.targets_tree.bind("<Motion>", self._hover_over_row)
        self.targets_tree.bind("<Leave>", lambda _event: self._set_hover_row(""))
        self.targets_tree.bind("<Configure>", lambda _event: self.targets_tree.after_idle(self._fit_columns))
        self._interactive.append(self.targets_tree)
        self._table_placed = False

    def _fit_columns(self) -> None:
        available = self.targets_tree.winfo_width()
        base = sum(dp(width) for name, _title, width, _anchor in TARGET_COLUMNS if name in self._shown_columns())
        factor = max(1.0, available / base) if available > 1 else 1.0
        for name, _title, width, _anchor in TARGET_COLUMNS:
            self.targets_tree.column(name, width=int(dp(width) * factor))

    def _shown_columns(self) -> list[str]:
        return [name for name, _title, _width, _anchor in TARGET_COLUMNS if name != "hit" or self._has_hits]

    def _hover_over_row(self, event) -> None:
        self._set_hover_row(self.targets_tree.identify_row(event.y) if self.targets_tree.identify_region(event.x, event.y) == "cell" else "")

    def _set_hover_row(self, row: str) -> None:
        if row == self._hover_row:
            return
        for item, add in ((self._hover_row, False), (row, True)):
            if item and self.targets_tree.exists(item):
                tags = [tag for tag in self.targets_tree.item(item, "tags") if tag != "hover"]
                self.targets_tree.item(item, tags=tags + (["hover"] if add else []))
        self._hover_row = row

    def _generate_from_panel(self) -> None:
        self.open_table()
        self._generate_pressed()

    def open_table(self) -> None:
        window = self._table_window
        if not self._table_placed:
            self._table_placed = True
            main = self.winfo_toplevel()
            width, height = dp(1000), dp(560)
            x = main.winfo_rootx() + max(dp(40), (main.winfo_width() - width) // 2)
            y = main.winfo_rooty() + dp(60)
            window.geometry(f"{width}x{height}+{x}+{y}")
        window.deiconify()
        add_window_buttons(window)
        dark_title_bar(window)
        window.lift()
        window.focus_force()

    def close_table(self) -> None:
        if self._table_window is None:
            return
        self._table_window.withdraw()
        self._on_interaction()

    def _apply_nature_lock(self, selection) -> None:
        if selection:
            if not self._nature_locked:
                self._nature_before = self.nature_variable.get()
                self._nature_locked = True
            self.nature_variable.set(self.targets_tree.item(selection[0], "values")[5])
            self._nature_box.state(["disabled"])
        elif self._nature_locked:
            self._nature_locked = False
            self.nature_variable.set(self._nature_before)
            self._nature_box.state(["disabled"] if self._running else ["!disabled"])

    def _update_summary(self) -> None:
        selection = self.targets_tree.selection()
        self._apply_nature_lock(selection)
        if selection:
            advance, pid, species = self.targets_tree.item(selection[0], "values")[:3]
            self.chosen_label.configure(text=f"Chosen: {species}" + chr(10) + f"advance {advance}  ·  PID {pid}")
            self.chosen_row.pack(fill="x", pady=(dp(10), 0))
        else:
            self.chosen_row.pack_forget()
        total = len(self._target_keys)
        if not total:
            self.table_count.configure(text="")
            return
        picked = len(self.targets_tree.selection())
        self.table_count.configure(text=f"{total:,} listed   ·   1 chosen" if picked else f"{total:,} listed")

    def _fill_list(self) -> None:
        self.mode_list.set_items(self.names)

    def set_game(self, game) -> None:
        self._active_bot = None
        self.bots = bots_for(game)
        self.names = list(self.bots)
        self._fill_list()
        self._mode_changed()

    def _show_choices(self, bot) -> None:
        for widget in self._choice_buttons.winfo_children():
            if widget in self._interactive:
                self._interactive.remove(widget)
            widget.destroy()
        choices = bot.options.choices
        as_buttons = bool(choices) and bot.options.choices_as_buttons
        as_list = bool(choices) and not bot.options.choices_as_buttons
        for widget in (self._choice_label, self._choice_buttons):
            widget.grid() if as_buttons else widget.grid_remove()
        for widget in (self._box_label, self._choice_box):
            widget.grid() if as_list else widget.grid_remove()
        if not choices:
            return
        values = [name.lower() for name in choices] if as_buttons else list(choices)
        remembered = self._last_choices.get(bot.options.name)
        self.choice_variable.set(remembered if remembered in values else values[0])
        if as_list:
            self._box_label.configure(text=bot.options.choice_label)
            self._choice_box.configure(values=values)
            return
        self._choice_label.configure(text=bot.options.choice_label)
        segmented = Segmented(self._choice_buttons, list(zip(values, choices)), self.choice_variable, command=self._on_interaction, bg=P.card, padx=14)
        segmented.pack(side="left")
        self._interactive.append(segmented)

    def _mode_changed(self) -> None:
        if self._active_bot is not None:
            self._last_choices[self._active_bot] = self.choice_variable.get()
        name = self.selected_bot()
        self._active_bot = name
        self.clear_targets()
        if not self._running:
            self.set_status("")
            self.set_result("")
        if name is None:
            self.show_targets(False)
            self.options_card.pack_forget()
            self._enable(self.start_button, False)
            return
        bot = self.bots[name]
        self.show_targets(bot.options.supports_targets)
        for widget in (self._nature_label, self._nature_box):
            widget.grid() if bot.options.has_nature else widget.grid_remove()
        if not bot.options.supports_targets:
            self.targets_hint.configure(text=bot.options.rows_note or "This bot has no table yet.")
        elif not bot.options.advances_from_boot:
            self.targets_hint.configure(text=GENERATE_HINT_FROM_HERE)
        self._show_choices(bot)
        self.options_card.pack(fill="x", padx=dp(14), pady=(0, dp(10)), before=self.buttons)
        if not self._running:
            self._enable(self.start_button, True)

    @property
    def fast_replay(self) -> bool:
        return bool(self.fast_variable.get())

    def selected_bot(self) -> str | None:
        selection = self.mode_list.curselection()
        return self.names[selection[0]] if selection and selection[0] < len(self.names) else None

    def chosen_options(self) -> dict:
        name = self.selected_bot()
        nature = self.nature_variable.get()
        return {
            "mode": name,
            "choice": self.choice_variable.get() if self.bots[name].options.choices else None,
            "nature": None if nature == "Any" or not self.bots[name].options.has_nature else nature,
        }

    def _start_pressed(self) -> None:
        if self.selected_bot() is None:
            return
        self._on_start(self.chosen_options())
        self._on_interaction()

    def _stop_pressed(self) -> None:
        self._on_stop()
        self._on_interaction()

    def set_running(self, running: bool) -> None:
        self._running = running
        self._enable(self.start_button, not running and self.selected_bot() is not None)
        self._enable(self.stop_button, running)
        self.mode_list.set_disabled(running)
        for widget in self._interactive:
            self._enable(widget, not running)
        if not running:
            self.clear_progress()
            self._apply_nature_lock(self.targets_tree.selection())

    @staticmethod
    def _enable(widget, enabled: bool) -> None:
        widget.state(["!disabled"] if enabled else ["disabled"])

    def _layout_feedback(self) -> None:
        for widget in (self.progress, self.status_label, self.result_label, self.result_card):
            if widget is not None:
                widget.pack_forget()
        if self._progress_shown:
            self.progress.pack(fill="x", padx=dp(18), pady=(dp(4), 0))
        if self.status_label.cget("text"):
            self.status_label.pack(fill="x", padx=dp(18), pady=(dp(8), dp(14)))
        if self.result_label.cget("text"):
            self.result_label.pack(fill="x", padx=dp(18), pady=(dp(2), dp(14)))
        if self.result_card is not None:
            self.result_card.pack(fill="x", padx=dp(14), pady=(dp(10), dp(10)))
        elif not self._progress_shown and not self.status_label.cget("text") and not self.result_label.cget("text"):
            self.feedback.configure(height=1)
        if self._progress_shown and self.result_card is None and not self.status_label.cget("text") and not self.result_label.cget("text"):
            self.progress.pack_configure(pady=(dp(4), dp(14)))

    def set_status(self, text: str, color: str = P.text) -> None:
        self.status_label.configure(text=text, foreground=color)
        self._layout_feedback()

    def set_result(self, text: str, shiny: bool = False) -> None:
        self._drop_result_card()
        self.result_label.configure(text=text, foreground=P.gold if shiny else P.text)
        self._layout_feedback()

    def dismiss_result(self) -> None:
        self._drop_result_card()
        self.clear_progress()

    def _drop_result_card(self) -> None:
        if self.result_card is not None:
            self.result_card.destroy()
            self.result_card = None

    def show_result(self, pokemon, ok: bool) -> None:
        self._drop_result_card()
        self.result_label.configure(text="")
        shiny = bool(getattr(pokemon, "is_shiny", False))
        card = RoundedFrame(self.feedback, radius=14, fill=P.card, outline=P.gold if shiny and ok else (P.border if ok else P.danger_dim), pad=16)
        body = card.body

        top = tk.Frame(body, background=P.card)
        top.pack(fill="x")
        tk.Label(top, text=pokemon.species_name, background=P.card, foreground=P.text, font=FONT_BIG).pack(side="left")
        Button(top, "✕", self.dismiss_result, kind="ghost", padx=9, pady=3, font=FONT_BOLD, radius=8, bg=P.card).pack(side="right", padx=(dp(8), 0))
        chips = tk.Frame(top, background=P.card)
        chips.pack(side="right")
        status = Chip(chips, bg=P.card)
        status.set("Done" if ok else "Not the wanted one", P.success if ok else P.danger, P.success_dim if ok else P.danger_dim)
        status.pack(side="right")
        if shiny:
            badge = Chip(chips, bg=P.card)
            badge.set("★ SHINY DVs" if getattr(pokemon, "generation", 3) == 1 else "★ SHINY", P.gold, P.warning_dim)
            badge.pack(side="right", padx=(0, dp(6)))

        detail, stats, note = describe_for_card(pokemon)
        if detail:
            tk.Label(body, text=detail, background=P.card, foreground=P.muted, font=FONT_MONO_SMALL, anchor="w").pack(fill="x", pady=(dp(4), dp(10)))
        grid = tk.Frame(body, background=P.card)
        grid.pack(fill="x")
        for column, (name, value) in enumerate(stats):
            grid.columnconfigure(column, weight=1, uniform="stats")
            cell = tk.Frame(grid, background=P.button)
            cell.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else dp(3), dp(3) if column < len(stats) - 1 else 0))
            tk.Label(cell, text=name.upper(), background=P.button, foreground=P.subtle, font=FONT_HEADING).pack(pady=(dp(7), 0))
            color = P.gold if value == 31 else (P.danger if value == 0 else P.text)
            tk.Label(cell, text=str(value), background=P.button, foreground=color, font=FONT_BIG).pack(pady=(0, dp(7)))
        if note:
            tk.Label(body, text=note, background=P.card, foreground=P.subtle, font=FONT_SMALL, anchor="w", wraplength=dp(380), justify="left").pack(fill="x", pady=(dp(10), 0))
        self.result_card = card
        self._layout_feedback()

    def set_progress(self, fraction: float | None) -> None:
        self._progress_shown = True
        self._layout_feedback()
        if fraction is None:
            self.progress.configure(mode="indeterminate")
            self.progress.start(14)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=max(0.0, min(1.0, fraction)) * 100)

    def clear_progress(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self._progress_shown = False
        self._layout_feedback()

    def set_wraplength(self, wraplength: int) -> None:
        for label in (self.status_label, self.result_label):
            label.configure(wraplength=wraplength)

    def show_targets(self, visible: bool) -> None:
        if self.on_targets_visible is not None:
            self.on_targets_visible(visible)
        if visible:
            self.targets_frame.pack(fill="x", padx=dp(14), pady=(0, dp(10)))
        else:
            self.targets_frame.pack_forget()
            if self._table_window is not None:
                self.close_table()

    def _toggle_row(self, event) -> str | None:
        if self.targets_tree.identify_region(event.x, event.y) not in ("cell", "tree"):
            return None
        row = self.targets_tree.identify_row(event.y)
        if row:
            if row in self.targets_tree.selection():
                self.targets_tree.selection_set(())
            else:
                self.targets_tree.selection_set(row)
        return "break"

    def _clear_chosen(self) -> None:
        self.targets_tree.selection_set(())
        self._on_interaction()

    def _clear_pressed(self) -> None:
        self.targets_tree.selection_set(())

    def clear_targets(self) -> None:
        self.targets_tree.delete(*self.targets_tree.get_children())
        self._target_keys = {}
        self._target_advances = {}
        self._note = ""
        self.targets_hint.configure(text=GENERATE_HINT)
        self._update_summary()

    def set_targets(self, rows, note: str = "") -> None:
        self.clear_targets()
        self._note = note
        self._has_hits = any(row.reachable is not None for row in rows)
        self.targets_tree.configure(displaycolumns=self._shown_columns())
        for row in rows:
            iid = f"{row.advance}-{row.pid:08X}"
            self._target_keys[iid] = row.key
            self._target_advances[iid] = row.advance
            hp, atk, defense, spa, spd, spe = row.ivs or ("—",) * 6
            self.targets_tree.insert(
                "", "end", iid=iid, tags=("odd",) if len(self._target_keys) % 2 == 0 else (),
                values=(f"{row.advance:,}", f"{row.pid:08X}", row.species, row.level, row.shiny, row.nature, row.ability, hp, atk, defense, spa,
                        spd, spe, row.hidden_power, "—" if row.power is None else row.power, row.gender, "" if row.reachable is None else ("✓" if row.reachable else "✗")),
            )
        if rows:
            self.targets_hint.configure(
                text=f"{len(rows)} shiny Pokémon. Click a row to choose it; click it again to unselect. None chosen = the next shiny. {note}".strip()
            )
        else:
            self.targets_hint.configure(text="No shiny Pokémon within that many advances: raise the number and press Generate.")
        self._update_summary()
        if self._table_window is not None and self._table_window.winfo_viewable():
            self._table_window.lift()

    def _selection_changed(self) -> None:
        self._update_summary()
        picked = len(self.targets_tree.selection())
        total = len(self._target_keys)
        if total:
            self.targets_hint.configure(
                text=(f"{total} shiny Pokémon. One row chosen: the hunt aims at it." if picked else f"{total} shiny Pokémon. Click a row to choose it; none chosen = the next shiny.")
                + f" {self._note}".rstrip()
            )

    def selected_targets(self) -> list[tuple[int, int]]:
        return [self._target_keys[item] for item in self.targets_tree.selection() if item in self._target_keys]

    def selected_advances(self) -> list[int]:
        return [self._target_advances[item] for item in self.targets_tree.selection() if item in self._target_advances]

    def selected_max_advance(self) -> int:
        return max(self._target_advances.get(item, 0) for item in self.targets_tree.selection()) if self.targets_tree.selection() else 0

    def max_advance(self) -> int:
        try:
            return max(1000, min(2_000_000, int(self.max_advance_variable.get().replace(",", "").strip())))
        except ValueError:
            return 200_000

    def _generate_pressed(self) -> None:
        self.targets_tree.selection_set(())
        self._on_generate()
        if self._table_window is not None and self._table_window.winfo_viewable():
            self._table_window.lift()
            self._table_window.focus_force()
