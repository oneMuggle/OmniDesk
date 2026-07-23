"""Application version — source of truth for the deployment."""

from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent.parent / "deployment" / "docker" / "VERSION"


def get_version() -> str:
    if VERSION_FILE.is_file():
        return VERSION_FILE.read_text().strip()
    return "0.0.0-dev"
