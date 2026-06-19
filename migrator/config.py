"""Загрузка конфигурации из переменных окружения и файла .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path=".env"):
    """Подгружает переменные из .env в окружение (уже заданные не перезаписывает)."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Config:
    cloudflare_token: str
    yandex_token: str

    @classmethod
    def from_env(cls):
        load_env()
        cf = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        ya = os.environ.get("YANDEX_OAUTH_TOKEN", "").strip()
        missing = [name for name, val in
                   (("CLOUDFLARE_API_TOKEN", cf), ("YANDEX_OAUTH_TOKEN", ya)) if not val]
        if missing:
            raise SystemExit(
                "Не заданы переменные окружения: " + ", ".join(missing) + ".\n"
                "Скопируйте .env.example в .env и впишите токены (см. README.md)."
            )
        return cls(cloudflare_token=cf, yandex_token=ya)
