from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from permissions.models import GroupPagePermission, PageRoute


class Command(BaseCommand):
    help = '设置游客组的只读页面权限。自动创建缺失的路由条目。'

    # 游客可访问的页面：(path, name, component)
    GUEST_PAGES = [
        ('/schedule', '排班表', 'SchedulePage'),
        ('/trial-schedule', '试验排班', 'TrialScheduleContainer'),
        ('/shift-schedule', '值班排班', 'ShiftScheduleContainer'),
        ('/announcements', '公告', 'AnnouncementsPage'),
        ('/communication/:postId', '帖子详情', 'PostDetailPage'),
        ('/docs/:docId', '文档查看', 'DocsPage'),
        ('/library', '图书馆', 'LibraryPage'),
        ('/books/:bookId', '书籍详情', 'BookPage'),
        ('/books/:bookId/reader', '书籍阅读', 'BookReaderPage'),
        ('/books/:bookId/editor', '书籍编辑', 'ChapterEditorPage'),
        ('/unauthorized', '无权限', 'UnauthorizedPage'),
    ]

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name='Guest')
        if created:
            self.stdout.write(self.style.SUCCESS('Created Guest group'))
        else:
            self.stdout.write('Guest group already exists')

        granted = 0
        for path, name, component in self.GUEST_PAGES:
            page, page_created = PageRoute.objects.get_or_create(
                path=path,
                defaults={'name': name, 'component': component},
            )
            if page_created:
                self.stdout.write(self.style.SUCCESS(f'Created route: {name} ({path})'))

            _, perm_created = GroupPagePermission.objects.get_or_create(group=group, page=page)
            if perm_created:
                granted += 1
                self.stdout.write(self.style.SUCCESS(f'Granted Guest group permission to: {name} ({path})'))
            else:
                self.stdout.write(f'Permission already exists for: {path}')

        self.stdout.write(self.style.SUCCESS(f'Done. Granted {granted} new permissions to Guest group.'))
