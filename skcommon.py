# Copyright (C) 2026 Enrico Miot (EndrX)
# Licensed under GNU GPL v3 or later — see the LICENSE file or <https://www.gnu.org/licenses/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared pieces of the Skorpion launcher, multicalculator, guide and SKAI
Manager: the wizard-style colour themes, the desktop environment we run in
and the choice of the Ollama model. Launcher, multicalculator and guide are
in the Lite (i3) and Mantis (Hyprland) editions; SKAI Manager is in every
edition, Cinnamon included (there desktop() answers 'other')."""

import os
import re
import json
import shutil
import pathlib

CONFIG_DIR = pathlib.Path.home() / ".config" / "pylauncher_settings"
THEME_FILE = CONFIG_DIR / "theme_config.json"

FONT = "'JetBrains Mono', 'JetBrainsMono Nerd Font', 'Fira Code', monospace"

# Same colours as the SKAI setup wizard (dark), plus a light version of them.
PALETTES = {
    "dark": {
        "bg": "#0d0d0d", "bg2": "#141414", "bg3": "#1c1c1c", "hover": "#222222",
        "accent": "#e05c00", "accent2": "#ff7a1a", "on_accent": "#000000",
        "text": "#e8e8e8", "muted": "#9a9a9a", "dim": "#666666",
        "border": "#2a2a2a", "green": "#39d353", "red": "#ff4444", "blue": "#4da6ff",
        "select": "rgba(224, 92, 0, 0.22)", "disabled": "#333333",
    },
    "light": {
        "bg": "#f6f4f1", "bg2": "#ffffff", "bg3": "#efebe6", "hover": "#e8e3dc",
        "accent": "#c75200", "accent2": "#e05c00", "on_accent": "#ffffff",
        "text": "#1a1a1a", "muted": "#5e5a55", "dim": "#8a8580",
        "border": "#d9d3cb", "green": "#1a7f37", "red": "#cf222e", "blue": "#0b63c5",
        "select": "rgba(199, 82, 0, 0.16)", "disabled": "#e3ded7",
    },
}


def load_theme() -> str:
    try:
        with open(THEME_FILE, "r", encoding="utf-8") as f:
            theme = json.load(f).get("theme", "dark")
        return theme if theme in PALETTES else "dark"
    except Exception:
        return "dark"


def save_theme(theme: str):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump({"theme": theme}, f)
    except Exception as e:
        print(f"Error saving theme config: {e}")


# ──────────────────────────────────────────────────────────────────────────
# DESKTOP ENVIRONMENT
# ──────────────────────────────────────────────────────────────────────────

def desktop() -> str:
    """'hyprland', 'i3' or 'other'."""
    current = (os.environ.get("XDG_CURRENT_DESKTOP", "") + ":" +
               os.environ.get("DESKTOP_SESSION", "")).lower()
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or "hyprland" in current:
        return "hyprland"
    if os.environ.get("I3SOCK") or "i3" in current.split(":"):
        return "i3"
    return "other"


DESKTOP_NAMES = {"hyprland": "Hyprland", "i3": "i3", "other": "Linux"}


# ──────────────────────────────────────────────────────────────────────────
# OLLAMA MODEL: every SKAI app uses the installed model with the most
# parameters (details.parameter_size of /api/tags, e.g. "14.8B", "494.03M");
# the size on disk only breaks ties, or decides when Ollama gives no count.
# ──────────────────────────────────────────────────────────────────────────

_PARAMETERS = re.compile(r"([\d.]+)\s*([KMBT]?)", re.IGNORECASE)
_SCALE = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def parameter_count(model: dict) -> float:
    """Parameters of one entry of /api/tags; 0 when unknown."""
    text = str((model.get("details") or {}).get("parameter_size") or "").strip()
    match = _PARAMETERS.match(text)
    if not match:
        return 0.0
    try:
        return float(match.group(1)) * _SCALE[match.group(2).upper()]
    except ValueError:
        return 0.0


def biggest_model(models):
    """The entry of /api/tags with the most parameters (None for no models)."""
    if not models:
        return None
    return max(models, key=lambda m: (parameter_count(m), m.get("size", 0) or 0))


# Shown by every SKAI tool when Ollama cannot be reached or has no model.
AI_UNAVAILABLE_TITLE = "AI unavailable"
AI_UNAVAILABLE_MESSAGE = ("AI features are disabled.\n"
                          "It looks like you turned off AI in the SKAI settings.\n"
                          "Without a selected model, SKAI cannot function.")


def is_wayland() -> bool:
    try:
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.instance():
            return QGuiApplication.platformName().startswith("wayland")
    except Exception:
        pass
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def terminal_command():
    """Terminal used for Terminal=true apps, as an argv prefix."""
    env = desktop()
    candidates = ["kitty"]
    if env == "i3":
        candidates.append("i3-sensible-terminal")
    candidates += ["x-terminal-emulator", "foot", "alacritty", "xterm"]
    for cmd in candidates:
        if shutil.which(cmd):
            if cmd in ("x-terminal-emulator", "xterm", "i3-sensible-terminal"):
                return [cmd, "-e"]
            return [cmd]
    return None


def logout_command():
    env = desktop()
    if env == "hyprland":
        # same command as Alt+Shift+E in ~/.config/hypr/hyprland.lua
        return ["sh", "-c", "command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown "
                            "|| hyprctl dispatch 'hl.dsp.exit()'"]
    if env == "i3" and shutil.which("i3-msg"):
        return ["i3-msg", "exit"]
    return None


def lock_command():
    env = desktop()
    if env == "hyprland" and shutil.which("hyprlock") and \
            (pathlib.Path.home() / ".config" / "hypr" / "hyprlock.conf").exists():
        return ["hyprlock"]
    if env == "i3" and shutil.which("i3lock"):
        return ["i3lock", "-c", "0d0d0d"]
    return None


def prepare_window(window):
    """Call before show(). The window stays a normal window, so on i3 it is
    tiled like any other app (no Dialog flag, which would make i3 float it).
    On Hyprland floating is decided only by the window rules in hyprland.lua
    through the app_id."""
    return


def center_window(window):
    """Center on the screen under the mouse. Works on X11 (i3);
    on Wayland a window cannot place itself, the compositor does it."""
    if is_wayland():
        return
    from PySide6.QtGui import QCursor, QGuiApplication
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    if not screen:
        return
    area = screen.availableGeometry()
    frame = window.frameGeometry()
    frame.moveCenter(area.center())
    window.move(frame.topLeft())
