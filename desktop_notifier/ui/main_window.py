import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget,
    QPushButton
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer, QDate, QDateTime
from PyQt6.QtGui import QScreen

from desktop_notifier.api.client import ApiClient
from desktop_notifier.ui.dialogs import SettingsDialog
from desktop_notifier.utils.config import save_theme


class MainWindow(QWidget):
    def __init__(self, api_client, access_token, theme_name="dark"):
        super().__init__()
        self.api_client = api_client
        self.access_token = access_token
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.initUI()
        self.apply_theme(theme_name)  # Apply initial theme
        self.is_docked = False
        self.drag_position = QPoint()

        # Set up data fetching
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_data)
        self.timer.start(5000)  # Fetch every 5 seconds
        self.fetch_data()  # Initial fetch

    def fetch_data(self):
        """Fetches data from multiple API endpoints and populates the tabs."""
        self.schedule_list.clear()
        schedules = self.api_client.get_schedules(self.access_token)
        for item in schedules:
            display_text = f"{item.get('duty_person_name', 'N/A')} - {item.get('duty_leader_name', 'N/A')}"
            self.schedule_list.addItem(display_text)

        self.experiment_list.clear()
        experiments = self.api_client.get_experiments(self.access_token)
        for item in experiments:
            self.experiment_list.addItem(item.get("name", str(item)))

        self.booking_list.clear()
        bookings = self.api_client.get_bookings(self.access_token)
        for item in bookings:
            display_text = f"{item.get('meeting_room_name', 'N/A')} by {item.get('user_name', 'N/A')} for {item.get('purpose', 'N/A')}"
            self.booking_list.addItem(display_text)

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
        dialog.theme_changed.connect(self.handle_theme_change)
        dialog.logout_requested.connect(self.handle_logout)
        dialog.server_address_changed.connect(self.handle_server_address_change)
        dialog.exec()

    def handle_server_address_change(self, new_address):
        self.api_client = ApiClient(new_address)
        self.fetch_data()

    def handle_theme_change(self, theme_name):
        self.apply_theme(theme_name)
        save_theme(theme_name)

    def handle_logout(self):
        self.close()

    def apply_theme(self, theme_name):
        """Loads and applies a theme from a QSS file."""
        app = QApplication.instance()
        try:
            style_sheet_path = os.path.join(os.path.dirname(__file__), "..", f"theme_{theme_name}.qss")
            with open(style_sheet_path, "r") as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Warning: Theme file theme_{theme_name}.qss not found. Using default style.")