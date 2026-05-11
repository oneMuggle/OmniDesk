import os
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget,
    QPushButton, QSpacerItem, QSizePolicy, QLabel, QFrame, QSystemTrayIcon, QMenu
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer, QDate, QDateTime
from PyQt5.QtGui import QScreen, QIcon

from desktop_notifier.api.client import ApiClient
from desktop_notifier.ui.dialogs import SettingsDialog
from desktop_notifier.utils.config import save_theme, load_server_address
from desktop_notifier.utils.cache import save as cache_save, load as cache_load
from desktop_notifier.utils.browser import open_frontend


class MainWindow(QWidget):
    def __init__(self, api_client, access_token, theme_name="dark"):
        super().__init__()
        self.api_client = api_client
        self.access_token = access_token
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # 系统托盘
        self.tray_icon = None
        self._setup_tray()

        self.initUI()
        self.apply_theme(theme_name)
        self.dock_location = "none"
        self.drag_position = QPoint()

        # 连接状态
        self.is_online = False

        # 数据获取定时器（5 秒）
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_data)
        self.timer.start(5000)

        # 健康检查定时器（30 秒）
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self.check_health)
        self.health_timer.start(30000)

        # 首次启动：健康检查 + 数据获取
        self.check_health()
        self.fetch_data()

    # ─── 系统托盘 ──────────────────────────────────────
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("OmniDesk 桌面助手")

        tray_menu = QMenu()
        action_open = tray_menu.addAction("打开管理页面")
        action_open.triggered.connect(self._open_frontend)
        action_notify = tray_menu.addAction("查看通知")
        action_notify.triggered.connect(self._show_notify_tab)
        action_settings = tray_menu.addAction("设置")
        action_settings.triggered.connect(self.open_settings_dialog)
        tray_menu.addSeparator()
        action_quit = tray_menu.addAction("退出")
        action_quit.triggered.connect(QApplication.instance().quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()

    def _open_frontend(self):
        server_url = load_server_address()
        open_frontend(server_url)

    def _show_notify_tab(self):
        self.nav_list.setCurrentRow(3)
        self.show()
        self.raise_()

    def _show_system_notification(self, title, message):
        if self.tray_icon:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    # ─── 健康检查 ──────────────────────────────────────
    def check_health(self):
        """调用 /api/health/ 检测后端连通性"""
        base_url = self.api_client.base_url.replace("/api", "")
        try:
            resp = requests.get(f"{base_url}/api/health/", timeout=5)
            if resp.status_code == 200:
                self.is_online = True
                self.status_indicator.setText("✅ 已连接")
                self.status_indicator.setStyleSheet("color: #4caf50;")
                return
        except Exception:
            pass
        self.is_online = False
        self.status_indicator.setText("❌ 连接断开")
        self.status_indicator.setStyleSheet("color: #f44336;")

    # ─── 数据获取 ──────────────────────────────────────
    def fetch_data(self):
        """从 API 获取数据，失败时回退到离线缓存"""
        if not self.api_client:
            self._load_from_cache_all()
            return

        # 排班
        schedules = self.api_client.get_schedules(self.access_token)
        if schedules:
            cache_save("schedules", schedules)
            self._populate_list(self.schedule_list, schedules, "schedule")
        else:
            self._load_from_cache("schedules", self.schedule_list, "schedule")

        # 试验
        experiments = self.api_client.get_experiments(self.access_token)
        if experiments:
            cache_save("experiments", experiments)
            self._populate_list(self.experiment_list, experiments, "experiment")
        else:
            self._load_from_cache("experiments", self.experiment_list, "experiment")

        # 会议室
        bookings = self.api_client.get_bookings(self.access_token)
        if bookings:
            cache_save("bookings", bookings)
            self._populate_list(self.booking_list, bookings, "booking")
        else:
            self._load_from_cache("bookings", self.booking_list, "booking")

        # 通知
        notifications = self._fetch_notifications()
        if notifications:
            cache_save("notifications", notifications)
            self._populate_notifications(notifications)
        else:
            cached = cache_load("notifications")
            if cached:
                self._populate_notifications(cached)

    def _fetch_notifications(self):
        """从后端拉取未读通知"""
        try:
            url = f"{self.api_client.base_url}/notifications/"
            headers = {'Authorization': f'Bearer {self.access_token}'}
            resp = requests.get(url, headers=headers, timeout=5, params={"is_read": "false"})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", data) if isinstance(data, dict) else data
        except Exception:
            pass
        return []

    def _populate_list(self, list_widget, data, data_type):
        list_widget.clear()
        items = data if isinstance(data, list) else data.get("results", [])
        for item in items:
            if isinstance(item, dict):
                if data_type == "schedule":
                    text = f"{item.get('duty_person_name', 'N/A')} - {item.get('duty_leader_name', 'N/A')}"
                elif data_type == "experiment":
                    text = item.get("name", "N/A")
                elif data_type == "booking":
                    text = f"{item.get('meeting_room_name', 'N/A')} by {item.get('user_name', 'N/A')} for {item.get('purpose', 'N/A')}"
                else:
                    text = "Unknown"
            elif isinstance(item, str):
                text = item
            else:
                text = "无效数据"
            list_widget.addItem(text)
        if not items:
            list_widget.addItem("暂无数据")

    def _load_from_cache_all(self):
        self._load_from_cache("schedules", self.schedule_list, "schedule")
        self._load_from_cache("experiments", self.experiment_list, "experiment")
        self._load_from_cache("bookings", self.booking_list, "booking")
        cached = cache_load("notifications")
        if cached:
            self._populate_notifications(cached)

    def _load_from_cache(self, key, list_widget, data_type):
        cached = cache_load(key)
        if cached:
            self._populate_list(list_widget, cached, data_type)
            list_widget.addItem("（离线缓存数据）")
        else:
            list_widget.clear()
            list_widget.addItem("无法连接服务器，无缓存数据")

    def _populate_notifications(self, notifications):
        self.notification_list.clear()
        items = notifications if isinstance(notifications, list) else notifications.get("results", [])
        for item in items:
            if isinstance(item, dict):
                title = item.get("title", "无标题")
                time_str = item.get("created_at", "")
                text = f"{title}\n  {time_str[:16] if time_str else ''}"
            else:
                text = str(item)
            self.notification_list.addItem(text)

        # 新通知检测（对比上一次数量）
        prev_count = getattr(self, "_last_notification_count", 0)
        current_count = len(items)
        if current_count > prev_count and prev_count > 0:
            self._show_system_notification("新通知", f"您有 {current_count - prev_count} 条新通知")
        self._last_notification_count = current_count

        if not items:
            self.notification_list.addItem("暂无通知")

    # ─── UI 初始化 ─────────────────────────────────────
    def initUI(self):
        self.setWindowTitle('OmniDesk 桌面助手')

        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        self.window_width = 320
        self.window_height = 700
        self.resize(self.window_width, self.window_height)

        self.w = self.window_width
        self.h = self.window_height
        self.visible_x_right = screen_width - self.w
        self.hidden_x_right = screen_width - 2
        self.visible_y_top = 0
        self.hidden_y_top = 2 - self.h

        start_x = (screen_width - self.window_width) // 2
        start_y = (screen_height - self.window_height) // 2
        self.move(start_x, start_y)

        top_layout = QVBoxLayout()

        # 顶部按钮
        close_button_layout = QHBoxLayout()
        close_button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.settings_button = QPushButton("S")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        close_button_layout.addWidget(self.settings_button)

        self.close_button = QPushButton("X")
        self.close_button.setObjectName("closeButton")
        self.close_button.clicked.connect(self.close)
        close_button_layout.addWidget(self.close_button)
        top_layout.addLayout(close_button_layout)

        # 主内容
        content_layout = QHBoxLayout()

        # 左侧导航（4个Tab）
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setMaximumWidth(80)
        self.nav_list.addItems(["排班", "试验", "会议室", "通知"])

        # 右侧内容区
        self.stacked_widget = QStackedWidget()
        self.schedule_list = QListWidget()
        self.experiment_list = QListWidget()
        self.booking_list = QListWidget()
        self.notification_list = QListWidget()
        self.stacked_widget.addWidget(self.schedule_list)
        self.stacked_widget.addWidget(self.experiment_list)
        self.stacked_widget.addWidget(self.booking_list)
        self.stacked_widget.addWidget(self.notification_list)

        self.nav_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

        content_layout.addWidget(self.nav_list)
        content_layout.addWidget(self.stacked_widget)

        top_layout.addLayout(content_layout)

        # 底部状态栏
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(8, 4, 8, 4)

        self.status_indicator = QLabel("检测中...")
        self.status_indicator.setStyleSheet("color: #999;")
        status_layout.addWidget(self.status_indicator)

        status_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        open_btn = QPushButton("打开前端")
        open_btn.setObjectName("openFrontendBtn")
        open_btn.clicked.connect(self._open_frontend)
        status_layout.addWidget(open_btn)

        top_layout.addWidget(status_bar)

        self.setLayout(top_layout)

        # 动画
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(300)

    # ─── 鼠标事件 ──────────────────────────────────────
    def enterEvent(self, event):
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
        if event.button() == Qt.LeftButton:
            self.dock_location = "none"
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            screen = QApplication.primaryScreen().geometry()
            pos = self.pos()

            if pos.y() < 30:
                self.dock_location = "top"
                self.animation.setStartValue(pos)
                self.animation.setEndValue(QPoint(pos.x(), self.hidden_y_top))
                self.animation.start()
            elif pos.x() + self.width() > screen.width() - 50:
                self.dock_location = "right"
                self.animation.setStartValue(pos)
                self.animation.setEndValue(QPoint(self.hidden_x_right, pos.y()))
                self.animation.start()
            else:
                self.dock_location = "none"

            event.accept()

    # ─── 设置/主题/登出 ────────────────────────────────
    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.theme_changed.connect(self.handle_theme_change)
        dialog.logout_requested.connect(self.handle_logout)
        dialog.server_address_changed.connect(self.handle_server_address_change)
        dialog.exec()

    def handle_server_address_change(self, new_address):
        self.api_client = ApiClient(new_address)
        self.fetch_data()
        self.check_health()

    def handle_theme_change(self, theme_name):
        self.apply_theme(theme_name)
        save_theme(theme_name)

    def handle_logout(self):
        QApplication.instance().quit()

    def apply_theme(self, theme_name):
        app = QApplication.instance()
        try:
            style_sheet_path = os.path.join(os.path.dirname(__file__), "..", f"theme_{theme_name}.qss")
            with open(style_sheet_path, "r") as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Warning: Theme file theme_{theme_name}.qss not found. Using default style.")

    def closeEvent(self, event):
        """关闭窗口时隐藏到托盘而非退出"""
        event.ignore()
        self.hide()
