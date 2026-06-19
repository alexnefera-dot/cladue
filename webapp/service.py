"""Оркестрация шагов переезда поверх интеграционного слоя migrator/.

Каждый шаг — отдельная функция (можно запускать по одному для отладки/повторов),
плюс составной run_full(). Все поддерживают dry_run. Клиенты создаются на вызов.
"""

from __future__ import annotations

import csv
import io

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


def _yandex(project=None):
    """Токен Яндекса: сперва аккаунт вкладки, иначе общий из Настроек."""
    token = None
    if project and project.get("yandex_account"):
        token = store.get_yandex_account(project["yandex_account"])
    if not token:
        token = store.get_yandex_token()
    if not token:
        raise ConfigError("Не задан токен Яндекса (Настройки → Яндекс-аккаунты или общий токен).")
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


# ---------------------------------- импорт из CSV --------------------------- #
def _acc(name):
    """Имя CF-аккаунта из CSV: кириллическая с (U+0441) → латинская c."""
    return (name or "").strip().replace("с", "c")


def _project_from(target, mirrors, new_account, prev):
    return {
        "id": prev.get("id") if prev else "p_" + target.replace(".", "_"),
        "name": prev.get("name") if prev else target.split(".")[0],
        "new_domain": target,
        "new_account": (prev.get("new_account") if prev else "") or new_account,
        "worker": prev.get("worker", "") if prev else "",
        "donor_domain": prev.get("donor_domain", "") if prev else "",
        "verify": prev.get("verify", "dns") if prev else "dns",
        "mirrors": mirrors,
    }


def import_from_csv(csv_text, existing_projects=None):
    """Строит проекты из domains.csv (колонки Домен; Профиль; Целевой домен; Новый домен).

    Группирует по «Целевой домен»: зеркала = «Домен» каждой строки, новый домен = цель.
    Для уже существующих проектов сохраняет воркер/донор/имя.
    """
    text = (csv_text or "").lstrip("﻿")
    if not text.strip():
        raise ConfigError("Пустой CSV.")
    sample = text[:4096]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample.splitlines() else ""
        delim = ";" if first.count(";") >= first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    cols = {(c or "").strip(): c for c in (reader.fieldnames or [])}
    if "Домен" not in cols or "Целевой домен" not in cols:
        raise ConfigError("Нужны колонки «Домен» и «Целевой домен» (как в domains.csv).")

    def cell(row, name):
        key = cols.get(name)
        return (row.get(key, "") or "").strip() if key else ""

    existing = {normalize_domain(p.get("new_domain", "")): p
                for p in (existing_projects or []) if p.get("new_domain")}
    groups, seen = {}, {}
    new_account_by_target = {}
    for row in reader:
        target = normalize_domain(cell(row, "Целевой домен"))
        mirror = normalize_domain(cell(row, "Домен"))
        account = _acc(cell(row, "Профиль"))
        if not target or not mirror:
            continue
        key = (target, mirror)
        if key in seen:
            continue
        seen[key] = True
        groups.setdefault(target, []).append({"domain": mirror, "account": account})
        new_dom = normalize_domain(cell(row, "Новый домен"))
        if new_dom == target and target not in new_account_by_target:
            new_account_by_target[target] = account

    projects = [
        _project_from(target, mirrors, new_account_by_target.get(target, ""), existing.get(target))
        for target, mirrors in sorted(groups.items())
    ]
    return {"projects": projects,
            "summary": f"проектов: {len(projects)}, зеркал: {sum(len(p['mirrors']) for p in projects)}"}


_FIELD_SYNONYMS = {
    "Домен": ["домен", "зеркало", "зеркала", "старое зеркало", "старый домен", "старые зеркала"],
    "Профиль": ["профиль", "аккаунт", "cf-аккаунт", "cf аккаунт", "cloudflare"],
    "Целевой домен": ["целевой домен", "целевой", "актуальный", "актуальный домен",
                       "рабочий", "рабочий домен", "текущий", "текущий домен"],
    "Новый домен": ["новый домен"],
    "Вкладка": ["вкладка", "название вкладки", "название", "проект", "бренд"],
}
_HEADER_TO_FIELD = {syn: canon for canon, syns in _FIELD_SYNONYMS.items() for syn in syns}


def _canon_map(headers):
    """{оригинальный заголовок: каноническое поле} для известных синонимов."""
    out = {}
    for h in headers:
        field = _HEADER_TO_FIELD.get((h or "").strip().lower())
        if field:
            out[h] = field
    return out


def _summary(projects):
    return f"проектов: {len(projects)}, зеркал: {sum(len(p['mirrors']) for p in projects)}"


def _group_projects(records, existing_projects=None):
    """records: итерируемое из (row, source_name). Группирует по «Целевой домен»;
    source_name (имя листа) становится названием новой вкладки."""
    existing = {normalize_domain(p.get("new_domain", "")): p
                for p in (existing_projects or []) if p.get("new_domain")}
    groups, seen, new_account, source = {}, set(), {}, {}
    for row, src in records:
        target = normalize_domain((row.get("Целевой домен") or "").strip())
        mirror = normalize_domain((row.get("Домен") or "").strip())
        account = _acc((row.get("Профиль") or "").strip())
        tabname = (row.get("Вкладка") or "").strip()
        if not target or not mirror or (target, mirror) in seen:
            continue
        seen.add((target, mirror))
        groups.setdefault(target, []).append({"domain": mirror, "account": account})
        if (tabname or src) and target not in source:
            source[target] = tabname or src       # имя вкладки: колонка «Вкладка» → имя листа
        if normalize_domain((row.get("Новый домен") or "").strip()) == target and target not in new_account:
            new_account[target] = account
    projects = []
    for target, mirrors in sorted(groups.items()):
        prev = existing.get(target)
        project = _project_from(target, mirrors, new_account.get(target, ""), prev)
        if not prev and source.get(target):
            project["name"] = source[target]
        projects.append(project)
    return projects


def _csv_rows(text):
    """Строки CSV как список dict с каноническими ключами (синонимы заголовков понимаются)."""
    sample = text[:4096]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample.splitlines() else ""
        delim = ";" if first.count(";") >= first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    cmap = _canon_map([(c or "").strip() for c in (reader.fieldnames or [])])
    fields = set(cmap.values())
    if "Домен" not in fields or "Целевой домен" not in fields:
        raise ConfigError("Нужны колонки: зеркало (Домен/Зеркало) и рабочий домен (Целевой/Актуальный/Рабочий).")
    rows = []
    for row in reader:
        canon = {}
        for key, value in row.items():
            field = cmap.get((key or "").strip())
            if field:
                canon[field] = (value or "").strip()
        rows.append(canon)
    return rows


def _xlsx_records(data):
    """Из .xlsx: (row, имя_листа) по всем листам с нужными колонками (синонимы понимаются)."""
    import openpyxl  # ленивый импорт — нужен только при импорте xlsx

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            headers = cmap = None
            for raw in sheet.iter_rows(values_only=True):
                if headers is None:
                    headers = [(str(c).strip() if c is not None else "") for c in raw]
                    cmap = _canon_map(headers)
                    if "Домен" not in cmap.values() or "Целевой домен" not in cmap.values():
                        break  # лист не похож на список доменов — пропускаем
                    continue
                row = {}
                for i, h in enumerate(headers):
                    field = cmap.get(h)
                    if field:
                        val = raw[i] if i < len(raw) else None
                        row[field] = "" if val is None else str(val).strip()
                yield row, sheet.title
    finally:
        workbook.close()


def import_from_files(files, existing_projects=None):
    """Проекты из нескольких файлов: .csv/.txt и .xlsx (каждый лист = вкладка)."""
    import base64

    records = []
    for f in files or []:
        name = (f.get("name") or "").lower()
        try:
            data = base64.b64decode(f.get("b64") or "")
        except Exception:
            continue
        if name.endswith(".xlsx"):
            try:
                records.extend(_xlsx_records(data))
            except ImportError:
                raise ConfigError("Для .xlsx нужен openpyxl — выполни: pip install -r requirements.txt")
        else:
            text = data.decode("utf-8-sig", errors="replace").lstrip("﻿")
            try:
                records.extend((r, "") for r in _csv_rows(text))
            except ConfigError:
                continue  # файл без нужных колонок — пропускаем
    projects = _group_projects(records, existing_projects)
    return {"projects": projects, "summary": _summary(projects)}


# ------------------------------ импорт из Cloudflare ------------------------ #
def import_from_cloudflare(existing_projects=None):
    """Реконструирует проекты по всем CF-аккаунтам: какие зоны куда редиректят.

    Зона с действующим редиректом → зеркало; цель редиректа → новый домен проекта.
    Для уже существующих проектов (по новому домену) сохраняются воркер/донор/имя.
    """
    existing = {normalize_domain(p.get("new_domain", "")): p
                for p in (existing_projects or []) if p.get("new_domain")}
    accounts = [a for a in store.load_settings().get("cf_accounts", []) if a.get("api_token")]
    if not accounts:
        raise ConfigError("Нет CF-аккаунтов с токеном (см. Настройки).")

    mirrors_by_target = {}   # целевой домен -> [{domain, account}]
    zone_account = {}        # имя зоны -> аккаунт (где она найдена)
    scanned = 0
    for acc in accounts:
        cf = Cloudflare(acc["api_token"])
        for zone in cf.list_zones():
            scanned += 1
            zone_account.setdefault(zone["name"], acc["name"])
            try:
                target = cf.find_redirect(zone["id"])
            except ApiError:
                target = None
            if target:
                t = normalize_domain(target)
                if t and t != zone["name"]:
                    mirrors_by_target.setdefault(t, []).append(
                        {"domain": zone["name"], "account": acc["name"]})

    projects = [
        _project_from(target, mirrors, zone_account.get(target, ""), existing.get(target))
        for target, mirrors in sorted(mirrors_by_target.items())
    ]
    return {
        "projects": projects,
        "scanned": scanned,
        "summary": f"аккаунтов: {len(accounts)}, зон просканировано: {scanned}, проектов найдено: {len(projects)}",
    }


# ----------------------------------- Яндекс --------------------------------- #
def yandex_prepare(project):
    new = _new_domain(project)
    ya = _yandex(project)
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
    ya = _yandex(project)
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
