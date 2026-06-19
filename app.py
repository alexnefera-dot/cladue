#!/usr/bin/env python3
"""Запуск локального веб-приложения Site Migrator.

    python app.py            # запустить и открыть в браузере
    python app.py --port 9000 --no-browser

Приложение работает только на localhost и использует те же токены, что и CLI
(см. README.md). Зависимостей нет — только стандартная библиотека Python 3.8+.
"""

from __future__ import annotations

import argparse
import threading
import webbrowser
from http.server import ThreadingHTTPServer

from webapp.server import Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Site Migrator — локальное приложение.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="не открывать браузер")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Site Migrator запущен: {url}\nОстановка — Ctrl+C.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановка…")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
