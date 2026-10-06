#!/usr/bin/env node
/**
 * Правило кэша преленда во всех зонах аккаунта — Cloudflare API.
 *
 * Ставит одно правило: путь начинается с /p/ → кэшировать на эдже с заданным TTL.
 * Страница преленда статическая и одинаковая для всех (параметры уезжают во
 * фрагмент после #, в адресе их нет), поэтому её должен отдавать эдж, а не наш
 * Apache.
 *
 * Правила кэша в Cloudflare хранятся одним списком на зону, и API принимает его
 * целиком. Поэтому скрипт сперва читает существующий список и дописывает своё
 * правило в конец, а не затирает: в зонах уже могут быть чужие правила.
 * Повторный запуск не плодит дубли — правило опознаётся по description и
 * обновляется на месте.
 *
 * Запуск:
 *   CF_TOKEN=... node cf-cache-rule.mjs              # проверка, ничего не меняет
 *   CF_TOKEN=... node cf-cache-rule.mjs --apply      # боевой прогон
 *   CF_TOKEN=... node cf-cache-rule.mjs --apply --zones a.top,b.top
 *   CF_TOKEN=... node cf-cache-rule.mjs --apply --ttl 3600
 *
 * Токен: My Profile → API Tokens → Create Token → Custom token, права
 *   Zone → Zone → Read          (увидеть список зон)
 *   Zone → Cache Rules → Edit   (в части интерфейсов называется Zone Ruleset)
 * и Zone Resources → Include → All zones from an account.
 */

const TOKEN = process.env.CF_TOKEN || '';
const API   = 'https://api.cloudflare.com/client/v4';
const DESC  = 'preland-cache';           // по нему правило узнаётся при повторном запуске

const args  = process.argv.slice(2);
const APPLY = args.includes('--apply');
const TTL   = Number((args[args.indexOf('--ttl') + 1] || 0)) || 300;
const ONLY  = (args.includes('--zones') ? args[args.indexOf('--zones') + 1] : '')
  .split(/[\s,;]+/).map(s => s.trim().toLowerCase()).filter(Boolean);

const RULE = {
  description: DESC,
  expression: 'starts_with(http.request.uri.path, "/p/")',
  action: 'set_cache_settings',
  action_parameters: {
    cache: true,
    edge_ttl: { mode: 'override_origin', default: TTL },
  },
  enabled: true,
};

if (!TOKEN) {
  console.error('нет токена: CF_TOKEN=... node cf-cache-rule.mjs');
  process.exit(1);
}

const api = async (path, opts = {}) => {
  const res = await fetch(API + path, {
    ...opts,
    headers: { authorization: 'Bearer ' + TOKEN, 'content-type': 'application/json', ...(opts.headers || {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!body.success) {
    const msg = (body.errors || []).map(e => `${e.code} ${e.message}`).join('; ') || ('HTTP ' + res.status);
    throw new Error(msg);
  }
  return body.result;
};

const zones = async () => {
  const out = [];
  for (let page = 1; ; page++) {
    const r = await api(`/zones?per_page=50&page=${page}`);
    out.push(...r);
    if (r.length < 50) break;
  }
  return out;
};

(async () => {
  console.log(APPLY ? `БОЕВОЙ РЕЖИМ · TTL ${TTL}с` : `ПРОВЕРКА (ничего не меняется) · TTL ${TTL}с`);

  let list;
  try { list = await zones(); }
  catch (e) { return console.error('не удалось получить список зон:', e.message); }

  if (ONLY.length) list = list.filter(z => ONLY.includes(z.name.toLowerCase()));
  console.log('зон в работе:', list.length);

  let added = 0, updated = 0, same = 0, failed = 0;

  for (const [i, z] of list.entries()) {
    const nom = `${i + 1}/${list.length} ${z.name}`;
    try {
      // список правил кэша зоны. Его может не быть вовсе — тогда начинаем с пустого.
      let rules = [];
      try {
        const ep = await api(`/zones/${z.id}/rulesets/phases/http_request_cache_settings/entrypoint`);
        rules = ep.rules || [];
      } catch (e) {
        if (!/10000|not found|404/i.test(e.message)) throw e;
      }

      const idx  = rules.findIndex(r => r.description === DESC);
      const cur  = idx >= 0 ? rules[idx] : null;
      const sameAlready = cur
        && cur.expression === RULE.expression
        && cur.enabled === true
        && cur.action === RULE.action
        && cur.action_parameters?.edge_ttl?.default === TTL;

      if (sameAlready) { same++; console.log(`${nom} — уже стоит`); continue; }

      // Чужие правила сохраняем как есть: отправляется весь список целиком,
      // и потерять их было бы легко.
      const next = rules.map(r => ({
        description: r.description, expression: r.expression, action: r.action,
        action_parameters: r.action_parameters, enabled: r.enabled,
      }));
      if (idx >= 0) next[idx] = { ...RULE }; else next.push({ ...RULE });

      if (!APPLY) {
        (idx >= 0 ? updated++ : added++);
        console.log(`${nom} — ${idx >= 0 ? 'БУДЕТ обновлено' : 'БУДЕТ добавлено'} (своих правил в зоне: ${rules.length})`);
        continue;
      }

      await api(`/zones/${z.id}/rulesets/phases/http_request_cache_settings/entrypoint`, {
        method: 'PUT',
        body: JSON.stringify({ rules: next }),
      });
      (idx >= 0 ? updated++ : added++);
      console.log(`${nom} — ${idx >= 0 ? 'обновлено' : 'добавлено'}`);
    } catch (e) {
      failed++;
      console.log(`${nom} — ошибка: ${e.message}`);
    }
  }

  console.log(`\nИТОГО: добавлено ${added}, обновлено ${updated}, уже стояло ${same}, ошибок ${failed}`);
  if (!APPLY) console.log('это была проверка — повтори с --apply');
})();
