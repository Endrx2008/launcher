# Copyright (C) 2026 Enrico Miot (EndrX)
# Licensed under GNU GPL v3 or later — see the LICENSE file or <https://www.gnu.org/licenses/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Skorpion OS guide (Hyprland and i3 releases). Shows index_dark.html or
index_light.html (launcher theme) and tells the page which desktop it runs
on and which keys are really bound there, read from the live configuration:
  Hyprland  ~/.config/hypr/hyprland.lua
  i3        ~/.config/i3/config
The page then shows the real key combinations on its cards."""

import os
import re
import sys
import json
import webbrowser
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skcommon.py lives in ~/.launcher

import skcommon  # noqa: E402

# Wayland app_id: ~/.config/hypr/hyprland.lua matches it to float and center the guide
APP_ID = "skorpion-guide"

# In VMs without 3D acceleration /etc/profile.d/99-swrast.sh forces software
# OpenGL: Chromium's GPU process then often draws a blank page, so render in software.
if os.environ.get("LIBGL_ALWAYS_SOFTWARE") == "1":
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu" not in flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + " --disable-gpu").strip()


# ──────────────────────────────────────────────────────────────────────────
# KEY NAMES AND COMMANDS
# ──────────────────────────────────────────────────────────────────────────

KEY_NAMES = {
    "alt": "Alt", "mod1": "Alt", "shift": "Shift", "ctrl": "Ctrl", "control": "Ctrl",
    "primary": "Ctrl", "super": "Super", "mod4": "Super", "win": "Super",
    "return": "Enter", "enter": "Enter", "escape": "Esc", "space": "Space",
    "ograve": "Ò", "left": "←", "right": "→", "up": "↑", "down": "↓", "tab": "Tab",
}


def key_name(k):
    k = k.strip()
    return KEY_NAMES.get(k.lower(), k.upper() if len(k) == 1 else k)


def classify(command):
    """Which guide card a bound command belongs to (None = not shown)."""
    c = command.lower()
    if "launcher.py" in c:
        return "launcher"
    if "visualizer.py" in c:
        return "guide"
    if "multicalculator" in c:
        return "calculator"
    if "skai_manager.py" in c:
        return "skai_manager"
    if re.search(r"\b(nano|vim?|nvim|gedit|xed|featherpad|geany)\b", c) and \
            re.search(r"config|\.lua|\.conf", c):
        return "config"
    if re.search(r"\b(pcmanfm|thunar|nemo|nautilus|caja|dolphin)\b", c):
        return "file_manager"
    if re.search(r"\b(firefox|firefox-esr|chromium|google-chrome|brave)\b", c):
        return "browser"
    if re.search(r"\b(fuzzel|dmenu_run|dmenu|rofi|wofi)\b", c):
        return "app_menu"
    if c in ("window.close", "kill", "i3-msg kill") or c.endswith("i3-msg kill"):
        return "close"
    if c in ("window.fullscreen", "fullscreen toggle"):
        return "fullscreen"
    if c in ("window.float", "floating toggle"):
        return "floating"
    if c in ("group.toggle", "layout tabbed"):
        return "tabs"
    if c == "layout stacking":
        return "stacking"
    if c in ("layout:togglesplit", "layout toggle split"):
        return "toggle_split"
    if c in ("layout:preselect r", "split h"):
        return "split_h"
    if c in ("layout:preselect d", "split v"):
        return "split_v"
    if c in ("submap:resize", 'mode "resize"'):
        return "resize"
    if c in ("hyprctl reload", "reload"):
        return "reload"
    if c == "restart":
        return "restart"
    if "hyprshutdown" in c or "hl.dsp.exit" in c or "i3-nagbar" in c or c == "exit":
        return "exit"
    if c == "focus mode_toggle":
        return "focus_mode"
    if c == "focus parent":
        return "focus_parent"
    if re.search(r"\b(kitty|alacritty|foot|xterm|i3-sensible-terminal|x-terminal-emulator)\b", c):
        return "terminal"
    return None


def collect(binds):
    """[(keys, command)] -> {action: {"keys": [...], "cmd": "..."}}.
    For each action an F-key binding wins (the Master Key system), then the first one."""
    result = {}
    for keys, command in binds:
        action = classify(command)
        if not action:
            continue
        has_f = any(re.fullmatch(r"F\d+", k) for k in keys)
        old = result.get(action)
        if old is None or (has_f and not old["f"]):
            result[action] = {"keys": keys, "cmd": command, "f": has_f}
    for value in result.values():
        value.pop("f")
    function_keys = [v["keys"] for a, v in result.items()
                     if a in ("launcher", "guide", "file_manager", "browser", "terminal", "config", "close")]
    if function_keys and all(k[0] == function_keys[0][0] for k in function_keys):
        result["master"] = {"keys": [function_keys[0][0]], "cmd": ""}
    return result


# ──────────────────────────────────────────────────────────────────────────
# HYPRLAND: ~/.config/hypr/hyprland.lua
# ──────────────────────────────────────────────────────────────────────────

LUA_TOKEN = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(\.\.)|([A-Za-z_]\w*)|(--.*))')


def lua_concat(expr, variables):
    """Value of a Lua expression made of string literals, variables and `..`."""
    out, pos = [], 0
    while pos < len(expr):
        m = LUA_TOKEN.match(expr, pos)
        if not m or m.group(5) is not None:
            break
        dq, sq, _concat, ident = m.group(1), m.group(2), m.group(3), m.group(4)
        if dq is not None or sq is not None:
            out.append(dq if dq is not None else sq)
        elif ident is not None:
            if ident not in variables:
                return None
            out.append(variables[ident])
        pos = m.end()
    return "".join(out)


def split_top_level(args):
    """Splits "a, f(b, c), d" on the top-level commas."""
    parts, depth, quote_char, cur = [], 0, None, ""
    for ch in args:
        if quote_char:
            cur += ch
            if ch == quote_char:
                quote_char = None
            continue
        if ch in "\"'":
            quote_char = ch
        elif ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def hyprland_bindings():
    path = os.path.expanduser("~/.config/hypr/hyprland.lua")
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return None
    variables = {"home": os.path.expanduser("~")}
    binds = []
    for line in lines:
        stripped = line.strip()
        m = re.match(r"local\s+(\w+)\s*=\s*(.+)$", stripped)
        if m:
            value = lua_concat(m.group(2), variables)
            if value is not None:
                variables[m.group(1)] = value
            continue
        # top-level binds only: loops and submaps are indented
        if not line.startswith("hl.bind("):
            continue
        inner = stripped[len("hl.bind("):]
        inner = inner[:inner.rfind(")")] if ")" in inner else inner
        args = split_top_level(inner)
        if len(args) < 2:
            continue
        combo = lua_concat(args[0], variables)
        if not combo:
            continue
        keys = [key_name(k) for k in combo.split("+") if k.strip()]
        action = args[1]
        m_exec = re.match(r"hl\.dsp\.exec_cmd\((.*)\)$", action)
        if m_exec:
            command = lua_concat(m_exec.group(1), variables)
        else:
            m_dsp = re.match(r"hl\.dsp\.([\w.]+)\((.*)\)$", action)
            if not m_dsp:
                continue
            name, arg = m_dsp.group(1), m_dsp.group(2).strip()
            literal = lua_concat(arg, variables) if arg.startswith(('"', "'")) else None
            command = f"{name}:{literal}" if literal else name
        if command:
            binds.append((keys, command))
    return collect(binds)


# ──────────────────────────────────────────────────────────────────────────
# i3: ~/.config/i3/config
# ──────────────────────────────────────────────────────────────────────────

def i3_bindings():
    for path in ("~/.config/i3/config", "~/.i3/config"):
        path = os.path.expanduser(path)
        if os.path.exists(path):
            break
    else:
        return None
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return None
    variables, binds, in_mode = {}, [], False
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("mode "):
            in_mode = True
            continue
        if in_mode:
            if s == "}":
                in_mode = False
            continue
        m = re.match(r"set\s+(\$\w+)\s+(.+)$", s)
        if m:
            variables[m.group(1)] = m.group(2).strip().strip('"')
            continue
        m = re.match(r"bind(?:sym|code)\s+((?:--\S+\s+)*)(\S+)\s+(.+)$", s)
        if not m:
            continue
        combo = m.group(2)
        for name, value in variables.items():
            combo = combo.replace(name, value)
        keys = [key_name(k) for k in combo.split("+")]
        command = m.group(3).strip()
        command = re.sub(r"^exec\s+(--no-startup-id\s+)?", "", command).strip().strip('"')
        binds.append((keys, command))
    return collect(binds)


def live_bindings(env):
    try:
        if env == "hyprland":
            return hyprland_bindings()
        if env == "i3":
            return i3_bindings()
    except Exception as e:
        print(f"Could not read the key bindings: {e}")
    return None


# ──────────────────────────────────────────────────────────────────────────
# WINDOW
# ──────────────────────────────────────────────────────────────────────────

def guide_url():
    """file:// URL of the guide in the launcher theme, with the desktop and
    its live key bindings in the fragment (read by the page's script)."""
    theme = skcommon.load_theme()
    html_file = os.path.join(HERE, f"index_{theme}.html")
    if not os.path.exists(html_file):
        html_file = os.path.join(HERE, "index_dark.html")
    env = skcommon.desktop()
    fragment = f"env={env}"
    bindings = live_bindings(env)
    if bindings:
        fragment += "&keys=" + quote(json.dumps(bindings, separators=(",", ":")))
    return html_file, fragment


def main():
    html_file, fragment = guide_url()
    try:
        from PySide6.QtWidgets import QApplication, QMainWindow
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        # qt6-webengine missing: the guide opens in the web browser
        webbrowser.open("file://" + quote(html_file) + "#" + fragment)
        return

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Skorpion OS Guide")
            self.resize(860, 700)
            self.browser = QWebEngineView()
            url = QUrl.fromLocalFile(html_file)
            url.setFragment(fragment, QUrl.ParsingMode.TolerantMode)
            self.browser.load(url)
            self.setCentralWidget(self.browser)
            # Ctrl+Q closes the guide (Alt+F5 works too); Esc closes the open card
            QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    QGuiApplication.setDesktopFileName(APP_ID)
    window = MainWindow()
    skcommon.prepare_window(window)
    skcommon.center_window(window)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
