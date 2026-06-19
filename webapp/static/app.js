"use strict";

// ---------- маленькие помощники ----------
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
  toastTimer = setTimeout(() => t.classList.add("hidden"), 4500);
}

// ---------- состояние ----------
const state = { projects: [], active: 0, settings: {} };
const statuses = {};   // pid -> результат /api/check
const logs = {};       // pid -> массив записей лога
const view = { busy: false, busyMsg: "", focusLastMirror: false };

function activeProject() { return state.projects[state.active] || null; }

let saveTimer;
function persistProjects() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    api("POST", "/api/projects", { projects: state.projects }).catch((e) => toast(e.message, true));
  }, 400);
}

function setBusy(on, msg = "") {
  view.busy = on;
  view.busyMsg = msg;
  render();
}

function pushLog(pid, entry) {
  (logs[pid] = logs[pid] || []).push(entry);
}

// ---------- вкладки ----------
function renderTabs() {
  const nav = $("#tabs");
  nav.replaceChildren();
  state.projects.forEach((p, i) => {
    const tab = el("div", { class: "tab" + (i === state.active ? " active" : ""),
                            onclick: () => { state.active = i; render(); } },
      el("span", { class: "name" }, p.name || "Без названия"),
      el("button", { class: "x", title: "Удалить проект", onclick: (e) => { e.stopPropagation(); deleteProject(i); } }, "×"),
    );
    nav.append(tab);
  });
  nav.append(el("button", { class: "tab-add", title: "Новый проект", onclick: addProject }, "+"));
}

function addProject() {
  const p = { id: "p_" + Date.now(), name: "Проект " + (state.projects.length + 1),
              new_domain: "", verify: "dns", mirrors: [""] };
  state.projects.push(p);
  state.active = state.projects.length - 1;
  persistProjects();
  render();
}

function deleteProject(i) {
  const p = state.projects[i];
  if (!confirm(`Удалить проект «${p.name}»? Домены в Cloudflare и Яндексе это не затронет.`)) return;
  delete statuses[p.id];
  delete logs[p.id];
  state.projects.splice(i, 1);
  if (state.active >= state.projects.length) state.active = Math.max(0, state.projects.length - 1);
  persistProjects();
  render();
}

// ---------- панель проекта ----------
function statusNode(domain) {
  const p = activeProject();
  const st = statuses[p.id];
  const d = normDomain(domain);
  if (!st || !d) return el("span", { class: "status" }, d ? "не проверено" : "");
  const row = (st.mirrors || []).find((m) => m.domain === d);
  if (!row) return el("span", { class: "status" }, "не проверено");
  if (row.error) return el("span", { class: "status" }, el("span", { class: "s-err" }, "ошибка проверки"));
  const zone = row.zone
    ? el("span", { class: "s-ok" }, "зона ✓")
    : el("span", { class: "s-err" }, "нет в Cloudflare");
  let redir;
  if (!row.zone) redir = "";
  else if (row.ok) redir = el("span", { class: "s-ok" }, " · редирект ✓");
  else if (row.redirect) redir = el("span", { class: "s-warn" }, ` · → ${row.redirect}`);
  else redir = el("span", { class: "muted" }, " · редирект —");
  return el("span", { class: "status" }, zone, redir);
}

function mirrorRow(p, i) {
  const input = el("input", { type: "text", value: p.mirrors[i] || "",
                              placeholder: "старое зеркало, напр. old-site.ru",
                              oninput: (e) => { p.mirrors[i] = e.target.value; persistProjects(); } });
  return el("div", { class: "mirror" },
    input,
    statusNode(p.mirrors[i]),
    el("button", { class: "x", title: "Убрать домен",
                   onclick: () => { p.mirrors.splice(i, 1); if (!p.mirrors.length) p.mirrors.push(""); persistProjects(); render(); } }, "×"),
  );
}

function renderLog(p) {
  const entries = logs[p.id] || [];
  if (!entries.length) return null;
  const box = el("div", { class: "log" }, el("h4", {}, "Журнал"));
  for (const e of entries) {
    if (e.kind === "verifyBtn") {
      box.append(el("div", { class: "line" },
        el("button", { class: "primary", onclick: () => doYandexVerify(e.method) },
          "Я разместил — проверить права")));
    } else {
      box.append(el("div", { class: "line " + (e.cls || "") }, e.text));
    }
  }
  return box;
}

function renderPanel() {
  const panel = $("#panel");
  panel.replaceChildren();
  const p = activeProject();
  if (!p) {
    panel.append(el("div", { class: "empty" },
      el("p", {}, "Пока нет проектов."),
      el("button", { class: "primary", onclick: addProject }, "Создать проект")));
    return;
  }

  const card = el("div", { class: "card" });

  // Имя проекта
  card.append(el("div", { class: "field" },
    el("label", {}, "Название проекта"),
    el("input", { type: "text", value: p.name || "",
                  oninput: (e) => { p.name = e.target.value; persistProjects(); renderTabs(); } })));

  // Новый домен + способ подтверждения
  card.append(el("div", { class: "field" },
    el("label", {}, "Новый (актуальный) домен"),
    el("input", { type: "text", value: p.new_domain || "", placeholder: "new-site.ru",
                  oninput: (e) => { p.new_domain = e.target.value; persistProjects(); } })));

  card.append(el("div", { class: "field" },
    el("label", {}, "Подтверждение прав в Яндексе"),
    (() => {
      const sel = el("select", { onchange: (e) => { p.verify = e.target.value; persistProjects(); } },
        el("option", { value: "dns" }, "DNS — автоматически через Cloudflare"),
        el("option", { value: "html" }, "HTML-файл — загрузить на хостинг вручную"),
        el("option", { value: "meta" }, "Мета-тег — добавить на главную вручную"));
      sel.value = p.verify || "dns";
      return sel;
    })()));

  // Зеркала
  card.append(el("div", { class: "section-title" }, "Старые зеркала (откуда редирект)"));
  const list = el("div", {});
  p.mirrors.forEach((_, i) => list.append(mirrorRow(p, i)));
  card.append(list);
  card.append(el("button", { class: "ghost", style: "margin-top:8px",
    onclick: () => { p.mirrors.push(""); view.focusLastMirror = true; persistProjects(); render(); } }, "+ добавить домен"));

  // Кнопки
  const actions = el("div", { class: "actions" });
  if (view.busy) {
    actions.append(el("span", { class: "busy" }, el("span", { class: "spinner" }), view.busyMsg || "Работаю…"));
  } else {
    actions.append(
      el("button", { onclick: doCheck }, "Проверить статус"),
      el("button", { class: "primary big", onclick: doMigrate }, "ПЕРЕЕЗД: все зеркала → новый"),
      el("button", { onclick: doYandexPrepare }, "Яндекс: подтвердить новый домен"),
    );
  }
  card.append(actions);

  const log = renderLog(p);
  if (log) card.append(log);

  panel.append(card);

  if (view.focusLastMirror) {
    view.focusLastMirror = false;
    const inputs = panel.querySelectorAll(".mirror input");
    if (inputs.length) inputs[inputs.length - 1].focus();
  }
}

function render() {
  renderTabs();
  renderPanel();
  renderTokenStatus();
}

// ---------- действия ----------
async function doCheck() {
  const p = activeProject();
  if (!p) return;
  setBusy(true, "Проверяю статус в Cloudflare…");
  try {
    statuses[p.id] = await api("POST", "/api/check", { project: p });
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(false);
  }
}

async function doMigrate() {
  const p = activeProject();
  if (!p) return;
  if (!normDomain(p.new_domain)) return toast("Сначала укажите новый домен", true);
  const mirrors = p.mirrors.map(normDomain).filter(Boolean);
  if (!mirrors.length) return toast("Добавьте хотя бы одно зеркало", true);
  if (!confirm(`Поставить 301-редирект на ${normDomain(p.new_domain)} для зеркал:\n${mirrors.join("\n")}`)) return;

  setBusy(true, "Ставлю редиректы в Cloudflare…");
  try {
    const res = await api("POST", "/api/migrate", { project: p });
    pushLog(p.id, { kind: "line", cls: "", text: `Переезд на ${res.new_domain}:` });
    for (const r of res.results) {
      pushLog(p.id, { kind: "line", cls: r.ok ? "s-ok" : "s-err",
                      text: `  ${r.ok ? "✓" : "✗"} ${r.domain} — ${r.message}` });
    }
    statuses[p.id] = await api("POST", "/api/check", { project: p });
    toast("Готово. Не забудьте шаг «Переезд» в Яндекс.Вебмастере (вручную).");
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(false);
  }
}

async function doYandexPrepare() {
  const p = activeProject();
  if (!p) return;
  if (!normDomain(p.new_domain)) return toast("Сначала укажите новый домен", true);
  const method = p.verify || "dns";

  setBusy(true, "Яндекс: добавляю домен…");
  try {
    const prep = await api("POST", "/api/yandex/prepare", { project: p });
    if (prep.state === "VERIFIED") {
      pushLog(p.id, { kind: "line", cls: "s-ok", text: `Яндекс: права на ${prep.new_domain} уже подтверждены ✓` });
      toast("Права уже подтверждены ✓");
      return;
    }
    if (method === "dns") {
      setBusy(true, "Яндекс: кладу TXT в Cloudflare и жду подтверждения (до 3 мин)…");
      const r = await api("POST", "/api/yandex/verify", { project: p, method: "dns" });
      reportVerify(p, r);
      return;
    }
    // html / meta — показать, что разместить, и кнопку «Проверить»
    const m = prep.methods[method] || {};
    pushLog(p.id, { kind: "line", text: `Яндекс: подтверждение домена ${prep.new_domain} способом «${method}».` });
    if (method === "html") {
      pushLog(p.id, { kind: "line", text: `  Загрузите в корень сайта файл ${m.filename}` });
      pushLog(p.id, { kind: "line", text: `  Содержимое: ${m.content}` });
      pushLog(p.id, { kind: "line", text: `  Проверка доступности: ${m.url}` });
    } else {
      pushLog(p.id, { kind: "line", text: `  Добавьте в <head> главной страницы: ${m.tag}` });
    }
    pushLog(p.id, { kind: "verifyBtn", method });
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(false);
  }
}

async function doYandexVerify(method) {
  const p = activeProject();
  setBusy(true, "Яндекс: проверяю права (до 3 мин)…");
  try {
    const r = await api("POST", "/api/yandex/verify", { project: p, method });
    reportVerify(p, r);
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(false);
  }
}

function reportVerify(p, r) {
  if (r.state === "VERIFIED") {
    pushLog(p.id, { kind: "line", cls: "s-ok", text: "Яндекс: права подтверждены ✓ — теперь шаг «Переезд» в Вебмастере (вручную)." });
    toast("Права подтверждены ✓");
  } else if (r.state === "PENDING") {
    pushLog(p.id, { kind: "line", cls: "s-warn", text: "Яндекс: пока не подтверждено. Запись могла не успеть примениться — нажмите «Проверить» ещё раз." });
    toast("Пока не подтверждено — попробуйте ещё раз", true);
  } else {
    pushLog(p.id, { kind: "line", cls: "s-err", text: "Яндекс: " + (r.message || r.state) });
    toast(r.message || "Ошибка подтверждения", true);
  }
}

// ---------- токены ----------
function renderTokenStatus() {
  const s = state.settings || {};
  const badge = $("#token-status");
  if (s.cloudflare && s.yandex) { badge.textContent = "токены: CF ✓ · Я ✓"; badge.className = "badge ok"; }
  else { badge.textContent = "токены не настроены"; badge.className = "badge err"; }
}

function openSettings() {
  $("#cf-token").value = "";
  $("#ya-token").value = "";
  $("#settings").classList.remove("hidden");
}
function closeSettings() { $("#settings").classList.add("hidden"); }

async function saveSettings() {
  try {
    state.settings = await api("POST", "/api/settings", {
      cloudflare_token: $("#cf-token").value,
      yandex_token: $("#ya-token").value,
    });
    closeSettings();
    renderTokenStatus();
    toast("Токены сохранены");
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------- старт ----------
async function init() {
  $("#btn-settings").addEventListener("click", openSettings);
  $("#settings-cancel").addEventListener("click", closeSettings);
  $("#settings-save").addEventListener("click", saveSettings);

  try {
    const data = await api("GET", "/api/state");
    state.projects = data.projects || [];
    state.settings = data.settings || {};
  } catch (e) {
    toast("Не удалось загрузить данные: " + e.message, true);
  }
  if (!state.projects.length) addProject();
  else render();
  if (!state.settings.cloudflare || !state.settings.yandex) openSettings();
}

init();
