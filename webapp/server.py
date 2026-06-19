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
            return self._send(200, {
                "projects": store.load_projects(),
                "settings": store.masked_settings(),
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
        store.save_settings(body.get("settings", {}))
        return store.masked_settings()

    def _run_full(self, body):
        return service.run_full(body["project"], dry_run=bool(body.get("dry_run")))

    def _step(self, body):
        steps = {
            "create-site": service.create_isp_site,
            "copy-files": service.copy_files,
            "cf-onboard": service.cf_onboard,
            "ssl": service.issue_ssl,
            "worker": service.bind_worker,
        }
        fn = steps.get(body.get("step"))
        if fn is None:
            raise service.ConfigError(f"Неизвестный шаг: {body.get('step')}")
        return fn(body["project"], dry_run=bool(body.get("dry_run")))

    def _migrate(self, body):
        return service.migrate_mirrors(body["project"], dry_run=bool(body.get("dry_run")))

    def _import_cf(self, body):
        return service.import_from_cloudflare(body.get("projects"))

    def _import_csv(self, body):
        return service.import_from_csv(body.get("csv", ""), body.get("projects"))

    def _check(self, body):
        return service.check_status(body["project"])

    def _yandex_prepare(self, body):
        return service.yandex_prepare(body["project"])

    def _yandex_verify(self, body):
        return service.yandex_verify(body["project"], body.get("method", "dns"))

    _POST_ROUTES = {
        "/api/projects": _save_projects,
        "/api/settings": _save_settings,
        "/api/run-full": _run_full,
        "/api/step": _step,
        "/api/migrate": _migrate,
        "/api/import-cloudflare": _import_cf,
        "/api/import-csv": _import_csv,
        "/api/check": _check,
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
