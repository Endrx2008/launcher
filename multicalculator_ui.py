# Copyright (C) 2026 Enrico Miot (EndrX)
# Licensed under GNU GPL v3 or later — see the LICENSE file or <https://www.gnu.org/licenses/>
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import os
import re
import subprocess
from string import Template

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QMessageBox, QSpinBox, QTabWidget, QGroupBox, QFormLayout,
    QGridLayout, QProgressBar, QSizePolicy
)
from PySide6.QtCore import QTimer, Qt, QLocale
from PySide6.QtGui import QDoubleValidator, QGuiApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # skcommon, safe_math
from safe_math import safe_eval

import skcommon
from skcommon import PALETTES, FONT

# Wayland app_id: ~/.config/hypr/hyprland.lua matches it to float and center the window
APP_ID = "skorpion-calculator"

STYLESHEET = Template("""
QWidget { background-color: $bg; color: $text; font-family: $font; }
QLabel { background: transparent; }
QLabel#dim { color: $dim; }
QLabel#big { color: $accent; font-size: 34px; font-weight: bold; letter-spacing: 2px; }
QLineEdit {
    background-color: $bg2; color: $text; border: 1px solid $border;
    padding: 6px 10px; border-radius: 4px;
}
QLineEdit:focus { border: 1px solid $accent; }
QLineEdit#display {
    background-color: $bg2; color: $text; font-size: 28px; padding: 6px 12px;
}
QPushButton {
    background-color: $bg2; color: $text; border: 1px solid $border;
    padding: 5px; border-radius: 4px;
}
QPushButton:hover { border-color: $accent; }
QPushButton:pressed { background-color: $accent; color: $on_accent; }
QPushButton#digit { font-size: 18px; }
QPushButton#op { background-color: $bg3; color: $accent2; font-size: 18px; }
QPushButton#mem { background-color: transparent; font-size: 13px; color: $muted; }
QPushButton#secondary { background-color: transparent; color: $muted; letter-spacing: 1px; }
QPushButton#secondary:hover { color: $text; }
QPushButton#equals, QPushButton#primary {
    background-color: $accent; color: $on_accent; border: none; font-size: 18px; font-weight: bold;
}
QPushButton#equals:hover, QPushButton#primary:hover { background-color: $accent2; }
QGroupBox { border: 1px solid $border; border-radius: 6px; margin-top: 14px; padding: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: $accent2; }
QTabWidget::pane { border: 1px solid $border; border-radius: 6px; top: -1px; }
QTabBar::tab {
    background: transparent; color: $dim; padding: 7px 14px; letter-spacing: 1px;
    border: 1px solid transparent; border-bottom: none; margin-right: 2px;
}
QTabBar::tab:selected { color: $accent; border-color: $border; border-top: 2px solid $accent; background: $bg; }
QTabBar::tab:hover { color: $text; }
QProgressBar {
    background-color: $bg2; border: 1px solid $border; border-radius: 3px; height: 8px;
}
QProgressBar::chunk { background-color: $accent; border-radius: 3px; }
QMessageBox { background-color: $bg; }
""")



def format_number(value):
    """2.0 -> "2", 0.1+0.2 -> "0.3", big/small values in exponent form."""
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Invalid result")
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.12g}"
    return str(value)


class Calculator(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.display = QLineEdit()
        self.display.setObjectName("display")
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setFixedHeight(56)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.display)

        self.result_label = QLabel("")
        self.result_label.setObjectName("dim")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.result_label.setStyleSheet("font-size: 14px; padding: 0 5px;")

        buttons_widget = QWidget()
        grid = QGridLayout(buttons_widget)
        spacing = 6
        grid.setSpacing(spacing)
        grid.setContentsMargins(0, 0, 0, 0)

        # Windows calculator standard layout buttons
        buttons = {
            'MC': (0, 0),
            'MR': (0, 1),
            'MS': (0, 2),
            'M+': (0, 3),
            'M-': (0, 4),

            '←': (1, 0),
            'CE': (1, 1),
            'C': (1, 2),
            '±': (1, 3),
            '√': (1, 4),

            '7': (2, 0),
            '8': (2, 1),
            '9': (2, 2),
            '/': (2, 3),
            '%': (2, 4),

            '4': (3, 0),
            '5': (3, 1),
            '6': (3, 2),
            '*': (3, 3),
            '1/x': (3, 4),

            '1': (4, 0),
            '2': (4, 1),
            '3': (4, 2),
            '-': (4, 3),
            '=': (4, 4, 2, 1),  # Span 2 rows

            '0': (5, 0, 1, 2),  # Span 2 columns
            '.': (5, 2),
            '+': (5, 3),
        }

        for btn_text, pos in buttons.items():
            button = QPushButton(btn_text)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keys always reach the calculator
            button.setMinimumSize(50, 46)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if btn_text == '=':
                button.setObjectName("equals")
            elif btn_text in ('MC', 'MR', 'MS', 'M+', 'M-'):
                button.setObjectName("mem")
            elif btn_text.isdigit() or btn_text == '.':
                button.setObjectName("digit")
            else:
                button.setObjectName("op")
            button.clicked.connect(self.on_button_clicked)
            if len(pos) == 2:
                grid.addWidget(button, pos[0], pos[1])
            else:
                grid.addWidget(button, pos[0], pos[1], pos[2], pos[3])

        layout.addWidget(self.result_label)
        layout.addWidget(buttons_widget, 1)

        self.memory_label = QLabel("")
        self.memory_label.setObjectName("dim")
        layout.addWidget(self.memory_label)

        self.setLayout(layout)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.current_expression = ""
        self.memory = 0.0

    def _show(self):
        self.display.setText(self.current_expression)

    def _update_memory_label(self):
        self.memory_label.setText(f"M = {format_number(self.memory)}" if self.memory else "")

    def _reset_after_error(self, message="Invalid expression"):
        QMessageBox.warning(self, "Error", message)
        self.current_expression = ""
        self._show()
        self.result_label.setText("")

    def _value(self):
        """Value of the whole expression on the display (e.g. 50+10 -> 60)."""
        return safe_eval(self.current_expression)

    def _compute_and_show(self, value, shown_expression=None):
        result = format_number(value)
        self.result_label.setText(f"{shown_expression or self.current_expression} =")
        self.current_expression = result
        self._show()

    def _safe(self, func):
        try:
            func()
        except ZeroDivisionError:
            self._reset_after_error("Cannot divide by zero")
        except Exception:
            self._reset_after_error()

    def on_button_clicked(self):
        self.handle(self.sender().text())

    def handle(self, text):
        if text == 'MC':
            self.memory = 0.0
            self._update_memory_label()
        elif text == 'MR':
            self.current_expression += format_number(self.memory)
            self._show()
        elif text == 'MS':
            def store():
                self.memory = float(self._value())
                self._update_memory_label()
            self._safe(store)
        elif text == 'M+':
            def add():
                self.memory += float(self._value())
                self._update_memory_label()
            self._safe(add)
        elif text == 'M-':
            def sub():
                self.memory -= float(self._value())
                self._update_memory_label()
            self._safe(sub)
        elif text == 'C':
            self.current_expression = ""
            self._show()
            self.result_label.setText("")
        elif text == 'CE':
            new_expr = re.sub(r'(\d+\.?\d*|\.\d+)$', '', self.current_expression)
            if new_expr == self.current_expression:
                new_expr = ""
            self.current_expression = new_expr
            self._show()
        elif text == '←':
            self.current_expression = self.current_expression[:-1]
            self._show()
        elif text == '±':
            if self.current_expression.startswith('-'):
                self.current_expression = self.current_expression[1:]
            elif self.current_expression:
                self.current_expression = '-' + self.current_expression
            self._show()
        elif text == '=':
            self._safe(lambda: self._compute_and_show(self._value()))
        elif text == '√':
            def root():
                value = self._value()
                if value < 0:
                    raise ValueError("Square root of a negative number")
                self._compute_and_show(value ** 0.5, f"√({self.current_expression})")
            self._safe(root)
        elif text == '1/x':
            self._safe(lambda: self._compute_and_show(
                1 / self._value(), f"1/({self.current_expression})"))
        elif text == '%':
            self._safe(lambda: self._compute_and_show(
                self._value() / 100, f"({self.current_expression})%"))
        else:
            self.current_expression += text
            self._show()

    def keyPressEvent(self, event):
        key = event.key()
        text = event.text()
        if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return) or text == '=':
            self.handle('=')
        elif key == Qt.Key.Key_Backspace:
            self.handle('←')
        elif key == Qt.Key.Key_Delete:
            self.handle('C')
        elif text == ',':
            self.handle('.')  # keypads with a decimal comma
        elif text and text in '0123456789.+-*/()':
            self.handle(text)
        elif text == '%':
            self.handle('%')
        elif key == Qt.Key.Key_Escape:
            if self.current_expression:
                self.handle('C')
            else:
                event.ignore()  # empty: let the window go back to the launcher
        else:
            super().keyPressEvent(event)


class PercentualCalculator(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        group = QGroupBox("Percentage")
        form_layout = QFormLayout()

        validator = QDoubleValidator(0.0, 1000000000.0, 6)
        validator.setLocale(QLocale.c())  # always accept "12.5"

        self.x_input = QLineEdit()
        self.x_input.setPlaceholderText("Percentage, e.g. 20")
        self.x_input.setValidator(validator)
        self.x_input.textChanged.connect(self.calculate_live)
        form_layout.addRow("Percent (%):", self.x_input)

        self.y_input = QLineEdit()
        self.y_input.setPlaceholderText("Value, e.g. 150")
        self.y_input.setValidator(validator)
        self.y_input.textChanged.connect(self.calculate_live)
        form_layout.addRow("Of:", self.y_input)

        group.setLayout(form_layout)
        layout.addWidget(group)

        self.result_label = QLabel("")
        self.result_label.setObjectName("big")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label, 1)

        btn_calc = QPushButton("Calculate")
        btn_calc.setObjectName("primary")
        btn_calc.setMinimumHeight(36)
        btn_calc.clicked.connect(self.calculate)
        layout.addWidget(btn_calc)

        self.setLayout(layout)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.calculate()
        else:
            super().keyPressEvent(event)

    def _numbers(self):
        x = float(self.x_input.text().replace(",", "."))
        y = float(self.y_input.text().replace(",", "."))
        return x, y

    def _show(self, x, y):
        self.result_label.setText(f"{format_number(x)}% of {format_number(y)}\n= {format_number(x / 100 * y)}")

    def calculate_live(self):
        try:
            self._show(*self._numbers())
        except ValueError:
            self.result_label.setText("")

    def calculate(self):
        try:
            x, y = self._numbers()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid number")
            return
        self._show(x, y)


class Stopwatch(QWidget):
    def __init__(self):
        super().__init__()
        self.elapsed = 0
        self.target = 0

        layout = QVBoxLayout()

        group = QGroupBox("Timer")
        form_layout = QFormLayout()

        self.time_input = QSpinBox()
        self.time_input.setRange(1, 3600)
        self.time_input.setSuffix(" seconds")
        self.time_input.setValue(10)
        self.time_input.valueChanged.connect(self._refresh)
        form_layout.addRow("Stop after:", self.time_input)

        group.setLayout(form_layout)
        layout.addWidget(group)

        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("big")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label, 1)

        self.info_label = QLabel("")
        self.info_label.setObjectName("dim")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self.start)
        btn_stop = QPushButton("Stop")
        btn_stop.clicked.connect(self.stop)
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self.reset)
        for b in (self.btn_start, btn_stop, btn_reset):
            b.setMinimumHeight(36)
            buttons.addWidget(b)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self._refresh()

    def _refresh(self):
        self.target = self.time_input.value()
        self.progress.setMaximum(self.target)
        self.progress.setValue(min(self.elapsed, self.target))
        minutes, seconds = divmod(self.elapsed, 60)
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
        self.info_label.setText(f"{self.elapsed} of {self.target} seconds")

    def start(self):
        """Start, or resume after Stop. After the limit it starts again from 0."""
        if self.elapsed >= self.time_input.value():
            self.elapsed = 0
        self._refresh()
        self.timer.start(1000)
        self.btn_start.setText("Start")

    def stop(self):
        self.timer.stop()
        if self.elapsed:
            self.btn_start.setText("Resume")

    def reset(self):
        self.timer.stop()
        self.elapsed = 0
        self.btn_start.setText("Start")
        self._refresh()

    def update_time(self):
        self.elapsed += 1
        self._refresh()
        if self.elapsed >= self.target:
            self.timer.stop()
            QApplication.beep()
            QMessageBox.information(
                self, "Time's up",
                f"{self.target} seconds have passed, the timer has stopped."
            )


class ClickableLabel(QLabel):
    def mousePressEvent(self, event):
        self.clicked()

    def clicked(self):
        pass


class MultiCalculatorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiCalculator")
        self.resize(420, 560)

        self.tabs = QTabWidget()
        self.calc = Calculator()
        self.perc = PercentualCalculator()
        self.cron = Stopwatch()

        self.tabs.addTab(self.calc, "CALCULATOR")
        self.tabs.addTab(self.perc, "PERCENT")
        self.tabs.addTab(self.cron, "TIMER")
        self.tabs.currentChanged.connect(lambda _i: self.tabs.currentWidget().setFocus())

        self.label_toggle_theme = ClickableLabel("")
        self.label_toggle_theme.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.label_toggle_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label_toggle_theme.setToolTip("Toggle theme (Ctrl+T)")
        self.label_toggle_theme.clicked = self.toggle_theme

        self.theme = skcommon.load_theme()
        self.apply_theme()

        self.btn_back_home = QPushButton("←  HOME")
        self.btn_back_home.setObjectName("secondary")
        self.btn_back_home.setFixedSize(100, 30)
        self.btn_back_home.setToolTip("Back to the launcher (Esc)")
        self.btn_back_home.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_back_home.clicked.connect(self.back_to_home)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.btn_back_home)
        top_layout.addStretch()
        top_layout.addWidget(self.label_toggle_theme)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        self.calc.setFocus()

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        ctrl = Qt.KeyboardModifier.ControlModifier
        if key == Qt.Key.Key_Escape:
            self.back_to_home()
        elif key == Qt.Key.Key_C and mods & ctrl:
            self.back_to_home()
        elif key == Qt.Key.Key_T and mods & ctrl:
            self.toggle_theme()
        elif key == Qt.Key.Key_I and mods & ctrl:
            self.show_shortcuts()
        else:
            super().keyPressEvent(event)

    def show_shortcuts(self):
        shortcuts_text = (
            "Shortcuts:\n"
            "Ctrl+T: Toggle theme (Light/Dark)\n"
            "Ctrl+C: Go back to the launcher\n"
            "Escape: clear the display, press it again to go back to the launcher\n"
            "Enter or =: calculate, Backspace: delete, Delete: clear all\n"
            "Ctrl+I: Show this shortcuts window\n"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()
        skcommon.save_theme(self.theme)

    def apply_theme(self):
        palette = dict(PALETTES.get(self.theme, PALETTES["dark"]), font=FONT)
        self.setStyleSheet(STYLESHEET.substitute(palette))
        # it names the theme you switch to, like the launcher and the wizard
        self.label_toggle_theme.setText("☀  LIGHT" if self.theme == "dark" else "☾  DARK")
        self.label_toggle_theme.setStyleSheet(
            f"color: {palette['muted']}; padding: 5px; letter-spacing: 1px;"
        )

    def back_to_home(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        launcher_path = os.path.join(current_dir, "launcher.py")
        subprocess.Popen([sys.executable, launcher_path], start_new_session=True)
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    QGuiApplication.setDesktopFileName(APP_ID)
    window = MultiCalculatorApp()
    skcommon.prepare_window(window)
    skcommon.center_window(window)
    window.show()
    sys.exit(app.exec())
