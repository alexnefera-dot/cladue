"""Управление сервером ISPmanager по SSH.

Возможности:
- создание сайта (webdomain) — порт логики исполнителя, устойчивой к таймаутам;
- чтение document root сайта;
- копирование файлов сайта-донора в папку нового зеркала;
- замена старого домена на новый в robots.txt / sitemap.xml / .htaccess;
- попытка выпуска Let's Encrypt-сертификата через ISPmanager API (экспериментально).

paramiko импортируется лениво внутри connect(), поэтому модуль можно импортировать
и юнит-тестировать (мокая _run) без установленной зависимости.
"""

from __future__ import annotations

import json
import shlex

CMD_TIMEOUT = 300  # webdomain.edit/LE перестраивают конфиги и веб-сервер — берём с запасом
DEFAULT_REPLACE_FILES = ("robots.txt", "sitemap.xml", ".htaccess")


class IspError(Exception):
    pass


def _sed_expr(old_domain, new_domain):
    """Выражение sed для замены домена. Разделитель '|' (в доменах его нет),
    точки экранируются, чтобы не матчить произвольный символ."""
    escaped_old = old_domain.replace("\\", r"\\").replace(".", r"\.")
    return f"s|{escaped_old}|{new_domain}|g"


class IspManager:
    def __init__(
        self, host, user, password, port=22,
        ispmgr_user=None, ispmgr_password=None, ispmgr_host="localhost",
        verbose=False,
    ):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.ispmgr_user = ispmgr_user or user
        self.ispmgr_password = ispmgr_password or password
        self.ispmgr_host = ispmgr_host
        self.verbose = verbose
        self._client = None

    # --- соединение ---
    def connect(self):
        import paramiko  # ленивый импорт

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host, port=self.port, username=self.user,
            password=self.password, timeout=30,
            look_for_keys=False, allow_agent=False,
        )
        self._client = client

    def disconnect(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def _run(self, cmd):
        """Выполняет команду на сервере → (stdout, stderr, exit_code)."""
        if self._client is None:
            raise RuntimeError("SSH не подключён")
        stdin, stdout, stderr = self._client.exec_command(cmd, timeout=CMD_TIMEOUT)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        code = stdout.channel.recv_exit_status()
        if self.verbose:
            print(f"  CMD: {cmd}")
            if out:
                print(f"  OUT: {out}")
            if err:
                print(f"  ERR: {err}")
        return out, err, code

    # --- ISPmanager API через curl на localhost:1500 ---
    def _api(self, func, **params):
        authinfo = f"{self.ispmgr_user}:{self.ispmgr_password}"
        data_parts = ["out=json", f"func={func}", f"authinfo={shlex.quote(authinfo)}"]
        for key, value in params.items():
            data_parts.append(f"{key}={shlex.quote(str(value))}")
        data_str = "&".join(data_parts)
        cmd = f"curl -sk -X POST 'https://{self.ispmgr_host}:1500/ispmgr' -d {shlex.quote(data_str)}"
        out, err, code = self._run(cmd)

        if not out:
            raise IspError(f"Пустой ответ ISPmanager (exit_code={code}, stderr={err})")
        try:
            result = json.loads(out)
        except json.JSONDecodeError:
            raise IspError(f"Не удалось разобрать ответ ISPmanager: {out[:200]}")

        doc = result.get("doc", result)
        if "error" in doc:
            error = doc["error"]
            msg = error.get("msg", {}).get("$") or str(error)
            raise IspError(f"ISPmanager API: {msg}")
        return result

    def _webdomains(self):
        """Список сайтов ISPmanager как список elem-словарей."""
        result = self._api("webdomain")
        doc = result.get("doc", result)
        elems = doc.get("elem", [])
        if isinstance(elems, dict):
            elems = [elems]
        return elems

    @staticmethod
    def _field(elem, key):
        value = elem.get(key)
        return value.get("$") if isinstance(value, dict) else value

    def webdomain_exists(self, domain):
        return any(self._field(e, "name") == domain for e in self._webdomains())

    def get_docroot(self, domain):
        """Document root сайта (path) или None, если сайт не найден."""
        for elem in self._webdomains():
            if self._field(elem, "name") == domain:
                return self._field(elem, "docroot") or self._field(elem, "home")
        return None

    def create_webdomain(self, domain, email=""):
        """Создаёт сайт без SSL/HTTPS-редиректа (HTTPS обеспечивает Cloudflare).

        Устойчиво к таймаутам: webdomain.edit может выполняться дольше, чем живёт
        SSH-канал, и упасть с пустой ошибкой уже ПОСЛЕ создания сайта — поэтому при
        любой ошибке перепроверяем наличие сайта.
        """
        try:
            self._api(
                "webdomain.edit", sok="ok", name=domain, domain=domain, email=email,
                php="on", php_mode="php_mode_cgi", php_cgi_version="isp-php74",
            )
            return "OK: создан"
        except Exception as exc:
            try:
                exists = self.webdomain_exists(domain)
            except Exception:
                exists = False
            if exists:
                return "OK: уже существует" if isinstance(exc, IspError) else "OK: создан (ответ не получен)"
            raise

    # --- файлы сайта ---
    def copy_site_files(self, src_dir, dst_dir):
        """Копирует содержимое src_dir в dst_dir (rsync, при отсутствии — cp)."""
        src = src_dir.rstrip("/") + "/"
        dst = dst_dir.rstrip("/") + "/"
        cmd = (
            f"mkdir -p {shlex.quote(dst)} && "
            f"(rsync -a {shlex.quote(src)} {shlex.quote(dst)} || "
            f"cp -a {shlex.quote(src)}. {shlex.quote(dst)})"
        )
        out, err, code = self._run(cmd)
        if code != 0:
            raise IspError(f"Копирование не удалось (exit_code={code}): {err or out}")
        return True

    def replace_domain_in_files(self, docroot, old_domain, new_domain, files=DEFAULT_REPLACE_FILES):
        """Заменяет old_domain → new_domain в указанных файлах docroot (если есть).

        Возвращает {имя_файла: 'changed' | 'skip'}. Создаёт .bak рядом с каждым изменённым.
        """
        expr = _sed_expr(old_domain, new_domain)
        results = {}
        for fname in files:
            path = docroot.rstrip("/") + "/" + fname
            cmd = (
                f"if [ -f {shlex.quote(path)} ]; then "
                f"sed -i.bak -e {shlex.quote(expr)} {shlex.quote(path)} && echo CHANGED; "
                f"else echo SKIP; fi"
            )
            out, err, code = self._run(cmd)
            results[fname] = "changed" if "CHANGED" in out else "skip"
        return results

    # --- Let's Encrypt (экспериментально) ---
    def issue_letsencrypt(self, domain, email, with_www=True):
        """Пытается выпустить LE-сертификат через ISPmanager API.

        Набор полей функции letsencrypt зависит от версии ISPmanager, поэтому здесь
        первый рабочий вариант; при ошибке возвращаем диагностику для доработки на
        живом сервере. Не бросает исключение — возвращает (ok: bool, detail: str).
        """
        params = {
            "sok": "ok",
            "domain": domain,
            "email": email,
            "wwwdomain": f"www.{domain}" if with_www else "",
        }
        try:
            self._api("letsencrypt.edit", **params)
            return True, "LE-сертификат заказан"
        except IspError as exc:
            return False, f"{exc} (функция/поля letsencrypt зависят от версии ISPmanager)"
