#!/usr/bin/env bash
# oformit7.sh <вход: папка с комплектами> <выход> [номер первой темы]
set -eu
E=$(cd "$(dirname "$0")" && pwd); IN=$1; OUT=$2; START=${3:-1}
mkdir -p "$OUT"
printf '# Темы (система «витрина»)\n\n| Комплект | Тема | Палитра | Заголовки | Форма | Слоты | Картинки | Сюжет | Раскладка | Метка | Шрифт |\n|---|---:|---|---|---|---|---|---|---|---|---|\n' > "$OUT/темы.md"
i=0
for kit in "$IN"/*/; do
  name=$(basename "$kit"); n=$((START+i)); i=$((i+1)); seed=$((9000+n*31))
  dst="$OUT/$name"; rm -rf "$dst"; mkdir -p "$dst"; cp "$kit"/*.html "$dst"/
  php "$E/kartinki7.php" "$dst" --тема=$n --сид=$seed >/dev/null
  php "$E/stili7.php" "$dst" --тема=$n >/dev/null
  php -r "require '$E/temy7.php'; \$t=v7Tema($n);
    printf('| %s | %d | %s | %s | %s | %s | %s | %d | %s | %s | %s |'.PHP_EOL, '$name', \$t['номер'], \$t['палитра'], \$t['заголовок'], \$t['форма'], \$t['слот'], \$t['картинка'], \$t['сюжет'], \$t['раскладка'], \$t['метка'], \$t['шрифт']);" >> "$OUT/темы.md"
done
echo "комплектов: $i"
python3 - "$OUT" <<'PY'
import os, re, sys
OUT = sys.argv[1]
ШАБЛОН = re.compile(r'^[a-z0-9_-]+_img_\d+\.webp$')
комплектов = картинок = ошибок = 0
for site in sorted(os.listdir(OUT)):
    d = os.path.join(OUT, site)
    if not os.path.isdir(d): continue
    комплектов += 1
    имена = set(os.listdir(os.path.join(d, 'images'))) if os.path.isdir(os.path.join(d, 'images')) else set()
    картинок += len(имена)
    ссылки = set()
    for f in os.listdir(d):
        if not f.endswith('.html'): continue
        стр = f[:-5]
        t = open(os.path.join(d, f), encoding='utf-8').read()
        for m in re.findall(r'images/([\w.-]+\.webp)', t):
            ссылки.add(m)
            if not ШАБЛОН.match(m) or not m.startswith(стр + '_img_'):
                print('  ОШИБКА имени:', site, f, m); ошибок += 1
    for x in имена - ссылки:
        print('  лишняя картинка:', site, x); ошибок += 1
    for x in ссылки - имена:
        print('  нет файла:', site, x); ошибок += 1
    if not os.path.exists(os.path.join(d, 'main.html')):
        print('  нет main.html:', site); ошибок += 1
print('комплектов %d, картинок %d, ошибок %d' % (комплектов, картинок, ошибок))
PY
