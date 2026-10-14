import tkinter as tk
from tkinter import ttk


class P:

    bg = "#0b0d12"
    panel = "#12151d"
    card = "#181c27"
    border = "#262c3b"
    text = "#e7eaf1"
    muted = "#8991a6"
    disabled = "#4a5165"
    accent = "#4da3ff"
    accent_hover = "#74b8ff"
    accent_dim = "#1d3a5e"
    button = "#212737"
    button_hover = "#2c3447"
    success = "#4ade80"
    warning = "#fbbf24"
    danger = "#f87171"
    danger_dim = "#6b2830"
    danger_hover = "#8a3540"
    gold = "#ffd24a"


STATUS_COLORS = {"info": P.text, "success": P.success, "warning": P.warning, "error": P.danger}

UI = "Segoe UI"
MONO = "Consolas"

FONT = (UI, 10)
FONT_BOLD = (UI, 10, "bold")
FONT_SMALL = (UI, 9)
FONT_HEADING = (UI, 8, "bold")
FONT_BIG = (UI, 12, "bold")
FONT_MONO = (MONO, 10)
FONT_MONO_SMALL = (MONO, 9)


def apply_style(root: tk.Tk) -> None:
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
    style.configure("TButton", background=P.button, foreground=P.text, borderwidth=0, focusthickness=0, padding=(14, 6))
    style.map(
        "TButton",
        background=[("disabled", P.card), ("pressed", P.accent_dim), ("active", P.button_hover)],
        foreground=[("disabled", P.disabled)],
    )
    style.configure("Accent.TButton", background=P.accent, foreground="#07111f", font=FONT_BOLD)
    style.map(
        "Accent.TButton",
        background=[("disabled", P.card), ("pressed", P.accent_dim), ("active", P.accent_hover)],
        foreground=[("disabled", P.disabled)],
    )
    style.configure("Danger.TButton", background=P.danger_dim, foreground="white", font=FONT_BOLD)
    style.map(
        "Danger.TButton",
        background=[("disabled", P.card), ("pressed", P.danger_dim), ("active", P.danger_hover)],
        foreground=[("disabled", P.disabled)],
    )
    style.configure("Compact.TButton", padding=(4, 5))
    style.configure("Treeview", background=P.card, fieldbackground=P.card, foreground=P.text, borderwidth=0, rowheight=24, font=FONT)
    style.map("Treeview", background=[("selected", P.accent_dim)], foreground=[("selected", "white")])
    style.configure("Treeview.Heading", background=P.button, foreground=P.muted, relief="flat", font=FONT)
    style.map("Treeview.Heading", background=[("active", P.button_hover)])
    style.configure("Tool.TButton", background=P.panel, padding=(10, 5))
    style.map("Tool.TButton", background=[("pressed", P.accent_dim), ("active", P.button_hover)])

    style.configure(
        "Segment.Toolbutton", background=P.button, foreground=P.text, padding=(10, 5), borderwidth=0, anchor="center"
    )
    style.map(
        "Segment.Toolbutton",
        background=[("disabled", P.card), ("selected", P.accent_dim), ("active", P.button_hover)],
        foreground=[("disabled", P.disabled), ("selected", "white")],
    )

    style.configure("TCheckbutton", background=P.card, foreground=P.text, padding=(2, 4))
    style.map(
        "TCheckbutton",
        indicatorcolor=[("disabled", P.card), ("selected", P.accent), ("!selected", P.bg)],
        foreground=[("disabled", P.disabled)],
        background=[("active", P.card)],
    )

    style.configure(
        "TCombobox",
        background=P.button,
        foreground=P.text,
        fieldbackground=P.bg,
        arrowcolor=P.text,
        bordercolor=P.border,
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", P.bg), ("disabled", P.card)],
        foreground=[("readonly", P.text), ("disabled", P.disabled)],
        selectbackground=[("readonly", P.bg)],
        selectforeground=[("readonly", P.text)],
        arrowcolor=[("disabled", P.disabled)],
        background=[("active", P.button_hover)],
    )
    root.option_add("*TCombobox*Listbox.background", P.card)
    root.option_add("*TCombobox*Listbox.foreground", P.text)
    root.option_add("*TCombobox*Listbox.selectBackground", P.accent_dim)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*TCombobox*Listbox.font", FONT)

    style.configure(
        "Horizontal.TProgressbar",
        background=P.accent,
        troughcolor=P.card,
        bordercolor=P.card,
        lightcolor=P.accent,
        darkcolor=P.accent,
        thickness=6,
    )
    style.configure(
        "Vertical.TScrollbar",
        background=P.button,
        troughcolor=P.card,
        bordercolor=P.card,
        arrowcolor=P.muted,
        lightcolor=P.button,
        darkcolor=P.button,
        gripcount=0,
    )
    style.map("Vertical.TScrollbar", background=[("active", P.button_hover)])
