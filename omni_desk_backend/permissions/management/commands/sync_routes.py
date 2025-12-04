import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from permissions.models import PageRoute

class Command(BaseCommand):
    help = 'Sync routes from frontend to database'

    def handle(self, *args, **options):
        frontend_dir = settings.BASE_DIR.parent / 'omni_desk_frontend'
        routes_file = frontend_dir / 'src' / 'routes' / 'index.js'

        if not os.path.exists(routes_file):
            self.stdout.write(self.style.ERROR(f'Routes file not found at {routes_file}'))
            return

        with open(routes_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # This regex is designed to find routes wrapped in ProtectedRoute that have a pagePath attribute.
        # These are the routes relevant for permission management.
        # It captures the pagePath and the name of the component being wrapped.
        route_pattern = re.compile(
            r'<ProtectedRoute.*?pageName="(?P<name>[^"]+)".*?pagePath="(?P<path>[^"]+)".*?>\s*<(?P<component>\w+)'
        )

        routes = route_pattern.finditer(content)
        
        # finditer returns an iterator, so we convert it to a list to get the count
        routes_list = list(routes)
        self.stdout.write(self.style.SUCCESS(f'Found {len(routes_list)} routes to sync.'))

        for match in routes_list:
            path = match.group('path')
            component = match.group('component')
            name = match.group('name')

            # Attempt to find an existing route by path
            page_route, created = PageRoute.objects.update_or_create(
                path=path,
                defaults={
                    'name': name,
                    'component': component,
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Created new route: {name} ({path})'))
            else:
                self.stdout.write(self.style.WARNING(f'Updated existing route: {name} ({path})'))

        self.stdout.write(self.style.SUCCESS('Successfully synced routes.'))