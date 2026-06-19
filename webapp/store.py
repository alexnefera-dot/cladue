"""Локальное хранилище проектов и токенов (JSON-файлы в каталоге data/).

Токены берутся из data/settings.json, а если там пусто — из переменных окружения
и файла .env (для совместимости с CLI). Каталог data/ добавлен в .gitignore.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from migrator.config import load_env

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROJECTS_FILE = DATA_DIR / "projects.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

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
    tmp.replace(path)  # атомарная замена


def load_projects():
    with _lock:
        return _read(PROJECTS_FILE, [])


def save_projects(projects):
    with _lock:
        _write(PROJECTS_FILE, projects)


def load_settings():
    with _lock:
        return _read(SETTINGS_FILE, {})


def save_settings(values):
    """Сохраняет непустые токены, не затирая уже сохранённые пустыми значениями."""
    with _lock:
        current = _read(SETTINGS_FILE, {})
        current.update({k: v for k, v in values.items() if v})
        _write(SETTINGS_FILE, current)


def get_tokens():
    """Возвращает (cloudflare_token, yandex_token) из настроек, окружения или .env."""
    settings = load_settings()
    cf = settings.get("cloudflare_token") or os.environ.get("CLOUDFLARE_API_TOKEN")
    ya = settings.get("yandex_token") or os.environ.get("YANDEX_OAUTH_TOKEN")
    if not (cf and ya):
        load_env()
        cf = cf or os.environ.get("CLOUDFLARE_API_TOKEN")
        ya = ya or os.environ.get("YANDEX_OAUTH_TOKEN")
    return cf, ya
