#!/usr/bin/env python3
"""Автоматизация переезда сайта на новый домен.

Один запуск делает три вещи:
  1. Cloudflare — ставит 301-редирект со старого домена (и www) на новый, с сохранением пути.
  2. Яндекс.Вебмастер — добавляет новый домен и подтверждает права (по умолчанию через DNS).
  3. Печатает, что осталось сделать вручную (шаг «Переезд» в Вебмастере — его нет в API).

Примеры:
    python migrate.py old-site.ru new-site.ru
    python migrate.py old-site.ru new-site.ru --verify html
    python migrate.py --batch domains.csv
"""

from __future__ import annotations

import argparse
import sys

from migrator.cloudflare import Cloudflare
from migrator.config import Config
from migrator.domains import apex, normalize_domain, redirect_hosts
from migrator.http import ApiError
from migrator.yandex import Yandex

VERIFY_TYPES = {"dns": "DNS_RECORD", "html": "HTML_FILE", "meta": "META_TAG"}


def place_proof(cf, new, kind, uin):
    """Размещает подтверждение прав: DNS — автоматически, html/meta — с подсказкой вручную."""
    if kind == "dns":
        zone = cf.get_zone_id(apex(new))
        if not zone:
            raise ApiError(
                f"Домен {new} не найден в Cloudflare — DNS-подтверждение невозможно.\n"
                f"  Вариант 1: добавьте {apex(new)} как сайт в Cloudflare и повторите запуск.\n"
                f"  Вариант 2: запустите с «--verify html» или «--verify meta»."
            )
        content = f"yandex-verification: {uin}"
        created = cf.upsert_txt(zone, new, content)
        print(f'[Cloudflare] TXT {new} = "{content}": '
              f"{'добавил' if created else 'уже есть'}")
    elif kind == "html":
        fname = f"yandex_{uin}.html"
        body = (f'<html><head><meta name="yandex-verification" content="{uin}" />'
                f'</head><body>Verification: {uin}</body></html>')
        print("\n  Загрузите в корень сайта на хостинге файл:")
        print(f"    Имя:        {fname}")
        print(f"    Содержимое: {body}")
        print(f"    Проверка:   https://{new}/{fname}")
        input("  Нажмите Enter, когда файл будет доступен… ")
    elif kind == "meta":
        print("\n  Добавьте в <head> главной страницы сайта метатег:")
        print(f'    <meta name="yandex-verification" content="{uin}" />')
        input("  Нажмите Enter, когда метатег будет опубликован… ")


def migrate_one(cf, ya, user_id, old, new, verify_kind, status_code, timeout):
    """Переносит один сайт old → new. Возвращает host_id в Вебмастере."""
    old, new = normalize_domain(old), normalize_domain(new)
    print(f"\n=== {old} → {new} ===")

    # 1) Cloudflare: редирект старого домена на новый
    old_zone = cf.get_zone_id(apex(old))
    if not old_zone:
        raise ApiError(f"Домен {old} не найден в Cloudflare. "
                       f"Сначала добавьте {apex(old)} как сайт в Cloudflare.")
    hosts = redirect_hosts(old)
    for host in hosts:
        created = cf.ensure_proxied_placeholder(old_zone, host)
        print(f"[Cloudflare] DNS {host}: "
              f"{'создал проксируемую запись' if created else 'уже настроен'}")
    cf.set_redirect(old_zone, hosts, f"https://{new}", status_code)
    print(f"[Cloudflare] {status_code}-редирект {', '.join(hosts)} → https://{new} готов")

    # 2) Яндекс: добавление и подтверждение прав на новый домен
    host_id = ya.add_host(user_id, f"https://{new}:443", new)
    print(f"[Яндекс] хост добавлен: {host_id}")

    info = ya.get_verification(user_id, host_id)
    if info.get("verification_state") == "VERIFIED":
        print("[Яндекс] права уже подтверждены ✓")
    else:
        uin = info.get("verification_uin")
        if not uin:
            raise ApiError("Яндекс не вернул verification_uin — проверьте права токена.")
        place_proof(cf, new, verify_kind, uin)
        ya.start_verification(user_id, host_id, VERIFY_TYPES[verify_kind])
        print(f"[Яндекс] запустил проверку ({VERIFY_TYPES[verify_kind]}), жду подтверждения…")
        ok = ya.wait_verified(user_id, host_id, timeout=timeout,
                              on_poll=lambda s: print(f"[Яндекс] статус: {s}"))
        if not ok:
            raise ApiError("Права не подтверждены (таймаут или ошибка). "
                           "Проверьте запись/файл и запустите скрипт ещё раз.")
        print("[Яндекс] права подтверждены ✓")

    # 3) Финальный шаг — только вручную (в API его нет)
    print(f"[Вручную] Вебмастер → сайт {new} → «Индексирование» → «Переезд сайта»: "
          f"укажите {new} главным зеркалом.")
    return host_id


def read_batch(path):
    """Читает CSV «old,new» (разделители , или ;). Пустые строки и # пропускаются."""
    pairs = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.replace(";", ",").split(",")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                print(f"Пропускаю строку (нужно «old,new»): {line!r}")
                continue
            pairs.append((parts[0], parts[1]))
    return pairs


def build_parser():
    p = argparse.ArgumentParser(
        description="Переезд сайта: редирект в Cloudflare + подтверждение в Яндекс.Вебмастере.")
    p.add_argument("old", nargs="?", help="старый домен, напр. old-site.ru")
    p.add_argument("new", nargs="?", help="новый домен, напр. new-site.ru")
    p.add_argument("--batch", metavar="FILE",
                   help="CSV-файл со строками «old,new» — обработать пачкой")
    p.add_argument("--verify", choices=("dns", "html", "meta"), default="dns",
                   help="способ подтверждения прав в Яндексе (по умолчанию dns)")
    p.add_argument("--status-code", type=int, default=301, choices=(301, 302, 307, 308),
                   help="код редиректа (по умолчанию 301)")
    p.add_argument("--timeout", type=int, default=300,
                   help="таймаут ожидания подтверждения прав, сек (по умолчанию 300)")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.batch:
        jobs = read_batch(args.batch)
        if not jobs:
            parser.error(f"в файле {args.batch} нет валидных строк «old,new»")
    elif args.old and args.new:
        jobs = [(args.old, args.new)]
    else:
        parser.error("укажите старый и новый домены, либо --batch FILE")

    config = Config.from_env()
    cf = Cloudflare(config.cloudflare_token)
    ya = Yandex(config.yandex_token)
    user_id = ya.get_user_id()

    results = []
    for old, new in jobs:
        try:
            migrate_one(cf, ya, user_id, old, new,
                        args.verify, args.status_code, args.timeout)
            results.append((old, new, "OK"))
        except (ApiError, OSError) as exc:
            print(f"[ОШИБКА] {old} → {new}: {exc}", file=sys.stderr)
            results.append((old, new, "ОШИБКА"))

    if len(results) > 1:
        print("\n=== Итог ===")
        for old, new, status in results:
            print(f"  {status:8} {old} → {new}")

    return 0 if all(status == "OK" for _, _, status in results) else 1


if __name__ == "__main__":
    sys.exit(main())
