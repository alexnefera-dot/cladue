"""Клиент API Яндекс.Вебмастера: добавление хоста и подтверждение прав.

Шага «Переезд сайта» (смена главного зеркала) в API Вебмастера нет — он доступен
только в веб-интерфейсе, поэтому здесь не реализуется (см. README.md).
"""

from __future__ import annotations

import time

from . import http
from .http import ApiError


def _host_domain(host):
    """Извлекает голый домен из записи хоста Вебмастера."""
    url = host.get("unicode_host_url") or host.get("ascii_host_url") or ""
    url = url.replace("https://", "").replace("http://", "")
    return url.split(":")[0].strip("/").lower()


class Yandex:
    BASE = "https://api.webmaster.yandex.net/v4"

    def __init__(self, oauth_token):
        # Яндекс использует схему авторизации OAuth, а не Bearer.
        self._headers = {"Authorization": f"OAuth {oauth_token}"}

    def _req(self, method, path, params=None, json_body=None):
        status, body = http.request(
            method, self.BASE + path, headers=self._headers,
            params=params, json_body=json_body,
        )
        if 200 <= status < 300:
            return body
        raise ApiError(f"Yandex {method} {path} → HTTP {status}: {body}", status, body)

    def get_user_id(self):
        return self._req("GET", "/user")["user_id"]

    def find_host(self, user_id, domain):
        """Находит host_id по голому домену среди уже добавленных хостов."""
        hosts = self._req("GET", f"/user/{user_id}/hosts").get("hosts", [])
        for host in hosts:
            if _host_domain(host) == domain.lower():
                return host["host_id"]
        return None

    def add_host(self, user_id, host_url, domain):
        """Добавляет хост и возвращает host_id. Если хост уже есть — находит его."""
        try:
            return self._req("POST", f"/user/{user_id}/hosts",
                             json_body={"host_url": host_url})["host_id"]
        except ApiError as exc:
            if exc.status in (400, 409):
                found = self.find_host(user_id, domain)
                if found:
                    return found
            raise

    def get_verification(self, user_id, host_id):
        return self._req("GET", f"/user/{user_id}/hosts/{host_id}/verification")

    def start_verification(self, user_id, host_id, verification_type):
        return self._req("POST", f"/user/{user_id}/hosts/{host_id}/verification",
                         params={"verification_type": verification_type})

    def wait_verified(self, user_id, host_id, timeout=300, interval=15, on_poll=None):
        """Опрашивает статус, пока он не станет VERIFIED, не упадёт или не выйдет таймаут."""
        deadline = time.time() + timeout
        while True:
            state = self.get_verification(user_id, host_id).get("verification_state")
            if on_poll:
                on_poll(state)
            if state == "VERIFIED":
                return True
            if state in ("VERIFICATION_FAILED", "INTERNAL_ERROR"):
                return False
            if time.time() >= deadline:
                return False
            time.sleep(interval)
