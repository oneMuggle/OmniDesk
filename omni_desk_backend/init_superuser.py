#!/usr/bin/env python
import logging
import os

from django.contrib.auth import get_user_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_superuser():
    User = get_user_model()

    username = os.environ.get('SUPERUSER_NAME', 'admin')
    email = os.environ.get('SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('SUPERUSER_PASSWORD')

    if not password:
        logger.error("Superuser password not set in environment variables")
        return False

    if User.objects.filter(username=username).exists():
        logger.info(f"Superuser {username} already exists")
        return True

    try:
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        logger.info(f"Successfully created superuser {username}")
        return True
    except Exception as e:
        logger.error(f"Failed to create superuser: {e!s}")
        return False

if __name__ == "__main__":
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'omni_desk_backend.settings')
    django.setup()

    create_superuser()
