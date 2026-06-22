#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XMLStock SERP — локальный сборщик ТОП-выдачи Яндекса (и Google) через API xmlstock.com.

Запускает локальный веб-сервер с интерфейсом в браузере: вставляете пачку
запросов (200-300 шт.), получаете ТОП-N результатов по каждому ключу и
выгружаете в файл (XLSX / CSV).

Запуск:  python app.py
Открыть: http://127.0.0.1:5000  (откроется автоматически)
"""

import csv
import io
import json
import os
import time
import uuid
import webbrowser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Event, Lock, Thread
from urllib.parse import urlparse

import requests
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Пресеты эндпоинтов xmlstock. У xmlstock единый путь для Яндекса —
# /yandex/xml/ (живая выдача или XML-лимиты определяются вашим тарифом),
# и /google/xml/ для Google. Если в кабинете другой адрес — выберите
# «Свой URL» в интерфейсе и вставьте точную ссылку.
ENDPOINTS = {
    "yandex": "https://xmlstock.com/yandex/xml/",
    "google": "https://xmlstock.com/google/xml/",
    # обратная совместимость со старыми сохранёнными значениями
    "yandex_live": "https://xmlstock.com/yandex/xml/",
    "yandex_xml": "https://xmlstock.com/yandex/xml/",
    "google_live": "https://xmlstock.com/google/xml/",
    "google_xml": "https://xmlstock.com/google/xml/",
}

# Хранилище задач в памяти процесса.
JOBS = {}
JOBS_LOCK = Lock()


# --------------------------------------------------------------------------- #
#  Парсинг ответа                                                             #
# --------------------------------------------------------------------------- #
def domain_from_url(url):
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def _is_retryable(error_text):
    """Временные ошибки, которые имеет смысл повторить."""
    if not error_text:
        return False
    t = error_text.lower()
    return any(
        s in t
        for s in ("limit", "лимит", "rps", "temporar", "временно", "503", "502", "504", "busy")
    )


def parse_xml(text):
    """Разбор ответа в формате Яндекс XML. Возвращает (results, error)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [], f"ошибка XML: {e}"

    err = root.find(".//response/error")
    if err is None:
        err = root.find(".//error")
    if err is not None:
        code = (err.get("code") or "").strip()
        msg = (err.text or "").strip()
        # 15 — «по запросу ничего не нашлось», это не ошибка, просто пусто.
        if code == "15":
            return [], None
        return [], f"API {code}: {msg}".strip()

    results = []
    for doc in root.findall(".//doc"):
        url = (doc.findtext("url") or "").strip()
        if not url:
            continue
        title_el = doc.find("title")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""
        domain = (doc.findtext("domain") or "").strip() or domain_from_url(url)
        results.append({"url": url, "title": title, "domain": domain})
    return results, None


def parse_json(data):
    """Запасной разбор JSON: рекурсивно собираем объекты с полем url."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("url"), str):
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    results = []
    for o in found:
        url = (o.get("url") or "").strip()
        if not url:
            continue
        title = o.get("title") or o.get("name") or ""
        if isinstance(title, dict):
            title = title.get("text", "")
        domain = (o.get("domain") or "").strip() or domain_from_url(url)
        results.append({"url": url, "title": str(title).strip(), "domain": domain})
    if not results:
        return [], "не удалось разобрать JSON-ответ"
    return results, None


def parse_response(text):
    text = (text or "").strip()
    if not text:
        return [], "пустой ответ"
    if text[0] == "<":
        return parse_xml(text)
    if text[0] in "{[":
        try:
            return parse_json(json.loads(text))
        except Exception:
            pass
    return [], "нераспознанный ответ: " + text[:200].replace("\n", " ")


# --------------------------------------------------------------------------- #
#  Запрос к API                                                               #
# --------------------------------------------------------------------------- #
def fetch_one(cfg, query, cancel):
    """Один запрос к xmlstock с ретраями. Возвращает (results, error)."""
    if cancel.is_set():
        return [], "отменено"
    if cfg["delay"] > 0:
        time.sleep(cfg["delay"])

    groupby = (
        f"attr=d.mode=deep.groups-on-page={cfg['top_n']}.docs-in-group=1"
    )
    params = {
        "user": cfg["user"],
        "key": cfg["key"],
        "query": query,
        "groupby": groupby,
        "page": 0,
    }
    if cfg.get("lr"):
        params["lr"] = cfg["lr"]
    if cfg.get("domain"):
        params["domain"] = cfg["domain"]
    if cfg.get("device"):
        params["device"] = cfg["device"]

    last_err = None
    for attempt in range(cfg["retries"] + 1):
        if cancel.is_set():
            return [], "отменено"
        try:
            r = requests.get(cfg["endpoint"], params=params, timeout=cfg["timeout"])
        except requests.RequestException as e:
            last_err = f"сеть: {e}"
            time.sleep(min(2 ** attempt, 8))
            continue

        if r.status_code >= 500:
            last_err = f"HTTP {r.status_code}"
            time.sleep(min(2 ** attempt, 8))
            continue
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}: {r.text[:200]}"

        results, err = parse_response(r.text)
        if err and _is_retryable(err) and attempt < cfg["retries"]:
            last_err = err
            time.sleep(min(2 ** attempt, 8))
            continue
        return results[: cfg["top_n"]], err

    return [], last_err or "не удалось выполнить запрос"


# --------------------------------------------------------------------------- #
#  Фоновая обработка пачки                                                    #
# --------------------------------------------------------------------------- #
def run_job(job_id, cfg, queries):
    job = JOBS[job_id]
    results_by_query = {}

    try:
        with ThreadPoolExecutor(max_workers=cfg["workers"]) as ex:
            futures = {}
            for q in queries:
                if job["cancel"].is_set():
                    break
                futures[ex.submit(fetch_one, cfg, q, job["cancel"])] = q

            for fut in as_completed(futures):
                q = futures[fut]
                try:
                    res, err = fut.result()
                except Exception as e:  # noqa: BLE001
                    res, err = [], f"исключение: {e}"
                with job["lock"]:
                    job["done"] += 1
                    results_by_query[q] = (res, err)
                    if err:
                        job["errors"].append({"query": q, "error": err})
                    job["recent"] = (
                        job["recent"] + [{"query": q, "count": len(res), "error": err}]
                    )[-15:]
    except Exception as e:  # noqa: BLE001
        with job["lock"]:
            job["status"] = "error"
            job["fatal"] = str(e)
        return

    # Сборка файлов в исходном порядке запросов.
    long_rows = []
    wide_rows = []
    for q in queries:
        res, err = results_by_query.get(q, ([], "не обработано"))
        if res:
            for i, r in enumerate(res, 1):
                long_rows.append([q, i, r["url"], r["title"], r["domain"]])
            urls = [r["url"] for r in res]
        else:
            note = f"[{err}]" if err else "[нет результатов]"
            long_rows.append([q, "", "", note, ""])
            urls = []
        urls = (urls + [""] * cfg["top_n"])[: cfg["top_n"]]
        wide_rows.append([q] + urls)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"serp_{stamp}.csv")
    xlsx_path = os.path.join(OUTPUT_DIR, f"serp_{stamp}.xlsx")

    _write_csv(csv_path, long_rows)
    xlsx_ok = _write_xlsx(xlsx_path, long_rows, wide_rows, cfg["top_n"])

    with job["lock"]:
        job["csv_path"] = csv_path
        job["xlsx_path"] = xlsx_path if xlsx_ok else None
        job["rows"] = len(long_rows)
        job["status"] = "cancelled" if job["cancel"].is_set() else "done"
        job["finished_at"] = time.time()


def _write_csv(path, long_rows):
    # utf-8-sig + разделитель «;» — корректно открывается двойным кликом в Excel (RU).
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["query", "position", "url", "title", "domain"])
        w.writerows(long_rows)


def _write_xlsx(path, long_rows, wide_rows, top_n):
    try:
        from openpyxl import Workbook
    except Exception:
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["query", "position", "url", "title", "domain"])
    for row in long_rows:
        ws.append(row)

    ws2 = wb.create_sheet("wide")
    ws2.append(["query"] + [f"url_{i}" for i in range(1, top_n + 1)])
    for row in wide_rows:
        ws2.append(row)

    try:
        wb.save(path)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
#  HTTP-маршруты                                                              #
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True, silent=True) or {}

    user = (data.get("user") or "").strip()
    key = (data.get("key") or "").strip()
    if not user or not key:
        return jsonify({"error": "Укажите User ID и API key из кабинета xmlstock."}), 400

    raw = data.get("queries") or ""
    seen, queries = set(), []
    for line in raw.replace("\r", "\n").split("\n"):
        q = line.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)
    if not queries:
        return jsonify({"error": "Список запросов пуст."}), 400

    engine = data.get("engine") or "yandex"
    endpoint = (data.get("endpoint") or "").strip() or ENDPOINTS.get(engine)
    if not endpoint or not endpoint.lower().startswith(("http://", "https://")):
        return jsonify({"error": "Некорректный URL эндпоинта."}), 400

    def clamp(val, lo, hi, default):
        try:
            return max(lo, min(hi, int(val)))
        except (TypeError, ValueError):
            return default

    def fnum(val, default):
        try:
            return max(0.0, float(val))
        except (TypeError, ValueError):
            return default

    cfg = {
        "user": user,
        "key": key,
        "endpoint": endpoint,
        "lr": (data.get("lr") or "").strip(),
        "domain": (data.get("domain") or "").strip(),
        "device": (data.get("device") or "").strip(),
        "top_n": clamp(data.get("top_n"), 1, 50, 10),
        "workers": clamp(data.get("workers"), 1, 20, 5),
        "delay": fnum(data.get("delay"), 0.0),
        "timeout": clamp(data.get("timeout"), 5, 120, 30),
        "retries": clamp(data.get("retries"), 0, 5, 2),
    }

    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "running",
            "total": len(queries),
            "done": 0,
            "errors": [],
            "recent": [],
            "lock": Lock(),
            "cancel": Event(),
            "csv_path": None,
            "xlsx_path": None,
            "rows": 0,
            "started_at": time.time(),
        }

    Thread(target=run_job, args=(job_id, cfg, queries), daemon=True).start()
    return jsonify({"job_id": job_id, "total": len(queries), "deduped": len(queries)})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    with job["lock"]:
        return jsonify(
            {
                "status": job["status"],
                "total": job["total"],
                "done": job["done"],
                "errors_count": len(job["errors"]),
                "recent": job["recent"],
                "rows": job.get("rows", 0),
                "has_csv": bool(job.get("csv_path")),
                "has_xlsx": bool(job.get("xlsx_path")),
                "fatal": job.get("fatal"),
            }
        )


@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    job["cancel"].set()
    return jsonify({"ok": True})


@app.route("/api/download/<job_id>")
def api_download(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    fmt = request.args.get("fmt", "xlsx")
    path = job.get("xlsx_path") if fmt == "xlsx" else job.get("csv_path")
    if not path or not os.path.exists(path):
        return jsonify({"error": "Файл ещё не готов"}), 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route("/api/errors/<job_id>")
def api_errors(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    with job["lock"]:
        return jsonify({"errors": job["errors"]})


def _open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"
    print(f"\n  XMLStock SERP запущен → {url}\n  (Ctrl+C для остановки)\n")
    if os.environ.get("NO_BROWSER") != "1":
        Thread(target=lambda: (time.sleep(1.0), _open_browser(url)), daemon=True).start()
    app.run(host=host, port=port, threaded=True, debug=False)
