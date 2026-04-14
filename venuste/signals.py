from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_migrate)
def ensure_rbac_groups(sender, **kwargs):
    if sender.name != "venuste":
        return

    privileged_group, _ = Group.objects.get_or_create(name="instructors")
    permission = Permission.objects.filter(codename="access_privileged_portal").first()
    if permission:
        privileged_group.permissions.add(permission)
