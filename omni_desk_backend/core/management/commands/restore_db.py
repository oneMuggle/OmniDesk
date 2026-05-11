"""Restore database from a backup file."""

import gzip
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Restore database from a backup file. Usage: python manage.py restore_db <backup_file.sql.gz>'

    def add_arguments(self, parser):
        parser.add_argument('backup_file', type=str, help='Path to the .sql.gz backup file')
        parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')

    def handle(self, *args, **options):
        backup_file = Path(options['backup_file'])
        if not backup_file.is_file():
            raise CommandError(f'Backup file not found: {backup_file}')

        if not options['force']:
            self.stdout.write(self.style.WARNING(
                f'WARNING: This will OVERWRITE the current database "{settings.DATABASES["default"]["NAME"]}".'
            ))
            confirm = input('Type "yes" to continue: ')
            if confirm.strip().lower() != 'yes':
                self.stdout.write('Restore cancelled.')
                return

        self.stdout.write(f'Restoring from {backup_file} ...')
        db = settings.DATABASES['default']

        if db['ENGINE'] != 'django.db.backends.postgresql':
            raise CommandError('Restore only supports PostgreSQL.')

        env = os.environ.copy()
        env['PGPASSWORD'] = db['PASSWORD']

        cmd = [
            'psql',
            '-h', db['HOST'],
            '-p', str(db['PORT']),
            '-U', db['USER'],
            '-d', db['NAME'],
        ]

        try:
            with gzip.open(backup_file, 'rb') as gz:
                result = subprocess.run(cmd, stdin=gz, env=env, capture_output=True, text=True)
                if result.returncode != 0:
                    raise CommandError(f'psql failed: {result.stderr}')

            self.stdout.write(self.style.SUCCESS('Database restored successfully.'))
        except FileNotFoundError:
            raise CommandError('psql not found. Please install PostgreSQL client tools.')
