import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from permissions.models import PageRoute


class Command(BaseCommand):
    help = "Sync routes from frontend to database"

    def handle(self, *args, **options):
        # 多个可能的位置(按优先级):
        # 1. 容器内 staticfiles 目录(Dockerfile build 时复制)
        # 2. 容器内 /usr/src/omni_desk_frontend/public/(源码路径,通常不存在)
        # 3. settings.BASE_DIR 相对路径(开发环境)
        possible_paths = [
            settings.BASE_DIR / "staticfiles" / "routes.json",
            "/usr/src/omni_desk_frontend/public/routes.json",
            settings.BASE_DIR.parent / "omni_desk_frontend" / "public" / "routes.json",
        ]

        routes_json_path = None
        for p in possible_paths:
            if os.path.exists(p):
                routes_json_path = p
                break

        if not routes_json_path:
            self.stdout.write(self.style.ERROR(
                f"Routes JSON file not found. Tried: {[str(p) for p in possible_paths]}"
            ))
            return

        self.stdout.write(f"Using routes.json from: {routes_json_path}")

        with open(routes_json_path, encoding="utf-8") as f:
            try:
                routes_data = json.load(f)
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR("Failed to decode routes.json. Please check for syntax errors."))
                return

        synced_paths = set()
        count = 0

        for route_info in routes_data:
            name = route_info.get("name")
            path = route_info.get("path")
            component = route_info.get("component")

            if not all([name, path, component]):
                self.stdout.write(self.style.WARNING(f"Skipping incomplete route data: {route_info}"))
                continue

            page_route, created = PageRoute.objects.update_or_create(
                path=path, defaults={"name": name, "component": component}
            )
            synced_paths.add(path)
            count += 1

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created new route: {name} ({path})"))
            else:
                self.stdout.write(f"Updated existing route: {name} ({path})")

        self.stdout.write(self.style.SUCCESS(f"Found and processed {count} routes."))

        # Clean up old routes
        all_db_paths = set(PageRoute.objects.values_list("path", flat=True))
        paths_to_delete = all_db_paths - synced_paths

        if paths_to_delete:
            PageRoute.objects.filter(path__in=paths_to_delete).delete()
            self.stdout.write(self.style.WARNING(f"Deleted {len(paths_to_delete)} old routes."))

        self.stdout.write(self.style.SUCCESS("Successfully synced routes."))
