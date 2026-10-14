import tkinter as tk
from tkinter import ttk
from typing import Callable

from shiny.app.ui.theme import FONT, FONT_BIG, FONT_BOLD, FONT_HEADING, FONT_SMALL, P
from shiny.core.pokemon.natures import NATURES
from shiny.hunts.registry import bots_for

TARGET_COLUMNS = (
    ("advance", "Advances", 64, "e"), ("pid", "PID", 72, "center"), ("species", "Pokémon", 78, "w"), ("level", "Lv", 30, "center"),
    ("shiny", "Shiny", 44, "center"), ("nature", "Nature", 64, "w"), ("ability", "Ability", 84, "w"), ("hp", "HP", 30, "center"),
    ("atk", "Atk", 30, "center"), ("def", "Def", 30, "center"), ("spa", "SpA", 32, "center"), ("spd", "SpD", 32, "center"),
    ("spe", "Spe", 30, "center"), ("hidden", "Hidden", 66, "w"), ("power", "Power", 44, "center"), ("gender", "Gender", 50, "center"),
    ("hit", "Hit", 32, "center"),
)

GENERATE_HINT = "Generate saves, reloads the game from its start and lists the shiny Pokémon that can be made, with their advances. Click rows to choose them; click again to unselect. None chosen = the next shiny."
GENERATE_HINT_FROM_HERE = (
    "Generate lists the shiny Pokémon this bot can make from where the game is now (the game is paused). Click rows to choose "
    "them; click again to unselect. None chosen = the next shiny."
)


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
        self._running = False
        self._active_bot: str | None = None
        self._last_choices: dict[str, str] = {}

        self.bots = bots_for(game)
        self.names = list(self.bots)
        self.mode_list = tk.Listbox(
            self,
            height=max(1, len(self.names)),
            exportselection=False,
            activestyle="none",
            background=P.card,
            foreground=P.text,
            selectbackground=P.accent_dim,
            selectforeground="white",
            highlightthickness=1,
            highlightbackground=P.border,
            highlightcolor=P.border,
            borderwidth=0,
            font=FONT_BOLD,
        )
        self.mode_list.pack(fill="x", padx=12, pady=(12, 6), ipady=2)
        self._fill_list()
        self.mode_list.bind("<<ListboxSelect>>", lambda _event: (self._mode_changed(), self._on_interaction()))

        self.choice_variable = tk.StringVar()
        self.nature_variable = tk.StringVar(value="Any")
        self.fast_variable = tk.BooleanVar(value=True)
        self._build_options_card()

        self.buttons = tk.Frame(self, background=P.panel)
        self.buttons.pack(fill="x", padx=12, pady=(10, 8))
        self.buttons.columnconfigure((0, 1), weight=1, uniform="buttons")
        self.start_button = ttk.Button(self.buttons, text="Start", style="Accent.TButton", command=self._start_pressed, takefocus=0)
        self.start_button.grid(row=0, column=0, sticky="we", padx=(0, 4))
        self.stop_button = ttk.Button(self.buttons, text="Stop", style="Danger.TButton", command=self._stop_pressed, takefocus=0)
        self.stop_button.grid(row=0, column=1, sticky="we", padx=(4, 0))
        self._enable(self.stop_button, False)
        self._enable(self.start_button, False)

        self.feedback = tk.Frame(self, background=P.panel)
        self.feedback.pack(fill="x")
        self.progress = ttk.Progressbar(self.feedback, mode="determinate", maximum=100)
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
        card = tk.Frame(self, background=P.card, highlightthickness=1, highlightbackground=P.border)
        self.options_card = card
        card.columnconfigure(1, weight=1)

        self._choice_label = tk.Label(card, text="", background=P.card, foreground=P.muted, font=FONT, anchor="w")
        self._choice_label.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=(10, 4))
        self._choice_buttons = tk.Frame(card, background=P.card)
        self._choice_buttons.grid(row=0, column=1, sticky="w", pady=(10, 4))

        self._nature_label = tk.Label(card, text="Nature", background=P.card, foreground=P.muted, font=FONT, anchor="w")
        self._nature_label.grid(row=1, column=0, sticky="w", padx=(12, 8), pady=4)
        self._nature_box = ttk.Combobox(card, textvariable=self.nature_variable, values=["Any", *NATURES], state="readonly", width=14, takefocus=0)
        self._nature_box.grid(row=1, column=1, sticky="w", pady=4)
        self._nature_box.bind("<<ComboboxSelected>>", lambda _event: self._on_interaction())
        self._interactive.append(self._nature_box)

        self._box_label = tk.Label(card, text="", background=P.card, foreground=P.muted, font=FONT, anchor="w")
        self._box_label.grid(row=3, column=0, sticky="w", padx=(12, 8), pady=4)
        self._choice_box = ttk.Combobox(card, textvariable=self.choice_variable, state="readonly", width=24, takefocus=0)
        self._choice_box.grid(row=3, column=1, sticky="w", pady=4)
        self._choice_box.bind("<<ComboboxSelected>>", lambda _event: self._on_interaction())
        self._interactive.append(self._choice_box)

        fast = ttk.Checkbutton(card, text="Fast replay (skip the long wait)", variable=self.fast_variable, command=self._on_interaction, takefocus=0)
        fast.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 8))
        self._interactive.append(fast)

    def _build_targets_section(self, wraplength: int) -> None:
        self.targets_frame = tk.Frame(self, background=P.panel)
        header = tk.Frame(self.targets_frame, background=P.panel)
        header.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(header, text="ADVANCED", background=P.panel, foreground=P.muted, font=FONT_HEADING).pack(side="left")
        generate = ttk.Button(header, text="Generate", style="Compact.TButton", command=self._generate_pressed, takefocus=0)
        generate.pack(side="right")
        self._interactive.append(generate)
        clear = ttk.Button(header, text="Clear", style="Compact.TButton", command=self._clear_pressed, takefocus=0)
        clear.pack(side="right", padx=(0, 6))
        self._interactive.append(clear)
        self.max_advance_variable = tk.StringVar(value="200000")
        max_advance = ttk.Entry(header, textvariable=self.max_advance_variable, width=9, justify="right")
        max_advance.pack(side="right", padx=(0, 8))
        self._interactive.append(max_advance)
        tk.Label(header, text="up to advance", background=P.panel, foreground=P.muted, font=FONT_SMALL).pack(side="right", padx=(0, 4))
        self.targets_hint = tk.Label(
            self.targets_frame, text="", background=P.panel, foreground=P.muted, font=FONT_SMALL, anchor="w", justify="left",
            wraplength=wraplength,
        )
        self.targets_hint.pack(fill="x", padx=14, pady=(0, 4))
        tree_frame = tk.Frame(self.targets_frame, background=P.card, highlightthickness=1, highlightbackground=P.border)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        self.targets_tree = ttk.Treeview(
            tree_frame, columns=[name for name, _title, _width, _anchor in TARGET_COLUMNS], show="headings", selectmode="extended",
            height=12, yscrollcommand=scroll_y.set, takefocus=0,
        )
        for name, title, width, anchor in TARGET_COLUMNS:
            self.targets_tree.heading(name, text=title)
            self.targets_tree.column(name, width=width, anchor=anchor, stretch=name == "ability")
        self.targets_tree.pack(side="left", fill="both", expand=True)
        scroll_y.configure(command=self.targets_tree.yview)
        self.targets_tree.bind("<<TreeviewSelect>>", lambda _event: (self._selection_changed(), self._on_interaction()))
        self.targets_tree.bind("<Button-1>", self._toggle_row)
        self._interactive.append(self.targets_tree)
        self._target_keys: dict[str, tuple[int, int]] = {}
        self._target_advances: dict[str, int] = {}
        self._note = ""

    def _fill_list(self) -> None:
        self.mode_list.configure(height=max(1, len(self.names)))
        self.mode_list.delete(0, "end")
        for name in self.names:
            self.mode_list.insert("end", f"  {name}")

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
        for name, value in zip(choices, values):
            button = ttk.Radiobutton(
                self._choice_buttons, text=name, value=value, variable=self.choice_variable, command=self._on_interaction,
                style="Segment.Toolbutton", takefocus=0, width=9,
            )
            button.pack(side="left", padx=(0, 2))
            self._interactive.append(button)

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
        self.show_targets(True)
        for widget in (self._nature_label, self._nature_box):
            widget.grid() if bot.options.has_nature else widget.grid_remove()
        if not bot.options.supports_targets:
            self.targets_hint.configure(text=bot.options.rows_note or "This bot has no table yet.")
        elif not bot.options.advances_from_boot:
            self.targets_hint.configure(text=GENERATE_HINT_FROM_HERE)
        self._show_choices(bot)
        self.options_card.pack(fill="x", padx=12, before=self.buttons)
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
        self.mode_list.configure(state="disabled" if running else "normal")
        for widget in self._interactive:
            self._enable(widget, not running)
        if not running:
            self.clear_progress()

    @staticmethod
    def _enable(widget: ttk.Widget, enabled: bool) -> None:
        if isinstance(widget, ttk.Combobox):
            widget.configure(state="readonly" if enabled else "disabled")
        else:
            widget.state(["!disabled"] if enabled else ["disabled"])

    def _layout_feedback(self) -> None:
        for widget in (self.progress, self.status_label, self.result_label):
            widget.pack_forget()
        if self._progress_shown:
            self.progress.pack(fill="x", padx=14, pady=(10, 0))
        if self.status_label.cget("text"):
            self.status_label.pack(fill="x", padx=14, pady=(8, 0))
        if self.result_label.cget("text"):
            self.result_label.pack(fill="x", padx=14, pady=(2, 0))

    def set_status(self, text: str, color: str = P.text) -> None:
        self.status_label.configure(text=text, foreground=color)
        self._layout_feedback()

    def set_result(self, text: str, shiny: bool = False) -> None:
        self.result_label.configure(text=text, foreground=P.gold if shiny else P.text)
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


    def show_targets(self, visible: bool) -> None:
        if visible:
            self.targets_frame.pack(fill="both", expand=True)
        else:
            self.targets_frame.pack_forget()

    def _toggle_row(self, event) -> str | None:
        if self.targets_tree.identify_region(event.x, event.y) not in ("cell", "tree"):
            return None
        row = self.targets_tree.identify_row(event.y)
        if row:
            self.targets_tree.selection_toggle(row)
        return "break"

    def _clear_pressed(self) -> None:
        self.targets_tree.selection_set(())
        self._on_interaction()

    def clear_targets(self) -> None:
        self.targets_tree.delete(*self.targets_tree.get_children())
        self._target_keys = {}
        self._target_advances = {}
        self._note = ""
        self.targets_hint.configure(text=GENERATE_HINT)

    def set_targets(self, rows, note: str = "") -> None:
        self.clear_targets()
        self._note = note
        for row in rows:
            iid = f"{row.advance}-{row.pid:08X}"
            self._target_keys[iid] = row.key
            self._target_advances[iid] = row.advance
            hp, atk, defense, spa, spd, spe = row.ivs or ("—",) * 6
            self.targets_tree.insert(
                "", "end", iid=iid,
                values=(f"{row.advance:,}", f"{row.pid:08X}", row.species, row.level, row.shiny, row.nature, row.ability, hp, atk, defense, spa,
                        spd, spe, row.hidden_power, "—" if row.power is None else row.power, row.gender, "" if row.reachable is None else ("✓" if row.reachable else "✗")),
            )
        if rows:
            self.targets_hint.configure(
                text=f"{len(rows)} shiny Pokémon. Click rows to choose them; click again to unselect. None chosen = the next shiny. {note}".strip()
            )
        else:
            self.targets_hint.configure(text="No shiny Pokémon within that many advances: raise the number and press Generate.")

    def _selection_changed(self) -> None:
        picked = len(self.targets_tree.selection())
        total = len(self._target_keys)
        if total:
            self.targets_hint.configure(
                text=(f"{picked} of {total} selected: the hunt aims at them." if picked else f"{total} shiny Pokémon. Click rows to choose them; none chosen = the next shiny.")
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
        self._on_generate()
        self._on_interaction()
