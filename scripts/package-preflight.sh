#!/usr/bin/env bash
# Пред-полётная проверка перед сборкой релиза Pipboy.
# Синхронизирует фронт в бандл iOS, прогоняет тесты, печатает чек-лист безопасности.
# Запуск из корня репозитория:  bash scripts/package-preflight.sh
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="app/public"
IOS="native/Pipboy iOS/public"
fail=0

echo "── Pipboy · pre-flight упаковки ───────────────────────────────"

# 1) Фронт в бандле iOS должен совпадать с app/public (иначе уедет старый UI)
echo "1) сверяю фронт app/public ↔ бандл iOS…"
if [ ! -d "$IOS" ]; then
  echo "   ⚠ нет каталога '$IOS' — добавь public/ в таргет iOS (folder reference)"; fail=1
else
  if diff -qr "$SRC" "$IOS" >/dev/null 2>&1; then
    echo "   ✓ совпадает"
  else
    echo "   • расхождения — синхронизирую app/public → бандл iOS:"
    diff -qr "$SRC" "$IOS" 2>/dev/null | sed 's/^/     /' || true
    rsync -a --delete "$SRC"/ "$IOS"/ 2>/dev/null || cp -R "$SRC"/. "$IOS"/
    echo "   ✓ синхронизировано (пересобери iOS-таргет, чтобы попало в бандл)"
  fi
fi

# 2) Тесты Node (логика API)
echo "2) тесты app/test…"
if ( cd app && node --test test/*.test.mjs >/tmp/pipboy-tests.log 2>&1 ); then
  echo "   ✓ $(grep -E '# pass' /tmp/pipboy-tests.log | head -1 | tr -dc '0-9') тестов прошли"
else
  echo "   ✗ тесты упали — см. /tmp/pipboy-tests.log"; fail=1
fi

# 3) Синтаксис фронта
echo "3) синтаксис JS…"
if for f in "$SRC"/*.js; do node --check "$f" || exit 1; done; then
  echo "   ✓ чисто"
else
  echo "   ✗ синтаксическая ошибка во фронте"; fail=1
fi

# 4) Напоминания, которые скрипт проверить не может — только глазами в Xcode
cat <<'EOF'
4) проверь вручную в Xcode (release-конфиг):
   □ SQLCipher привязан к ОБОИМ таргетам → Database.sqlcipherActive == true
     (иначе база НЕ шифруется — главный пункт безопасности)
   □ macOS: Hardened Runtime = YES, если будешь нотаризовать .app
   □ macOS: public/ добавлен в Copy Bundle Resources (folder reference),
     чтобы .app работал не только на твоём Mac с клоном в ~/Downloads/cladue
   □ версии: CFBundleShortVersionString / CURRENT_PROJECT_VERSION подняты
   □ оба устройства обновляются вместе (SAS-гейт; см. docs/SECURITY-REVIEW.md)
EOF

echo "───────────────────────────────────────────────────────────────"
[ "$fail" = 0 ] && echo "PRE-FLIGHT OK" || { echo "PRE-FLIGHT С ОШИБКАМИ — поправь выше"; exit 1; }
