# Copyright (C) 2026 Enrico Miot (EndrX)
# Licensed under GNU GPL v3 or later — see the LICENSE file or <https://www.gnu.org/licenses/>
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
import sys
import json
import html
import shlex
import shutil
import pathlib
import threading
import subprocess
from string import Template
from datetime import datetime
from functools import partial

import requests

from PySide6 import QtWidgets, QtGui, QtCore, QtNetwork
from PySide6.QtCore import Signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # skcommon, safe_math
import skcommon
import skai_memory_bridge as memory_bridge  # SKAI_ Memory: shared memory of the SKAI apps (optional)
from skcommon import PALETTES, FONT, CONFIG_DIR

ICON_DIR = "/usr/share/icons/Ars-Dark-Icons/apps/48"
SPECIAL_ICON_DIR = "/usr/share/icons/Sours-Full-Color/apps/scalable"
ICON_THEME = "Ars-Dark-Icons"

OLLAMA_URL = "http://localhost:11434"

# Wayland app_id: ~/.config/hypr/hyprland.lua matches it to float and center the launcher
APP_ID = "skorpion-launcher"
WINDOW_TITLE = "Skorpion Launcher"
INSTANCE_NAME = f"skorpion-launcher-{os.getuid()}"

# freedesktop main categories -> (label shown, icon names to try)
CATEGORY_INFO = {
    "AudioVideo":  ("Multimedia",  ["applications-multimedia"]),
    "Development": ("Development", ["applications-development"]),
    "Education":   ("Education",   ["applications-education"]),
    "Game":        ("Games",       ["applications-games"]),
    "Graphics":    ("Graphics",    ["applications-graphics"]),
    "Network":     ("Internet",    ["applications-internet", "applications-network"]),
    "Office":      ("Office",      ["applications-office"]),
    "Science":     ("Science",     ["applications-science"]),
    "Settings":    ("Settings",    ["preferences-system", "applications-system"]),
    "System":      ("System",      ["applications-system"]),
    "Utility":     ("Accessories", ["applications-utilities", "applications-accessories"]),
    "Other":       ("Other",       ["applications-other"]),
}
CATEGORY_ALIASES = {"Audio": "AudioVideo", "Video": "AudioVideo"}

BLACKLIST = {"i3", "gnome-shell", "plasmashell", "xfce4-panel", "lxpanel",
             "portal", "desktop", "pcmanfm-qt"}

FIELD_CODE = re.compile(r"%[fFuUdDnNickvm]")

ENGLISH = QtCore.QLocale(QtCore.QLocale.Language.English, QtCore.QLocale.Country.UnitedStates)


# ──────────────────────────────────────────────────────────────────────────
# THEME (same look as the SKAI setup wizard)
# ──────────────────────────────────────────────────────────────────────────

STYLESHEET = Template("""
QMainWindow, QWidget#central { background-color: $bg; }
QWidget { color: $text; font-family: $font; }
QWidget#topBar, QWidget#chatHeader { background-color: $bg2; border-bottom: 1px solid $border; }
QLabel { background: transparent; }
QLabel#clock { color: $accent; font-size: 16pt; font-weight: bold; letter-spacing: 2px; }
QLabel#date, QLabel#appComment, QLabel#typing { color: $dim; }
QLabel#section { color: $accent2; font-weight: bold; letter-spacing: 1px; }
QLabel#chatState { color: $muted; padding: 16px; }
QLabel#modelName { color: $accent; font-weight: bold; letter-spacing: 1px; }
QWidget#appRow { background: transparent; }
QListWidget {
    background-color: $bg2; border: 1px solid $border; border-radius: 6px;
    padding: 4px; outline: 0;
}
QListWidget::item { border-radius: 4px; padding: 2px; }
QListWidget::item:hover { background-color: $hover; }
QListWidget::item:selected { background-color: $select; color: $text; }
QTextEdit {
    background-color: $bg; color: $text; border: none; padding: 8px;
}
QLineEdit {
    background-color: $bg2; color: $text; border: 1px solid $border;
    border-radius: 4px; padding: 7px 10px;
}
QLineEdit:focus { border: 1px solid $accent; }
QPushButton {
    background-color: transparent; color: $muted; border: 1px solid $border;
    border-radius: 4px; padding: 6px 12px; letter-spacing: 1px;
}
QPushButton:hover { border-color: $accent; color: $text; }
QPushButton:disabled { color: $dim; }
QPushButton#primary {
    background-color: $accent; color: $on_accent; border: none; font-weight: bold;
}
QPushButton#primary:hover { background-color: $accent2; }
QPushButton#flat { border: none; font-size: 14pt; color: $dim; padding: 0; }
QPushButton#flat:hover { color: $accent; }
QToolButton { border: none; padding: 3px; border-radius: 4px; color: $muted; }
QToolButton:hover { background-color: $select; color: $text; }
QSplitter::handle { background-color: $border; width: 1px; }
QScrollBar:vertical, QScrollBar:horizontal { background: transparent; width: 8px; height: 8px; }
QScrollBar::handle { background: $border; border-radius: 4px; min-height: 24px; min-width: 24px; }
QScrollBar::handle:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QToolTip { background-color: $bg2; color: $text; border: 1px solid $accent; padding: 4px; }
QMenu { background-color: $bg2; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 5px 18px; border-radius: 4px; }
QMenu::item:selected { background-color: $select; }
QMessageBox { background-color: $bg; }
""")


def setup_icon_theme():
    """Without a desktop platform theme (Hyprland, i3) Qt finds no icon theme:
    use the Skorpion one so category/toolbar icons are not blank. A theme set
    by the desktop (e.g. through qt6ct) is kept."""
    if QtGui.QIcon.themeName() in ("", "hicolor") and os.path.isdir(f"/usr/share/icons/{ICON_THEME}"):
        QtGui.QIcon.setThemeName(ICON_THEME)


def load_special_icon(icon_name):
    """Loads an icon from SPECIAL_ICON_DIR, falling back to the icon theme."""
    for ext in ['png', 'svg', 'xpm']:
        icon_path = os.path.join(SPECIAL_ICON_DIR, f"{icon_name}.{ext}")
        if os.path.isfile(icon_path):
            return QtGui.QIcon(icon_path)
    return QtGui.QIcon.fromTheme(icon_name)


def create_special_icon_label(icon_name, tooltip, callback):
    """Flat clickable button with a special icon (text if the icon is missing)."""
    button = QtWidgets.QToolButton()
    button.setAutoRaise(True)
    icon = load_special_icon(icon_name)
    if icon.isNull():
        button.setText(tooltip)
    else:
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(22, 22))
    button.setToolTip(tooltip)
    button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    button.clicked.connect(callback)
    return button


# ──────────────────────────────────────────────────────────────────────────
# .desktop FILES
# ──────────────────────────────────────────────────────────────────────────

def _applications_dirs():
    """$XDG_DATA_HOME first, so the user's own .desktop files win."""
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    dirs = [data_home] + [d for d in data_dirs.split(":") if d]
    for extra in ("/usr/local/share", "/usr/share"):
        if extra not in dirs:
            dirs.append(extra)
    seen, result = set(), []
    for d in dirs:
        path = os.path.join(d, "applications")
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _main_category(categories):
    for cat in categories:
        cat = CATEGORY_ALIASES.get(cat, cat)
        if cat in CATEGORY_INFO:
            return cat
    return "Other"


def _command_exists(cmd):
    if os.path.isabs(cmd):
        return os.access(cmd, os.X_OK)
    return shutil.which(cmd) is not None


def parse_desktop_file(filepath, desktop_id="", current_desktops=(), terminal=None):
    """Reads the [Desktop Entry] group; returns None for entries that must not
    be shown. Names are the untranslated (English) ones."""
    entry = {}
    in_main = False
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("["):
                    if in_main:
                        break  # [Desktop Action ...] groups follow: ignore them
                    in_main = (line == "[Desktop Entry]")
                    continue
                if in_main and "=" in line:
                    key, value = line.split("=", 1)
                    entry.setdefault(key.strip(), value.strip())
    except OSError:
        return None

    def flag(key):
        return entry.get(key, "").lower() == "true"

    def str_list(key):
        return [x for x in entry.get(key, "").split(";") if x]

    if entry.get("Type", "Application") != "Application":
        return None
    if flag("NoDisplay") or flag("Hidden"):
        return None
    only = str_list("OnlyShowIn")
    if only and not any(d in only for d in current_desktops):
        return None
    if any(d in str_list("NotShowIn") for d in current_desktops):
        return None
    if entry.get("TryExec") and not _command_exists(entry["TryExec"]):
        return None

    name = entry.get("Name", "")
    raw_exec = entry.get("Exec", "")
    if not name or not raw_exec:
        return None
    try:
        parts = shlex.split(raw_exec)
    except ValueError:
        parts = raw_exec.split()
    # drop the freedesktop field codes (%f %F %u %U %i %c %k ...)
    parts = [FIELD_CODE.sub("", p).replace("%%", "%") for p in parts]
    parts = [p for p in parts if p]
    if not parts:
        return None

    if flag("Terminal") and terminal:
        parts = terminal + parts  # e.g. nano, htop: they need a terminal window

    return {
        'id': desktop_id,
        'name': name,
        'exec': " ".join(shlex.quote(p) for p in parts),
        'icon': entry.get("Icon", ""),
        'category': _main_category(str_list("Categories")),
        'comment': entry.get("Comment", ""),
        'generic': entry.get("GenericName", ""),
        'keywords': entry.get("Keywords", "").replace(";", " "),
        'path': entry.get("Path", ""),
    }


def find_applications():
    current_desktops = [d for d in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":") if d]
    terminal = skcommon.terminal_command()
    seen_ids = set()
    applications = []
    for base in _applications_dirs():
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for filename in sorted(files):
                if not filename.endswith(".desktop"):
                    continue
                filepath = os.path.join(root, filename)
                desktop_id = os.path.relpath(filepath, base).replace(os.sep, "-")
                if desktop_id in seen_ids:
                    continue  # same id earlier in the search path overrides this one
                seen_ids.add(desktop_id)
                app = parse_desktop_file(filepath, desktop_id, current_desktops, terminal)
                if not app:
                    continue
                exec_bin = os.path.basename(shlex.split(app['exec'])[0]).lower()
                if app['name'].lower() in BLACKLIST or exec_bin in BLACKLIST:
                    continue
                applications.append(app)
    return sorted(applications, key=lambda x: x['name'].lower())


def start_detached(argv, cwd=None):
    subprocess.Popen(
        argv,
        cwd=cwd if cwd and os.path.isdir(cwd) else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# OLLAMA (background threads, results back through Qt signals)
# ──────────────────────────────────────────────────────────────────────────

def detect_ollama_model():
    """Asks Ollama's /api/tags for the largest installed model.
    Returns None if Ollama is not reachable or has no models."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if not resp.ok:
            return None
        models = resp.json().get("models", [])
        if not models:
            return None
        best = max(models, key=lambda m: m.get("size", 0))
        return best["name"]
    except Exception:
        return None


class OllamaBridge(QtCore.QObject):
    """Signals emitted from worker threads, delivered on the UI thread."""
    model_detected = Signal(object)
    token_received = Signal(int, str)
    response_finished = Signal(int, str)
    error = Signal(int, str)


def stream_chat(bridge, request_id, model, messages, cancel):
    """Calls Ollama /api/chat with streaming and emits the tokens one by one."""
    full_text = ""
    try:
        with requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
            stream=True,
            timeout=(5, 300),  # loading a big model the first time can take minutes
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if cancel.is_set():
                    break
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                if data.get("error"):
                    raise RuntimeError(data["error"])
                token = data.get("message", {}).get("content", "")
                if token:
                    full_text += token
                    bridge.token_received.emit(request_id, token)
                if data.get("done"):
                    break
        bridge.response_finished.emit(request_id, full_text)
    except Exception as exc:
        bridge.error.emit(request_id, str(exc))


# ──────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ──────────────────────────────────────────────────────────────────────────

class AppLauncher(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(880, 600)
        self._icon_cache = {}
        self.desktop = skcommon.desktop()

        self.applications = find_applications()
        self.categories = self.group_applications_by_category(self.applications)

        self.preferred_apps = []
        self.config_dir = CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "preferred_apps.json"
        self.category_order_file = self.config_dir / "categories_order.json"
        self.splitter_config_file = self.config_dir / "splitter_sizes.json"

        self.toggle_button = QtWidgets.QPushButton(self)
        self.toggle_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.toggle_button.setToolTip("Toggle theme (Ctrl+T)")
        self.toggle_button.clicked.connect(self.toggle_dark_mode)

        self.ollama = OllamaBridge(self)
        self.ollama.model_detected.connect(self._on_model_detected)
        self.ollama.token_received.connect(self._on_token)
        self.ollama.response_finished.connect(self._on_response_finished)
        self.ollama.error.connect(self._on_response_error)
        self._request_id = 0
        self._cancel = threading.Event()
        self._busy = False

        self.dark_mode = skcommon.load_theme() == "dark"

        # ── Top bar: power actions, clock, theme toggle ──
        top_bar_widget = QtWidgets.QWidget()
        top_bar_widget.setObjectName("topBar")
        top_bar_widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        top_bar_widget.setFixedHeight(46)
        top_bar = QtWidgets.QHBoxLayout(top_bar_widget)
        top_bar.setContentsMargins(10, 0, 10, 0)
        top_bar.setSpacing(10)

        self.system_icons_layout = QtWidgets.QHBoxLayout()
        self.system_icons_layout.setSpacing(4)
        power = [
            ('system-shutdown', 'Shut down', ['systemctl', 'poweroff'], True),
            ('system-reboot', 'Restart', ['systemctl', 'reboot'], True),
            ('system-suspend', 'Sleep', ['systemctl', 'suspend'], False),
            ('system-lock-screen', 'Lock screen', skcommon.lock_command(), False),
            ('system-log-out', 'Log out', skcommon.logout_command(), True),
        ]
        for icon_name, label, argv, confirm in power:
            if argv:
                self.system_icons_layout.addWidget(create_special_icon_label(
                    icon_name, label, partial(self.power_action, label, argv, confirm)))

        self.category_title = QtWidgets.QLabel()
        self.category_title.setObjectName("clock")
        self.date_label = QtWidgets.QLabel()
        self.date_label.setObjectName("date")
        clock_box = QtWidgets.QHBoxLayout()
        clock_box.setSpacing(10)
        clock_box.addWidget(self.category_title, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        clock_box.addWidget(self.date_label, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.update_time()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

        top_bar.addLayout(self.system_icons_layout)
        top_bar.addStretch()
        top_bar.addLayout(clock_box)
        top_bar.addStretch()
        top_bar.addWidget(self.toggle_button)

        # ── Left side: home page / app list + search box ──
        self.stacked_widget = QtWidgets.QStackedWidget()

        self.category_page = QtWidgets.QWidget()
        self.category_layout = QtWidgets.QVBoxLayout(self.category_page)
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setSpacing(8)

        fav_title = QtWidgets.QLabel("FAVORITES")
        fav_title.setObjectName("section")
        self.category_layout.addWidget(fav_title)

        self.preferred_apps_widget = QtWidgets.QListWidget()
        self.preferred_apps_widget.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.preferred_apps_widget.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.preferred_apps_widget.setWrapping(False)
        self.preferred_apps_widget.setMovement(QtWidgets.QListView.Movement.Static)
        self.preferred_apps_widget.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.preferred_apps_widget.setIconSize(QtCore.QSize(40, 40))
        self.preferred_apps_widget.setGridSize(QtCore.QSize(100, 80))
        self.preferred_apps_widget.setWordWrap(True)
        self.preferred_apps_widget.setFixedHeight(96)
        self.preferred_apps_widget.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.preferred_apps_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.preferred_apps_widget.customContextMenuRequested.connect(self._favorite_context_menu)
        self.preferred_apps_widget.itemClicked.connect(self.launch_selected)
        self.category_layout.addWidget(self.preferred_apps_widget)

        self.no_favorites_label = QtWidgets.QLabel(
            "No favorites yet: open a category and press + next to an app."
        )
        self.no_favorites_label.setObjectName("date")
        self.no_favorites_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.no_favorites_label.setFixedHeight(96)
        self.category_layout.addWidget(self.no_favorites_label)

        cat_title = QtWidgets.QLabel("CATEGORIES")
        cat_title.setObjectName("section")
        self.category_layout.addWidget(cat_title)

        self.category_list_widget = QtWidgets.QListWidget()
        self.category_list_widget.setIconSize(QtCore.QSize(32, 32))
        self.category_list_widget.setDragDropMode(
            QtWidgets.QAbstractItemView.DragDropMode.InternalMove
        )
        self.category_list_widget.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.category_list_widget.setDragEnabled(True)
        self.category_list_widget.setAcceptDrops(True)
        self.category_list_widget.setDropIndicatorShown(True)
        self.category_list_widget.itemClicked.connect(self.show_category_apps)
        self.category_list_widget.model().rowsMoved.connect(self.save_category_order)
        self.category_layout.addWidget(self.category_list_widget, 1)

        self.stacked_widget.addWidget(self.category_page)

        self.app_list_container = QtWidgets.QWidget()
        self.app_list_layout = QtWidgets.QVBoxLayout(self.app_list_container)
        self.app_list_layout.setContentsMargins(0, 0, 0, 0)
        self.app_list_layout.setSpacing(8)

        list_header = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("←  Home")
        self.back_button.setFixedWidth(110)
        self.back_button.clicked.connect(self.show_categories)
        self.list_title = QtWidgets.QLabel("")
        self.list_title.setObjectName("section")
        list_header.addWidget(self.back_button)
        list_header.addStretch()
        list_header.addWidget(self.list_title)
        self.app_list_layout.addLayout(list_header)

        self.app_list_widget = QtWidgets.QListWidget()
        self.app_list_widget.setIconSize(QtCore.QSize(40, 40))
        self.app_list_widget.itemDoubleClicked.connect(self.launch_selected)
        self.app_list_layout.addWidget(self.app_list_widget, 1)
        self.stacked_widget.addWidget(self.app_list_container)

        search_layout = QtWidgets.QHBoxLayout()
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("Search apps…  (just start typing)")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setMinimumWidth(200)
        self.search_box.textChanged.connect(self.search_apps)
        self.search_box.returnPressed.connect(self.launch_first_result)
        search_layout.addWidget(self.search_box)

        self.search_btn = QtWidgets.QPushButton("Search")
        self.search_btn.setObjectName("primary")
        self.search_btn.setFixedWidth(84)
        self.search_btn.clicked.connect(self.search_apps)
        search_layout.addWidget(self.search_btn)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(14, 12, 14, 14)
        left_layout.setSpacing(10)
        left_layout.addWidget(self.stacked_widget, 1)
        left_layout.addLayout(search_layout)

        # The chat panel is always added; the Ollama check decides if it works
        self.chat_widget = self.create_chat_widget()
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(self.chat_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([560, 320])
        self.load_splitter_sizes()

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(top_bar_widget)
        main_layout.addWidget(self.splitter, 1)

        central_widget = QtWidgets.QWidget()
        central_widget.setObjectName("central")
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.load_preferred_apps()
        self.update_preferred_apps()
        self.load_category_order()
        self.populate_categories()
        self.show_categories()

        for widget in (self.preferred_apps_widget, self.category_list_widget,
                       self.app_list_widget, self.search_box):
            widget.installEventFilter(self)
        self.preferred_apps_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.category_list_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.app_list_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        for keys, slot in (("Ctrl+T", self.toggle_dark_mode),
                           ("Ctrl+I", self.show_shortcuts),
                           ("Ctrl+F", self.focus_search)):
            QtGui.QShortcut(QtGui.QKeySequence(keys), self, activated=slot)

        self.apply_dark_mode_style()
        self.start_model_detection()

    # ──────────────────────────────────────────────────────────────────────
    # CHAT PANEL
    # ──────────────────────────────────────────────────────────────────────

    def create_chat_widget(self):
        """Side chat panel. While Ollama is being looked for it shows a waiting
        state; if Ollama is missing or has no model it says so, with a Retry button."""
        self.ollama_model = None
        self.conversation_history = []
        self._bot_response_started = False

        widget = QtWidgets.QWidget()
        widget.setMinimumWidth(0)
        main_layout = QtWidgets.QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setObjectName("chatHeader")
        header.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setFixedHeight(38)
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        self.model_label = QtWidgets.QLabel("SKAI ASSISTANT")
        self.model_label.setObjectName("modelName")
        header_layout.addWidget(self.model_label)
        header_layout.addStretch()
        main_layout.addWidget(header)

        self.chat_stack = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.chat_stack, 1)

        # ── State page (waiting / AI not available) ──
        state_page = QtWidgets.QWidget()
        state_layout = QtWidgets.QVBoxLayout(state_page)
        state_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_state_label = QtWidgets.QLabel("Looking for Ollama…")
        self.chat_state_label.setObjectName("chatState")
        self.chat_state_label.setWordWrap(True)
        self.chat_state_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.retry_button = QtWidgets.QPushButton("Retry")
        self.retry_button.setFixedWidth(120)
        self.retry_button.clicked.connect(self.start_model_detection)
        self.retry_button.hide()
        state_layout.addStretch()
        state_layout.addWidget(self.chat_state_label)
        state_layout.addWidget(self.retry_button, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        state_layout.addStretch()
        self.chat_stack.addWidget(state_page)

        # ── Chat page ──
        chat_page = QtWidgets.QWidget()
        chat_layout = QtWidgets.QVBoxLayout(chat_page)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self.chat_display = QtWidgets.QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setAcceptRichText(True)
        chat_layout.addWidget(self.chat_display, 1)

        self.typing_label = QtWidgets.QLabel("")
        self.typing_label.setObjectName("typing")
        self.typing_label.setContentsMargins(12, 2, 12, 0)
        chat_layout.addWidget(self.typing_label)

        input_widget = QtWidgets.QWidget()
        input_layout = QtWidgets.QHBoxLayout(input_widget)
        input_layout.setContentsMargins(8, 6, 8, 8)

        self.chat_input = QtWidgets.QLineEdit()
        self.chat_input.setPlaceholderText('Type a message… (e.g. "open firefox")')
        self.chat_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.chat_input)

        self.send_chat_btn = QtWidgets.QPushButton("➤")
        self.send_chat_btn.setObjectName("primary")
        self.send_chat_btn.setFixedSize(36, 34)
        self.send_chat_btn.setToolTip("Send")
        self.send_chat_btn.clicked.connect(self._send_or_stop)
        input_layout.addWidget(self.send_chat_btn)
        chat_layout.addWidget(input_widget)
        self.chat_stack.addWidget(chat_page)

        return widget

    def start_model_detection(self):
        self.chat_state_label.setText("Looking for Ollama…")
        self.retry_button.hide()
        self.chat_stack.setCurrentIndex(0)
        threading.Thread(
            target=lambda: self.ollama.model_detected.emit(detect_ollama_model()),
            daemon=True,
        ).start()

    def _on_model_detected(self, model):
        self.ollama_model = model
        if not model:
            self.model_label.setText("SKAI ASSISTANT")
            self.chat_state_label.setText(
                "AI features are turned off.\n\n"
                "Ollama is not running or has no model installed, so the "
                "assistant can't work. The launcher itself works as usual."
            )
            self.retry_button.show()
            self.chat_stack.setCurrentIndex(0)
            return
        self.model_label.setText(model.upper())
        self.chat_stack.setCurrentIndex(1)
        if self.chat_display.document().isEmpty():
            self._append_chat_html(
                '<span class="sys">Hi! I can help you find and open apps, '
                'e.g. <i>"open firefox"</i>.</span>'
            )

    def _chat_stylesheet(self):
        p = PALETTES["dark" if self.dark_mode else "light"]
        return (
            "p { margin: 0; padding: 0; }"
            f".you {{ color: {p['accent']}; font-weight: bold; }}"
            f".bot {{ color: {p['green']}; font-weight: bold; }}"
            f".sys {{ color: {p['muted']}; font-style: italic; }}"
            f".err {{ color: {p['red']}; }}"
        )

    def _append_chat_html(self, html_text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertHtml(html_text + "<br>")
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    # ── Ollama streaming ───────────────────────────────────────────────

    def _send_or_stop(self):
        if self._busy:
            self._cancel.set()  # stop the answer being written
            return
        self.send_message()

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.chat_input.setEnabled(not busy)
        self.send_chat_btn.setText("■" if busy else "➤")
        self.send_chat_btn.setToolTip("Stop" if busy else "Send")

    def send_message(self):
        if not self.ollama_model:
            return
        message = self.chat_input.text().strip()
        if not message:
            return

        self.chat_input.clear()
        self._append_chat_html(f'<span class="you">You:</span> {html.escape(message)}')

        launch_result = self._try_launch_from_message(message)

        self.conversation_history.append({"role": "user", "content": message})
        if launch_result:
            self.conversation_history[-1]["content"] += f"\n[System: {launch_result}]"

        app_names = [a["name"] for a in self.applications[:80]]
        system_prompt = (
            "You are an assistant built into an application launcher on Linux "
            f"(Skorpion OS, {skcommon.DESKTOP_NAMES[self.desktop]} desktop). "
            "You help the user find and open applications. "
            f"The available apps include: {', '.join(app_names)}. "
            "If the user asks to open an app, confirm the result. "
            "Always answer in English, briefly."
        )
        # SKAI_ Memory: what the other SKAI apps know about this question (nothing when it is not installed)
        memory = memory_bridge.open_memory("launcher")
        if memory:
            system_prompt += "\n\n" + memory_bridge.recall_text(memory, message)
        self._last_question = message
        messages = [{"role": "system", "content": system_prompt.rstrip()}] + self.conversation_history

        self.typing_label.setText("● Ollama is answering…")
        self._set_busy(True)
        self._request_id += 1
        self._cancel = threading.Event()
        self._bot_response_started = False
        threading.Thread(
            target=stream_chat,
            args=(self.ollama, self._request_id, self.ollama_model, messages, self._cancel),
            daemon=True,
        ).start()

    def _try_launch_from_message(self, message: str) -> str:
        msg_lower = message.lower()
        if not re.search(r"\b(open|launch|start|run)\b", msg_lower):
            return ""
        best_app = None
        best_score = 0
        for app in self.applications:
            name_lower = app["name"].lower()
            if name_lower in msg_lower:
                score = len(name_lower)
                if score > best_score:
                    best_score = score
                    best_app = app
        if best_app:
            try:
                self.start_app(best_app)
                return f"App '{best_app['name']}' started successfully."
            except Exception as e:
                return f"Could not start '{best_app['name']}': {e}"
        return "No matching app found."

    def _on_token(self, request_id: int, token: str):
        if request_id != self._request_id:
            return
        if not self._bot_response_started:
            self._bot_response_started = True
            self._append_chat_html('<span class="bot">SKAI:</span> ')
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            cursor.deletePreviousChar()  # stay on the "SKAI:" line
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _on_response_finished(self, request_id: int, full_text: str):
        if request_id != self._request_id:
            return
        stopped = self._cancel.is_set()
        self._bot_response_started = False
        self.typing_label.setText("")
        self._append_chat_html(' <span class="sys">(stopped)</span>' if stopped else "")
        self.conversation_history.append({"role": "assistant", "content": full_text})
        if not stopped and full_text.strip():
            threading.Thread(target=self._remember_exchange, args=(full_text,), daemon=True).start()
        self._set_busy(False)
        self.chat_input.setFocus()

    def _remember_exchange(self, answer: str):
        """Keep the exchange in this app's notes of SKAI_ Memory (off the UI thread: it runs the sudo helper)."""
        memory = memory_bridge.open_memory("launcher")
        if memory:
            memory_bridge.remember_turn(memory, "launcher", getattr(self, "_last_question", ""), answer)

    def _on_response_error(self, request_id: int, error_msg: str):
        if request_id != self._request_id:
            return
        self._bot_response_started = False
        self.typing_label.setText("")
        self._append_chat_html(f'<br><span class="err">✗ Error: {html.escape(error_msg)}</span>')
        # the question had no answer: drop it so the next turn stays consistent
        if self.conversation_history and self.conversation_history[-1]["role"] == "user":
            self.conversation_history.pop()
        self._set_busy(False)

    # ──────────────────────────────────────────────────────────────────────
    # THEME
    # ──────────────────────────────────────────────────────────────────────

    def apply_dark_mode_style(self):
        palette = dict(PALETTES["dark" if self.dark_mode else "light"], font=FONT)
        self.setStyleSheet(STYLESHEET.substitute(palette))
        self.chat_display.document().setDefaultStyleSheet(self._chat_stylesheet())
        self.update_toggle_icon()

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_dark_mode_style()
        skcommon.save_theme("dark" if self.dark_mode else "light")

    def update_toggle_icon(self):
        # Same wording as the wizard's toggle: it names the theme you switch to
        self.toggle_button.setText("☀  LIGHT" if self.dark_mode else "☾  DARK")

    # ──────────────────────────────────────────────────────────────────────
    # APPLICATIONS
    # ──────────────────────────────────────────────────────────────────────

    def group_applications_by_category(self, applications):
        categories = {}
        for app in applications:
            categories.setdefault(app.get('category') or "Other", []).append(app)
        return categories

    def populate_categories(self):
        self.category_list_widget.clear()
        ordered_cats = getattr(self, 'category_order', [])
        if ordered_cats:
            ordered_cats = [cat for cat in ordered_cats if cat in self.categories]
            ordered_cats.extend(sorted(cat for cat in self.categories if cat not in ordered_cats))
        else:
            ordered_cats = sorted(self.categories.keys(),
                                  key=lambda c: (c == "Other", CATEGORY_INFO.get(c, (c,))[0]))

        for cat in ordered_cats:
            label, icon_names = CATEGORY_INFO.get(cat, (cat, []))
            count = len(self.categories[cat])
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, cat)
            item.setToolTip(f"{count} app" + ("s" if count != 1 else ""))
            for icon_name in icon_names + ["folder"]:
                icon = QtGui.QIcon.fromTheme(icon_name)
                if not icon.isNull():
                    item.setIcon(icon)
                    break
            font = item.font()
            font.setPointSize(11)
            item.setFont(font)
            item.setSizeHint(QtCore.QSize(item.sizeHint().width(), 44))
            self.category_list_widget.addItem(item)
        if self.category_list_widget.count():
            self.category_list_widget.setCurrentRow(0)

    def create_app_list_item(self, app):
        widget = QtWidgets.QWidget()
        widget.setObjectName("appRow")
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(self.load_icon(app['icon']).pixmap(40, 40))
        icon_label.setFixedSize(40, 40)
        layout.addWidget(icon_label)

        text_box = QtWidgets.QVBoxLayout()
        text_box.setSpacing(0)
        name_label = QtWidgets.QLabel(app['name'])
        font = name_label.font()
        font.setPointSize(11)
        font.setBold(True)
        name_label.setFont(font)
        text_box.addWidget(name_label)
        subtitle = app.get('comment') or app.get('generic')
        if subtitle:
            comment_label = QtWidgets.QLabel(subtitle)
            comment_label.setObjectName("appComment")
            text_box.addWidget(comment_label)
        layout.addLayout(text_box, 1)

        plus_button = QtWidgets.QPushButton("−" if app in self.preferred_apps else "+")
        plus_button.setObjectName("flat")
        plus_button.setFixedSize(28, 28)
        plus_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        plus_button.setToolTip("Add to / remove from favorites")
        plus_button.clicked.connect(partial(self.plus_button_clicked, app, plus_button))
        layout.addWidget(plus_button)

        return widget

    def _fill_app_list(self, apps, title):
        self.app_list_widget.clear()
        for app in apps:
            list_item = QtWidgets.QListWidgetItem()
            widget = self.create_app_list_item(app)
            list_item.setSizeHint(widget.sizeHint())
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, app)
            if app.get('comment'):
                list_item.setToolTip(app['comment'])
            self.app_list_widget.addItem(list_item)
            self.app_list_widget.setItemWidget(list_item, widget)
        if self.app_list_widget.count():
            self.app_list_widget.setCurrentRow(0)
        self.list_title.setText(title.upper())
        self.stacked_widget.setCurrentWidget(self.app_list_container)

    def show_category_apps(self, item):
        category = item.data(QtCore.Qt.ItemDataRole.UserRole) or item.text()
        apps = sorted(self.categories.get(category, []), key=lambda x: x['name'].lower())
        self._fill_app_list(apps, item.text())
        self.app_list_widget.setFocus()

    def search_apps(self):
        text = self.search_box.text().strip().lower()
        if not text:
            self.show_categories(keep_focus=True)
            return

        def score(app):
            name = app['name'].lower()
            if name.startswith(text):
                return 0
            if text in name:
                return 1
            if text in app.get('generic', '').lower() or text in app.get('keywords', '').lower():
                return 2
            if text in app.get('comment', '').lower():
                return 3
            return None

        scored = [(score(app), app) for app in self.applications]
        filtered = [app for s, app in sorted(
            ((s, a) for s, a in scored if s is not None),
            key=lambda x: (x[0], x[1]['name'].lower()))]
        self._fill_app_list(filtered, f"{len(filtered)} result" + ("s" if len(filtered) != 1 else ""))

    def launch_first_result(self):
        if self.stacked_widget.currentWidget() is self.app_list_container:
            item = self.app_list_widget.currentItem()
            if item:
                self.launch_selected(item)

    def focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def show_categories(self, keep_focus=False):
        if not keep_focus and self.search_box.text():
            self.search_box.blockSignals(True)
            self.search_box.clear()
            self.search_box.blockSignals(False)
        self.stacked_widget.setCurrentWidget(self.category_page)
        if not keep_focus:
            self.category_list_widget.setFocus()

    def load_icon(self, icon_name):
        if icon_name in self._icon_cache:
            return self._icon_cache[icon_name]
        icon = QtGui.QIcon()
        if icon_name:
            for ext in ['png', 'svg', 'xpm']:
                icon_path = os.path.join(ICON_DIR, f"{icon_name}.{ext}")
                if os.path.isfile(icon_path):
                    icon = QtGui.QIcon(icon_path)
                    break
            else:
                if os.path.isabs(icon_name) and os.path.isfile(icon_name):
                    icon = QtGui.QIcon(icon_name)
                else:
                    icon = QtGui.QIcon.fromTheme(icon_name)
        if icon.isNull():
            icon = QtGui.QIcon.fromTheme("application-x-executable")
        self._icon_cache[icon_name] = icon
        return icon

    def start_app(self, app):
        start_detached(shlex.split(app['exec']), app.get('path'))

    def launch_selected(self, item):
        app = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if app:
            try:
                self.start_app(app)
                self.close()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Could not start {app['name']}.\n{e}")

    def power_action(self, label, argv, confirm):
        if confirm:
            answer = QtWidgets.QMessageBox.question(
                self, label, f"{label} now?\nUnsaved work in open apps will be lost.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        try:
            start_detached(argv)
            self.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"{label} failed.\n{e}")

    def launch_calculator(self):
        try:
            script_dir = pathlib.Path(__file__).parent.resolve()
            calculator_path = script_dir / "multicalculator_ui.py"
            if calculator_path.exists():
                start_detached([sys.executable, str(calculator_path)])
                self.close()
            else:
                QtWidgets.QMessageBox.warning(self, "File not found",
                                              f"Calculator not found: {calculator_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Could not start the calculator.\n{e}")

    # ──────────────────────────────────────────────────────────────────────
    # FAVORITES, CATEGORY ORDER, SPLITTER
    # ──────────────────────────────────────────────────────────────────────

    def plus_button_clicked(self, app, button):
        if app not in self.preferred_apps:
            self.preferred_apps.append(app)
            button.setText("−")
        else:
            self.preferred_apps.remove(app)
            button.setText("+")
        self.update_preferred_apps()
        self.save_preferred_apps()

    def _favorite_context_menu(self, pos):
        item = self.preferred_apps_widget.itemAt(pos)
        if not item:
            return
        app = item.data(QtCore.Qt.ItemDataRole.UserRole)
        menu = QtWidgets.QMenu(self)
        open_action = menu.addAction("Open")
        remove_action = menu.addAction("Remove from favorites")
        chosen = menu.exec(self.preferred_apps_widget.mapToGlobal(pos))
        if chosen is open_action:
            self.launch_selected(item)
        elif chosen is remove_action and app in self.preferred_apps:
            self.preferred_apps.remove(app)
            self.update_preferred_apps()
            self.save_preferred_apps()

    def update_preferred_apps(self):
        self.preferred_apps_widget.clear()
        has_apps = bool(self.preferred_apps)
        self.preferred_apps_widget.setVisible(has_apps)
        self.no_favorites_label.setVisible(not has_apps)
        for app in self.preferred_apps:
            item = QtWidgets.QListWidgetItem(app['name'])
            item.setIcon(self.load_icon(app['icon']))
            item.setToolTip(app['name'] + (f"\n{app['comment']}" if app.get('comment') else ""))
            item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, app)
            self.preferred_apps_widget.addItem(item)

    def save_preferred_apps(self):
        try:
            data = [app['exec'] for app in self.preferred_apps]
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving preferred apps: {e}")

    def load_preferred_apps(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                by_exec = {app['exec']: app for app in self.applications}
                # keep the order in which the user added them
                self.preferred_apps = [by_exec[e] for e in dict.fromkeys(data) if e in by_exec]
        except Exception as e:
            print(f"Error loading preferred apps: {e}")

    def save_category_order(self, *args):
        try:
            categories = [self.category_list_widget.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
                          for i in range(self.category_list_widget.count())]
            with open(self.category_order_file, 'w', encoding='utf-8') as f:
                json.dump(categories, f)
        except Exception as e:
            print(f"Error saving category order: {e}")

    def load_category_order(self):
        try:
            if self.category_order_file.exists():
                with open(self.category_order_file, 'r', encoding='utf-8') as f:
                    self.category_order = json.load(f)
            else:
                self.category_order = []
        except Exception as e:
            print(f"Error loading category order: {e}")
            self.category_order = []

    def load_splitter_sizes(self):
        try:
            if self.splitter_config_file.exists():
                with open(self.splitter_config_file, 'r', encoding='utf-8') as f:
                    sizes = json.load(f)
                if isinstance(sizes, list) and len(sizes) == 2:
                    self.splitter.setSizes([int(s) for s in sizes])
        except Exception as e:
            print(f"Error loading splitter sizes: {e}")

    def save_splitter_sizes(self):
        try:
            sizes = self.splitter.sizes()
            with open(self.splitter_config_file, 'w', encoding='utf-8') as f:
                json.dump(sizes, f)
        except Exception as e:
            print(f"Error saving splitter sizes: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # KEYBOARD
    # ──────────────────────────────────────────────────────────────────────

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.Type.KeyPress:
            key = event.key()
            ctrl = QtCore.Qt.KeyboardModifier.ControlModifier
            mods = event.modifiers()

            # Ctrl+C: open the multicalculator (in the search box only when
            # nothing is selected, so copying text still works)
            if key == QtCore.Qt.Key.Key_C and mods & ctrl:
                if source is self.search_box and self.search_box.hasSelectedText():
                    return False
                self.launch_calculator()
                return True

            if key == QtCore.Qt.Key.Key_Escape:
                if self.stacked_widget.currentWidget() is self.app_list_container or self.search_box.text():
                    self.show_categories()
                else:
                    self.close()  # Escape on the home page closes the launcher
                return True

            if source is self.search_box:
                if key in (QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Up):
                    target = (self.app_list_widget
                              if self.stacked_widget.currentWidget() is self.app_list_container
                              else self.category_list_widget)
                    target.setFocus()
                    QtWidgets.QApplication.sendEvent(target, event)
                    return True
                return False

            if source is self.category_list_widget and key in (
                QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter
            ):
                item = source.currentItem()
                if item:
                    self.show_category_apps(item)
                return True
            if source in (self.app_list_widget, self.preferred_apps_widget) and key in (
                QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Underscore
            ):
                item = source.currentItem()
                if item:
                    self.launch_selected(item)
                return True
            if source is self.app_list_widget and key == QtCore.Qt.Key.Key_Backspace:
                self.show_categories()
                return True

            # Type to search: printable keys typed on a list go to the search box
            text = event.text()
            if text and text.isprintable() and not text.isspace() and not (mods & ctrl):
                self.search_box.setFocus()
                self.search_box.end(False)
                self.search_box.insert(text)
                return True
        return super().eventFilter(source, event)

    def show_shortcuts(self):
        shortcuts_text = (
            "Shortcuts:\n"
            "Type anywhere: search apps (Enter opens the first result)\n"
            "Ctrl+T: Toggle theme (Light/Dark)\n"
            "Ctrl+C: Open the multicalculator\n"
            "Ctrl+F: Go to the search box\n"
            "Escape: Back to the categories; on the home page it closes the launcher\n"
            "Ctrl+I: Show this shortcuts window\n"
            "\n"
            "Alt+F1 opens the launcher, pressing it again closes it."
        )
        QtWidgets.QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def update_time(self):
        now = QtCore.QDateTime.currentDateTime()
        self.category_title.setText(now.toString("HH:mm:ss"))
        self.date_label.setText(ENGLISH.toString(now.date(), "ddd, MMM d"))

    def closeEvent(self, event):
        self._cancel.set()
        self.save_splitter_sizes()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────────────────
# SINGLE INSTANCE: a second launch (Alt+F1 again) closes the open launcher
# ──────────────────────────────────────────────────────────────────────────

def toggle_running_instance() -> bool:
    socket = QtNetwork.QLocalSocket()
    socket.connectToServer(INSTANCE_NAME)
    if not socket.waitForConnected(1500):
        return False
    socket.write(b"toggle")
    socket.flush()
    connected = QtNetwork.QLocalSocket.LocalSocketState.ConnectedState
    if socket.state() == connected and socket.bytesToWrite():
        socket.waitForBytesWritten(1000)
    if socket.state() == connected:
        socket.disconnectFromServer()
    return True


def listen_for_toggle(window):
    QtNetwork.QLocalServer.removeServer(INSTANCE_NAME)  # stale socket of a crashed launcher
    server = QtNetwork.QLocalServer(window)
    server.newConnection.connect(window.close)
    server.listen(INSTANCE_NAME)
    return server


if __name__ == "__main__":
    script_dir = pathlib.Path(__file__).parent.resolve()

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(WINDOW_TITLE)
    QtGui.QGuiApplication.setDesktopFileName(APP_ID)

    if toggle_running_instance():
        sys.exit(0)

    setup_icon_theme()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # First-run guide: shown only the first time
    guide_flag_file = CONFIG_DIR / "guide_shown.json"
    if not guide_flag_file.exists():
        try:
            guide_script = script_dir / "guide" / "visualizer.py"
            if guide_script.exists():
                start_detached([sys.executable, str(guide_script)])
                with open(guide_flag_file, 'w', encoding='utf-8') as f:
                    json.dump({"shown": True, "timestamp": datetime.now().isoformat()}, f)
            else:
                print(f"Guide not found: {guide_script}")
        except Exception as e:
            print(f"Could not start the guide: {e}")

    launcher = AppLauncher()
    server = listen_for_toggle(launcher)
    skcommon.prepare_window(launcher)
    skcommon.center_window(launcher)
    launcher.show()

    shortcuts_flag_file = launcher.config_dir / "shortcuts_shown.json"
    show_shortcuts = True
    if shortcuts_flag_file.exists():
        try:
            with open(shortcuts_flag_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            show_shortcuts = not data.get("shown", False)
        except Exception:
            show_shortcuts = True

    if show_shortcuts:
        # after the window is mapped, so the dialog opens on top of it
        def _first_run_shortcuts():
            launcher.show_shortcuts()
            try:
                with open(shortcuts_flag_file, 'w', encoding='utf-8') as f:
                    json.dump({"shown": True}, f)
            except Exception:
                pass
        QtCore.QTimer.singleShot(300, _first_run_shortcuts)

    sys.exit(app.exec())
