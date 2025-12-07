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

        # This pattern finds all ProtectedRoute components and captures the props and the child component.
        protected_route_pattern = re.compile(
            r'<ProtectedRoute(?P<props>.*?)>(?P<children>.*?)</ProtectedRoute>',
            re.DOTALL
        )

        # These patterns extract specific props from the props string.
        name_pattern = re.compile(r'pageName="([^"]+)"')
        path_pattern = re.compile(r'pagePath="([^"]+)"')
        component_pattern = re.compile(r'<(\w+)')

        routes_found = protected_route_pattern.finditer(content)
        
        synced_paths = set()
        count = 0

        for match in routes_found:
            props_str = match.group('props')
            children_str = match.group('children')

            name_match = name_pattern.search(props_str)
            path_match = path_pattern.search(props_str)
            component_match = component_pattern.search(children_str)

            if name_match:
                name = name_match.group(1)
                # If pagePath is not found, check if it's the root route which has a different structure.
                if path_match:
                    path = path_match.group(1)
                else:
                    # A bit of a hack: check if the route is the main dashboard
                    if name == "仪表盘":
                        path = "/"
                    else:
                        # If there's no path, we can't sync it.
                        continue
                
                component = component_match.group(1) if component_match else 'Unknown'

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