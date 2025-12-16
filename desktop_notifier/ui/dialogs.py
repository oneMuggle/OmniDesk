import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QMessageBox, QCheckBox, QDialogButtonBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from desktop_notifier.api.client import ApiClient
from desktop_notifier.utils.config import is_autostart_enabled, set_autostart, save_refresh_token, save_theme, \
    load_theme, remove_refresh_token


class LoginDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setWindowTitle("登录")
        self.access_token = None
        self.refresh_token = None

        layout = QVBoxLayout(self)

        # Username
        self.username_label = QLabel("用户名:")
        self.username_input = QLineEdit()
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)

        # Password
        self.password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        # Auto login checkbox
        self.auto_login_checkbox = QCheckBox("自动登录")
        layout.addWidget(self.auto_login_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        self.login_button = QPushButton("登录")
        self.login_button.clicked.connect(self.handle_login)
        self.register_button = QPushButton("注册")
        self.register_button.clicked.connect(self.handle_register)
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.register_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "输入错误", "用户名和密码不能为空。")
            return

        data = self.api_client.login(username, password)
        if data:
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")

            if self.access_token:
                if self.auto_login_checkbox.isChecked():
                    save_refresh_token(self.refresh_token)
                self.accept()
            else:
                QMessageBox.critical(self, "登录失败", "未能从响应中获取令牌。")
        else:
            QMessageBox.critical(self, "登录失败", "用户名或密码错误。")

    def handle_register(self):
        register_dialog = RegisterDialog(self.api_client, self)
        register_dialog.exec()


class RegisterDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setWindowTitle("注册")

        layout = QVBoxLayout(self)

        # Username
        self.username_label = QLabel("用户名:")
        self.username_input = QLineEdit()
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)

        # Password
        self.password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        # Confirm Password
        self.confirm_password_label = QLabel("确认密码:")
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.confirm_password_label)
        layout.addWidget(self.confirm_password_input)

        # Register button
        self.register_button = QPushButton("确认注册")
        self.register_button.clicked.connect(self.handle_registration)
        layout.addWidget(self.register_button)

        self.setLayout(layout)

    def handle_registration(self):
        username = self.username_input.text()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not username or not password or not confirm_password:
            QMessageBox.warning(self, "输入错误", "所有字段都不能为空。")
            return

        if password != confirm_password:
            QMessageBox.warning(self, "密码不匹配", "两次输入的密码不一致。")
            return

        response = self.api_client.register(username, password)
        if response and response.status_code == 201:
            QMessageBox.information(self, "注册成功", "用户注册成功！现在您可以登录了。")
            self.accept()
        else:
            error_message = "注册失败"
            if response is not None:
                try:
                    error_data = response.json()
                    error_message = error_data.get("username", ["注册失败"])[0]
                except (ValueError, KeyError):
                    error_message = f"服务器返回错误: {response.status_code}"
            QMessageBox.critical(self, "注册失败", error_message)


class SettingsDialog(QDialog):
    theme_changed = pyqtSignal(str)
    logout_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        layout = QVBoxLayout(self)

        # Autostart checkbox
        self.autostart_checkbox = QCheckBox("开机时自动启动")
        self.autostart_checkbox.setChecked(is_autostart_enabled())
        self.autostart_checkbox.stateChanged.connect(self.toggle_autostart)
        layout.addWidget(self.autostart_checkbox)

        # Theme selection
        self.theme_label = QLabel("主题:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色", "浅色"])
        layout.addWidget(self.theme_label)
        layout.addWidget(self.theme_combo)

        # Set current theme
        current_theme = load_theme()
        if current_theme == "light":
            self.theme_combo.setCurrentText("浅色")
        else:
            self.theme_combo.setCurrentText("深色")
        
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)

        # Logout button
        self.logout_button = QPushButton("登出")
        self.logout_button.clicked.connect(self.handle_logout)
        layout.addWidget(self.logout_button)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def toggle_autostart(self, state):
        enabled = state == Qt.CheckState.Checked.value
        set_autostart(enabled)

    def on_theme_changed(self, text):
        theme_name = "light" if text == "浅色" else "dark"
        save_theme(theme_name)
        self.theme_changed.emit(theme_name)

    def handle_logout(self):
        remove_refresh_token()
        self.logout_requested.emit()
        self.parent().close()  # Close MainWindow
        self.accept()  # Close SettingsDialog