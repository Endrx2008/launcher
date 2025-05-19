import sys
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QMessageBox, QComboBox, QSpinBox, QTabWidget, QGroupBox, QFormLayout
)
import subprocess
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtGui import QDoubleValidator


class Calculator(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setFixedHeight(50)
        self.display.setStyleSheet("font-size: 24px; padding: 5px;")
        layout.addWidget(self.display)

        buttons_widget = QWidget()
        grid = QGridLayout(buttons_widget)
        grid.setSpacing(3)
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
            # Remove fixed sizes to allow resizing and locking in place
            # Instead, set minimum size and size policy
            if btn_text == '0':
                button.setMinimumSize(110, 50)
            elif btn_text == '=':
                button.setMinimumSize(50, 110)
            else:
                button.setMinimumSize(50, 50)
            button.setSizePolicy(button.sizePolicy().horizontalPolicy(), button.sizePolicy().verticalPolicy())
            button.setStyleSheet("font-size: 18px;")
            button.clicked.connect(self.on_button_clicked)
            if len(pos) == 2:
                grid.addWidget(button, pos[0], pos[1])
            else:
                grid.addWidget(button, pos[0], pos[1], pos[2], pos[3])

        layout.addWidget(buttons_widget)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-size: 16px; padding: 5px;")
        layout.addWidget(self.result_label)

        self.setLayout(layout)

        self.current_expression = ""
        self.memory = 0.0

    def on_button_clicked(self):
        sender = self.sender()
        text = sender.text()

        if text == 'MC':
            self.memory = 0.0
        elif text == 'MR':
            self.current_expression = str(self.memory)
            self.display.setText(self.current_expression)
        elif text == 'MS':
            try:
                self.memory = float(self.current_expression)
            except ValueError:
                QMessageBox.warning(self, "Errore", "Espressione non valida")
        elif text == 'M+':
            try:
                self.memory += float(self.current_expression)
            except ValueError:
                QMessageBox.warning(self, "Errore", "Espressione non valida")
        elif text == 'M-':
            try:
                self.memory -= float(self.current_expression)
            except ValueError:
                QMessageBox.warning(self, "Errore", "Espressione non valida")
        elif text == 'C':
            self.current_expression = ""
            self.display.setText(self.current_expression)
            self.result_label.setText("")
        elif text == 'CE':
            import re
            new_expr = re.sub(r'(\d+\.?\d*|\.\d+)$', '', self.current_expression)
            if new_expr == self.current_expression:
                new_expr = ""
            self.current_expression = new_expr
            self.display.setText(self.current_expression)
        elif text == '←':
            self.current_expression = self.current_expression[:-1]
            self.display.setText(self.current_expression)
        elif text == '±':
            if self.current_expression.startswith('-'):
                self.current_expression = self.current_expression[1:]
            elif self.current_expression:
                self.current_expression = '-' + self.current_expression
            self.display.setText(self.current_expression)
        elif text == '=':
            try:
                # Evaluate the expression safely
                result = eval(self.current_expression, {"__builtins__": None}, {})
                self.result_label.setText(f"Risultato: {result}")
                self.current_expression = str(result)
                self.display.setText(self.current_expression)
            except Exception:
                QMessageBox.warning(self, "Errore", "Espressione non valida")
                self.current_expression = ""
                self.display.setText(self.current_expression)
                self.result_label.setText("")
        elif text == '√':
            try:
                result = str(eval(self.current_expression, {"__builtins__": None}, {}) ** 0.5)
                self.result_label.setText(f"Risultato: {result}")
                self.current_expression = result
                self.display.setText(self.current_expression)
            except Exception:
                QMessageBox.warning(self, "Errore", "Espressione non valida")
                self.current_expression = ""
                self.display.setText(self.current_expression)
                self.result_label.setText("")
        elif text == '1/x':
            try:
                result = str(1 / float(self.current_expression))
                self.result_label.setText(f"Risultato: {result}")
                self.current_expression = result
                self.display.setText(self.current_expression)
            except Exception:
                QMessageBox.warning(self, "Errore", "Espressione non valida")
                self.current_expression = ""
                self.display.setText(self.current_expression)
                self.result_label.setText("")
        elif text == '%':
            try:
                result = str(float(self.current_expression) / 100)
                self.result_label.setText(f"Risultato: {result}")
                self.current_expression = result
                self.display.setText(self.current_expression)
                self.result_label.setText("")
            except Exception:
                QMessageBox.warning(self, "Errore", "Espressione non valida")
                self.current_expression = ""
                self.display.setText(self.current_expression)
                self.result_label.setText("")
        else:
            self.current_expression += text
            self.display.setText(self.current_expression)

    def keyPressEvent(self, event):
        key = event.key()
        text = event.text()
        if key in (Qt.Key_Enter, Qt.Key_Return):
            self.on_button_clicked_enter()
        elif key == Qt.Key_Backspace:
            self.current_expression = self.current_expression[:-1]
            self.display.setText(self.current_expression)
        elif text in '0123456789.+-*/%()':
            self.current_expression += text
            self.display.setText(self.current_expression)
        elif key == Qt.Key_Escape:
            self.current_expression = ""
            self.display.setText(self.current_expression)
            self.result_label.setText("")

    def on_button_clicked_enter(self):
        try:
            result = eval(self.current_expression, {"__builtins__": None}, {})
            self.result_label.setText(f"Risultato: {result}")
            self.current_expression = str(result)
            self.display.setText(self.current_expression)
        except Exception:
            QMessageBox.warning(self, "Errore", "Espressione non valida")
            self.current_expression = ""
            self.display.setText(self.current_expression)
            self.result_label.setText("")


class PercentualCalculator(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        group = QGroupBox("Calcolatore Percentuale")
        form_layout = QFormLayout()

        self.x_input = QLineEdit()
        self.x_input.setPlaceholderText("Inserisci valore percentuale")
        self.x_input.setValidator(QDoubleValidator(0.0, 1000000.0, 6))
        form_layout.addRow("Percentuale (%):", self.x_input)

        self.y_input = QLineEdit()
        self.y_input.setPlaceholderText("Inserisci il valore base")
        self.y_input.setValidator(QDoubleValidator(0.0, 1000000.0, 6))
        form_layout.addRow("Del valore:", self.y_input)

        group.setLayout(form_layout)
        layout.addWidget(group)

        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

        btn_calc = QPushButton("Calcola")
        btn_calc.clicked.connect(self.calculate)
        layout.addWidget(btn_calc)

        self.setLayout(layout)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Enter, Qt.Key_Return):
            self.calculate()

    def calculate(self):
        try:
            x = float(self.x_input.text())
            y = float(self.y_input.text())
        except ValueError:
            QMessageBox.warning(self, "Errore", "Inserisci un numero valido")
            return

        fract = x / 100
        molt = fract * y
        self.result_label.setText(f"{x} % di {y} = {molt}")


class Stopwatch(QWidget):
    def __init__(self):
        super().__init__()
        self.elapsed = 0
        self.target = 0

        layout = QVBoxLayout()

        group = QGroupBox("Cronometro")
        form_layout = QFormLayout()

        self.time_input = QSpinBox()
        self.time_input.setRange(1, 3600)
        self.time_input.setSuffix(" secondi")
        self.time_input.setValue(10)
        form_layout.addRow("Imposta un limite di tempo:", self.time_input)

        group.setLayout(form_layout)
        layout.addWidget(group)

        self.time_label = QLabel("Secondi trascorsi: 0")
        layout.addWidget(self.time_label)

        btn_start = QPushButton("Reset")
        btn_start.clicked.connect(self.start)
        layout.addWidget(btn_start)

        btn_stop = QPushButton("Stop")
        btn_stop.clicked.connect(self.stop)
        layout.addWidget(btn_stop)

        btn_restart = QPushButton("Start")
        btn_restart.clicked.connect(self.restart)
        layout.addWidget(btn_restart)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)

    def start(self):
        self.elapsed = 0
        self.target = self.time_input.value()
        self.time_label.setText(f"Secondi trascorsi: {self.elapsed}")
        self.timer.start(1000)

    def stop(self):
        self.timer.stop()

    def restart(self):
        self.target = self.time_input.value()
        self.time_label.setText(f"Secondi trascorsi: {self.elapsed}")
        self.timer.start(1000)

    def update_time(self):
        self.elapsed += 1
        self.time_label.setText(f"Secondi trascorsi: {self.elapsed}")
        if self.elapsed >= self.target:
            self.timer.stop()
            QMessageBox.information(self, "Tempo scaduto", f"Sono passati {self.target} secondi, fermo il conteggio")


class ClickableLabel(QLabel):
    def mousePressEvent(self, event):
        self.clicked()
    def clicked(self):
        pass


import json
import pathlib

class MultiCalculatorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiCalculator")

        self.config_dir = pathlib.Path.home() / ".config" / "pylauncher_settings"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.theme_config_file = self.config_dir / "theme_config.json"

        self.tabs = QTabWidget()
        self.calc = Calculator()
        self.perc = PercentualCalculator()
        self.cron = Stopwatch()

        self.tabs.addTab(self.calc, "Calcolatrice")
        self.tabs.addTab(self.perc, "Calcolatore Percentuale")
        self.tabs.addTab(self.cron, "Cronometro")

        self.theme = "dark"
        self.load_theme_config()
        self.apply_theme()

        self.label_toggle_theme = ClickableLabel("Dark Mode")
        self.label_toggle_theme.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.label_toggle_theme.clicked = self.toggle_theme

        self.btn_back_home = QPushButton("Back to Home")
        self.btn_back_home.setFixedSize(100, 30)
        self.btn_back_home.clicked.connect(self.back_to_home)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.btn_back_home)
        top_layout.addStretch()
        top_layout.addWidget(self.label_toggle_theme)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.back_to_home()
        elif event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            self.back_to_home()
        elif event.key() == Qt.Key_T and event.modifiers() & Qt.ControlModifier:
            self.toggle_theme()
        elif event.key() == Qt.Key_I and event.modifiers() & Qt.ControlModifier:
            self.show_shortcuts()

    def show_shortcuts(self):
        from PyQt5.QtWidgets import QMessageBox
        shortcuts_text = (
            "Shortcuts:\n"
            "Ctrl+T: Toggle theme (Light/Dark)\n"
            "Ctrl+C: Go back to the home\n"
            "Escape: Show Categories (home)\n"
            "Ctrl+I: Show this shortcuts window\n"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def toggle_theme(self):
        if self.theme == "dark":
            self.theme = "light"
        else:
            self.theme = "dark"
        self.apply_theme()
        self.save_theme_config()

    def apply_theme(self):
        if self.theme == "dark":
            self.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #f0f0f0;
                }
                QPushButton {
                    background-color: #444444;
                    color: #f0f0f0;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #555555;
                }
                QLineEdit {
                    background-color: #3c3c3c;
                    color: #f0f0f0;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                }
                QTabBar::tab {
                    background: #444444;
                    color: #f0f0f0;
                    padding: 5px;
                    border: 1px solid #555555;
                    border-bottom-color: #2b2b2b;
                    border-radius: 3px;
                }
                QTabBar::tab:selected {
                    background: #2b2b2b;
                    border-color: #f0f0f0;
                }
            """)
            self.label_toggle_theme.setText("Dark")
            self.label_toggle_theme.setStyleSheet("color: white; text-decoration: none; cursor: default; padding: 5px;")

    def back_to_home(self):
        # Launch launcher2.py and close current app
        subprocess.Popen([sys.executable, "/home/endrx/Scrivania/codes/python/pyblauncher/newlauncher/launcher.py"])
        self.close()

    def load_theme_config(self):
        try:
            if self.theme_config_file.exists():
                with open(self.theme_config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                theme = data.get("theme", "dark")
                self.theme = theme
            else:
                self.theme = "dark"
        except Exception as e:
            print(f"Error loading theme config: {e}")

    def save_theme_config(self):
        try:
            data = {"theme": self.theme}
            with open(self.theme_config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving theme config: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MultiCalculatorApp()
    window.show()
    sys.exit(app.exec_())
