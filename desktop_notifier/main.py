import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings

from desktop_notifier.api.client import ApiClient
from desktop_notifier.ui.dialogs import LoginDialog
from desktop_notifier.ui.main_window import MainWindow
from desktop_notifier.utils.config import load_refresh_token, remove_refresh_token, load_theme


def main():
    app = QApplication(sys.argv)

    # Setup settings
    QApplication.setOrganizationName("MyCompany")
    QApplication.setApplicationName("DesktopNotifier")
    
    api_client = ApiClient()

    while True:
        theme_name = load_theme()
        access_token = None
        refresh_token = load_refresh_token()

        if refresh_token:
            access_token = api_client.refresh_token(refresh_token)
            if not access_token:
                remove_refresh_token()

        if access_token:
            window = MainWindow(api_client=api_client, access_token=access_token, theme_name=theme_name)
            window.show()
            app.exec()
            # After the main window is closed (e.g., by logout), the loop will restart
        else:
            login_dialog = LoginDialog(api_client=api_client)
            if login_dialog.exec():
                access_token = login_dialog.access_token
                # The loop will restart and try to launch the main window
            else:
                # User closed the login dialog without logging in
                break  # Exit the application
    
    sys.exit()

if __name__ == '__main__':
    main()