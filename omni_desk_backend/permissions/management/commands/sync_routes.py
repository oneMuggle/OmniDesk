import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from permissions.models import PageRoute

class Command(BaseCommand):
    help = 'Sync routes from frontend to database'

    def handle(self, *args, **options):
        # Path to the routes.json file
        routes_json_path = settings.BASE_DIR.parent / 'omni_desk_frontend' / 'public' / 'routes.json'

        if not os.path.exists(routes_json_path):
            self.stdout.write(self.style.ERROR(f'Routes JSON file not found at {routes_json_path}'))
            return

        with open(routes_json_path, 'r', encoding='utf-8') as f:
            try:
                routes_data = json.load(f)
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR('Failed to decode routes.json. Please check for syntax errors.'))
                return

        synced_paths = set()
        count = 0

        for route_info in routes_data:
            name = route_info.get('name')
            path = route_info.get('path')
            component = route_info.get('component')

            if not all([name, path, component]):
                self.stdout.write(self.style.WARNING(f'Skipping incomplete route data: {route_info}'))
                continue

            page_route, created = PageRoute.objects.update_or_create(
                path=path,
                defaults={'name': name, 'component': component}
            )
            synced_paths.add(path)
            count += 1
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created new route: {name} ({path})'))
            else:
                self.stdout.write(f'Updated existing route: {name} ({path})')

        self.stdout.write(self.style.SUCCESS(f'Found and processed {count} routes.'))

        # Clean up old routes
        all_db_paths = set(PageRoute.objects.values_list('path', flat=True))
        paths_to_delete = all_db_paths - synced_paths
        
        if paths_to_delete:
            PageRoute.objects.filter(path__in=paths_to_delete).delete()
            self.stdout.write(self.style.WARNING(f'Deleted {len(paths_to_delete)} old routes.'))

        self.stdout.write(self.style.SUCCESS('Successfully synced routes.'))