import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

from shiny.app.states import SLOT_COUNT, SLOTS_PER_BANK
from shiny.app.ui.menus import DarkMenu
from shiny.app.ui.theme import FONT, FONT_MONO, P
from shiny.app.ui.toolbar import SPEEDS

if TYPE_CHECKING:
    from shiny.app.window import Viewer

SHORTCUTS = [
    ("Arrow keys", "D-pad"),
    ("X  /  Z", "A  /  B"),
    ("A  /  S", "L  /  R"),
    ("Enter  /  Backspace", "Start  /  Select"),
    ("", ""),
    ("1 – 9,  0", "Load a state (slots 1 – 10; 0 is slot 10)"),
    ("Ctrl + 1 – 9,  0", "Save a state (the same slots)"),
    ("P", "Pause / resume"),
    (",   and   .", "Back / forward one frame (pauses the game)"),
    ("F2", "Reset the game"),
    ("M", "Mute / unmute"),
    ("F12", "Screenshot"),
    ("F11", "Fullscreen"),
    ("Tab", "Show / hide the side panel"),
    ("Ctrl + O", "Load a ROM"),
    ("F10  or  Alt + F / E / A / V / H", "Open the File / Emulation / Audio / View / Help menu"),
    ("Esc", "Leave fullscreen, or quit"),
]
GAME_SIZES = range(1, 7)


class AppMenus:
    def __init__(self, app: "Viewer"):
        self.app = app
        self.slot_menu_entries: list[tuple[int, DarkMenu, int]] = []
        self.recent_menu: DarkMenu | None = None

    def build(self) -> dict[str, DarkMenu]:
        app, window, files = self.app, self.app.window, self.app.files

        file_menu = DarkMenu(window)
        file_menu.add_command(label="Load ROM...", accelerator="Ctrl+O", command=files.load_rom_from_file)
        self.recent_menu = DarkMenu(window, postcommand=self.refresh_recent_menu)
        file_menu.add_cascade(label="Recent ROMs", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Load save game...", command=files.load_save_from_file)
        file_menu.add_separator()
        file_menu.add_cascade(label="Load state", menu=self._slot_menu(files.load_slot, "From file...", files.load_state_from_file))
        file_menu.add_cascade(label="Save state", menu=self._slot_menu(files.save_slot, "To file...", files.save_state_to_file))
        file_menu.add_separator()
        file_menu.add_command(label="Screenshot", accelerator="F12", command=files.take_screenshot)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Esc", command=window.destroy)

        emulation_menu = DarkMenu(window)
        emulation_menu.add_checkbutton(label="Pause", accelerator="P", variable=app.paused_variable, command=app.loop.toggle_pause_from_menu)
        emulation_menu.add_command(label="Reset", accelerator="F2", command=files.reset)
        emulation_menu.add_separator()
        speed_menu = DarkMenu(window)
        for value, label in SPEEDS:
            speed_menu.add_radiobutton(
                label="Maximum" if value == 0 else label, value=value, variable=app.speed_variable, command=app.loop.on_speed_changed
            )
        emulation_menu.add_cascade(label="Speed", menu=speed_menu)
        emulation_menu.add_separator()
        emulation_menu.add_command(label="Cheats...", command=app.cheats.show_dialog)

        audio_menu = DarkMenu(window)
        audio_menu.add_checkbutton(label="Mute", accelerator="M", variable=app.muted_variable, command=app.on_mute_changed)
        audio_menu.add_separator()
        audio_menu.add_slider("Volume", app.volume_variable, command=app.set_volume)

        view_menu = DarkMenu(window)
        view_menu.add_checkbutton(label="Fullscreen", accelerator="F11", variable=app.fullscreen_variable, command=app.apply_fullscreen)
        view_menu.add_checkbutton(label="Side panel", accelerator="Tab", variable=app.side_panel_variable, command=app.apply_side_panel)
        scale_menu = DarkMenu(window)
        scale_menu.add_radiobutton(label="Fit the window", value=0, variable=app.scale_variable, command=app.recompute_scale)
        for factor in GAME_SIZES:
            scale_menu.add_radiobutton(label=f"{factor}×", value=factor, variable=app.scale_variable, command=app.recompute_scale)
        view_menu.add_cascade(label="Game size", menu=scale_menu)

        help_menu = DarkMenu(window)
        help_menu.add_command(label="Keyboard shortcuts", command=self.show_shortcuts)

        return {"File": file_menu, "Emulation": emulation_menu, "Audio": audio_menu, "View": view_menu, "Help": help_menu}

    def _slot_menu(self, action, file_label: str, file_action) -> DarkMenu:
        window = self.app.window
        menu = DarkMenu(window, postcommand=self.refresh_slot_labels)
        for first in range(1, SLOT_COUNT + 1, SLOTS_PER_BANK):
            last = min(first + SLOTS_PER_BANK - 1, SLOT_COUNT)
            group = menu if SLOT_COUNT <= SLOTS_PER_BANK else DarkMenu(window)
            for slot in range(first, last + 1):
                group.add_command(label=f"Slot {slot}", command=lambda slot=slot: action(slot))
                self.slot_menu_entries.append((slot, group, len(group.entries) - 1))
            if group is not menu:
                menu.add_cascade(label=f"Slots {first} – {last}", menu=group)
        menu.add_separator()
        menu.add_command(label=file_label, command=file_action)
        return menu

    def refresh_slot_labels(self) -> None:
        for slot, menu, index in self.slot_menu_entries:
            path = self.app.files.slot_path(slot)
            if path.is_file():
                description = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime))
            else:
                description = "empty"
            menu.entryconfigure(index, label=f"Slot {slot}   ({description})")

    def refresh_recent_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        existing = [path for path in self.app.settings.recent if Path(path).is_file()]
        if not existing:
            self.recent_menu.add_command(label="(none)", state="disabled")
        for path in existing:
            self.recent_menu.add_command(label=Path(path).name, command=lambda path=path: self.app.files.load_rom(Path(path)))

    def show_shortcuts(self) -> None:
        window = tk.Toplevel(self.app.window)
        window.title("Keyboard shortcuts")
        window.configure(background=P.panel)
        window.resizable(False, False)
        window.transient(self.app.window)
        frame = tk.Frame(window, background=P.panel)
        frame.pack(padx=24, pady=20)
        for row, (keys, action) in enumerate(SHORTCUTS):
            if not keys:
                tk.Frame(frame, background=P.border, height=1).grid(row=row, column=0, columnspan=2, sticky="we", pady=8)
                continue
            tk.Label(frame, text=keys, background=P.panel, foreground=P.accent, font=FONT_MONO, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(0, 28), pady=2
            )
            tk.Label(frame, text=action, background=P.panel, foreground=P.text, font=FONT, anchor="w").grid(row=row, column=1, sticky="w", pady=2)
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 18))
        window.bind("<Escape>", lambda _event: window.destroy())
        window.focus_set()
