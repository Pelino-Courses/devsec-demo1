from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone


class LoginThrottle:
    def __init__(self, request, username):
        self.request = request
        self.username = self._normalize_username(username)
        self.ip_address = self._get_client_ip(request)

    @staticmethod
    def _normalize_username(username):
        return (username or "").strip().lower() or "__empty__"

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
        return request.META.get("REMOTE_ADDR", "unknown")

    @property
    def account_key(self):
        return f"login-throttle:account:{self.username}"

    @property
    def ip_key(self):
        return f"login-throttle:ip:{self.ip_address}"

    @property
    def failure_limit(self):
        return getattr(settings, "LOGIN_THROTTLE_FAILURE_LIMIT", 5)

    @property
    def lockout_seconds(self):
        return getattr(settings, "LOGIN_THROTTLE_LOCKOUT_SECONDS", 15 * 60)

    @property
    def lockout_delta(self):
        return timedelta(seconds=self.lockout_seconds)

    @property
    def lockout_message(self):
        minutes = max(1, self.lockout_seconds // 60)
        suffix = "minute" if minutes == 1 else "minutes"
        return (
            "Too many failed login attempts. "
            f"Try again in {minutes} {suffix}."
        )

    def _empty_state(self):
        return {"failures": 0, "locked_until": None}

    def _load_state(self, key):
        state = cache.get(key) or self._empty_state()
        locked_until = state.get("locked_until")
        if locked_until and locked_until <= timezone.now():
            cache.delete(key)
            return self._empty_state()
        return {
            "failures": int(state.get("failures", 0)),
            "locked_until": locked_until,
        }

    def _save_state(self, key, failures, locked_until):
        cache.set(
            key,
            {"failures": failures, "locked_until": locked_until},
            timeout=self.lockout_seconds,
        )

    def _is_locked(self, state):
        locked_until = state["locked_until"]
        return bool(locked_until and locked_until > timezone.now())

    def _state_for(self, key):
        return self._load_state(key)

    def ensure_allowed(self):
        account_state = self._state_for(self.account_key)
        ip_state = self._state_for(self.ip_key)
        if self._is_locked(account_state) or self._is_locked(ip_state):
            raise ValidationError(self.lockout_message)

    def record_failure(self):
        self._increment(self.account_key)
        self._increment(self.ip_key)

    def record_success(self):
        cache.delete(self.account_key)
        cache.delete(self.ip_key)

    def _increment(self, key):
        state = self._state_for(key)
        if self._is_locked(state):
            return

        failures = state["failures"] + 1
        if failures >= self.failure_limit:
            self._save_state(key, self.failure_limit, timezone.now() + self.lockout_delta)
            return

        self._save_state(key, failures, None)
