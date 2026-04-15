from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import m2m_changed, post_migrate, post_save, pre_save
from django.dispatch import receiver

from .audit import log_security_event
from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(user_logged_in)
def audit_login_success(sender, request, user, **kwargs):
    log_security_event("auth.login.success", request=request, actor=user, target=user)


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    log_security_event("auth.logout", request=request, actor=user, target=user)


@receiver(user_login_failed)
def audit_login_failure(sender, credentials, request, **kwargs):
    username = credentials.get("username", "") if credentials else ""
    log_security_event(
        "auth.login.failure",
        outcome="denied",
        request=request,
        details={"username": username[:150]},
    )


@receiver(post_migrate)
def ensure_rbac_groups(sender, **kwargs):
    if sender.name != "venuste":
        return

    privileged_group, _ = Group.objects.get_or_create(name="instructors")
    permission = Permission.objects.filter(codename="access_privileged_portal").first()
    if permission:
        privileged_group.permissions.add(permission)


@receiver(pre_save, sender=User)
def capture_previous_user_flags(sender, instance, **kwargs):
    if not instance.pk:
        instance._audit_previous_flags = None
        return
    previous = sender.objects.filter(pk=instance.pk).values(
        "is_staff",
        "is_superuser",
        "is_active",
    ).first()
    instance._audit_previous_flags = previous


@receiver(post_save, sender=User)
def audit_privileged_user_flag_changes(sender, instance, created, **kwargs):
    if created:
        return
    previous = getattr(instance, "_audit_previous_flags", None)
    if not previous:
        return

    changes = {}
    for field in ("is_staff", "is_superuser", "is_active"):
        old_value = previous.get(field)
        new_value = getattr(instance, field)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}

    if changes:
        log_security_event(
            "auth.privilege.user_flags_changed",
            outcome="changed",
            target=instance,
            details={"changes": changes},
        )


@receiver(m2m_changed, sender=User.groups.through)
def audit_user_group_membership_changes(sender, instance, action, pk_set, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    group_names = []
    if pk_set:
        group_names = list(Group.objects.filter(pk__in=pk_set).values_list("name", flat=True))

    log_security_event(
        "auth.privilege.user_groups_changed",
        outcome="changed",
        target=instance,
        details={
            "action": action,
            "group_names": sorted(group_names),
        },
    )


@receiver(m2m_changed, sender=User.user_permissions.through)
def audit_user_permission_changes(sender, instance, action, pk_set, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    permission_codenames = []
    if pk_set:
        permission_codenames = list(
            Permission.objects.filter(pk__in=pk_set).values_list("codename", flat=True)
        )

    log_security_event(
        "auth.privilege.user_permissions_changed",
        outcome="changed",
        target=instance,
        details={
            "action": action,
            "permission_codenames": sorted(permission_codenames),
        },
    )


@receiver(m2m_changed, sender=Group.permissions.through)
def audit_group_permission_changes(sender, instance, action, pk_set, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    permission_codenames = []
    if pk_set:
        permission_codenames = list(
            Permission.objects.filter(pk__in=pk_set).values_list("codename", flat=True)
        )

    log_security_event(
        "auth.privilege.group_permissions_changed",
        outcome="changed",
        details={
            "action": action,
            "group_name": instance.name,
            "permission_codenames": sorted(permission_codenames),
        },
    )
