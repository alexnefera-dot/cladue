"""Бизнес-действия приложения поверх пакета migrator.

Каждая функция получает «проект» (dict из фронтенда) и возвращает данные для UI.
Клиенты создаются на каждый вызов — они без состояния (хранят только токен).
"""

from __future__ import annotations

from migrator.cloudflare import Cloudflare
from migrator.domains import apex, normalize_domain, redirect_hosts
from migrator.http import ApiError
from migrator.yandex import Yandex

from . import store

VERIFY_TYPES = {"dns": "DNS_RECORD", "html": "HTML_FILE", "meta": "META_TAG"}


class ConfigError(Exception):
    """Не хватает токена для операции."""


def _clients(need_yandex=False):
    cf_token, ya_token = store.get_tokens()
    if not cf_token:
        raise ConfigError("Не задан токен Cloudflare. Откройте «Токены» и впишите его.")
    if need_yandex and not ya_token:
        raise ConfigError("Не задан токен Яндекса. Откройте «Токены» и впишите его.")
    return Cloudflare(cf_token), (Yandex(ya_token) if ya_token else None)


def _mirrors(project):
    seen, result = set(), []
    for raw in project.get("mirrors", []):
        domain = normalize_domain(raw)
        if domain and domain not in seen:
            seen.add(domain)
            result.append(domain)
    return result


def check_project(project):
    """Read-only статус: есть ли зона у каждого зеркала и куда стоит редирект."""
    cf, _ = _clients()
    new = normalize_domain(project.get("new_domain", ""))
    target = f"https://{new}" if new else ""
    out = {"new_domain": new, "new_in_cf": False, "mirrors": []}
    if new:
        out["new_in_cf"] = bool(cf.get_zone_id(apex(new)))
    for domain in _mirrors(project):
        row = {"domain": domain, "zone": False, "redirect": None, "ok": False}
        try:
            zone = cf.get_zone_id(apex(domain))
            row["zone"] = bool(zone)
            if zone:
                row["redirect"] = cf.find_redirect(zone, apex(domain))
                row["ok"] = bool(target) and row["redirect"] == target
        except ApiError as exc:
            row["error"] = str(exc)
        out["mirrors"].append(row)
    return out


def migrate_project(project, status_code=301):
    """Ставит/обновляет 301-редирект всех зеркал проекта на новый домен."""
    cf, _ = _clients()
    new = normalize_domain(project.get("new_domain", ""))
    if not new:
        raise ConfigError("Укажите новый (актуальный) домен.")
    target = f"https://{new}"
    results = []
    for domain in _mirrors(project):
        row = {"domain": domain, "ok": False}
        try:
            zone = cf.get_zone_id(apex(domain))
            if not zone:
                row["message"] = "нет зоны в Cloudflare"
            else:
                hosts = redirect_hosts(domain)
                for host in hosts:
                    cf.ensure_proxied_placeholder(zone, host)
                cf.set_redirect(zone, hosts, target, status_code)
                row["ok"] = True
                row["message"] = f"301 → {target}"
        except ApiError as exc:
            row["message"] = str(exc)
        results.append(row)
    return {"new_domain": new, "results": results}


def yandex_prepare(project):
    """Добавляет новый домен в Вебмастер и возвращает данные для подтверждения прав."""
    cf, ya = _clients(need_yandex=True)
    new = normalize_domain(project.get("new_domain", ""))
    if not new:
        raise ConfigError("Укажите новый (актуальный) домен.")
    user_id = ya.get_user_id()
    host_id = ya.add_host(user_id, f"https://{new}:443", new)
    info = ya.get_verification(user_id, host_id)
    uin = info.get("verification_uin")
    methods = {}
    if uin:
        methods = {
            "dns": {"name": new, "content": f"yandex-verification: {uin}"},
            "html": {
                "filename": f"yandex_{uin}.html",
                "content": (f'<html><head><meta name="yandex-verification" '
                            f'content="{uin}" /></head><body>Verification: {uin}'
                            f"</body></html>"),
                "url": f"https://{new}/yandex_{uin}.html",
            },
            "meta": {"tag": f'<meta name="yandex-verification" content="{uin}" />'},
        }
    return {"new_domain": new, "host_id": host_id, "uin": uin,
            "state": info.get("verification_state"), "methods": methods,
            "new_in_cf": bool(cf.get_zone_id(apex(new)))}


def yandex_verify(project, method="dns", timeout=180):
    """Запускает проверку прав (для DNS сам кладёт TXT в Cloudflare) и ждёт результат."""
    cf, ya = _clients(need_yandex=True)
    new = normalize_domain(project.get("new_domain", ""))
    if not new:
        raise ConfigError("Укажите новый (актуальный) домен.")
    user_id = ya.get_user_id()
    host_id = ya.add_host(user_id, f"https://{new}:443", new)
    info = ya.get_verification(user_id, host_id)
    if info.get("verification_state") == "VERIFIED":
        return {"state": "VERIFIED", "host_id": host_id}
    uin = info.get("verification_uin")
    if not uin:
        return {"state": "ERROR", "message": "Яндекс не вернул код подтверждения."}

    if method == "dns":
        zone = cf.get_zone_id(apex(new))
        if not zone:
            return {"state": "ERROR",
                    "message": "Новый домен не в Cloudflare — DNS-проверка невозможна. "
                               "Выберите способ HTML или мета-тег."}
        cf.upsert_txt(zone, new, f"yandex-verification: {uin}")

    ya.start_verification(user_id, host_id, VERIFY_TYPES[method])
    ok = ya.wait_verified(user_id, host_id, timeout=timeout, interval=10)
    return {"state": "VERIFIED" if ok else "PENDING", "host_id": host_id}
