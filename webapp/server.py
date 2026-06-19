"""HTTP-сервер на стандартной библиотеке: статика + JSON-API."""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from . import service, store

STATIC_DIR = Path(__file__).resolve().parent / "static"


class Handler(BaseHTTPRequestHandler):
    server_version = "SiteMigrator"

    # --- утилиты ответа ---
    def _send(self, status, body=None, content_type="application/json; charset=utf-8"):
        if body is None:
            data = b""
        elif isinstance(body, (bytes, bytearray)):
            data = bytes(body)
        else:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    # --- маршруты ---
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._static("index.html")
        if self.path.startswith("/static/"):
            return self._static(self.path[len("/static/"):])
        if self.path == "/api/state":
            cf, ya = store.get_tokens()
            return self._send(200, {
                "projects": store.load_projects(),
                "settings": {"cloudflare": bool(cf), "yandex": bool(ya)},
            })
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._body()
            handler = self._POST_ROUTES.get(self.path)
            if handler is None:
                return self._send(404, {"error": "not found"})
            return self._send(200, handler(self, body))
        except service.ConfigError as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:  # любая ошибка API/сети — в понятный JSON
            return self._send(500, {"error": str(exc)})

    # --- обработчики POST ---
    def _save_projects(self, body):
        store.save_projects(body.get("projects", []))
        return {"ok": True}

    def _save_settings(self, body):
        store.save_settings({
            "cloudflare_token": (body.get("cloudflare_token") or "").strip(),
            "yandex_token": (body.get("yandex_token") or "").strip(),
        })
        cf, ya = store.get_tokens()
        return {"cloudflare": bool(cf), "yandex": bool(ya)}

    def _check(self, body):
        return service.check_project(body["project"])

    def _migrate(self, body):
        return service.migrate_project(body["project"])

    def _yandex_prepare(self, body):
        return service.yandex_prepare(body["project"])

    def _yandex_verify(self, body):
        return service.yandex_verify(body["project"], body.get("method", "dns"))

    _POST_ROUTES = {
        "/api/projects": _save_projects,
        "/api/settings": _save_settings,
        "/api/check": _check,
        "/api/migrate": _migrate,
        "/api/yandex/prepare": _yandex_prepare,
        "/api/yandex/verify": _yandex_verify,
    }

    # --- статика ---
    def _static(self, rel):
        path = (STATIC_DIR / rel).resolve()
        if not str(path).startswith(str(STATIC_DIR)) or not path.is_file():
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return self._send(200, path.read_bytes(), ctype)

    def log_message(self, *args):  # без шума в консоли
        pass
