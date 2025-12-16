import sys
import os
import winreg
from PyQt6.QtCore import QSettings

APP_NAME = "DesktopNotifier"
COMPANY_NAME = "MyCompany"

def save_refresh_token(token):
    settings = QSettings(COMPANY_NAME, APP_NAME)
    settings.setValue("refresh_token", token)

def load_refresh_token():
    settings = QSettings(COMPANY_NAME, APP_NAME)
    return settings.value("refresh_token")

def remove_refresh_token():
    settings = QSettings(COMPANY_NAME, APP_NAME)
    settings.remove("refresh_token")

def save_theme(theme_name):
    settings = QSettings(COMPANY_NAME, APP_NAME)
    settings.setValue("theme", theme_name)

def load_theme():
    settings = QSettings(COMPANY_NAME, APP_NAME)
    return settings.value("theme", "dark")

def save_server_address(address: str):
    """Saves the server address."""
    settings = QSettings(COMPANY_NAME, APP_NAME)
    settings.setValue("server_address", address)

def load_server_address() -> str:
    """Loads the server address."""
    settings = QSettings(COMPANY_NAME, APP_NAME)
    return settings.value("server_address", "http://127.0.0.1:8000")

def is_autostart_enabled() -> bool:
    """Checks if the application is set to run at startup."""
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
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    # Determine the command to run the application
    if getattr(sys, 'frozen', False):
        # Path to the executable when bundled with PyInstaller
        app_path = sys.executable
    else:
        # Path to the python interpreter and the script
        # This needs to be adjusted to point to the new main.py
        app_path = f'"{sys.executable}" "{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))}"'

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