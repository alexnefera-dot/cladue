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

# Хранилище задач трекера позиций.
MONITORS = {}
MON_LOCK = Lock()
ACTIVE_MONITOR = {"id": None}


# --------------------------------------------------------------------------- #
#  Парсинг ответа                                                             #
# --------------------------------------------------------------------------- #
def domain_from_url(url):
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def normalize_domain(value):
    """Приводит «www.Site.ru/path» или «https://site.ru» к «site.ru»."""
    s = (value or "").strip().lower()
    if not s:
        return ""
    if "://" in s:
        s = urlparse(s).netloc or s.split("://", 1)[1]
    s = s.split("/")[0].strip()
    if s.startswith("www."):
        s = s[4:]
    return s


def _domain_matches(found, target):
    """Совпадение домена в любую сторону: точное, либо один является
    поддоменом другого. Так сайт ловится и если ввели корень (k4r.team —
    поймает spacewin.k4r.team), и если ввели поддомен (spacewin.k4r.team —
    поймает и корень k4r.team). Путь/раздел и www роли не играют."""
    if not found or not target:
        return False
    found = found.lower()
    if found.startswith("www."):
        found = found[4:]
    return (
        found == target
        or found.endswith("." + target)
        or target.endswith("." + found)
    )


def find_position(results, target):
    """Позиция целевого домена в выдаче (1-based) или None, если не найден."""
    for i, r in enumerate(results, 1):
        dom = r.get("domain") or domain_from_url(r.get("url", ""))
        if _domain_matches(dom, target):
            return i
    return None


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
#  Трекер позиций: прогон по раундам                                          #
# --------------------------------------------------------------------------- #
def run_monitor(job_id, cfg):
    job = MONITORS[job_id]
    try:
        for rnd in range(1, job["rounds_total"] + 1):
            if job["cancel"].is_set():
                break
            round_pos = {}
            with ThreadPoolExecutor(max_workers=cfg["workers"]) as ex:
                futs = {
                    ex.submit(fetch_one, cfg, kw, job["cancel"]): kw
                    for kw in job["keywords"]
                }
                for fut in as_completed(futs):
                    kw = futs[fut]
                    try:
                        results, err = fut.result()
                    except Exception as e:  # noqa: BLE001
                        results, err = [], f"исключение: {e}"
                    if err:
                        with job["lock"]:
                            job["errors"].append({"round": rnd, "query": kw, "error": err})
                    doms = job["pairs_by_kw"].get(kw, [])
                    round_pos[kw] = {dom: find_position(results, dom) for dom in doms}

            with job["lock"]:
                job["snapshots"].append(
                    {"round": rnd, "at": time.time(), "positions": round_pos}
                )
                job["rounds_done"] = rnd

            # Пауза до следующего снятия (прерываемая), кроме последнего раунда.
            if rnd < job["rounds_total"] and not job["cancel"].is_set():
                target = time.time() + job["interval_sec"]
                with job["lock"]:
                    job["next_run_at"] = target
                while time.time() < target and not job["cancel"].is_set():
                    time.sleep(1)
                with job["lock"]:
                    job["next_run_at"] = None
    except Exception as e:  # noqa: BLE001
        with job["lock"]:
            job["status"] = "error"
            job["fatal"] = str(e)
            job["next_run_at"] = None
        return

    with job["lock"]:
        job["status"] = "cancelled" if job["cancel"].is_set() else "done"
        job["finished_at"] = time.time()
        job["next_run_at"] = None


def monitor_rows(job):
    """Сводка по каждой паре ключ+домен (только назначенные пары)."""
    snaps = job["snapshots"]
    rows = []
    for kw, dom in job.get("pairs", []):
        positions = [s["positions"].get(kw, {}).get(dom) for s in snaps]
        found = [p for p in positions if p is not None]
        rows.append(
            {
                "keyword": kw,
                "domain": dom,
                "positions": positions,
                "avg": round(sum(found) / len(found), 1) if found else None,
                "best": min(found) if found else None,
                "worst": max(found) if found else None,
                "found": len(found),
                "checks": len(snaps),
            }
        )
    return rows


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


# --- Трекер позиций -------------------------------------------------------- #
def _split_unique(raw, limit):
    seen, out = set(), []
    for line in (raw or "").replace("\r", "\n").split("\n"):
        v = line.strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out[:limit]


def _split_multi(raw):
    """Домены в одном поле через запятую/пробел/перенос строки."""
    s = (raw or "").replace(",", " ").replace(";", " ").replace("\r", " ").replace("\n", " ")
    return [p for p in s.split() if p]


@app.route("/api/monitor/run", methods=["POST"])
def api_monitor_run():
    data = request.get_json(force=True, silent=True) or {}

    user = (data.get("user") or "").strip()
    key = (data.get("key") or "").strip()
    if not user or not key:
        return jsonify({"error": "Укажите User ID и API key из кабинета xmlstock."}), 400

    # Блоки «домен(ы) + его ключи». Старый формат (общие keywords+domains)
    # поддерживается как один блок ради совместимости.
    def parse_group(g):
        kws = _split_unique((g or {}).get("keywords"), 100)
        doms, dseen = [], set()
        for d in _split_multi((g or {}).get("domains")):
            nd = normalize_domain(d)
            if nd and nd not in dseen:
                dseen.add(nd)
                doms.append(nd)
        return {"domains": doms, "keywords": kws} if (kws and doms) else None

    raw_groups = data.get("groups")
    groups = []
    if isinstance(raw_groups, list) and raw_groups:
        for g in raw_groups[:20]:
            parsed = parse_group(g)
            if parsed:
                groups.append(parsed)
    else:
        parsed = parse_group({"keywords": data.get("keywords"), "domains": data.get("domains")})
        if parsed:
            groups.append(parsed)

    if not groups:
        return jsonify({"error": "Добавьте хотя бы один домен с его ключами."}), 400

    # Уникальные ключи (запрашиваются 1 раз за раунд) и пары (ключ, домен).
    keywords, kseen = [], set()
    pairs, pairs_by_kw, pseen = [], {}, set()
    for g in groups:
        for kw in g["keywords"]:
            if kw not in kseen:
                kseen.add(kw)
                keywords.append(kw)
        for dom in g["domains"]:
            for kw in g["keywords"]:
                if (kw, dom) not in pseen:
                    pseen.add((kw, dom))
                    pairs.append([kw, dom])
                pairs_by_kw.setdefault(kw, [])
                if dom not in pairs_by_kw[kw]:
                    pairs_by_kw[kw].append(dom)
    keywords = keywords[:100]
    all_domains = list(dict.fromkeys(d for g in groups for d in g["domains"]))

    engine = data.get("engine") or "yandex"
    endpoint = (data.get("endpoint") or "").strip() or ENDPOINTS.get(engine)
    if not endpoint or not endpoint.lower().startswith(("http://", "https://")):
        return jsonify({"error": "Некорректный URL эндпоинта."}), 400

    def clamp(val, lo, hi, default):
        try:
            return max(lo, min(hi, int(val)))
        except (TypeError, ValueError):
            return default

    try:
        interval_min = float(data.get("interval_min"))
    except (TypeError, ValueError):
        interval_min = 4.0
    interval_sec = int(max(5, min(3600, interval_min * 60)))
    rounds_total = clamp(data.get("rounds"), 1, 100, 10)

    cfg = {
        "user": user,
        "key": key,
        "endpoint": endpoint,
        "lr": (data.get("lr") or "").strip(),
        "domain": (data.get("domain") or "").strip(),
        "device": (data.get("device") or "").strip(),
        "top_n": clamp(data.get("depth"), 10, 100, 100),
        "workers": clamp(data.get("workers"), 1, 10, 5),
        "delay": 0.0,
        "timeout": 30,
        "retries": 2,
    }

    job_id = uuid.uuid4().hex
    with MON_LOCK:
        MONITORS[job_id] = {
            "id": job_id,
            "status": "running",
            "keywords": keywords,
            "domains": all_domains,
            "groups": groups,
            "pairs": pairs,
            "pairs_by_kw": pairs_by_kw,
            "rounds_total": rounds_total,
            "rounds_done": 0,
            "interval_sec": interval_sec,
            "depth": cfg["top_n"],
            "snapshots": [],
            "errors": [],
            "next_run_at": None,
            "lock": Lock(),
            "cancel": Event(),
            "started_at": time.time(),
        }
        ACTIVE_MONITOR["id"] = job_id

    Thread(target=run_monitor, args=(job_id, cfg), daemon=True).start()
    return jsonify(
        {
            "job_id": job_id,
            "keywords": len(keywords),
            "domains": all_domains,
            "pairs": len(pairs),
            "rounds": rounds_total,
            "interval_sec": interval_sec,
            "depth": cfg["top_n"],
        }
    )


@app.route("/api/monitor/status/<job_id>")
def api_monitor_status(job_id):
    job = MONITORS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    with job["lock"]:
        nxt = job.get("next_run_at")
        return jsonify(
            {
                "status": job["status"],
                "rounds_total": job["rounds_total"],
                "rounds_done": job["rounds_done"],
                "interval_sec": job["interval_sec"],
                "seconds_to_next": int(max(0, nxt - time.time())) if nxt else None,
                "depth": job["depth"],
                "domains": job["domains"],
                "rows": monitor_rows(job),
                "errors_count": len(job["errors"]),
                "fatal": job.get("fatal"),
            }
        )


@app.route("/api/monitor/cancel/<job_id>", methods=["POST"])
def api_monitor_cancel(job_id):
    job = MONITORS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    job["cancel"].set()
    return jsonify({"ok": True})


@app.route("/api/monitor/active")
def api_monitor_active():
    jid = ACTIVE_MONITOR.get("id")
    if jid and jid in MONITORS:
        return jsonify({"job_id": jid, "status": MONITORS[jid]["status"]})
    return jsonify({"job_id": None})


@app.route("/api/monitor/download/<job_id>")
def api_monitor_download(job_id):
    job = MONITORS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    fmt = request.args.get("fmt", "csv")
    with job["lock"]:
        rows = monitor_rows(job)
        n = len(job["snapshots"])
    headers = (
        ["keyword", "domain", "avg_position", "best", "worst", "found", "checks"]
        + [f"round_{i}" for i in range(1, n + 1)]
    )

    def cells(r):
        return (
            [r["keyword"], r["domain"], r["avg"], r["best"], r["worst"], r["found"], r["checks"]]
            + [p if p is not None else "" for p in r["positions"]]
        )

    if fmt == "xlsx":
        try:
            from openpyxl import Workbook
        except Exception:
            return jsonify({"error": "openpyxl не установлен"}), 400
        wb = Workbook()
        ws = wb.active
        ws.title = "positions"
        ws.append(headers)
        for r in rows:
            ws.append(cells(r))
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"positions_{job_id[:8]}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    sbuf = io.StringIO()
    w = csv.writer(sbuf, delimiter=";")
    w.writerow(headers)
    for r in rows:
        w.writerow(cells(r))
    payload = ("﻿" + sbuf.getvalue()).encode("utf-8")
    return send_file(
        io.BytesIO(payload),
        as_attachment=True,
        download_name=f"positions_{job_id[:8]}.csv",
        mimetype="text/csv",
    )


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
