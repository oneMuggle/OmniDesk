import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget,
    QPushButton, QSpacerItem, QSizePolicy
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
        self.dock_location = "none"  # Can be "none", "right", "top"
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
        schedules_list = schedules.get('results', []) if isinstance(schedules, dict) else schedules
        for item in schedules_list:
            if isinstance(item, dict):
                display_text = f"{item.get('duty_person_name', 'N/A')} - {item.get('duty_leader_name', 'N/A')}"
            elif isinstance(item, str):
                display_text = item
            else:
                display_text = "Invalid schedule data"
            self.schedule_list.addItem(display_text)

        self.experiment_list.clear()
        experiments = self.api_client.get_experiments(self.access_token)
        experiments_list = experiments.get('results', []) if isinstance(experiments, dict) else experiments
        for item in experiments_list:
            if isinstance(item, dict):
                display_text = item.get("name", "N/A")
            elif isinstance(item, str):
                display_text = item
            else:
                display_text = "Invalid experiment data"
            self.experiment_list.addItem(display_text)

        self.booking_list.clear()
        bookings = self.api_client.get_bookings(self.access_token)
        bookings_list = bookings.get('results', []) if isinstance(bookings, dict) else bookings
        for item in bookings_list:
            if isinstance(item, dict):
                display_text = f"{item.get('meeting_room_name', 'N/A')} by {item.get('user_name', 'N/A')} for {item.get('purpose', 'N/A')}"
            elif isinstance(item, str):
                display_text = item
            else:
                display_text = "Invalid booking data"
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
        self.w = self.window_width
        self.h = self.window_height
        self.visible_x_right = screen_width - self.w
        self.hidden_x_right = screen_width - 2
        self.visible_y_top = 0
        self.hidden_y_top = 2 - self.h

        # Center window on startup
        start_x = (screen_width - self.window_width) // 2
        start_y = (screen_height - self.window_height) // 2
        self.move(start_x, start_y)

        # Top-level layout
        top_layout = QVBoxLayout()

        # Close button layout
        close_button_layout = QHBoxLayout()
        close_button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        self.settings_button = QPushButton("S")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.clicked.connect(self.open_settings)
        close_button_layout.addWidget(self.settings_button)

        self.close_button = QPushButton("X")
        self.close_button.setObjectName("closeButton")
        self.close_button.clicked.connect(self.close)
        close_button_layout.addWidget(self.close_button)
        top_layout.addLayout(close_button_layout)

        # Main content layout
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
        top_layout.addLayout(content_layout)
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        top_layout.addWidget(self.settings_button)

        self.setLayout(top_layout)

        # Set up animation
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(300)

    def enterEvent(self, event):
        """Show window when mouse enters if docked."""
        if self.dock_location == "right":
            self.animation.setStartValue(self.pos())
            self.animation.setEndValue(QPoint(self.visible_x_right, self.pos().y()))
            self.animation.start()
        elif self.dock_location == "top":
            self.animation.setStartValue(self.pos())
            self.animation.setEndValue(QPoint(self.pos().x(), self.visible_y_top))
            self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide window when mouse leaves if docked."""
        if self.dock_location == "right":
            self.animation.setStartValue(self.pos())
            self.animation.setEndValue(QPoint(self.hidden_x_right, self.pos().y()))
            self.animation.start()
        elif self.dock_location == "top":
            self.animation.setStartValue(self.pos())
            self.animation.setEndValue(QPoint(self.pos().x(), self.hidden_y_top))
            self.animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dock_location = "none"  # Undock when dragging starts
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
            pos = self.pos()

            # Check for top docking first
            if pos.y() < 30:
                self.dock_location = "top"
                self.animation.setStartValue(pos)
                self.animation.setEndValue(QPoint(pos.x(), self.hidden_y_top))
                self.animation.start()
            # Check for right docking
            elif pos.x() + self.width() > screen.width() - 50:
                self.dock_location = "right"
                self.animation.setStartValue(pos)
                self.animation.setEndValue(QPoint(self.hidden_x_right, pos.y()))
                self.animation.start()
            else:
                self.dock_location = "none"

            event.accept()


    def open_settings(self):
        pass

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
        QApplication.instance().quit()

    def apply_theme(self, theme_name):
        """Loads and applies a theme from a QSS file."""
        app = QApplication.instance()
        try:
            style_sheet_path = os.path.join(os.path.dirname(__file__), "..", f"theme_{theme_name}.qss")
            with open(style_sheet_path, "r") as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Warning: Theme file theme_{theme_name}.qss not found. Using default style.")