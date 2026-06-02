from django.core.management.base import BaseCommand
from django.utils import timezone

from communication.models import Post


class Command(BaseCommand):
    help = "Archives posts that have expired."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_posts = Post.objects.filter(expires_at__lt=now, is_archived=False)
        count = expired_posts.update(is_archived=True)
        self.stdout.write(self.style.SUCCESS(f"Successfully archived {count} posts."))
