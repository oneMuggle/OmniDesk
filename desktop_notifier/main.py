import sys
import os

# Add the project root to the Python path to allow absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import QSettings

from desktop_notifier.api.client import ApiClient
from desktop_notifier.ui.dialogs import LoginDialog
from desktop_notifier.ui.main_window import MainWindow
from desktop_notifier.utils.config import load_refresh_token, remove_refresh_token, load_theme, load_server_address


def main():
    app = QApplication(sys.argv)

    # Setup settings
    QApplication.setOrganizationName("MyCompany")
    QApplication.setApplicationName("DesktopNotifier")

    theme_name = load_theme()
    access_token = None
    api_client = None
    
    # First, try to use the refresh token
    refresh_token = load_refresh_token()
    if refresh_token:
        server_address = load_server_address()
        temp_api_client = ApiClient(base_url=server_address)
        access_token = temp_api_client.refresh_token(refresh_token)
        if access_token:
            api_client = temp_api_client
        else:
            remove_refresh_token()

    if not (access_token and api_client):
        login_dialog = LoginDialog()
        if login_dialog.exec() == QDialog.Accepted:
            access_token = login_dialog.access_token
            api_client = login_dialog.api_client
        else:
            # User closed the login dialog without logging in
            sys.exit(0)  # Exit the application cleanly

    if access_token and api_client:
        window = MainWindow(api_client=api_client, access_token=access_token, theme_name=theme_name)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(1) # Exit if login fails and no token is available

if __name__ == '__main__':
    main()