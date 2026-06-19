"use strict";

// ---------- помощники ----------
const $ = (sel, root = document) => root.querySelector(sel);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

function normDomain(v) {
  v = (v || "").trim().toLowerCase().replace(/^https?:\/\//, "");
  return v.replace(/\/+$/, "").split("/")[0];
}

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

let toastTimer;
function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isError ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 5000);
}

// ---------- состояние ----------
const state = { projects: [], active: 0, settings: {} };
const statuses = {};   // pid -> /api/check
const logs = {};       // pid -> записи журнала
const view = { busy: false, busyMsg: "", focusLastMirror: false, dryRun: false };

function activeProject() { return state.projects[state.active] || null; }
function accountNames() { return state.settings.account_names || []; }

let saveTimer;
function persistProjects() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    api("POST", "/api/projects", { projects: state.projects }).catch((e) => toast(e.message, true));
  }, 400);
}

function setBusy(on, msg = "") { view.busy = on; view.busyMsg = msg; render(); }
function pushLog(pid, entry) { (logs[pid] = logs[pid] || []).push(entry); }

// ---------- вкладки ----------
function renderTabs() {
  const nav = $("#tabs");
  nav.replaceChildren();
  state.projects.forEach((p, i) => {
    nav.append(el("div", { class: "tab" + (i === state.active ? " active" : ""),
        onclick: () => { state.active = i; render(); } },
      el("span", { class: "name" }, p.name || "Без названия"),
      el("button", { class: "x", title: "Удалить проект",
        onclick: (e) => { e.stopPropagation(); deleteProject(i); } }, "×")));
  });
  nav.append(el("button", { class: "tab-add", title: "Новый проект", onclick: addProject }, "+"));
}

function addProject() {
  state.projects.push({
    id: "p_" + Date.now(), name: "Проект " + (state.projects.length + 1),
    new_domain: "", new_account: "", worker: "", donor_domain: "", verify: "dns",
    mirrors: [{ domain: "", account: "" }],
  });
  state.active = state.projects.length - 1;
  persistProjects();
  render();
}

function deleteProject(i) {
  const p = state.projects[i];
  if (!confirm(`Удалить проект «${p.name}»? Домены в Cloudflare/ISP это не затронет.`)) return;
  delete statuses[p.id]; delete logs[p.id];
  state.projects.splice(i, 1);
  if (state.active >= state.projects.length) state.active = Math.max(0, state.projects.length - 1);
  persistProjects();
  render();
}

// ---------- выпадающий список аккаунтов ----------
function accountSelect(value, onchange) {
  const sel = el("select", { onchange: (e) => onchange(e.target.value) },
    el("option", { value: "" }, "— аккаунт —"),
    accountNames().map((n) => el("option", { value: n }, n)));
  sel.value = value || "";
  return sel;
}

// ---------- статус зеркала ----------
function statusNode(domain) {
  const p = activeProject();
  const st = statuses[p.id];
  const d = normDomain(domain);
  if (!st || !d) return el("span", { class: "status" }, d ? "не проверено" : "");
  const row = (st.mirrors || []).find((m) => m.domain === d);
  if (!row) return el("span", { class: "status" }, "не проверено");
  if (row.error) return el("span", { class: "status" }, el("span", { class: "s-err" }, row.error));
  const zone = row.zone ? el("span", { class: "s-ok" }, "зона ✓")
                        : el("span", { class: "s-err" }, "нет в CF");
  let redir = "";
  if (row.zone && row.ok) redir = el("span", { class: "s-ok" }, " · редирект ✓");
  else if (row.zone && row.redirect) redir = el("span", { class: "s-warn" }, ` · → ${row.redirect}`);
  else if (row.zone) redir = el("span", { class: "muted" }, " · редирект —");
  return el("span", { class: "status" }, zone, redir);
}

function mirrorRow(p, i) {
  const m = p.mirrors[i];
  return el("div", { class: "mirror" },
    el("input", { type: "text", value: m.domain || "", placeholder: "старое зеркало, напр. old.ru",
      oninput: (e) => { m.domain = e.target.value; persistProjects(); } }),
    accountSelect(m.account, (v) => { m.account = v; persistProjects(); }),
    statusNode(m.domain),
    el("button", { class: "x", title: "Убрать",
      onclick: () => { p.mirrors.splice(i, 1); if (!p.mirrors.length) p.mirrors.push({ domain: "", account: "" }); persistProjects(); render(); } }, "×"));
}

// ---------- журнал ----------
function renderLog(p) {
  const entries = logs[p.id] || [];
  if (!entries.length) return null;
  const box = el("div", { class: "log" },
    el("h4", {}, "Журнал"),
    el("button", { class: "ghost small", style: "float:right;margin-top:-26px",
      onclick: () => { logs[p.id] = []; render(); } }, "очистить"));
  for (const e of entries) {
    if (e.kind === "verifyBtn") {
      box.append(el("div", { class: "line" },
        el("button", { class: "primary small", onclick: () => doYandexVerify(e.method) },
          "Я разместил — проверить права")));
    } else {
      box.append(el("div", { class: "line " + (e.cls || "") }, e.text));
    }
  }
  return box;
}

// ---------- панель проекта ----------
function field(labelText, input, full) {
  return el("div", { class: "field" + (full ? " full" : "") }, el("label", {}, labelText), input);
}

function renderPanel() {
  const panel = $("#panel");
  panel.replaceChildren();
  const p = activeProject();
  if (!p) {
    panel.append(el("div", { class: "empty" }, el("p", {}, "Пока нет проектов."),
      el("button", { class: "primary", onclick: addProject }, "Создать проект")));
    return;
  }
  const card = el("div", { class: "card" });

  card.append(field("Название проекта",
    el("input", { type: "text", value: p.name || "",
      oninput: (e) => { p.name = e.target.value; persistProjects(); renderTabs(); } }), true));

  const grid = el("div", { class: "grid-fields" });
  grid.append(
    field("Новый (целевой) домен",
      el("input", { type: "text", value: p.new_domain || "", placeholder: "new-site.casino",
        oninput: (e) => { p.new_domain = e.target.value; persistProjects(); } })),
    field("CF-аккаунт нового домена", accountSelect(p.new_account, (v) => { p.new_account = v; persistProjects(); })),
    field("Воркер (имя в Cloudflare)",
      el("input", { type: "text", value: p.worker || "", placeholder: "ru-mobile-...",
        oninput: (e) => { p.worker = e.target.value; persistProjects(); } })),
    field("Домен-донор (откуда копировать файлы)",
      el("input", { type: "text", value: p.donor_domain || "", placeholder: "рабочее зеркало бренда",
        oninput: (e) => { p.donor_domain = e.target.value; persistProjects(); } })),
  );
  card.append(grid);

  const verify = el("select", { onchange: (e) => { p.verify = e.target.value; persistProjects(); } },
    el("option", { value: "dns" }, "Яндекс: DNS — авто через Cloudflare"),
    el("option", { value: "html" }, "Яндекс: HTML-файл — вручную"),
    el("option", { value: "meta" }, "Яндекс: мета-тег — вручную"));
  verify.value = p.verify || "dns";
  card.append(field("Подтверждение прав в Яндексе", verify, true));

  card.append(el("div", { class: "section-title" }, "Старые зеркала (откуда редирект)"));
  const list = el("div", {});
  p.mirrors.forEach((_, i) => list.append(mirrorRow(p, i)));
  card.append(list);
  card.append(el("button", { class: "ghost", style: "margin-top:8px",
    onclick: () => { p.mirrors.push({ domain: "", account: "" }); view.focusLastMirror = true; persistProjects(); render(); } },
    "+ добавить домен"));

  // Основные действия
  const actions = el("div", { class: "actions" });
  if (view.busy) {
    actions.append(el("span", { class: "busy" }, el("span", { class: "spinner" }), view.busyMsg || "Работаю…"));
  } else {
    actions.append(
      el("button", { class: "primary big", onclick: doRunFull }, "Поднять новый домен"),
      el("button", { class: "big", onclick: doMigrate }, "Переезд зеркал"),
      el("button", { onclick: doCheck }, "Проверить статус"),
      el("button", { onclick: doYandexPrepare }, "Яндекс: подтвердить"),
      el("label", { class: "dry-toggle" },
        el("input", { type: "checkbox", ...(view.dryRun ? { checked: "checked" } : {}),
          onchange: (e) => { view.dryRun = e.target.checked; } }),
        "тест (dry-run)"));
  }
  card.append(actions);

  // Отдельные шаги
  if (!view.busy) {
    card.append(el("div", { class: "actions-steps" },
      el("span", { class: "label" }, "Отдельные шаги «Поднять новый домен» (для отладки и повторов):"),
      el("button", { class: "small", onclick: () => doStep("create-site", "Сайт в ISPmanager") }, "1. Сайт"),
      el("button", { class: "small", onclick: () => doStep("copy-files", "Копирование файлов") }, "2. Файлы"),
      el("button", { class: "small", onclick: () => doStep("cf-onboard", "Cloudflare онбординг") }, "3. Cloudflare"),
      el("button", { class: "small", onclick: () => doStep("ssl", "SSL (Let's Encrypt)") }, "4. SSL"),
      el("button", { class: "small", onclick: () => doStep("worker", "Воркер-роут") }, "5. Воркер")));
  }

  const log = renderLog(p);
  if (log) card.append(log);
  panel.append(card);

  if (view.focusLastMirror) {
    view.focusLastMirror = false;
    const inputs = panel.querySelectorAll(".mirror input");
    if (inputs.length) inputs[inputs.length - 1].focus();
  }
}

function render() { renderTabs(); renderPanel(); renderTokenStatus(); }

// ---------- действия ----------
function mirrorsOf(p) {
  return (p.mirrors || []).map((m) => normDomain(m.domain)).filter(Boolean);
}
function allOk(arr) { return arr.every((x) => x.ok); }

async function doRunFull() {
  const p = activeProject(); if (!p) return;
  if (!normDomain(p.new_domain)) return toast("Укажите новый домен", true);
  const dry = view.dryRun;
  if (!dry && !confirm(`Поднять новый домен ${normDomain(p.new_domain)}?\nСайт → файлы → Cloudflare → SSL → воркер.`)) return;
  setBusy(true, dry ? "Тест (dry-run)…" : "Поднимаю новый домен…");
  try {
    const res = await api("POST", "/api/run-full", { project: p, dry_run: dry });
    pushLog(p.id, { kind: "line", text: (dry ? "[ТЕСТ] " : "") + `Поднятие домена ${normDomain(p.new_domain)}:` });
    for (const s of res.results)
      pushLog(p.id, { kind: "line", cls: s.ok ? "s-ok" : "s-err", text: `  ${s.ok ? "✓" : "✗"} ${s.step} — ${s.message}` });
    toast(allOk(res.results) ? "Готово ✓" : "Завершено с ошибками — см. журнал", !allOk(res.results));
  } catch (e) { toast(e.message, true); } finally { setBusy(false); }
}

async function doStep(step, label) {
  const p = activeProject(); if (!p) return;
  const dry = view.dryRun;
  setBusy(true, `${label}…`);
  try {
    const r = await api("POST", "/api/step", { project: p, step, dry_run: dry });
    pushLog(p.id, { kind: "line", cls: r.ok ? "s-ok" : "s-err", text: `${r.ok ? "✓" : "✗"} ${label} — ${r.message}` });
  } catch (e) {
    pushLog(p.id, { kind: "line", cls: "s-err", text: `✗ ${label} — ${e.message}` });
    toast(e.message, true);
  } finally { setBusy(false); }
}

async function doMigrate() {
  const p = activeProject(); if (!p) return;
  if (!normDomain(p.new_domain)) return toast("Укажите новый домен", true);
  const mirrors = mirrorsOf(p);
  if (!mirrors.length) return toast("Добавьте хотя бы одно зеркало", true);
  const dry = view.dryRun;
  if (!dry && !confirm(`Поставить 301-редирект на ${normDomain(p.new_domain)} для ${mirrors.length} зеркал?`)) return;
  setBusy(true, dry ? "Тест переезда…" : "Ставлю редиректы…");
  try {
    const res = await api("POST", "/api/migrate", { project: p, dry_run: dry });
    pushLog(p.id, { kind: "line", text: (dry ? "[ТЕСТ] " : "") + `Переезд зеркал → ${res.new_domain}:` });
    for (const r of res.results)
      pushLog(p.id, { kind: "line", cls: r.ok ? "s-ok" : "s-err", text: `  ${r.ok ? "✓" : "✗"} ${r.domain} — ${r.message}` });
    if (!dry) statuses[p.id] = await api("POST", "/api/check", { project: p });
    toast(allOk(res.results) ? "Готово ✓" : "Есть ошибки — см. журнал", !allOk(res.results));
  } catch (e) { toast(e.message, true); } finally { setBusy(false); }
}

async function doCheck() {
  const p = activeProject(); if (!p) return;
  setBusy(true, "Проверяю статус…");
  try { statuses[p.id] = await api("POST", "/api/check", { project: p }); }
  catch (e) { toast(e.message, true); } finally { setBusy(false); }
}

async function doYandexPrepare() {
  const p = activeProject(); if (!p) return;
  if (!normDomain(p.new_domain)) return toast("Укажите новый домен", true);
  const method = p.verify || "dns";
  setBusy(true, "Яндекс: добавляю домен…");
  try {
    const prep = await api("POST", "/api/yandex/prepare", { project: p });
    if (prep.state === "VERIFIED") {
      pushLog(p.id, { kind: "line", cls: "s-ok", text: `Яндекс: права на ${prep.new_domain} уже подтверждены ✓` });
      toast("Права уже подтверждены ✓"); return;
    }
    if (method === "dns") {
      setBusy(true, "Яндекс: кладу TXT в Cloudflare и жду подтверждения (до 3 мин)…");
      reportVerify(p, await api("POST", "/api/yandex/verify", { project: p, method: "dns" }));
      return;
    }
    const m = (prep.methods || {})[method] || {};
    pushLog(p.id, { kind: "line", text: `Яндекс: подтверждение ${prep.new_domain} способом «${method}».` });
    if (method === "html") {
      pushLog(p.id, { kind: "line", text: `  Файл в корень сайта: ${m.filename}` });
      pushLog(p.id, { kind: "line", text: `  Содержимое: ${m.content}` });
      pushLog(p.id, { kind: "line", text: `  Проверка: ${m.url}` });
    } else {
      pushLog(p.id, { kind: "line", text: `  В <head> главной: ${m.tag}` });
    }
    pushLog(p.id, { kind: "verifyBtn", method });
  } catch (e) { toast(e.message, true); } finally { setBusy(false); }
}

async function doYandexVerify(method) {
  const p = activeProject();
  setBusy(true, "Яндекс: проверяю права (до 3 мин)…");
  try { reportVerify(p, await api("POST", "/api/yandex/verify", { project: p, method })); }
  catch (e) { toast(e.message, true); } finally { setBusy(false); }
}

function reportVerify(p, r) {
  if (r.state === "VERIFIED") {
    pushLog(p.id, { kind: "line", cls: "s-ok", text: "Яндекс: права подтверждены ✓ — далее шаг «Переезд» в Вебмастере (вручную)." });
    toast("Права подтверждены ✓");
  } else if (r.state === "PENDING") {
    pushLog(p.id, { kind: "line", cls: "s-warn", text: "Яндекс: пока не подтверждено — запись могла не примениться, попробуйте ещё раз." });
    toast("Пока не подтверждено", true);
  } else {
    pushLog(p.id, { kind: "line", cls: "s-err", text: "Яндекс: " + (r.message || r.state) });
    toast(r.message || "Ошибка подтверждения", true);
  }
}

// ---------- статус токенов ----------
function renderTokenStatus() {
  const s = state.settings || {};
  const badge = $("#token-status");
  const accs = (s.cf_accounts || []).length;
  const ok = accs > 0 && s.ssh && s.ssh.host;
  badge.textContent = ok ? `CF: ${accs} акк. · сервер ✓` : "настройки не заполнены";
  badge.className = "badge " + (ok ? "ok" : "err");
}

// ---------- настройки ----------
function accountRow(acc) {
  acc = acc || { name: "", has_token: false, has_account_id: false, has_spaceship: false };
  const ph = (set, txt) => (set ? "задан — пусто=без изменений" : txt);
  return el("div", { class: "account-row" },
    el("label", {}, "Название аккаунта",
      el("input", { class: "acc-name", type: "text", value: acc.name || "", placeholder: "casino-stand" })),
    el("label", {}, "CF API-токен",
      el("input", { class: "acc-token", type: "password", autocomplete: "off", placeholder: ph(acc.has_token, "токен") })),
    el("label", {}, "account_id",
      el("input", { class: "acc-aid", type: "password", autocomplete: "off", placeholder: ph(acc.has_account_id, "account_id") })),
    el("div", { class: "two" },
      el("label", {}, "Spaceship key",
        el("input", { class: "acc-spk", type: "password", autocomplete: "off", placeholder: ph(acc.has_spaceship, "key") })),
      el("label", {}, "Spaceship secret",
        el("input", { class: "acc-sps", type: "password", autocomplete: "off", placeholder: ph(acc.has_spaceship, "secret") }))),
    el("button", { class: "row-del ghost small", onclick: (e) => e.target.closest(".account-row").remove() }, "Удалить аккаунт"));
}

function renderAccounts() {
  const box = $("#accounts");
  box.replaceChildren();
  const accs = state.settings.cf_accounts || [];
  if (accs.length) accs.forEach((a) => box.append(accountRow(a)));
  else box.append(accountRow(null));
}

function openSettings() {
  const s = state.settings || {};
  const ssh = s.ssh || {};
  $("#ssh-host").value = ssh.host || "";
  $("#ssh-port").value = ssh.port || "22";
  $("#ssh-user").value = ssh.user || "";
  $("#ispmgr-user").value = ssh.ispmgr_user || "";
  $("#ispmgr-host").value = ssh.ispmgr_host || "";
  $("#ssh-email").value = ssh.email || "";
  $("#server-ip").value = s.server_ip || "";
  ["ssh-password", "ispmgr-password", "ya-token"].forEach((id) => { $("#" + id).value = ""; });
  $("#ssh-password").placeholder = ssh.has_password ? "задан — пусто=без изменений" : "пароль";
  $("#ispmgr-password").placeholder = ssh.has_ispmgr_password ? "задан — пусто=без изменений" : "пароль";
  $("#ya-token").placeholder = s.has_yandex_token ? "задан — пусто=без изменений" : "OAuth-токен";
  renderAccounts();
  $("#settings").classList.remove("hidden");
}
function closeSettings() { $("#settings").classList.add("hidden"); }

function collectSettings() {
  const accounts = [...document.querySelectorAll(".account-row")].map((row) => ({
    name: $(".acc-name", row).value,
    api_token: $(".acc-token", row).value,
    account_id: $(".acc-aid", row).value,
    spaceship_api_key: $(".acc-spk", row).value,
    spaceship_api_secret: $(".acc-sps", row).value,
  })).filter((a) => a.name.trim());
  return {
    cf_accounts: accounts,
    ssh: {
      host: $("#ssh-host").value, port: $("#ssh-port").value, user: $("#ssh-user").value,
      password: $("#ssh-password").value, ispmgr_user: $("#ispmgr-user").value,
      ispmgr_password: $("#ispmgr-password").value, ispmgr_host: $("#ispmgr-host").value,
      email: $("#ssh-email").value,
    },
    server_ip: $("#server-ip").value,
    yandex_token: $("#ya-token").value,
  };
}

async function saveSettings() {
  try {
    state.settings = await api("POST", "/api/settings", { settings: collectSettings() });
    closeSettings();
    render();
    toast("Настройки сохранены");
  } catch (e) { toast(e.message, true); }
}

// ---------- старт ----------
async function init() {
  $("#btn-settings").addEventListener("click", openSettings);
  $("#settings-cancel").addEventListener("click", closeSettings);
  $("#settings-save").addEventListener("click", saveSettings);
  $("#add-account").addEventListener("click", () => $("#accounts").append(accountRow(null)));

  try {
    const data = await api("GET", "/api/state");
    state.projects = data.projects || [];
    state.settings = data.settings || {};
  } catch (e) { toast("Не удалось загрузить данные: " + e.message, true); }

  if (!state.projects.length) addProject();
  else render();

  if (!(state.settings.cf_accounts || []).length) openSettings();
}

init();
