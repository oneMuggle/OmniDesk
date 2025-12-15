import sys
import os
import winreg
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget,
    QDialog, QCheckBox, QPushButton, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer
from PyQt6.QtGui import QScreen

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.initUI()
        self.is_docked = False
        self.drag_position = QPoint()

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
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # Set window size
        self.window_width = 320
        self.window_height = 700
        self.resize(self.window_width, self.window_height)

        # Define docking positions
        self.start_pos_x = screen_width - 10  # Hidden position
        self.end_pos_x = screen_width - self.window_width  # Visible position

        # Center window on startup
        start_x = (screen_width - self.window_width) // 2
        start_y = (screen_height - self.window_height) // 2
        self.move(start_x, start_y)

        # Main layout
        main_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()

        # Left-side List Widget (Navigation)
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setMaximumWidth(80)
        self.nav_list.addItems(["排班", "试验", "会议室"])

        # Right-side Stacked Widget (Content)
        self.stacked_widget = QStackedWidget()
        self.schedule_list = QListWidget()
        self.experiment_list = QListWidget()
        self.booking_list = QListWidget()
        self.stacked_widget.addWidget(self.schedule_list)
        self.stacked_widget.addWidget(self.experiment_list)
        self.stacked_widget.addWidget(self.booking_list)

        # Connect navigation list to stacked widget
        self.nav_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        self.nav_list.setCurrentRow(0)  # Set initial selection

        # Add widgets to content layout
        content_layout.addWidget(self.nav_list)
        content_layout.addWidget(self.stacked_widget)

        # Add content layout and settings button to main layout
        main_layout.addLayout(content_layout)
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        main_layout.addWidget(self.settings_button)

        self.setLayout(main_layout)

        # Set up animation
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(300)

    def enterEvent(self, event):
        """Show window when mouse enters if docked."""
        if self.is_docked:
            self.slide_in()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide window when mouse leaves if docked."""
        if self.is_docked:
            self.slide_out()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_docked = False  # Undock when dragging starts
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to check for docking."""
        if event.button() == Qt.MouseButton.LeftButton:
            screen = QApplication.primaryScreen().geometry()
            # Check if the window is close to the right edge
            if self.pos().x() + self.width() > screen.width() - 50:
                self.is_docked = True
                self.slide_out()  # Snap to the edge
            event.accept()

    def slide_in(self):
        """Slides the window in to be fully visible."""
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(QPoint(self.end_pos_x, self.pos().y()))
        self.animation.start()

    def slide_out(self):
        """Slides the window out to a partially hidden state."""
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(QPoint(self.start_pos_x, self.pos().y()))
        self.animation.start()

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
        style_path = os.path.join(os.path.dirname(__file__), "styles.qss")
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: styles.qss not found. Using default style.")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()