#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path

# Load environment variables from .env.local if it exists (local dev only)
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env.local"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omni_desk_backend.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
