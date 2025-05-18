import os
import subprocess
import sys
import shlex
import json
import pathlib
from PyQt5 import QtWidgets, QtGui, QtCore

ICON_DIR = "/usr/share/icons/Sours-Full-Color/apps/scalable"  # Icon directory, can be changed on the icons theme you want the app to be

class AppLauncher2(QtWidgets.QMainWindow):

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

        self.stacked_widget = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Category list widget container with title label
        self.category_page = QtWidgets.QWidget()
        self.category_layout = QtWidgets.QVBoxLayout()
        self.category_page.setLayout(self.category_layout)

        # Add system control icons layout above the Home label
        self.system_icons_layout = QtWidgets.QHBoxLayout()
        self.system_icons_layout.setSpacing(20)
        self.system_icons_layout.setAlignment(QtCore.Qt.AlignCenter)

        # Helper function to create icon label with click event
        def create_icon_label(icon_name, tooltip, callback):
            label = QtWidgets.QLabel()
            icon = self.load_icon(icon_name)
            pixmap = icon.pixmap(20, 20)
            label.setPixmap(pixmap)
            label.setToolTip(tooltip)
            label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            label.mousePressEvent = lambda event: callback()
            return label

        # Define system action callbacks
        def shutdown():
            subprocess.Popen(['systemctl', 'poweroff'])

        def reboot():
            subprocess.Popen(['systemctl', 'reboot'])

        def suspend():
            subprocess.Popen(['systemctl', 'suspend'])

        # Create icon labels
        shutdown_icon = create_icon_label('system-shutdown', 'Shutdown', shutdown)
        reboot_icon = create_icon_label('system-reboot', 'Reboot', reboot)
        suspend_icon = create_icon_label('system-suspend', 'Suspend', suspend)

        # Add icons to layout
        self.system_icons_layout.addWidget(shutdown_icon)
        self.system_icons_layout.addWidget(reboot_icon)
        self.system_icons_layout.addWidget(suspend_icon)

        # Create a horizontal layout to hold the icons on the left and the Home label on the right
        self.top_layout = QtWidgets.QHBoxLayout()
        self.top_layout.setSpacing(10)
        self.top_layout.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # Add the system icons layout to the left of the top layout
        self.top_layout.addLayout(self.system_icons_layout)

        # Add stretch to push the Home label to center
        self.top_layout.addStretch(1)

        # Create the Home label
        self.category_title = QtWidgets.QLabel("Home")
        font = self.category_title.font()
        font.setPointSize(16)
        font.setBold(True)
        self.category_title.setFont(font)
        self.category_title.setAlignment(QtCore.Qt.AlignCenter)

        # Add the Home label to the top layout
        self.top_layout.addWidget(self.category_title)

        # Add another stretch to keep the Home label centered
        self.top_layout.addStretch(1)

        # Add the combined top layout to the category layout
        self.category_layout.addLayout(self.top_layout)

        # Preferred apps widget on home page
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
        self.category_list_widget.model().rowsMoved.connect(self.category_order_changed)
        self.category_layout.addWidget(self.category_list_widget)

        # Add search box and send button under the category list widget
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

        # Call the Escape key function at startup to show categories
        self.show_categories()

        # App list widget
        self.app_list_widget = QtWidgets.QListWidget()
        self.app_list_widget.setIconSize(QtCore.QSize(48, 48))
        self.app_list_widget.itemDoubleClicked.connect(self.launch_selected)

        # Back button for app list
        self.back_button = QtWidgets.QPushButton("Back to Home")
        self.back_button.clicked.connect(self.show_categories)
        self.back_button.setFixedWidth(150)

        # Layout for app list with back button
        self.app_list_layout = QtWidgets.QVBoxLayout()
        self.app_list_container = QtWidgets.QWidget()
        self.app_list_layout.addWidget(self.back_button)
        self.app_list_layout.addWidget(self.app_list_widget)
        self.app_list_container.setLayout(self.app_list_layout)
        self.stacked_widget.addWidget(self.app_list_container)

        self.load_category_order()
        self.populate_categories()

        self.dark_mode = True
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

        # Install event filter on preferred_apps_widget to handle key events
        self.preferred_apps_widget.installEventFilter(self)
        self.category_list_widget.installEventFilter(self)
        self.app_list_widget.installEventFilter(self)

        # Set focus policy to allow key events on widgets
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
                }
                QLabel {
                    color: #a0a0ff;
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
                        if app_info:
                            if app_info['name'].lower() in blacklist or app_info['exec'].lower() in blacklist:
                                continue
                            applications.append(app_info)
        applications.sort(key=lambda x: x['name'].lower())
        return applications

    def parse_desktop_file(self, filepath):
        name = None
        exec_cmd = None
        icon_name = None
        categories = None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line.startswith("Name=") and not name:
                    name = line.split("=", 1)[1]
                elif line.startswith("Exec=") and not exec_cmd:
                    exec_cmd = line.split("=", 1)[1]
                    exec_cmd = exec_cmd.split()[0]
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
            cat = app.get('category') or "Other"
            categories.setdefault(cat, []).append(app)
        return categories

    def populate_categories(self):
        self.category_list_widget.clear()
        # Use the order from self.category_order if available, else sorted keys
        if hasattr(self, 'category_order') and self.category_order:
            ordered_cats = [cat for cat in self.category_order if cat in self.categories]
            # Add any new categories not in saved order at the end
            new_cats = [cat for cat in self.categories.keys() if cat not in ordered_cats]
            ordered_cats.extend(new_cats)
        else:
            ordered_cats = sorted(self.categories.keys())

        for cat in ordered_cats:
            item = QtWidgets.QListWidgetItem(cat)
            icon = QtGui.QIcon.fromTheme("folder")
            if not icon.isNull():
                item.setIcon(icon)
            font = item.font()
            font.setPointSize(11)  # Increase font size for better visibility
            item.setFont(font)
            item.setSizeHint(QtCore.QSize(item.sizeHint().width(), 50))  # Increase height for better selection
            self.category_list_widget.addItem(item)

    def show_category_apps(self, item):
        category = item.text()
        self.app_list_widget.clear()
        apps = self.categories.get(category, [])
        for app in sorted(apps, key=lambda x: x['name'].lower()):
            # Create a custom widget for each app item
            widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout()
            layout.setContentsMargins(5, 2, 5, 2)

            icon_label = QtWidgets.QLabel()
            icon = self.load_icon(app['icon'])
            pixmap = icon.pixmap(48, 48)
            icon_label.setPixmap(pixmap)
            layout.addWidget(icon_label)

            name_label = QtWidgets.QLabel(app['name'])
            layout.addWidget(name_label)

            layout.addStretch()

            # Determine button text based on preferred status
            btn_text = "-" if app in self.preferred_apps else "+"
            plus_button = QtWidgets.QPushButton(btn_text)
            plus_button.setFixedSize(24, 24)
            plus_button.setFlat(True)
            plus_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            plus_button.clicked.connect(lambda checked, a=app, b=plus_button: self.plus_button_clicked(a, b))
            layout.addWidget(plus_button)

            widget.setLayout(layout)

            list_item = QtWidgets.QListWidgetItem()
            list_item.setSizeHint(widget.sizeHint())
            list_item.setData(QtCore.Qt.UserRole, app)

            self.app_list_widget.addItem(list_item)
            self.app_list_widget.setItemWidget(list_item, widget)
        self.stacked_widget.setCurrentWidget(self.app_list_container)
        self.app_list_widget.setFocus()

    def search_apps(self, text):
        text = text.strip().lower()
        self.app_list_widget.clear()
        if not text:
            # If search box is empty, show categories in category list widget and keep category page visible
            self.populate_categories()
            self.stacked_widget.setCurrentWidget(self.category_page)
            return
        # Filter apps by name containing the search text
        filtered_apps = [app for app in self.applications if text in app['name'].lower()]
        for app in sorted(filtered_apps, key=lambda x: x['name'].lower()):
            widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout()
            layout.setContentsMargins(5, 2, 5, 2)
            
    def search_apps(self):
        text = self.search_box.text().strip().lower()
        self.app_list_widget.clear()
        if not text:
            # If search box is empty, show categories in category list widget and keep category page visible
            self.populate_categories()
            self.stacked_widget.setCurrentWidget(self.category_page)
            return
        # Filter apps by name containing the search text
        filtered_apps = [app for app in self.applications if text in app['name'].lower()]
        for app in sorted(filtered_apps, key=lambda x: x['name'].lower()):
            widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout()
            layout.setContentsMargins(5, 2, 5, 2)

            icon_label = QtWidgets.QLabel()
            icon = self.load_icon(app['icon'])
            pixmap = icon.pixmap(48, 48)
            icon_label.setPixmap(pixmap)
            layout.addWidget(icon_label)

            name_label = QtWidgets.QLabel(app['name'])
            layout.addWidget(name_label)

            layout.addStretch()

            btn_text = "-" if app in self.preferred_apps else "+"
            plus_button = QtWidgets.QPushButton(btn_text)
            plus_button.setFixedSize(24, 24)
            plus_button.setFlat(True)
            plus_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            plus_button.clicked.connect(lambda checked, a=app, b=plus_button: self.plus_button_clicked(a, b))
            layout.addWidget(plus_button)

            widget.setLayout(layout)

            list_item = QtWidgets.QListWidgetItem()
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
        possible_extensions = ['png', 'svg', 'xpm']
        for ext in possible_extensions:
            icon_path = os.path.join(ICON_DIR, f"{icon_name}.{ext}")
            if os.path.isfile(icon_path):
                return QtGui.QIcon(icon_path)
        if os.path.isabs(icon_name) and os.path.isfile(icon_name):
            return QtGui.QIcon(icon_name)
        icon = QtGui.QIcon.fromTheme(icon_name)
        if not icon.isNull():
            return icon
        return QtGui.QIcon()

    def launch_selected(self, item):
        app = item.data(QtCore.Qt.UserRole)
        if app:
            try:
                cmd = shlex.split(app['exec'])
                subprocess.Popen(cmd)
                self.close()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to launch {app['name']}.\n{e}")

    def toggle_dark_mode(self):
        if not self.dark_mode:
            self.dark_mode = True
            self.apply_dark_mode_style()
        else:
            self.setStyleSheet("")
            self.dark_mode = False
        self.update_toggle_icon()

    def update_toggle_icon(self):
        if self.dark_mode:
            icon = QtGui.QIcon.fromTheme("weather-clear")  # sun icon for light mode
        else:
            icon = QtGui.QIcon.fromTheme("weather-clear-night")  # moon icon for dark mode
        if icon.isNull():
            # Fallback to text if icon not found
            self.toggle_button.setText("Light" if self.dark_mode else "Dark")
            self.toggle_button.setIcon(QtGui.QIcon())
        else:
            self.toggle_button.setText("")
            self.toggle_button.setIcon(icon)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'toggle_button'):
            self.toggle_button.move(self.width() - 40, 10)
        if hasattr(self, 'plus_button'):
            self.plus_button.move(self.width() - 40, 50)

    def plus_button_clicked(self, app):
        if app not in self.preferred_apps:
            self.preferred_apps.append(app)
            self.update_preferred_apps()
        else:
            QtWidgets.QMessageBox.information(self, "System error.")

    def plus_button_clicked(self, app, button):
        if app not in self.preferred_apps:
            self.preferred_apps.append(app)
            button.setText("-")
        else:
            self.preferred_apps.remove(app)
            button.setText("+")
        self.update_preferred_apps()
        self.save_preferred_apps()

    def category_order_changed(self, parent, start, end, destination, row):
        # Save the new order of categories when rows are moved
        self.save_category_order()

    def save_category_order(self):
        try:
            categories = []
            for i in range(self.category_list_widget.count()):
                item = self.category_list_widget.item(i)
                categories.append(item.text())
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
                # Match saved exec commands with current applications
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

        # Determine icon size based on number of preferred apps
        max_icon_size = 64
        min_icon_size = 48

        # Calculate available width and estimate needed width per item with icon+name
        available_width = self.preferred_apps_widget.width()
        # Estimate width per item: icon size + approx 80 pixels for text + spacing
        estimated_item_width = max_icon_size + 80
        total_needed_width = estimated_item_width * count

        # Decide if show names or only icons based on available width
        show_names = total_needed_width <= available_width

        if show_names:
            icon_size = max(min_icon_size, max_icon_size // count)
        else:
            # If not enough space, reduce icon size and show only icons
            icon_size = max(min_icon_size, max_icon_size // (count * 2))

        self.preferred_apps_widget.setIconSize(QtCore.QSize(icon_size, icon_size))

        # Adjust preferred_apps_widget height based on icon size
        height = icon_size + 20  # some padding
        self.preferred_apps_widget.setFixedHeight(height)

        for app in self.preferred_apps:
            if not show_names or icon_size <= 24:
                # Show only icon, no text
                item = QtWidgets.QListWidgetItem()
                icon = self.load_icon(app['icon'])
                item.setIcon(icon)
                item.setData(QtCore.Qt.UserRole, app)
                self.preferred_apps_widget.addItem(item)
            else:
                # Show icon and name
                item = QtWidgets.QListWidgetItem(app['name'])
                icon = self.load_icon(app['icon'])
                item.setIcon(icon)
                item.setData(QtCore.Qt.UserRole, app)
                self.preferred_apps_widget.addItem(item)

        # Center the items if only one preferred app
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
            if event.key() == QtCore.Qt.Key_Escape:
                self.show_categories()
                return True
            if source is self.category_list_widget:
                if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    item = source.currentItem()
                    if item:
                        self.show_category_apps(item)
                    return True
            elif source is self.app_list_widget or source is self.preferred_apps_widget:
                if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    item = source.currentItem()
                    if item:
                        self.launch_selected(item)
                    return True
                elif event.key() == QtCore.Qt.Key_Underscore or (event.key() == QtCore.Qt.Key_Minus and event.modifiers() & QtCore.Qt.ShiftModifier):
                    item = source.currentItem()
                    if item:
                        self.launch_selected(item)
                    return True
        return super().eventFilter(source, event)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    launcher = AppLauncher2()
    launcher.show()
    sys.exit(app.exec_())
