"""Локальное хранилище проектов и настроек (JSON-файлы в каталоге data/).

Настройки содержат секреты (токены, пароли), поэтому:
- наружу (в браузер) отдаётся только masked_settings() — без секретов, с флагами наличия;
- при сохранении пустые поля НЕ затирают уже сохранённые секреты (merge);
- каталог data/ в .gitignore.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROJECTS_FILE = DATA_DIR / "projects.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

_CF_SECRET_KEYS = ("api_token", "account_id", "spaceship_api_key", "spaceship_api_secret")

_lock = threading.Lock()


def _read(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default
    return default


def _write(path, data):
    DATA_DIR.mkdir(exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_projects():
    with _lock:
        return _read(PROJECTS_FILE, [])


def save_projects(projects):
    with _lock:
        _write(PROJECTS_FILE, projects)


def load_settings():
    with _lock:
        return _read(SETTINGS_FILE, {})


def _clean(value):
    return value.strip() if isinstance(value, str) else value


def _merge_settings(current, incoming):
    """Сливает настройки: непустые значения перезаписывают, пустые — не трогают."""
    out = dict(current)

    for key in ("server_ip", "yandex_token"):
        if key in incoming and _clean(incoming[key]):
            out[key] = _clean(incoming[key])

    if "ssh" in incoming:
        ssh = dict(out.get("ssh") or {})
        for key, value in (incoming["ssh"] or {}).items():
            value = _clean(value)
            if value not in ("", None):
                ssh[key] = value
        out["ssh"] = ssh

    if "cf_accounts" in incoming:
        existing = {a.get("name"): a for a in (out.get("cf_accounts") or [])}
        result = []
        for acc in incoming["cf_accounts"] or []:
            name = _clean(acc.get("name") or "")
            if not name:
                continue
            merged = dict(existing.get(name, {}))
            merged["name"] = name
            for key in _CF_SECRET_KEYS:
                value = _clean(acc.get(key) or "")
                if value:
                    merged[key] = value
                else:
                    merged.setdefault(key, "")
            result.append(merged)
        out["cf_accounts"] = result

    return out


def save_settings(incoming):
    with _lock:
        merged = _merge_settings(_read(SETTINGS_FILE, {}), incoming)
        _write(SETTINGS_FILE, merged)
    return merged


# --- типизированный доступ (для backend, с секретами) ---
def get_cf_account(name):
    for acc in load_settings().get("cf_accounts", []):
        if acc.get("name") == name:
            return acc
    return None


def get_ssh():
    return load_settings().get("ssh", {})


def get_yandex_token():
    return load_settings().get("yandex_token") or os.environ.get("YANDEX_OAUTH_TOKEN")


def get_server_ip():
    return load_settings().get("server_ip") or "5.45.75.15"


# --- безопасное представление для браузера (без секретов) ---
def masked_settings():
    s = load_settings()
    accounts = [{
        "name": a.get("name", ""),
        "has_token": bool(a.get("api_token")),
        "has_account_id": bool(a.get("account_id")),
        "has_spaceship": bool(a.get("spaceship_api_key") and a.get("spaceship_api_secret")),
    } for a in s.get("cf_accounts", [])]
    ssh = s.get("ssh", {})
    return {
        "cf_accounts": accounts,
        "account_names": [a.get("name", "") for a in s.get("cf_accounts", [])],
        "ssh": {
            "host": ssh.get("host", ""),
            "port": ssh.get("port", 22),
            "user": ssh.get("user", ""),
            "ispmgr_user": ssh.get("ispmgr_user", ""),
            "ispmgr_host": ssh.get("ispmgr_host", ""),
            "email": ssh.get("email", ""),
            "has_password": bool(ssh.get("password")),
            "has_ispmgr_password": bool(ssh.get("ispmgr_password")),
        },
        "has_yandex_token": bool(get_yandex_token()),
        "server_ip": get_server_ip(),
    }
