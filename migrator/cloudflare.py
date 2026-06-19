"""Клиент Cloudflare API: зоны, DNS-записи и правила редиректа (Single Redirects)."""

from __future__ import annotations

from . import http
from .http import ApiError

MARKER = "[site-migrator]"
REDIRECT_PHASE = "http_request_dynamic_redirect"


class Cloudflare:
    BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self, token):
        self._headers = {"Authorization": f"Bearer {token}"}

    def _req(self, method, path, params=None, json_body=None, allow_404=False):
        """Запрос к API с разворачиванием обёртки Cloudflare {success, result, errors}."""
        status, body = http.request(
            method, self.BASE + path, headers=self._headers,
            params=params, json_body=json_body,
        )
        if status == 404 and allow_404:
            return None
        if isinstance(body, dict) and body.get("success"):
            return body.get("result")
        errors = body.get("errors") if isinstance(body, dict) else body
        raise ApiError(f"Cloudflare {method} {path} → HTTP {status}: {errors}", status, body)

    # --- зоны ---
    def get_zone_id(self, domain):
        """id зоны по имени домена или None, если зоны нет в аккаунте."""
        result = self._req("GET", "/zones", params={"name": domain})
        return result[0]["id"] if result else None

    # --- DNS-записи ---
    def list_dns(self, zone_id, type=None, name=None):
        return self._req("GET", f"/zones/{zone_id}/dns_records",
                         params={"type": type, "name": name, "per_page": 100}) or []

    def create_dns(self, zone_id, type, name, content, proxied=False, ttl=300):
        return self._req("POST", f"/zones/{zone_id}/dns_records", json_body={
            "type": type, "name": name, "content": content,
            "proxied": proxied, "ttl": 1 if proxied else ttl,
        })

    def ensure_proxied_placeholder(self, zone_id, hostname):
        """Гарантирует проксируемую запись, чтобы запросы к хосту шли через Cloudflare.

        Если у хоста уже есть проксируемая A/AAAA/CNAME-запись — не трогает её.
        Иначе создаёт AAAA на 100:: (зарезервированный «discard»-адрес: трафик до origin
        не доходит, его обрабатывает правило редиректа на edge Cloudflare).
        """
        for rec in self.list_dns(zone_id, name=hostname):
            if rec["type"] in ("A", "AAAA", "CNAME") and rec.get("proxied"):
                return False
        self.create_dns(zone_id, "AAAA", hostname, "100::", proxied=True)
        return True

    def upsert_txt(self, zone_id, name, content):
        """Создаёт TXT-запись, если такой ещё нет (идемпотентно)."""
        for rec in self.list_dns(zone_id, type="TXT", name=name):
            if rec.get("content", "").strip('"') == content:
                return False
        self.create_dns(zone_id, "TXT", name, content, proxied=False, ttl=300)
        return True

    # --- редирект (Single Redirect через Rulesets API) ---
    def set_redirect(self, zone_id, match_hosts, target_base, status_code=301):
        """Правило редиректа всех путей перечисленных хостов на target_base с сохранением пути.

        Идемпотентно: ранее созданное этим скриптом правило для тех же хостов заменяется.
        """
        host_expr = " or ".join(f'http.host eq "{h}"' for h in match_hosts)
        rule = {
            "expression": f"({host_expr})",
            "description": f"{MARKER} {' '.join(match_hosts)} -> {target_base}",
            "action": "redirect",
            "action_parameters": {
                "from_value": {
                    "status_code": status_code,
                    "target_url": {
                        "expression": f'concat("{target_base}", http.request.uri.path)'
                    },
                    "preserve_query_string": True,
                }
            },
        }

        entry = self._req(
            "GET", f"/zones/{zone_id}/rulesets/phases/{REDIRECT_PHASE}/entrypoint",
            allow_404=True,
        )
        if entry is None:
            # фазового ruleset ещё нет — создаём вместе с нашим правилом
            self._req("POST", f"/zones/{zone_id}/rulesets", json_body={
                "name": "default", "kind": "zone",
                "phase": REDIRECT_PHASE, "rules": [rule],
            })
            return

        ruleset_id = entry["id"]
        for existing in entry.get("rules", []) or []:
            desc = existing.get("description") or ""
            if MARKER in desc and any(h in desc for h in match_hosts):
                self._req("DELETE",
                          f"/zones/{zone_id}/rulesets/{ruleset_id}/rules/{existing['id']}")
        self._req("POST", f"/zones/{zone_id}/rulesets/{ruleset_id}/rules", json_body=rule)
