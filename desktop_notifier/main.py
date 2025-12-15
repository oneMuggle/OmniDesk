import sys
import os
import winreg
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget, QTabWidget,
    QDialog, QCheckBox, QPushButton, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer
from PyQt6.QtGui import QScreen

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        # Make the window frameless and stay on top
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.initUI()
        self.is_hidden = True

        # Set up data fetching
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_data)
        self.timer.start(5000)  # Fetch every 5 seconds
        self.fetch_data()  # Initial fetch

    def fetch_data(self):
        """Fetches data from multiple API endpoints and populates the tabs."""
        # Clear all list widgets before fetching new data
        self.schedule_list.clear()
        self.experiment_list.clear()
        self.booking_list.clear()

        endpoints = {
            "schedules": "http://127.0.0.1:8000/api/schedules/today/",
            "experiments": "http://127.0.0.1:8000/api/experiments/today/",
            "bookings": "http://127.0.0.1:8000/api/bookings/today/",
        }

        for name, url in endpoints.items():
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()

                if name == "schedules":
                    for item in data:
                        display_text = f"{item.get('personnel_name', 'N/A')} - {item.get('start_time', '')}-{item.get('end_time', '')}"
                        self.schedule_list.addItem(display_text)
                elif name == "experiments":
                    for item in data:
                        self.experiment_list.addItem(item.get("name", str(item)))
                elif name == "bookings":
                    for item in data:
                        display_text = f"{item.get('room_name', 'N/A')} by {item.get('booked_by_name', 'N/A')} for {item.get('purpose', 'N/A')}"
                        self.booking_list.addItem(display_text)

            except requests.exceptions.RequestException as e:
                error_message = f"Error fetching {name}: {e}"
                if name == "schedules":
                    self.schedule_list.addItem(error_message)
                elif name == "experiments":
                    self.experiment_list.addItem(error_message)
                elif name == "bookings":
                    self.booking_list.addItem(error_message)

    def initUI(self):
        self.setWindowTitle('Desktop Notifier')
        
        # Get screen geometry
        screen = QScreen.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # Set window size
        self.window_width = 300
        self.window_height = 200
        self.resize(self.window_width, self.window_height)

        # Define visible and hidden positions
        self.visible_x = screen_width - self.window_width
        self.hidden_x = screen_width - 10  # Leave 10 pixels visible
        
        # Center vertically
        y_pos = (screen_height - self.window_height) // 2
        
        self.start_pos = QPoint(self.hidden_x, y_pos)
        self.end_pos = QPoint(self.visible_x, y_pos)

        # Set initial position
        self.move(self.start_pos)

        layout = QVBoxLayout(self)
        
        # Create Tab Widget
        self.tabs = QTabWidget()
        self.schedule_list = QListWidget()
        self.experiment_list = QListWidget()
        self.booking_list = QListWidget()
        
        self.tabs.addTab(self.schedule_list, "排班")
        self.tabs.addTab(self.experiment_list, "试验")
        self.tabs.addTab(self.booking_list, "会议室")
        
        layout.addWidget(self.tabs)

        # Add settings button
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        layout.addWidget(self.settings_button)

        self.setLayout(layout)

        # Set up animation
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(300)

    def enterEvent(self, event):
        """Mouse enters the window."""
        if self.is_hidden:
            self.slide_in()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse leaves the window."""
        if not self.is_hidden:
            self.slide_out()
        super().leaveEvent(event)

    def slide_in(self):
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(self.end_pos)
        self.animation.start()
        self.is_hidden = False

    def slide_out(self):
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(self.start_pos)
        self.animation.start()
        self.is_hidden = True

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        layout = QVBoxLayout(self)

        # Autostart checkbox
        self.autostart_checkbox = QCheckBox("开机时自动启动")
        self.autostart_checkbox.setChecked(is_autostart_enabled())
        self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
        layout.addWidget(self.autostart_checkbox)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def toggle_autostart(self, state):
        enabled = state == Qt.CheckState.Checked.value
        set_autostart(enabled)


def is_autostart_enabled() -> bool:
    """Checks if the application is set to run at startup."""
    APP_NAME = "DesktopNotifier"
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_autostart(enabled: bool):
    """
    Adds or removes the application from Windows startup registry.

    :param enabled: If True, add to startup. If False, remove from startup.
    """
    APP_NAME = "DesktopNotifier"
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    # Determine the command to run the application
    if getattr(sys, 'frozen', False):
        # Path to the executable when bundled with PyInstaller
        app_path = sys.executable
    else:
        # Path to the python interpreter and the script
        app_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass  # Key not found, which is fine.
    except OSError as e:
        print(f"Error accessing the registry: {e}")


def main():
    app = QApplication(sys.argv)

    # 加载QSS样式
    try:
        with open("desktop_notifier/styles.qss", "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: styles.qss not found. Using default style.")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()