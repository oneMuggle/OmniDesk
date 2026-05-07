from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from permissions.models import GroupPagePermission, PageRoute


class Command(BaseCommand):
    help = '设置游客组的只读页面权限'

    # 游客可访问的页面路径列表（对应 PageRoute.path）
    GUEST_PAGE_PATHS = [
        '/schedule',
        '/trial-schedule',
        '/shift-schedule',
        '/announcements',
        '/communication/:postId',
        '/docs/:docId',
        '/library',
        '/books/:bookId',
        '/books/:bookId/reader',
        '/books/:bookId/editor',
        '/unauthorized',
    ]

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name='Guest')
        if created:
            self.stdout.write(self.style.SUCCESS('Created Guest group'))
        else:
            self.stdout.write('Guest group already exists')

        existing_paths = set(PageRoute.objects.values_list('path', flat=True))

        granted = 0
        for path in self.GUEST_PAGE_PATHS:
            if path not in existing_paths:
                self.stdout.write(self.style.WARNING(f'Route not found in database: {path} (skip)'))
                continue

            page = PageRoute.objects.get(path=path)
            _, perm_created = GroupPagePermission.objects.get_or_create(group=group, page=page)
            if perm_created:
                granted += 1
                self.stdout.write(self.style.SUCCESS(f'Granted Guest group permission to: {page.name} ({path})'))
            else:
                self.stdout.write(f'Permission already exists for: {path}')

        self.stdout.write(self.style.SUCCESS(f'Done. Granted {granted} new permissions to Guest group.'))
