from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def ensure_core_groups(sender, **kwargs):
    """Keep core role groups available after migrations."""
    for name in ("Staff", "Management", "StoreKeeper"):
        Group.objects.get_or_create(name=name)
