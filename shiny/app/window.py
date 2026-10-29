import ctypes
import sys
import tkinter as tk
from pathlib import Path

from shiny.app.bot_controller import BotController
from shiny.app.cheat_codes import CheatCodes
from shiny.app.emulation_loop import GBA_FPS, EmulationLoop
from shiny.app.menus import AppMenus
from shiny.app.panels.bot_panel import BotPanel
from shiny.app.panels.info_panel import InfoPanel
from shiny.app.settings import Settings
from shiny.app.states import GameFiles, open_game
from shiny.app.ui.kit import Toast
from shiny.app.ui.menus import DarkMenu
from shiny.app.ui.theme import FONT_BOLD, P, apply_style, dp, make_dpi_aware
from shiny.app.ui.toolbar import Toolbar
from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorError
from shiny.core.emulator.mgba_backend import Emulator
from shiny.core.emulator.no_game import NO_GAME_ROM, OPEN_FIRST, NoGame
from shiny.core.emulator.sound import AudioOutput
from shiny.paths import ASSETS_DIRECTORY, ROMS_DIRECTORY, SAVES_DIRECTORY, SCREENSHOTS_DIRECTORY, STATES_DIRECTORY

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_user32.GetDC.argtypes = [ctypes.c_void_p]
_user32.GetDC.restype = ctypes.c_void_p
_user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.SetStretchBltMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
_gdi32.StretchDIBits.argtypes = [ctypes.c_void_p] + [ctypes.c_int] * 8 + [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint32]
COLORONCOLOR = 3
SRCCOPY = 0x00CC0020


class BitmapInfo(ctypes.Structure):

    _fields_ = [("size", ctypes.c_uint32), ("width", ctypes.c_int32), ("height", ctypes.c_int32), ("planes", ctypes.c_uint16),
                ("bits", ctypes.c_uint16), ("compression", ctypes.c_uint32), ("image_size", ctypes.c_uint32), ("x_pixels", ctypes.c_int32),
                ("y_pixels", ctypes.c_int32), ("colors", ctypes.c_uint32), ("important", ctypes.c_uint32)]


DEFAULT_ROM = ROMS_DIRECTORY / "Pokemon - Emerald Version (USA, Europe).gba"

KEY_MAP = {
    "up": Button.UP,
    "down": Button.DOWN,
    "left": Button.LEFT,
    "right": Button.RIGHT,
    "x": Button.A,
    "z": Button.B,
    "a": Button.L,
    "s": Button.R,
    "return": Button.START,
    "backspace": Button.SELECT,
}

INPUT_WIDGET_CLASSES = {"Entry", "TEntry", "TCombobox", "Listbox", "Text"}
CTRL_KEY_STATE = 0x4
MAX_COUNTED_ADVANCES = 100_000_000
GBA_WIDTH = 240
GBA_HEIGHT = 160
SIDE_PANEL_WIDTH = 900
NARROW_SIDE_PANEL_WIDTH = 460
MENU_LETTERS = (("f", "File"), ("e", "Emulation"), ("a", "Audio"), ("v", "View"), ("h", "Help"))


class Viewer:
    def __init__(self, emulator: Emulator, game, rom: Path, save_path: Path):
        self.emulator = emulator
        self.game = game
        self.rom = rom
        self.save_path = save_path
        self.pressed = 0
        self._redraw_jobs: list = []
        self.held_keys: set[str] = set()
        self.settings = Settings()
        self.audio = AudioOutput()
        self.audio.attach(emulator)

        self.set_taskbar_identity()
        make_dpi_aware()
        self.window = tk.Tk()
        self.window.title(self.window_title())
        self.set_app_icon()
        self.window.configure(background=P.bg)
        self.window.state("zoomed")
        self.window.bind("<KeyPress>", self.on_key_down)
        self.window.bind("<KeyRelease>", self.on_key_up)
        self.window.bind("<F10>", lambda _event: self.open_menu("File"))
        for letter, name in MENU_LETTERS:
            self.window.bind(f"<Alt-{letter}>", lambda _event, name=name: self.open_menu(name))
        apply_style(self.window)

        self.files = GameFiles(self)
        self.loop = EmulationLoop(self)
        self.cheats = CheatCodes(self)
        self.bots = BotController(self)
        self.menus = AppMenus(self)

        if self.has_game:
            self.settings.remember_rom(str(rom))
        self.muted_variable = tk.BooleanVar(value=self.settings.muted)
        self.volume_variable = tk.IntVar(value=self.settings.volume)
        self.speed_variable = tk.IntVar(value=1)
        self.paused_variable = tk.BooleanVar(value=False)
        self.fullscreen_variable = tk.BooleanVar(value=False)
        self.side_panel_variable = tk.BooleanVar(value=True)
        self.scale_variable = tk.IntVar(value=0)

        self.build_layout()
        self.update_info()
        self.set_status("Ready.")
        self.window.focus_force()

    @property
    def has_game(self) -> bool:
        return not getattr(self.emulator, "placeholder", False)

    def window_title(self) -> str:
        return f"{self.emulator.title} ({self.emulator.code})" if self.has_game else self.emulator.title

    def require_game(self) -> bool:
        if not self.has_game:
            self.set_status(OPEN_FIRST, "warning")
        return self.has_game

    def save_settings(self) -> None:
        self.settings.muted = self.muted_variable.get()
        self.settings.save()

    def build_layout(self) -> None:
        window = self.window
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)

        self.toolbar = Toolbar(
            window,
            menus=self.menus.build(),
            speed_variable=self.speed_variable,
            on_pause=self.loop.toggle_pause,
            on_prev_frame=self.loop.step_back,
            on_next_frame=self.loop.step_forward,
            on_reset=self.files.reset,
            on_screenshot=self.files.take_screenshot,
            on_speed=self.loop.on_speed_changed,
            on_panel=self.toggle_side_panel,
        )
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="we")

        self.game_area = tk.Frame(window, background=P.bg)
        self.game_area.grid(row=1, column=0, sticky="nsew")
        self.screen = tk.Canvas(self.game_area, bd=0, highlightthickness=0, background=P.bg)
        self.screen.place(relx=0.5, rely=0.5, anchor="center")
        self.pause_badge = tk.Label(
            self.game_area, text="PAUSED", background=P.warning_dim, foreground=P.warning, font=FONT_BOLD, padx=dp(14), pady=dp(5),
            highlightthickness=1, highlightbackground=P.warning_dim,
        )
        self.scale = 1
        self.screen.bind("<Expose>", lambda _event: self.request_redraw())
        self.game_area_size = (GBA_WIDTH, GBA_HEIGHT)
        self.screen_size = self.emulator.resolution
        self.game_area.bind("<Configure>", self.on_game_area_resized)

        self.side_panel = tk.Frame(window, background=P.panel, width=dp(SIDE_PANEL_WIDTH))
        self.side_panel.grid(row=1, column=1, sticky="ns")
        self.side_panel.pack_propagate(False)
        self.info_panel = InfoPanel(self.side_panel, dp(SIDE_PANEL_WIDTH - 50))
        self.info_panel.pack(fill="x")
        self.bot_panel = BotPanel(
            self.side_panel, self.bots.start_bot, self.bots.stop_bot, self.focus_game, dp(SIDE_PANEL_WIDTH - 50), self.bots.generate_targets, self.game
        )
        self.bot_panel.pack(fill="both", expand=True)
        self.bot_panel.on_targets_visible = lambda _visible: self.fit_side_panel()
        self.fit_side_panel()
        tk.Frame(self.side_panel, background=P.border, width=1).place(x=0, y=0, relheight=1)

        self.toast = Toast(self.game_area)

    def request_redraw(self) -> None:
        if self._redraw_jobs:
            return
        self.draw_screen()
        self._redraw_jobs = [self.window.after(delay, self._redraw_step) for delay in (20, 120)]

    def _redraw_step(self) -> None:
        self.draw_screen()
        self._redraw_jobs = self._redraw_jobs[1:]

    def draw_screen(self) -> None:
        width, height = self.screen_size
        header = BitmapInfo(ctypes.sizeof(BitmapInfo), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        handle = self.screen.winfo_id()
        context = _user32.GetDC(handle)
        _gdi32.SetStretchBltMode(context, COLORONCOLOR)
        _gdi32.StretchDIBits(
            context, 0, 0, width * self.scale, height * self.scale, 0, 0, width, height, self.emulator.frame_bgrx(), ctypes.byref(header), 0, SRCCOPY
        )
        _user32.ReleaseDC(handle, context)

    def on_game_area_resized(self, event: tk.Event) -> None:
        self.game_area_size = (event.width, event.height)
        self.recompute_scale()

    def recompute_scale(self) -> None:
        width, height = self.game_area_size
        screen_width, screen_height = self.screen_size
        fit = max(1, min(width // screen_width, height // screen_height))
        wanted = self.scale_variable.get()
        self.scale = fit if wanted == 0 else max(1, min(wanted, fit))
        self.screen.configure(width=screen_width * self.scale, height=screen_height * self.scale)
        self.request_redraw()

    @staticmethod
    def set_taskbar_identity() -> None:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ShinyBoy.Viewer")
        except (AttributeError, OSError):
            pass

    def set_app_icon(self) -> None:
        icon, picture = ASSETS_DIRECTORY / "logo.ico", ASSETS_DIRECTORY / "logo.png"
        try:
            if icon.is_file():
                self.window.iconbitmap(str(icon))
                self.window.iconbitmap(default=str(icon))
            elif picture.is_file():
                self.app_icon = tk.PhotoImage(file=str(picture))
                self.window.iconphoto(True, self.app_icon)
        except tk.TclError:
            pass

    def open_menu(self, name: str) -> str:
        self.toolbar.open_menu(name)
        return "break"

    def focus_game(self) -> None:
        self.window.focus_set()

    def set_status(self, text: str, level: str = "info") -> None:
        self.toast.show(text, level)

    def reset_inputs(self) -> None:
        self.pressed = 0
        self.held_keys.clear()

    def switch_game(self, emulator: Emulator, game, rom: Path, save_path: Path) -> None:
        self.audio.attach(emulator)
        self.loop.history.clear()
        self.emulator, self.game, self.rom, self.save_path = emulator, game, rom, save_path
        self.screen_size = emulator.resolution
        self.recompute_scale()
        self.reset_inputs()
        self.window.title(self.window_title())
        self.settings.remember_rom(str(rom))
        self.bot_panel.set_game(game)
        self.cheats.restore()
        self.save_settings()
        self.update_info()

    def advances(self) -> int | None:
        steps = getattr(self.game, "advances_since_seed", self.game.advances)()
        return steps if steps is not None and steps <= MAX_COUNTED_ADVANCES else None

    def update_info(self) -> None:
        emulator = self.emulator
        title = f"{emulator.title}  ({emulator.code})"
        if not self.has_game:
            self.info_panel.refresh(
                game="No ROM detected", frame=None, fps=0, callback=None, ids=None, rng=None, map_group_and_number=None, position=None,
            )
            return
        if self.game is None:
            self.info_panel.refresh(
                game=title, frame=emulator.frame_count, fps=self.loop.fps, callback="—", ids=None, rng=None, map_group_and_number=None, position=None,
                notice="Not one of the English Pokémon Ruby, Sapphire, Emerald, FireRed, LeafGreen, Red, Blue, Yellow, Gold, Silver or Crystal: it plays normally, but the debug readouts and bots are off.",
            )
            return
        try:
            ids = self.game.trainer_ids()
            name = self.game.trainer_name()
        except EmulatorError:
            ids, name = None, None
        self.info_panel.refresh(
            game=title,
            frame=emulator.frame_count,
            fps=self.loop.fps,
            callback=self.game.state_name(),
            ids=ids,
            rng=self.game.rng_text(),
            map_group_and_number=self.game.map_group_and_number(),
            position=self.game.player_position(),
            advances=self.advances(),
            name=name,
            speed=self.speed_text(),
        )

    def speed_text(self) -> str | None:
        speed = self.speed_variable.get()
        actual = self.loop.fps / GBA_FPS
        if self.bots.state == "replaying" and self.bot_panel.fast_replay:
            return f"fast replay ({actual:.0f}×)"
        if speed == 0:
            return f"max ({actual:.0f}×)"
        if speed >= 16 and actual < speed * 0.9:
            return f"{speed}× (only {actual:.0f}×: the limit of this computer)"
        return None if speed == 1 else f"{speed}×"

    def apply_fullscreen(self) -> None:
        self.window.attributes("-fullscreen", bool(self.fullscreen_variable.get()))
        self.request_redraw()
        self.focus_game()

    def toggle_fullscreen(self) -> None:
        self.fullscreen_variable.set(not self.fullscreen_variable.get())
        self.apply_fullscreen()

    def fit_side_panel(self) -> None:
        width = dp(NARROW_SIDE_PANEL_WIDTH)
        self.side_panel.configure(width=width)
        self.info_panel.set_wraplength(width - dp(50))
        self.info_panel.arrange(1)
        self.bot_panel.set_wraplength(width - dp(50))

    def apply_side_panel(self) -> None:
        if self.side_panel_variable.get():
            self.side_panel.grid()
        else:
            self.side_panel.grid_remove()
        self.toolbar.set_panel_open(bool(self.side_panel_variable.get()))
        self.request_redraw()
        self.focus_game()

    def toggle_side_panel(self) -> None:
        self.side_panel_variable.set(not self.side_panel_variable.get())
        self.apply_side_panel()

    @property
    def gain(self) -> float:
        if self.muted_variable.get():
            return 0.0
        return (self.settings.volume / 100) ** 2

    def set_volume(self, percent: int) -> None:
        self.settings.volume = percent
        if self.volume_variable.get() != percent:
            self.volume_variable.set(percent)
        self.save_settings()

    def on_mute_changed(self) -> None:
        self.save_settings()
        self.set_status("Audio muted." if self.muted_variable.get() else "Audio unmuted.")
        self.focus_game()

    def toggle_mute(self) -> None:
        self.muted_variable.set(not self.muted_variable.get())
        self.on_mute_changed()

    def on_key_down(self, event: tk.Event) -> str | None:
        if getattr(event.widget, "winfo_class", lambda: "")() in INPUT_WIDGET_CLASSES:
            return None
        if DarkMenu.open_chain or getattr(event.widget, "winfo_toplevel", lambda: self.window)() is not self.window:
            return None

        key = event.keysym.lower()
        self.pressed |= KEY_MAP.get(key, 0)

        if key in self.held_keys:
            return None
        self.held_keys.add(key)

        if len(key) == 1 and key.isdigit():
            slot = self.files.slot_for_key(key)
            if event.state & CTRL_KEY_STATE:
                self.files.save_slot(slot)
            else:
                self.files.load_slot(slot)
            return None

        match key:
            case "bracketleft":
                self.files.change_slot_bank(-1)
            case "bracketright":
                self.files.change_slot_bank(1)
            case "escape":
                if self.fullscreen_variable.get():
                    self.toggle_fullscreen()
                else:
                    self.window.destroy()
            case "o" if event.state & CTRL_KEY_STATE:
                self.files.load_rom_from_file()
            case "p":
                self.loop.toggle_pause()
            case "comma":
                self.loop.step_back()
            case "period":
                self.loop.step_forward()
            case "m":
                self.toggle_mute()
            case "f2":
                self.files.reset()
            case "f11":
                self.toggle_fullscreen()
            case "f12":
                self.files.take_screenshot()
            case "tab":
                self.toggle_side_panel()
                return "break"
        return None

    def on_key_up(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        self.pressed &= ~KEY_MAP.get(key, 0)
        self.held_keys.discard(key)

    def run(self) -> None:
        try:
            self.cheats.restore()
            self.loop.tick()
            self.window.mainloop()
        finally:
            self.save_settings()
            self.bots.shut_down()
            self.audio.close()


ROM_SUFFIXES = {".gba", ".gb", ".gbc", ".sgb", ".zip"}


def find_rom() -> Path | None:
    recent = [Path(path) for path in Settings().recent if Path(path).is_file()]
    if recent:
        return recent[0]
    if DEFAULT_ROM.is_file():
        return DEFAULT_ROM
    found = sorted(path for path in ROMS_DIRECTORY.glob("*") if path.suffix.lower() in ROM_SUFFIXES) if ROMS_DIRECTORY.is_dir() else []
    return found[0] if found else None


def show_error(text: str) -> None:
    print(f"FAIL: {text}")
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Shiny Boy", text)
    root.destroy()


def main() -> int:
    for folder in (ROMS_DIRECTORY, SAVES_DIRECTORY, STATES_DIRECTORY, SCREENSHOTS_DIRECTORY):
        folder.mkdir(parents=True, exist_ok=True)
    rom = Path(sys.argv[1]) if len(sys.argv) > 1 else find_rom()
    if rom is None:
        emulator, game, rom, save_path = NoGame(), None, NO_GAME_ROM, SAVES_DIRECTORY / "(no game).sav"
    else:
        try:
            emulator, game, save_path = open_game(rom)
        except EmulatorError as error:
            show_error(str(error))
            return 1
    Viewer(emulator, game, rom, save_path).run()
    return 0
