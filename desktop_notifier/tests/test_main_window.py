import sys
import os
import pytest
from PyQt5.QtWidgets import QApplication

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from desktop_notifier.ui.main_window import MainWindow
from desktop_notifier.api.client import ApiClient

def test_main_window_instantiation(qtbot):
    """
    Tests if the MainWindow can be instantiated without crashing.
    """
    # We don't need a real API client for this smoke test
    api_client = None 
    access_token = "dummy_token"
    theme_name = "dark"
    
    # Ensure a QApplication instance exists
    if QApplication.instance() is None:
        _ = QApplication(sys.argv)

    window = MainWindow(api_client=api_client, access_token=access_token, theme_name=theme_name)
    qtbot.addWidget(window)
    
    # Check if the window title is set correctly
    assert window.windowTitle() == "Desktop Notifier"