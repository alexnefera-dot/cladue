"""Оркестрация шагов переезда поверх интеграционного слоя migrator/.

Каждый шаг — отдельная функция (можно запускать по одному для отладки/повторов),
плюс составной run_full(). Все поддерживают dry_run. Клиенты создаются на вызов.
"""

from __future__ import annotations

from migrator.cloudflare import Cloudflare
from migrator.domains import apex, normalize_domain
from migrator.http import ApiError
from migrator.ispmanager import IspError, IspManager
from migrator.spaceship import Spaceship
from migrator.yandex import Yandex

from . import store

VERIFY_TYPES = {"dns": "DNS_RECORD", "html": "HTML_FILE", "meta": "META_TAG"}

# Настройки зоны при онбординге нового домена (как у исполнителя).
ZONE_SETTINGS = [
    ("ssl", "full"),
    ("always_use_https", "on"),
    ("tls_1_3", "off"),
    ("automatic_https_rewrites", "on"),
]


class ConfigError(Exception):
    """Не хватает настройки/данных проекта для шага."""


# ----------------------------- фабрики клиентов ----------------------------- #
def _cf(account_name):
    if not account_name:
        raise ConfigError("Не выбран CF-аккаунт.")
    acc = store.get_cf_account(account_name)
    if not acc or not acc.get("api_token"):
        raise ConfigError(f"Для аккаунта «{account_name}» не задан токен Cloudflare (см. Настройки).")
    return Cloudflare(acc["api_token"]), acc


def _spaceship(account_name):
    acc = store.get_cf_account(account_name) or {}
    if acc.get("spaceship_api_key") and acc.get("spaceship_api_secret"):
        return Spaceship(acc["spaceship_api_key"], acc["spaceship_api_secret"])
    return None


def _isp():
    s = store.get_ssh()
    missing = [k for k in ("host", "user", "password") if not s.get(k)]
    if missing:
        raise ConfigError("Не заданы SSH-доступы: " + ", ".join(missing) + " (см. Настройки).")
    return IspManager(
        host=s["host"], port=int(s.get("port") or 22),
        user=s["user"], password=s["password"],
        ispmgr_user=s.get("ispmgr_user") or s["user"],
        ispmgr_password=s.get("ispmgr_password") or s["password"],
        ispmgr_host=s.get("ispmgr_host") or "localhost",
    )


def _yandex():
    token = store.get_yandex_token()
    if not token:
        raise ConfigError("Не задан OAuth-токен Яндекса (см. Настройки).")
    return Yandex(token)


# ----------------------------------- helpers -------------------------------- #
def _new_domain(project):
    domain = normalize_domain(project.get("new_domain", ""))
    if not domain:
        raise ConfigError("Укажите новый домен в проекте.")
    return domain


def _mirrors(project):
    out = []
    for m in project.get("mirrors", []):
        if isinstance(m, str):
            m = {"domain": m, "account": ""}
        domain = normalize_domain(m.get("domain", ""))
        if domain:
            out.append({"domain": domain, "account": m.get("account", "")})
    return out


# ------------------------------- шаги нового домена ------------------------- #
def create_isp_site(project, dry_run=False):
    new = _new_domain(project)
    if dry_run:
        return {"ok": True, "message": f"DRY: создать сайт {new} в ISPmanager"}
    isp = _isp()
    isp.connect()
    try:
        msg = isp.create_webdomain(new, email=store.get_ssh().get("email", ""))
        docroot = isp.get_docroot(new)
        return {"ok": True, "message": f"{msg}; docroot={docroot}", "docroot": docroot}
    finally:
        isp.disconnect()


def copy_files(project, dry_run=False):
    new = _new_domain(project)
    donor = normalize_domain(project.get("donor_domain", ""))
    if not donor:
        raise ConfigError("Укажите домен-донор (откуда копировать файлы) в проекте.")
    if dry_run:
        return {"ok": True, "message": f"DRY: копировать {donor} → {new}, заменить {donor}→{new} в robots/sitemap/.htaccess"}
    isp = _isp()
    isp.connect()
    try:
        src = isp.get_docroot(donor)
        dst = isp.get_docroot(new)
        if not src:
            raise ConfigError(f"Сайт-донор {donor} не найден в ISPmanager.")
        if not dst:
            raise ConfigError(f"Сайт {new} не найден в ISPmanager — сначала создайте сайт.")
        isp.copy_site_files(src, dst)
        replaced = isp.replace_domain_in_files(dst, donor, new)
        changed = [f for f, st in replaced.items() if st == "changed"]
        return {"ok": True, "message": f"скопировано {donor} → {new}; домен заменён в: {', '.join(changed) or '—'}"}
    finally:
        isp.disconnect()


def cf_onboard(project, dry_run=False):
    new = _new_domain(project)
    account = project.get("new_account", "")
    server_ip = store.get_server_ip()
    if dry_run:
        return {"ok": True, "message": f"DRY: зона {new} в «{account}», A @/www→{server_ip}, SSL/HTTPS, NS→Spaceship"}
    cf, acc = _cf(account)
    account_id = acc.get("account_id")
    if not account_id:
        raise ConfigError(f"Для аккаунта «{account}» не задан account_id (см. Настройки).")
    zone_id = cf.create_zone(new, account_id)
    done = ["зона"]
    for name in ("@", "www"):
        try:
            cf.create_dns(zone_id, "A", name, server_ip, proxied=True)
        except ApiError:
            pass  # запись уже могла существовать
    done.append("DNS")
    for setting, value in ZONE_SETTINGS:
        try:
            cf.patch_setting(zone_id, setting, value)
        except ApiError:
            pass
    try:
        cf.patch_bot_management(zone_id, ai_bots_protection="disabled")
    except ApiError:
        pass
    done.append("настройки")
    ns = cf.get_nameservers(zone_id)
    sp = _spaceship(account)
    if sp and ns:
        try:
            sp.update_nameservers(new, ns)
            ns_msg = "NS→Spaceship ✓"
        except ApiError as exc:
            ns_msg = f"NS вручную ({', '.join(ns)}): {exc}"
    elif ns:
        ns_msg = f"Spaceship не настроен, NS вручную: {', '.join(ns)}"
    else:
        ns_msg = "NS не получены"
    return {"ok": True, "message": f"{new}: {', '.join(done)}; {ns_msg}", "zone_id": zone_id, "nameservers": ns}


def issue_ssl(project, dry_run=False):
    new = _new_domain(project)
    if dry_run:
        return {"ok": True, "message": f"DRY: выпустить Let's Encrypt для {new}"}
    isp = _isp()
    isp.connect()
    try:
        ok, detail = isp.issue_letsencrypt(new, store.get_ssh().get("email", ""))
        return {"ok": ok, "message": detail}
    finally:
        isp.disconnect()


def bind_worker(project, dry_run=False):
    new = _new_domain(project)
    account = project.get("new_account", "")
    worker = (project.get("worker") or "").strip()
    if not worker:
        raise ConfigError("Укажите имя воркера в проекте.")
    pattern = f"{new}/*"
    if dry_run:
        return {"ok": True, "message": f"DRY: воркер {worker} → {pattern}"}
    cf, _ = _cf(account)
    zone_id = cf.get_zone_id(new)
    if not zone_id:
        raise ConfigError(f"Зона {new} не найдена в «{account}» — сначала онбординг.")
    status = cf.add_worker_route(zone_id, pattern, worker)
    return {"ok": True, "message": f"воркер {worker} → {pattern}: {status}"}


def run_full(project, dry_run=False):
    """Поднять новый домен: сайт → файлы → Cloudflare → SSL → воркер."""
    steps = [
        ("Сайт в ISPmanager", create_isp_site),
        ("Копирование файлов", copy_files),
        ("Cloudflare онбординг", cf_onboard),
        ("SSL (Let's Encrypt)", issue_ssl),
        ("Воркер-роут", bind_worker),
    ]
    results = []
    for label, fn in steps:
        try:
            r = fn(project, dry_run=dry_run)
            results.append({"step": label, "ok": bool(r.get("ok", True)), "message": r.get("message", "")})
        except (ConfigError, IspError, ApiError) as exc:
            results.append({"step": label, "ok": False, "message": str(exc)})
    return {"results": results}


# ------------------------------- переезд зеркал ----------------------------- #
def migrate_mirrors(project, dry_run=False, status_code=301):
    new = _new_domain(project)
    mirrors = _mirrors(project)
    if not mirrors:
        raise ConfigError("Добавьте старые зеркала в проект.")
    results = []
    clients = {}
    for m in mirrors:
        row = {"domain": m["domain"], "account": m["account"], "ok": False}
        account = m["account"]
        try:
            if not account:
                raise ConfigError("не выбран CF-аккаунт зеркала")
            if account not in clients:
                clients[account] = _cf(account)[0]
            cf = clients[account]
            if dry_run:
                row["ok"] = True
                row["message"] = f"DRY: redirect-all → https://{new}"
            else:
                zone_id = cf.get_zone_id(apex(m["domain"]))
                if not zone_id:
                    row["message"] = "зона не найдена в CF"
                else:
                    cf.upsert_redirect_all(zone_id, new, status_code)
                    row["ok"] = True
                    row["message"] = f"301 → https://{new}"
        except (ConfigError, ApiError) as exc:
            row["message"] = str(exc)
        results.append(row)
    return {"new_domain": new, "results": results}


# ---------------------------------- статус ---------------------------------- #
def check_status(project):
    new = _new_domain(project)
    target = f"https://{new}"
    out = {"new_domain": new, "new_in_cf": False, "mirrors": []}
    account = project.get("new_account", "")
    if account and store.get_cf_account(account):
        try:
            cf, _ = _cf(account)
            out["new_in_cf"] = bool(cf.get_zone_id(apex(new)))
        except (ApiError, ConfigError):
            pass
    clients = {}
    for m in _mirrors(project):
        row = {"domain": m["domain"], "account": m["account"], "zone": False, "redirect": None, "ok": False}
        account = m["account"]
        if account and store.get_cf_account(account):
            try:
                if account not in clients:
                    clients[account] = _cf(account)[0]
                cf = clients[account]
                zone_id = cf.get_zone_id(apex(m["domain"]))
                row["zone"] = bool(zone_id)
                if zone_id:
                    row["redirect"] = cf.find_redirect(zone_id)
                    row["ok"] = row["redirect"] == target
            except (ApiError, ConfigError) as exc:
                row["error"] = str(exc)
        else:
            row["error"] = "нет CF-аккаунта"
        out["mirrors"].append(row)
    return out


# ----------------------------------- Яндекс --------------------------------- #
def yandex_prepare(project):
    new = _new_domain(project)
    ya = _yandex()
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
                "content": (f'<html><head><meta name="yandex-verification" content="{uin}" />'
                            f"</head><body>Verification: {uin}</body></html>"),
                "url": f"https://{new}/yandex_{uin}.html",
            },
            "meta": {"tag": f'<meta name="yandex-verification" content="{uin}" />'},
        }
    return {"new_domain": new, "host_id": host_id, "uin": uin,
            "state": info.get("verification_state"), "methods": methods}


def yandex_verify(project, method="dns", timeout=180):
    new = _new_domain(project)
    ya = _yandex()
    user_id = ya.get_user_id()
    host_id = ya.add_host(user_id, f"https://{new}:443", new)
    info = ya.get_verification(user_id, host_id)
    if info.get("verification_state") == "VERIFIED":
        return {"state": "VERIFIED"}
    uin = info.get("verification_uin")
    if not uin:
        return {"state": "ERROR", "message": "Яндекс не вернул код подтверждения."}
    if method == "dns":
        cf, _ = _cf(project.get("new_account", ""))
        zone_id = cf.get_zone_id(apex(new))
        if not zone_id:
            return {"state": "ERROR", "message": "Новый домен не в Cloudflare — DNS-проверка невозможна (выберите HTML/мета)."}
        cf.upsert_txt(zone_id, new, f"yandex-verification: {uin}")
    ya.start_verification(user_id, host_id, VERIFY_TYPES[method])
    ok = ya.wait_verified(user_id, host_id, timeout=timeout, interval=10)
    return {"state": "VERIFIED" if ok else "PENDING"}
