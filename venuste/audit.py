import hashlib
import json
import logging

from django.utils import timezone

AUDIT_LOGGER = logging.getLogger("venuste.security")


def _client_ip(request):
    if request is None:
        return ""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _request_snapshot(request):
    if request is None:
        return {}
    return {
        "method": request.method,
        "path": request.path,
        "ip": _client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
    }


def _user_snapshot(user):
    if not user:
        return {}
    return {
        "id": getattr(user, "pk", None),
        "username": getattr(user, "get_username", lambda: "")(),
        "is_authenticated": bool(getattr(user, "is_authenticated", False)),
    }


def fingerprint(value):
    if not value:
        return ""
    normalized = str(value).strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:12]


def log_security_event(event, outcome="success", request=None, actor=None, target=None, details=None):
    payload = {
        "timestamp": timezone.now().isoformat(),
        "event": event,
        "outcome": outcome,
        "request": _request_snapshot(request),
        "actor": _user_snapshot(actor),
        "target": _user_snapshot(target),
        "details": details or {},
    }
    AUDIT_LOGGER.info(json.dumps(payload, sort_keys=True))
