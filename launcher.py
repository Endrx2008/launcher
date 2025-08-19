import os
import subprocess
import sys
import shlex
import json
import pathlib
from functools import partial
from PyQt5 import QtWidgets, QtGui, QtCore

ICON_DIR = "/usr/share/icons/Ars-Dark-Icons/apps/48"
SPECIAL_ICON_DIR = "/usr/share/icons/Sours-Full-Color/apps/scalable"

def load_special_icon(icon_name):
    """Carica un'icona speciale da SPECIAL_ICON_DIR con estensioni comuni."""
    for ext in ['png', 'svg', 'xpm']:
        icon_path = os.path.join(SPECIAL_ICON_DIR, f"{icon_name}.{ext}")
        if os.path.isfile(icon_path):
            return QtGui.QIcon(icon_path)
    return QtGui.QIcon()  # fallback se non trova nulla

def create_special_icon_label(icon_name, tooltip, callback):
    """Crea un QLabel cliccabile con icona speciale."""
    label = QtWidgets.QLabel()
    icon = load_special_icon(icon_name)
    label.setPixmap(icon.pixmap(20, 20))
    label.setToolTip(tooltip)
    label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
    label.mousePressEvent = lambda event: callback()
    return label

class AppLauncher(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Application Launcher")
        self.resize(800, 600)

        self.applications = self.find_applications()
        self.categories = self.group_applications_by_category(self.applications)

        self.preferred_apps = []
        self.config_dir = pathlib.Path.home() / ".config" / "pylauncher_settings"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "preferred_apps.json"
        self.category_order_file = self.config_dir / "categories_order.json"
        self.theme_config_file = self.config_dir / "theme_config.json"

        self.load_theme_config()

        self.stacked_widget = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Pagina categorie
        self.category_page = QtWidgets.QWidget()
        self.category_layout = QtWidgets.QVBoxLayout(self.category_page)

        # Barra icone di sistema
        self.system_icons_layout = QtWidgets.QHBoxLayout()
        self.system_icons_layout.setSpacing(20)
        self.system_icons_layout.setAlignment(QtCore.Qt.AlignCenter)

        self.system_icons_layout.addWidget(
            create_special_icon_label('system-shutdown', 'Shutdown', lambda: subprocess.Popen(['systemctl', 'poweroff']))
        )
        self.system_icons_layout.addWidget(
            create_special_icon_label('system-reboot', 'Reboot', lambda: subprocess.Popen(['systemctl', 'reboot']))
        )
        self.system_icons_layout.addWidget(
            create_special_icon_label('system-suspend', 'Suspend', lambda: subprocess.Popen(['systemctl', 'suspend']))
        )

        self.top_layout = QtWidgets.QHBoxLayout()
        self.top_layout.setSpacing(10)
        self.top_layout.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.top_layout.addLayout(self.system_icons_layout)
        self.top_layout.addStretch(1)

        self.category_title = QtWidgets.QLabel("Home")
        font = self.category_title.font()
        font.setPointSize(16)
        font.setBold(True)
        self.category_title.setFont(font)
        self.category_title.setAlignment(QtCore.Qt.AlignCenter)
        self.top_layout.addWidget(self.category_title)
        self.top_layout.addStretch(1)

        self.category_layout.addLayout(self.top_layout)

        self.preferred_apps_widget = QtWidgets.QListWidget()
        self.preferred_apps_widget.setIconSize(QtCore.QSize(32, 32))
        self.preferred_apps_widget.setFixedHeight(60)
        self.preferred_apps_widget.setFlow(QtWidgets.QListView.LeftToRight)
        self.preferred_apps_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.preferred_apps_widget.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.preferred_apps_widget.setSpacing(5)
        self.preferred_apps_widget.itemClicked.connect(self.launch_selected)
        self.category_layout.addWidget(self.preferred_apps_widget)

        self.category_list_widget = QtWidgets.QListWidget()
        self.category_list_widget.setIconSize(QtCore.QSize(48, 48))
        self.category_list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.category_list_widget.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.category_list_widget.setDragEnabled(True)
        self.category_list_widget.setAcceptDrops(True)
        self.category_list_widget.setDropIndicatorShown(True)
        self.category_list_widget.itemClicked.connect(self.show_category_apps)
        self.category_list_widget.model().rowsMoved.connect(self.save_category_order)
        self.category_layout.addWidget(self.category_list_widget)

        search_layout = QtWidgets.QHBoxLayout()
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("Search apps by name...")
        self.search_box.setMinimumWidth(200)
        self.search_box.returnPressed.connect(self.search_apps)
        search_layout.addWidget(self.search_box)

        self.send_button = QtWidgets.QPushButton("Search")
        self.send_button.setFixedWidth(60)
        self.send_button.clicked.connect(self.search_apps)
        search_layout.addWidget(self.send_button)

        self.category_layout.addLayout(search_layout)

        self.stacked_widget.addWidget(self.category_page)

        self.load_preferred_apps()
        self.update_preferred_apps()
        self.show_categories()

        self.app_list_widget = QtWidgets.QListWidget()
        self.app_list_widget.setIconSize(QtCore.QSize(48, 48))
        self.app_list_widget.itemDoubleClicked.connect(self.launch_selected)
        self.app_list_widget.currentItemChanged.connect(self.update_app_list_selection_background)

        self.back_button = QtWidgets.QPushButton("Back to Home")
        self.back_button.setFixedWidth(150)
        self.back_button.clicked.connect(self.show_categories)

        self.app_list_layout = QtWidgets.QVBoxLayout()
        self.app_list_container = QtWidgets.QWidget()
        self.app_list_layout.addWidget(self.back_button)
        self.app_list_layout.addWidget(self.app_list_widget)
        self.app_list_container.setLayout(self.app_list_layout)
        self.stacked_widget.addWidget(self.app_list_container)

        self.load_category_order()
        self.populate_categories()

        self.toggle_button = QtWidgets.QPushButton(self)
        self.toggle_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.toggle_button.setFixedSize(32, 32)
        self.toggle_button.setFlat(True)
        self.toggle_button.move(self.width() - 40, 10)
        self.toggle_button.clicked.connect(self.toggle_dark_mode)
        self.update_toggle_icon()
        self.toggle_button.show()

        self.apply_dark_mode_style()
        self.installEventFilter(self)
        self.preferred_apps_widget.installEventFilter(self)
        self.category_list_widget.installEventFilter(self)
        self.app_list_widget.installEventFilter(self)

        self.preferred_apps_widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.category_list_widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.app_list_widget.setFocusPolicy(QtCore.Qt.StrongFocus)


    def apply_dark_mode_style(self):
        if self.dark_mode:
            dark_style = """
                QWidget {
                    background-color: #2b2b2b;
                    color: #f0f0f0;
                }
                QListWidget {
                    background-color: #2b2b2b;
                    color: #f0f0f0;
                }
                QListWidget::item:selected {
                    background-color: #5a5a5a;
                    color: white;
                }
                QLabel {
                    color: #a0a0a0;
                }
            """
            self.setStyleSheet(dark_style)
        else:
            self.setStyleSheet("")

    def find_applications(self):
        applications = []
        desktop_dirs = [
            "/usr/share/applications",
            os.path.expanduser("~/.local/share/applications"),
            "/usr/local/share/applications"
        ]
        blacklist = {"i3", "gnome-shell", "plasmashell", "xfce4-panel", "lxpanel", "portal", "desktop"}

        for d in desktop_dirs:
            if os.path.isdir(d):
                for filename in os.listdir(d):
                    if filename.endswith(".desktop"):
                        filepath = os.path.join(d, filename)
                        app_info = self.parse_desktop_file(filepath)
                        if app_info and app_info['name'].lower() not in blacklist and app_info['exec'].lower() not in blacklist:
                            applications.append(app_info)
        return sorted(applications, key=lambda x: x['name'].lower())

    def parse_desktop_file(self, filepath):
        name = exec_cmd = icon_name = categories = None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("Name=") and not name:
                        name = line.split("=", 1)[1]
                    elif line.startswith("Exec=") and not exec_cmd:
                        exec_cmd = line.split("=", 1)[1].split()[0]
                    elif line.startswith("Icon=") and not icon_name:
                        icon_name = line.split("=", 1)[1]
                    elif line.startswith("Categories=") and not categories:
                        categories = line.split("=", 1)[1]
                    if name and exec_cmd and icon_name and categories:
                        break
            main_category = categories.split(";")[0] if categories else "Other"
            if name and exec_cmd:
                return {'name': name, 'exec': exec_cmd, 'icon': icon_name, 'category': main_category}
        except Exception:
            pass
        return None

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
            ordered_cats.extend([cat for cat in self.categories if cat not in ordered_cats])
        else:
            ordered_cats = sorted(self.categories.keys())

        for cat in ordered_cats:
            item = QtWidgets.QListWidgetItem(cat)
            icon = QtGui.QIcon.fromTheme("folder")
            if not icon.isNull():
                item.setIcon(icon)
            font = item.font()
            font.setPointSize(11)
            item.setFont(font)
            item.setSizeHint(QtCore.QSize(item.sizeHint().width(), 50))
            self.category_list_widget.addItem(item)

    def create_app_list_item(self, app):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)

        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(self.load_icon(app['icon']).pixmap(48, 48))
        layout.addWidget(icon_label)

        name_label = QtWidgets.QLabel(app['name'])
        layout.addWidget(name_label)

        layout.addStretch()

        btn_text = "-" if app in self.preferred_apps else "+"
        plus_button = QtWidgets.QPushButton(btn_text)
        plus_button.setFixedSize(24, 24)
        plus_button.setFlat(True)
        plus_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        plus_button.clicked.connect(partial(self.plus_button_clicked, app, plus_button))
        layout.addWidget(plus_button)

        return widget

    def show_category_apps(self, item):
        category = item.text()
        self.app_list_widget.clear()
        for app in sorted(self.categories.get(category, []), key=lambda x: x['name'].lower()):
            list_item = QtWidgets.QListWidgetItem()
            widget = self.create_app_list_item(app)
            list_item.setSizeHint(widget.sizeHint())
            list_item.setData(QtCore.Qt.UserRole, app)
            self.app_list_widget.addItem(list_item)
            self.app_list_widget.setItemWidget(list_item, widget)
        self.stacked_widget.setCurrentWidget(self.app_list_container)
        self.app_list_widget.setFocus()

    def search_apps(self):
        text = self.search_box.text().strip().lower()
        self.app_list_widget.clear()
        if not text:
            self.populate_categories()
            self.stacked_widget.setCurrentWidget(self.category_page)
            return
        filtered_apps = [app for app in self.applications if text in app['name'].lower()]
        for app in sorted(filtered_apps, key=lambda x: x['name'].lower()):
            list_item = QtWidgets.QListWidgetItem()
            widget = self.create_app_list_item(app)
            list_item.setSizeHint(widget.sizeHint())
            list_item.setData(QtCore.Qt.UserRole, app)
            self.app_list_widget.addItem(list_item)
            self.app_list_widget.setItemWidget(list_item, widget)
        self.stacked_widget.setCurrentWidget(self.app_list_container)

    def show_categories(self):
        self.stacked_widget.setCurrentWidget(self.category_page)
        self.category_list_widget.setFocus()

    def load_icon(self, icon_name):
        if not icon_name:
            return QtGui.QIcon()
        for ext in ['png', 'svg', 'xpm']:
            icon_path = os.path.join(ICON_DIR, f"{icon_name}.{ext}")
            if os.path.isfile(icon_path):
                return QtGui.QIcon(icon_path)
        if os.path.isabs(icon_name) and os.path.isfile(icon_name):
            return QtGui.QIcon(icon_name)
        icon = QtGui.QIcon.fromTheme(icon_name)
        return icon if not icon.isNull() else QtGui.QIcon()

    def launch_selected(self, item):
        app = item.data(QtCore.Qt.UserRole)
        if app:
            try:
                subprocess.Popen(shlex.split(app['exec']))
                self.close()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to launch {app['name']}.\n{e}")

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.apply_dark_mode_style()
        else:
            self.setStyleSheet("")
        self.update_toggle_icon()
        self.update_app_list_selection_background(self.app_list_widget.currentItem(), None)
        self.save_theme_config()

    def load_theme_config(self):
        try:
            if self.theme_config_file.exists():
                with open(self.theme_config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                theme = data.get("theme", "dark")
                self.dark_mode = (theme == "dark")
            else:
                self.dark_mode = True
            if self.dark_mode:
                self.apply_dark_mode_style()
            else:
                self.setStyleSheet("")
            self.update_toggle_icon()
        except Exception as e:
            print(f"Error loading theme config: {e}")

    def save_theme_config(self):
        try:
            data = {"theme": "dark" if self.dark_mode else "light"}
            with open(self.theme_config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving theme config: {e}")

    def update_toggle_icon(self):
        icon_name = "weather-clear" if self.dark_mode else "weather-clear-night"
        icon = QtGui.QIcon.fromTheme(icon_name)
        if icon.isNull():
            self.toggle_button.setText("Light" if self.dark_mode else "Dark")
            self.toggle_button.setIcon(QtGui.QIcon())
        else:
            self.toggle_button.setText("")
            self.toggle_button.setIcon(icon)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.toggle_button.move(self.width() - 40, 10)

    def plus_button_clicked(self, app, button):
        if app not in self.preferred_apps:
            self.preferred_apps.append(app)
            button.setText("-")
        else:
            self.preferred_apps.remove(app)
            button.setText("+")
        self.update_preferred_apps()
        self.save_preferred_apps()

    def save_category_order(self):
        try:
            categories = [self.category_list_widget.item(i).text() for i in range(self.category_list_widget.count())]
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
                exec_set = set(data)
                self.preferred_apps = [app for app in self.applications if app['exec'] in exec_set]
                self.update_preferred_apps()
        except Exception as e:
            print(f"Error loading preferred apps: {e}")

    def update_preferred_apps(self):
        self.preferred_apps_widget.clear()
        count = len(self.preferred_apps)
        if count == 0:
            return

        max_icon_size = 64
        min_icon_size = 48
        available_width = self.preferred_apps_widget.width()
        estimated_item_width = max_icon_size + 80
        total_needed_width = estimated_item_width * count
        show_names = total_needed_width <= available_width

        icon_size = max(min_icon_size, max_icon_size // count) if show_names else max(min_icon_size, max_icon_size // (count * 2))
        self.preferred_apps_widget.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.preferred_apps_widget.setFixedHeight(icon_size + 20)

        for app in self.preferred_apps:
            item = QtWidgets.QListWidgetItem(app['name'] if show_names and icon_size > 24 else "")
            item.setIcon(self.load_icon(app['icon']))
            item.setData(QtCore.Qt.UserRole, app)
            self.preferred_apps_widget.addItem(item)

        if count == 1:
            self.preferred_apps_widget.setFlow(QtWidgets.QListView.LeftToRight)
            self.preferred_apps_widget.setSpacing(10)
            self.preferred_apps_widget.setStyleSheet("QListWidget::item { margin-left: auto; margin-right: auto; }")
        else:
            self.preferred_apps_widget.setFlow(QtWidgets.QListView.LeftToRight)
            self.preferred_apps_widget.setSpacing(5)
            self.preferred_apps_widget.setStyleSheet("")

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.KeyPress:
            # Detect Control+C
            if event.key() == QtCore.Qt.Key_C and event.modifiers() & QtCore.Qt.ControlModifier:
                # Launch calcolatrice.py
                try:
                    import pathlib
                    script_dir = pathlib.Path(__file__).parent.resolve()
                    calcolatrice_path = script_dir / "multicalculator_ui.py"
                    if calcolatrice_path.exists():
                        subprocess.Popen([sys.executable, str(calcolatrice_path)])
                        self.close()
                    else:
                        QtWidgets.QMessageBox.warning(self, "File Not Found", f"Calculator file not found in {calcolatrice_path}")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Error", f"Failed to launch calculator app.\n{e}")
                return True

            # Detect Control+T for theme toggle
            if event.key() == QtCore.Qt.Key_T and event.modifiers() & QtCore.Qt.ControlModifier:
                self.toggle_dark_mode()
                return True

            # Detect Control+I for shortcuts display
            if event.key() == QtCore.Qt.Key_I and event.modifiers() & QtCore.Qt.ControlModifier:
                self.show_shortcuts()
                return True

            if event.key() == QtCore.Qt.Key_Escape:
                self.show_categories()
                return True
            if source is self.category_list_widget and event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                item = source.currentItem()
                if item:
                    self.show_category_apps(item)
                return True
            if source in (self.app_list_widget, self.preferred_apps_widget) and event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Underscore):
                item = source.currentItem()
                if item:
                    self.launch_selected(item)
                return True
        return super().eventFilter(source, event)

    def show_shortcuts(self):
        from PyQt5.QtWidgets import QMessageBox
        shortcuts_text = (
            "Shortcuts:\n"
            "Ctrl+T: Toggle theme (Light/Dark)\n"
            "Ctrl+C: Launch The multicalculator\n"
            "Escape: Show Categories (home)\n"
            "Ctrl+I: Show this shortcuts window\n"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def update_app_list_selection_background(self, current, previous):
        if previous:
            prev_widget = self.app_list_widget.itemWidget(previous)
            if prev_widget:
                prev_widget.setStyleSheet("")
        if current:
            curr_widget = self.app_list_widget.itemWidget(current)
            if curr_widget:
                curr_widget.setStyleSheet("background-color: #5a5a5a; color: white;" if self.dark_mode else "background-color: #3a6efb; color: white;")

import json

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    launcher = AppLauncher()

    guide_flag_file = launcher.config_dir / "guide.json"
    show_guide = True
    if guide_flag_file.exists():
        try:
            with open(guide_flag_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            show_guide = not data.get("shown", False)
        except Exception:
            show_guide = True

    if show_guide:
        try:
            import pathlib
            script_dir = pathlib.Path(__file__).parent.resolve()
            subprocess.Popen([sys.executable, script_dir / "guide/visualizer.py"])
            with open(guide_flag_file, 'w', encoding='utf-8') as f:
                json.dump({"shown": True}, f)
        except Exception as e:
            print(f"Error launching guide visualizer or writing guide flag: {e}")

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
        launcher.show_shortcuts()
        try:
            with open(shortcuts_flag_file, 'w', encoding='utf-8') as f:
                json.dump({"shown": True}, f)
        except Exception:
            pass

    sys.exit(app.exec_())
