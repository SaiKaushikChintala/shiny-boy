import ctypes
import tkinter as tk
from tkinter import ttk


class P:

    bg = "#09090b"
    panel = "#0f0f13"
    card = "#16161b"
    card_hover = "#1c1c22"
    border = "#26262e"
    border_strong = "#3a3a45"
    text = "#f4f4f5"
    muted = "#a1a1aa"
    subtle = "#71717a"
    disabled = "#52525b"
    accent = "#6366f1"
    accent_hover = "#818cf8"
    accent_press = "#4f46e5"
    accent_dim = "#252552"
    accent_text = "#c7d2fe"
    button = "#1f1f26"
    button_hover = "#2a2a33"
    button_press = "#34343f"
    success = "#34d399"
    success_dim = "#12372c"
    warning = "#fbbf24"
    warning_dim = "#3b2f10"
    danger = "#fb7185"
    danger_dim = "#4a1d2b"
    danger_hover = "#5e2536"
    danger_press = "#6f2b40"
    gold = "#fcd34d"


STATUS_COLORS = {"info": P.text, "success": P.success, "warning": P.warning, "error": P.danger}

UI = "Segoe UI Variable Text"
MONO = "Cascadia Mono"

FONT = (UI, 10)
FONT_BOLD = (UI, 10, "bold")
FONT_SMALL = (UI, 9)
FONT_HEADING = (UI, 8, "bold")
FONT_BIG = (UI, 13, "bold")
FONT_TITLE = (UI, 12, "bold")
FONT_MONO = (MONO, 10)
FONT_MONO_SMALL = (MONO, 9)

_scale = 1.0


def make_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def init_scale(root: tk.Misc) -> None:
    global _scale
    _scale = max(1.0, root.winfo_fpixels("1i") / 96)


def dp(pixels: float) -> int:
    return max(1, round(pixels * _scale)) if pixels else 0


def apply_style(root: tk.Tk) -> None:
    init_scale(root)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        ".",
        background=P.panel,
        foreground=P.text,
        fieldbackground=P.bg,
        troughcolor=P.card,
        bordercolor=P.border,
        lightcolor=P.panel,
        darkcolor=P.panel,
        focuscolor=P.panel,
        font=FONT,
    )

    style.configure("TButton", background=P.button, foreground=P.text, borderwidth=0, focusthickness=0, padding=(dp(16), dp(8)), font=FONT)
    style.map("TButton", background=[("disabled", P.card), ("pressed", P.button_press), ("active", P.button_hover)], foreground=[("disabled", P.disabled)])
    style.configure("Accent.TButton", background=P.accent, foreground="white", font=FONT_BOLD)
    style.map("Accent.TButton", background=[("disabled", P.card), ("pressed", P.accent_press), ("active", P.accent_hover)], foreground=[("disabled", P.disabled)])

    style.configure("Treeview", background=P.card, fieldbackground=P.card, foreground=P.text, borderwidth=0, rowheight=dp(30), font=FONT)
    style.map("Treeview", background=[("selected", P.accent_dim)], foreground=[("selected", "white")])
    style.configure(
        "Treeview.Heading", background=P.button, foreground=P.muted, relief="flat", font=FONT_HEADING, padding=(dp(4), dp(10)), borderwidth=0,
        bordercolor=P.button, lightcolor=P.button, darkcolor=P.button,
    )
    style.map("Treeview.Heading", background=[("active", P.button_hover)], foreground=[("active", P.text)], bordercolor=[("active", P.button_hover)])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure("TCheckbutton", background=P.card, foreground=P.text, padding=(dp(2), dp(4)), font=FONT)
    style.map(
        "TCheckbutton",
        indicatorcolor=[("disabled", P.card), ("selected", P.accent), ("!selected", P.bg)],
        foreground=[("disabled", P.disabled)],
        background=[("active", P.card)],
    )

    style.configure(
        "TCombobox",
        background=P.bg,
        foreground=P.text,
        fieldbackground=P.bg,
        arrowcolor=P.muted,
        bordercolor=P.border_strong,
        lightcolor=P.border_strong,
        darkcolor=P.border_strong,
        arrowsize=dp(14),
        padding=(dp(8), dp(6)),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", P.bg), ("disabled", P.card)],
        foreground=[("readonly", P.text), ("disabled", P.disabled)],
        selectbackground=[("readonly", P.bg)],
        selectforeground=[("readonly", P.text)],
        arrowcolor=[("disabled", P.disabled), ("active", P.text)],
        background=[("active", P.button_hover), ("readonly", P.bg)],
        bordercolor=[("focus", P.accent), ("active", P.border_strong)],
        lightcolor=[("focus", P.accent)],
        darkcolor=[("focus", P.accent)],
    )
    style.configure("TEntry", fieldbackground=P.bg, foreground=P.text, bordercolor=P.border_strong, lightcolor=P.border_strong, darkcolor=P.border_strong, padding=(dp(8), dp(6)), insertcolor=P.text)
    style.map("TEntry", bordercolor=[("focus", P.accent)], lightcolor=[("focus", P.accent)], darkcolor=[("focus", P.accent)], fieldbackground=[("disabled", P.card)], foreground=[("disabled", P.disabled)])
    root.option_add("*TCombobox*Listbox.background", P.card)
    root.option_add("*TCombobox*Listbox.foreground", P.text)
    root.option_add("*TCombobox*Listbox.selectBackground", P.accent_dim)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*TCombobox*Listbox.font", FONT)
    root.option_add("*TCombobox*Listbox.borderWidth", 0)

    style.configure(
        "Horizontal.TProgressbar",
        background=P.accent,
        troughcolor=P.button,
        bordercolor=P.panel,
        lightcolor=P.accent,
        darkcolor=P.accent,
        thickness=dp(6),
    )

    style.layout(
        "Slim.Vertical.TScrollbar",
        [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})],
    )
    style.configure("Slim.Vertical.TScrollbar", background=P.button_hover, troughcolor=P.card, bordercolor=P.card, lightcolor=P.button_hover, darkcolor=P.button_hover, gripcount=0, width=dp(10))
    style.map("Slim.Vertical.TScrollbar", background=[("active", P.border_strong), ("pressed", P.disabled)], lightcolor=[("active", P.border_strong)], darkcolor=[("active", P.border_strong)])
    style.configure("Vertical.TScrollbar", background=P.button_hover, troughcolor=P.card, bordercolor=P.card, arrowcolor=P.muted, lightcolor=P.button_hover, darkcolor=P.button_hover, gripcount=0)
