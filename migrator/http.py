"""Минимальный HTTP-клиент на стандартной библиотеке (без внешних зависимостей)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    """Ошибка обращения к внешнему API (Cloudflare или Яндекс)."""

    def __init__(self, message, status=None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def request(method, url, headers=None, params=None, json_body=None, timeout=30):
    """Выполняет HTTP-запрос и возвращает кортеж (status_code, parsed_body).

    Тело ответа парсится как JSON; если это не JSON — возвращается строкой.
    Сетевые ошибки HTTP (4xx/5xx) не выбрасываются, а возвращаются как (код, тело),
    чтобы вызывающий код сам решал, что с ними делать.
    """
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query:
            url = f"{url}?{query}"

    headers = dict(headers or {})
    data = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _parse(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read().decode("utf-8", errors="replace"))


def _parse(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
