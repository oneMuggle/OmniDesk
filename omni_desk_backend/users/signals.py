from django.apps import apps
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Group)
def create_page_visibility_for_new_group(sender, instance, created, **kwargs):
    """
    Create PageVisibility for all pages when a new group is created.
    """
    if created:
        Page = apps.get_model("config", "Page")
        PageVisibility = apps.get_model("config", "PageVisibility")
        pages = Page.objects.all()
        for page in pages:
            PageVisibility.objects.create(page=page, group=instance, is_visible=False)


@receiver(post_save, sender="config.Page")
def create_page_visibility_for_new_page(sender, instance, created, **kwargs):
    """
    Create PageVisibility for all groups when a new page is created.
    """
    if created:
        PageVisibility = apps.get_model("config", "PageVisibility")
        groups = Group.objects.all()
        for group in groups:
            PageVisibility.objects.create(page=instance, group=group, is_visible=False)
