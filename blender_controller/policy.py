"""Pure capability policy. No network listener, no unattended permission."""
from __future__ import annotations
from dataclasses import dataclass
import secrets
import time


@dataclass(frozen=True)
class ViewGrant:
    token: str
    hwnd: int
    pid: int
    expires: float


class ViewGrants:
    def __init__(self, now=None, ttl=120.0, minimum_interval=0.50):
        self.now = now or time.monotonic
        self.ttl = min(float(ttl), 120.0)
        self.minimum_interval = float(minimum_interval)
        self._current = None
        self._last_capture = float("-inf")

    def issue(self, hwnd: int, pid: int) -> ViewGrant:
        if not isinstance(hwnd, int) or hwnd < 1 or not isinstance(pid, int) or pid < 1:
            raise ValueError("Invalid Blender window")
        grant = ViewGrant(secrets.token_urlsafe(32), hwnd, pid, self.now() + self.ttl)
        self._current = grant
        self._last_capture = float("-inf")
        return grant

    def check(self, token: str, hwnd: int, pid: int, *, capture=False) -> None:
        g = self._current
        if (g is None or not isinstance(token, str) or
                not secrets.compare_digest(g.token, token) or
                hwnd != g.hwnd or pid != g.pid or self.now() >= g.expires):
            raise PermissionError("No valid attended view grant for this Blender window")
        if capture:
            now = self.now()
            if now - self._last_capture < self.minimum_interval:
                raise PermissionError("Capture rate limit")
            self._last_capture = now

    def revoke(self, token: str) -> None:
        g = self._current
        if g is not None and isinstance(token, str) and secrets.compare_digest(g.token, token):
            self._current = None
            return
        raise PermissionError("Invalid view grant")
