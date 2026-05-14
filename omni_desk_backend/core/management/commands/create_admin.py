import os
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Create an admin user non-interactively (for deployment scripts)."

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin', help='Admin username (default: admin)')
        parser.add_argument('--email', default='admin@localhost', help='Admin email (default: admin@localhost)')
        parser.add_argument('--password', default=None, help='Admin password (required if not using env vars)')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password'] or os.environ.get('DJANGO_ADMIN_PASSWORD')

        if not password:
            self.stderr.write(self.style.ERROR(
                'Password not provided. Pass --password or set DJANGO_ADMIN_PASSWORD env var.'
            ))
            sys.exit(1)

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'Admin user "{username}" already exists. Skipping.'
            ))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(
            f'Admin user "{username}" created successfully.'
        ))
