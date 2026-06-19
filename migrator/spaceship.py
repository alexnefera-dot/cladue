"""Клиент Spaceship API: обновление NS-серверов домена у регистратора."""

from __future__ import annotations

from . import http
from .http import ApiError


class Spaceship:
    BASE = "https://spaceship.dev/api/v1"

    def __init__(self, api_key, api_secret):
        self._headers = {"X-API-Key": api_key, "X-API-Secret": api_secret}

    def update_nameservers(self, domain, nameservers):
        """Прописывает домену кастомные NS (NS-серверы Cloudflare)."""
        status, body = http.request(
            "PUT", f"{self.BASE}/domains/{domain}/nameservers",
            headers=self._headers,
            json_body={"provider": "custom", "hosts": list(nameservers)},
        )
        if not 200 <= status < 300:
            raise ApiError(f"Spaceship PUT nameservers → HTTP {status}: {body}", status, body)
        return True
