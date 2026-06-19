"""Утилиты нормализации доменов (общие для CLI и веб-приложения)."""

from __future__ import annotations


def normalize_domain(value):
    """Голый домен: без схемы и без пути. Префикс www сохраняется как есть."""
    value = (value or "").strip().lower()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.rstrip("/").split("/")[0]


def apex(domain):
    """Домен без префикса www (для поиска зоны Cloudflare)."""
    return domain[4:] if domain.startswith("www.") else domain


def redirect_hosts(domain):
    """Хосты, которые должны редиректиться: домен и его www-версия."""
    base = apex(domain)
    return [base, f"www.{base}"]
