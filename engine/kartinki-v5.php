<?php
/**
 * Картинки к комплекту v5: рисует по две иллюстрации на страницу
 * и вшивает <img> в разметку. Имена файлов — {страница}_img_{N}.webp,
 * в HTML подставляется голое имя файла.
 *
 * php engine/kartinki-v5.php <папка> [--сид=N]
 */

$папка = null; $сид = 1;
foreach (array_slice($argv, 1) as $а) {
    if (preg_match('~^--сид=(\d+)$~u', $а, $m)) { $сид = (int) $m[1]; continue; }
    if ($а[0] !== '-') { $папка = rtrim($а, '/'); }
}
if ($папка === null || !is_dir($папка)) {
    fwrite(STDERR, "usage: php engine/kartinki-v5.php <папка> [--сид=N]\n"); exit(1);
}

const ШИР = 1200, ВЫС = 630;
$шрифт = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf';
$шрифтТонкий = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';

/**
 * Тема страницы: базовый тон, два мотива, три варианта подписей и alt.
 * Вариант выбирается сидом, поэтому наборы не повторяют друг друга.
 */
$ТЕМЫ = [
'main' => [212, ['барабаны','лента'], [
    ['Игровая витрина', 'Каталог и live-раздел'],
    ['Что внутри', 'Слоты, столы, турниры'],
    ['Стартовый экран', 'Разделы и навигация']], [
    ['главная витрина казино %brand_name_ru% с каталогом игр', 'схема разделов сайта %brand_name_ru%'],
    ['каталог игр %brand_name_ru%: слоты, столы и live', 'лента турниров и акций на главной странице'],
    ['навигация по разделам %brand_name_ru%', 'обзор стартового экрана площадки']]],

'obzor' => [268, ['диаграмма','щит'], [
    ['Разбор площадки', 'Выплаты, правила, поддержка'],
    ['По каким критериям', 'Скорость, честность, сервис'],
    ['Что проверять', 'Лицензия и условия вывода']], [
    ['обзор казино %brand_name_ru%: на что смотреть при выборе', 'сравнение скорости выплат и условий отыгрыша'],
    ['критерии оценки площадки %brand_name_ru%', 'показатели надёжности и работы поддержки'],
    ['проверка условий вывода средств в %brand_name_ru%', 'разбор лицензии и правил площадки']]],

'promo' => [340, ['купон','монеты'], [
    ['Промокоды', 'Условия и сроки действия'],
    ['Акции недели', 'Где искать актуальный код'],
    ['Купоны и бонусы', 'Читай мелкий шрифт']], [
    ['промокоды и акции казино %brand_name_ru%', 'как проверить срок действия промокода'],
    ['актуальные акции недели в %brand_name_ru%', 'где публикуют свежие промокоды'],
    ['купоны и бонусные предложения %brand_name_ru%', 'условия отыгрыша по промокоду']]],

'news' => [196, ['лента','график'], [
    ['Новости и турниры', 'Анонсы по датам'],
    ['Что нового', 'Обновления и события'],
    ['Афиша турниров', 'Призовые и расписание']], [
    ['лента новостей и анонсов турниров %brand_name_ru%', 'календарь турнирных анонсов'],
    ['свежие обновления и события %brand_name_ru%', 'график публикации новостей площадки'],
    ['афиша турниров %brand_name_ru% с расписанием', 'призовые фонды и даты проведения']]],

'info' => [186, ['щит','форма'], [
    ['Правила и лицензия', 'Верификация и лимиты'],
    ['Безопасность', 'Документы и проверки'],
    ['Как всё устроено', 'Правила, KYC, поддержка']], [
    ['лицензия и правила площадки %brand_name_ru%', 'этапы верификации аккаунта перед выводом'],
    ['защита данных игроков в %brand_name_ru%', 'какие документы просят при проверке'],
    ['порядок работы площадки %brand_name_ru%', 'правила, верификация и обращение в поддержку']]],

'partnery' => [154, ['график','диаграмма'], [
    ['Партнёрская программа', 'Трафик и отчисления'],
    ['Доход партнёра', 'От чего зависит процент'],
    ['Статистика в кабинете', 'Клики, депозиты, выплаты']], [
    ['партнёрская программа %brand_name_ru%: схема отчислений', 'статистика по кликам, депозитам и доходу'],
    ['как формируется доход партнёра %brand_name_ru%', 'зависимость процента от качества трафика'],
    ['кабинет партнёра %brand_name_ru% со статистикой', 'отчёт по кликам, регистрациям и выплатам']]],

'app' => [228, ['телефон','форма'], [
    ['Мобильное приложение', 'Android и iOS'],
    ['Игра с телефона', 'Установка и вход'],
    ['Приложение', 'Те же игры и выплаты']], [
    ['мобильное приложение %brand_name_ru% на Android и iOS', 'экран приложения со списком игр'],
    ['установка приложения %brand_name_ru% на телефон', 'вход в аккаунт через мобильное приложение'],
    ['интерфейс приложения %brand_name_ru%', 'разделы игр и касса в мобильной версии']]],

'bonus' => [42, ['монеты','купон'], [
    ['Бонусы', 'Вейджер и отыгрыш'],
    ['Подарок к депозиту', 'Процент и условия'],
    ['Бонусный баланс', 'Путь до вывода']], [
    ['бонусы и вейджер в казино %brand_name_ru%', 'как считается отыгрыш бонусного баланса'],
    ['подарок к первому депозиту в %brand_name_ru%', 'процент бонуса и требования по отыгрышу'],
    ['бонусный баланс %brand_name_ru%', 'путь от начисления бонуса до выплаты']]],

'registracia' => [174, ['форма','ключ'], [
    ['Регистрация', 'Почта, телефон, пароль'],
    ['Создать аккаунт', 'Минута на всё'],
    ['Анкета игрока', 'Что заполнять на старте']], [
    ['форма регистрации аккаунта в %brand_name_ru%', 'шаги создания аккаунта и подтверждения почты'],
    ['создание аккаунта в %brand_name_ru% за минуту', 'подтверждение телефона при регистрации'],
    ['поля анкеты при регистрации в %brand_name_ru%', 'что заполнять перед первым депозитом']]],

'slots' => [284, ['барабаны','диаграмма'], [
    ['Слоты', 'RTP и волатильность'],
    ['Барабаны и линии', 'Как читать характеристики'],
    ['Автоматы', 'Отдача на дистанции']], [
    ['игровые автоматы %brand_name_ru% с показателем RTP', 'барабаны слота и линии выплат'],
    ['характеристики слотов в %brand_name_ru%', 'волатильность и частота выплат автомата'],
    ['каталог автоматов %brand_name_ru%', 'показатель отдачи на длинной дистанции']]],

'vhod' => [206, ['ключ','телефон'], [
    ['Вход в кабинет', 'Логин и восстановление'],
    ['Доступ к аккаунту', 'Пароль и подтверждение'],
    ['Личный кабинет', 'Баланс, история, касса']], [
    ['вход в личный кабинет %brand_name_ru%', 'форма входа и восстановление доступа'],
    ['доступ к аккаунту %brand_name_ru%', 'подтверждение входа и смена пароля'],
    ['личный кабинет игрока %brand_name_ru%', 'баланс, история ставок и раздел кассы']]],

'zerkalo' => [16, ['зеркало','щит'], [
    ['Рабочее зеркало', 'Запасной адрес входа'],
    ['Если сайт не грузится', 'Тот же аккаунт, другой адрес'],
    ['Зеркало', 'Как отличить официальное']], [
    ['рабочее зеркало казино %brand_name_ru%', 'схема доступа через запасной адрес'],
    ['вход через зеркало %brand_name_ru% при блокировке', 'аккаунт и баланс на запасном адресе'],
    ['официальное зеркало %brand_name_ru%', 'как отличить настоящий адрес от подделки']]],
];

/* ───────────────────────── цвет и холст ───────────────────────── */

const S = 2;                       // рисуем вдвое крупнее и ужимаем — так нет лесенки

function hsl(float $h, float $s, float $l): array {
    $h = fmod(fmod($h, 360) + 360, 360) / 360;
    $q = $l < 0.5 ? $l * (1 + $s) : $l + $s - $l * $s;
    $p = 2 * $l - $q;
    $к = function ($t) use ($p, $q) {
        if ($t < 0) $t += 1; if ($t > 1) $t -= 1;
        if ($t < 1/6) return $p + ($q - $p) * 6 * $t;
        if ($t < 1/2) return $q;
        if ($t < 2/3) return $p + ($q - $p) * (2/3 - $t) * 6;
        return $p;
    };
    return [(int) round($к($h + 1/3) * 255), (int) round($к($h) * 255), (int) round($к($h - 1/3) * 255)];
}

function цв($im, array $rgb, int $a = 0) { return imagecolorallocatealpha($im, $rgb[0], $rgb[1], $rgb[2], $a); }
function смесь(array $a, array $b, float $t): array {
    return [(int) round($a[0] + ($b[0] - $a[0]) * $t),
            (int) round($a[1] + ($b[1] - $a[1]) * $t),
            (int) round($a[2] + ($b[2] - $a[2]) * $t)];
}

/** Вертикальный градиент с лёгким уводом по диагонали. */
function фон($im, int $w, int $h, array $верх, array $низ): void {
    for ($y = 0; $y < $h; $y++) {
        $t = $y / max(1, $h - 1);
        $t = $t * $t * (3 - 2 * $t);                    // мягкая кривая вместо линейной
        imageline($im, 0, $y, $w, $y, цв($im, смесь($верх, $низ, $t)));
    }
}

/** Мягкое свечение — стопка прозрачных эллипсов вместо попиксельного прохода. */
function свечение($im, int $cx, int $cy, int $r, array $rgb, int $шагов = 64, int $макс = 118): void {
    for ($i = $шагов; $i > 0; $i--) {
        $rr = (int) ($r * $i / $шагов);
        imagefilledellipse($im, $cx, $cy, $rr * 2, $rr * 2, цв($im, $rgb, $макс));
    }
}

/** Затемнение к краям. */
function виньетка($im, int $w, int $h): void {
    $г = (int) ($w * 0.30);
    for ($i = 0; $i < $г; $i++) {
        $a = 127 - (int) (46 * pow(1 - $i / $г, 2.2));
        if ($a >= 127) continue;
        $c = imagecolorallocatealpha($im, 6, 6, 14, $a);
        imageline($im, $i, 0, $i, $h, $c);
        imageline($im, $w - 1 - $i, 0, $w - 1 - $i, $h, $c);
    }
    $г = (int) ($h * 0.34);
    for ($i = 0; $i < $г; $i++) {
        $a = 127 - (int) (44 * pow(1 - $i / $г, 2.2));
        if ($a >= 127) continue;
        $c = imagecolorallocatealpha($im, 6, 6, 14, $a);
        imageline($im, 0, $i, $w, $i, $c);
        imageline($im, 0, $h - 1 - $i, $w, $h - 1 - $i, $c);
    }
}

/** Прямоугольник со скруглением. */
function скругл($im, int $x1, int $y1, int $x2, int $y2, int $r, $c): void {
    imagefilledrectangle($im, $x1 + $r, $y1, $x2 - $r, $y2, $c);
    imagefilledrectangle($im, $x1, $y1 + $r, $x2, $y2 - $r, $c);
    imagefilledellipse($im, $x1 + $r, $y1 + $r, $r * 2, $r * 2, $c);
    imagefilledellipse($im, $x2 - $r, $y1 + $r, $r * 2, $r * 2, $c);
    imagefilledellipse($im, $x1 + $r, $y2 - $r, $r * 2, $r * 2, $c);
    imagefilledellipse($im, $x2 - $r, $y2 - $r, $r * 2, $r * 2, $c);
}

/** Скруглённая обводка: кант снаружи, тело внутри. */
function кант($im, int $x1, int $y1, int $x2, int $y2, int $r, $кант, $тело, int $t): void {
    скругл($im, $x1, $y1, $x2, $y2, $r, $кант);
    скругл($im, $x1 + $t, $y1 + $t, $x2 - $t, $y2 - $t, max(2, $r - $t), $тело);
}

/** Объёмная монета: тень, тело, ободок, блик. */
function монета($im, int $cx, int $cy, int $r, array $金, array $блик): void {
    imagefilledellipse($im, $cx, $cy + (int) ($r * 0.16), $r * 2, $r * 2, imagecolorallocatealpha($im, 0, 0, 0, 96));
    imagefilledellipse($im, $cx, $cy, $r * 2, $r * 2, цв($im, смесь($金, [40, 24, 0], 0.30)));
    imagefilledellipse($im, $cx, $cy, (int) ($r * 1.72), (int) ($r * 1.72), цв($im, $金));
    imagefilledellipse($im, $cx, $cy, (int) ($r * 1.10), (int) ($r * 1.10), цв($im, смесь($金, $блик, 0.34)));
    imagefilledellipse($im, $cx - (int) ($r * 0.32), $cy - (int) ($r * 0.36), (int) ($r * 0.62), (int) ($r * 0.44),
                       цв($im, $блик, 58));
}

/** Фишка казино с насечками по ободу. */
function фишка($im, int $cx, int $cy, int $r, array $осн, array $бел): void {
    imagefilledellipse($im, $cx, $cy + (int) ($r * 0.18), $r * 2, $r * 2, imagecolorallocatealpha($im, 0, 0, 0, 100));
    imagefilledellipse($im, $cx, $cy, $r * 2, $r * 2, цв($im, $осн));
    for ($i = 0; $i < 8; $i++) {
        $a = $i * M_PI / 4 + 0.2;
        $x = $cx + (int) (cos($a) * $r * 0.84); $y = $cy + (int) (sin($a) * $r * 0.84);
        imagefilledellipse($im, $x, $y, (int) ($r * 0.42), (int) ($r * 0.42), цв($im, $бел, 84));
    }
    imagefilledellipse($im, $cx, $cy, (int) ($r * 1.24), (int) ($r * 1.24), цв($im, смесь($осн, $бел, 0.20)));
    imagefilledellipse($im, $cx, $cy, (int) ($r * 1.02), (int) ($r * 1.02), цв($im, $осн));
    imagefilledellipse($im, $cx - (int) ($r * 0.3), $cy - (int) ($r * 0.34), (int) ($r * 0.7), (int) ($r * 0.5),
                       цв($im, $бел, 96));
}

/** Гранёный самоцвет. */
function самоцвет($im, int $cx, int $cy, int $r, array $осн, array $бел): void {
    $верх = смесь($осн, $бел, 0.42); $низ = смесь($осн, [10, 6, 30], 0.35);
    imagefilledpolygon($im, [$cx, $cy - $r, $cx + $r, $cy - (int) ($r * 0.22),
                             $cx + (int) ($r * 0.62), $cy + $r, $cx - (int) ($r * 0.62), $cy + $r,
                             $cx - $r, $cy - (int) ($r * 0.22)], 5, цв($im, $осн));
    imagefilledpolygon($im, [$cx, $cy - $r, $cx + $r, $cy - (int) ($r * 0.22), $cx, $cy + (int) ($r * 0.12)], 3, цв($im, $верх));
    imagefilledpolygon($im, [$cx, $cy - $r, $cx - $r, $cy - (int) ($r * 0.22), $cx, $cy + (int) ($r * 0.12)], 3, цв($im, $низ));
    imagefilledpolygon($im, [$cx, $cy + (int) ($r * 0.12), $cx + (int) ($r * 0.62), $cy + $r,
                             $cx - (int) ($r * 0.62), $cy + $r], 3, цв($im, смесь($осн, $бел, 0.18)));
}

/** Искры и блики для глубины. */
function искры($im, int $w, int $h, int $n, array $rgb, int $сид): void {
    mt_srand($сид);
    for ($i = 0; $i < $n; $i++) {
        $x = mt_rand(0, $w); $y = mt_rand(0, $h); $r = mt_rand(2, 9) * S;
        imagefilledellipse($im, $x, $y, $r * 2, $r * 2, цв($im, $rgb, mt_rand(70, 112)));
        if ($i % 5 === 0) {
            $l = $r * 4;
            $c = цв($im, $rgb, 96);
            imageline($im, $x - $l, $y, $x + $l, $y, $c);
            imageline($im, $x, $y - $l, $x, $y + $l, $c);
        }
    }
}

/* ───────────────────────── мотивы страниц ───────────────────────── */

function мотив($im, string $вид, array $акц, array $свет, array $золото, int $вар, int $cx, int $cy): void {
    $бел = [255, 255, 255];
    $тень = imagecolorallocatealpha($im, 0, 0, 0, 92);
    $стекло = цв($im, $свет, 92);
    $рамка = цв($im, $свет, 46);

    switch ($вид) {
        case 'барабаны':                                   // три барабана с символами
            $ш = 132 * S; $в = 344 * S; $з = 20 * S;
            for ($i = 0; $i < 3; $i++) {
                $x = $cx + ($i - 1) * ($ш + $з) - $ш / 2;
                скругл($im, (int) $x + 6 * S, $cy - $в / 2 + 8 * S, (int) $x + $ш + 6 * S, $cy + $в / 2 + 8 * S, 18 * S, $тень);
                кант($im, (int) $x, $cy - $в / 2, (int) $x + $ш, $cy + $в / 2, 18 * S,
                     цв($im, $золото, 24), цв($im, смесь($акц, [10, 8, 26], 0.72)), 5 * S);
                скругл($im, (int) $x + 10 * S, $cy - $в / 2 + 10 * S, (int) $x + $ш - 10 * S, $cy - $в / 2 + 62 * S, 12 * S,
                       цв($im, $бел, 110));
                for ($j = -1; $j <= 1; $j++) {
                    $sy = $cy + $j * 106 * S;
                    $t = ($i * 3 + $j + $вар + 3) % 3;
                    if ($t === 0)      самоцвет($im, (int) $x + $ш / 2, $sy, 40 * S, $акц, $бел);
                    elseif ($t === 1)  монета($im, (int) $x + $ш / 2, $sy, 38 * S, $золото, $бел);
                    else               фишка($im, (int) $x + $ш / 2, $sy, 38 * S, смесь($акц, [200, 30, 60], 0.5), $бел);
                }
            }
            imagesetthickness($im, 4 * S);
            imageline($im, $cx - 250 * S, $cy, $cx + 250 * S, $cy, цв($im, $золото, 40));
            imagesetthickness($im, 1);
            break;

        case 'монеты':                                     // горка монет с бликами
            $мест = [[-118, 96, 54], [0, 110, 60], [118, 96, 54], [-62, 6, 58], [62, 6, 58], [0, -92, 62]];
            foreach ($мест as $k => [$dx, $dy, $r]) {
                монета($im, $cx + (int) ($dx * S), $cy + (int) ($dy * S), (int) ($r * S * 0.9), $золото, $бел);
            }
            свечение($im, $cx, $cy - 20 * S, 200 * S, $золото, 40, 121);
            break;

        case 'купон':                                      // билеты-купоны стопкой
            for ($i = 2; $i >= 0; $i--) {
                $x = $cx - 210 * S + $i * 22 * S; $y = $cy - 130 * S + $i * 96 * S;
                $c = $i === 1 ? цв($im, $акц, 20) : $стекло;
                скругл($im, $x + 6 * S, $y + 8 * S, $x + 420 * S + 6 * S, $y + 96 * S + 8 * S, 16 * S, $тень);
                скругл($im, $x, $y, $x + 420 * S, $y + 96 * S, 16 * S, $c);
                imagefilledellipse($im, $x + 300 * S, $y, 34 * S, 34 * S, imagecolorallocatealpha($im, 0, 0, 0, 127));
                imagefilledellipse($im, $x + 300 * S, $y + 96 * S, 34 * S, 34 * S, imagecolorallocatealpha($im, 0, 0, 0, 127));
                imagefilledrectangle($im, $x + 40 * S, $y + 34 * S, $x + 250 * S, $y + 48 * S, цв($im, $бел, 60));
                imagefilledrectangle($im, $x + 40 * S, $y + 58 * S, $x + 190 * S, $y + 68 * S, цв($im, $бел, 96));
                imagefilledellipse($im, $x + 356 * S, $y + 48 * S, 44 * S, 44 * S, цв($im, $золото, 30));
            }
            break;

        case 'диаграмма':                                  // столбцы с подсветкой
            $h = [150, 232, 186, 288, 214];
            for ($i = 0; $i < 5; $i++) {
                $x = $cx - 230 * S + $i * 100 * S;
                $v = (int) ($h[($i + $вар) % 5] * S * 0.86);
                $c = $i % 2 ? цв($im, $акц, 18) : $стекло;
                скругл($im, $x, $cy + 150 * S - $v, $x + 68 * S, $cy + 150 * S, 12 * S, $c);
                imagefilledrectangle($im, $x + 10 * S, $cy + 150 * S - $v + 10 * S, $x + 24 * S, $cy + 130 * S, цв($im, $бел, 104));
            }
            imagesetthickness($im, 4 * S);
            imageline($im, $cx - 250 * S, $cy + 152 * S, $cx + 250 * S, $cy + 152 * S, цв($im, $свет, 60));
            imagesetthickness($im, 1);
            break;

        case 'график':                                     // ломаная роста с узлами
            $pts = [];
            for ($i = 0; $i <= 6; $i++) {
                $pts[] = [$cx - 240 * S + $i * 80 * S,
                          $cy + 160 * S - (int) (sin(($i + $вар) * 0.75) * 60 * S) - $i * 30 * S];
            }
            $обл = [];
            foreach ($pts as $p) { $обл[] = $p[0]; $обл[] = $p[1]; }
            $обл[] = $pts[6][0]; $обл[] = $cy + 190 * S;
            $обл[] = $pts[0][0]; $обл[] = $cy + 190 * S;
            imagefilledpolygon($im, $обл, count($обл) / 2, цв($im, $акц, 104));
            imagesetthickness($im, 8 * S);
            for ($i = 0; $i < 6; $i++) imageline($im, $pts[$i][0], $pts[$i][1], $pts[$i+1][0], $pts[$i+1][1], цв($im, $акц));
            imagesetthickness($im, 1);
            foreach ($pts as $p) {
                imagefilledellipse($im, $p[0], $p[1], 26 * S, 26 * S, цв($im, $бел, 10));
                imagefilledellipse($im, $p[0], $p[1], 12 * S, 12 * S, цв($im, $акц));
            }
            break;

        case 'лента':                                      // карточки новостей
            for ($i = 0; $i < 4; $i++) {
                $y = $cy - 190 * S + $i * 104 * S;
                скругл($im, $cx - 220 * S + 6 * S, $y + 8 * S, $cx + 220 * S + 6 * S, $y + 78 * S + 8 * S, 14 * S, $тень);
                скругл($im, $cx - 220 * S, $y, $cx + 220 * S, $y + 78 * S, 14 * S, $i % 2 ? $стекло : цв($im, $акц, 30));
                скругл($im, $cx - 200 * S, $y + 16 * S, $cx - 116 * S, $y + 62 * S, 10 * S, цв($im, $золото, 40));
                imagefilledrectangle($im, $cx - 96 * S, $y + 24 * S, $cx + 100 * S - $i * 26 * S, $y + 38 * S, цв($im, $бел, 66));
                imagefilledrectangle($im, $cx - 96 * S, $y + 46 * S, $cx + 40 * S - $i * 18 * S, $y + 56 * S, цв($im, $бел, 100));
            }
            break;

        case 'щит':                                        // щит с галочкой
            $r = 210 * S;
            $щ = [$cx, $cy - $r, $cx + (int) ($r * 0.86), $cy - (int) ($r * 0.56),
                  $cx + (int) ($r * 0.78), $cy + (int) ($r * 0.34), $cx, $cy + $r,
                  $cx - (int) ($r * 0.78), $cy + (int) ($r * 0.34), $cx - (int) ($r * 0.86), $cy - (int) ($r * 0.56)];
            $щт = []; foreach ($щ as $k => $v) $щт[] = $k % 2 ? $v + 10 * S : $v + 8 * S;
            imagefilledpolygon($im, $щт, 6, $тень);
            imagefilledpolygon($im, $щ, 6, цв($im, $акц, 26));
            $вн = []; foreach ($щ as $k => $v) $вн[] = $k % 2 ? (int) ($cy + ($v - $cy) * 0.82) : (int) ($cx + ($v - $cx) * 0.82);
            imagefilledpolygon($im, $вн, 6, $стекло);
            imagesetthickness($im, 20 * S);
            imageline($im, $cx - 78 * S, $cy + 6 * S, $cx - 16 * S, $cy + 76 * S, цв($im, $золото));
            imageline($im, $cx - 16 * S, $cy + 76 * S, $cx + 96 * S, $cy - 82 * S, цв($im, $золото));
            imagesetthickness($im, 1);
            break;

        case 'телефон':                                    // смартфон с плиткой игр
            $w = 250 * S; $h = 430 * S;
            скругл($im, $cx - $w / 2 + 8 * S, $cy - $h / 2 + 10 * S, $cx + $w / 2 + 8 * S, $cy + $h / 2 + 10 * S, 34 * S, $тень);
            скругл($im, $cx - $w / 2, $cy - $h / 2, $cx + $w / 2, $cy + $h / 2, 34 * S, цв($im, $свет, 40));
            скругл($im, $cx - $w / 2 + 14 * S, $cy - $h / 2 + 16 * S, $cx + $w / 2 - 14 * S, $cy + $h / 2 - 44 * S, 22 * S,
                   цв($im, смесь($акц, [8, 6, 24], 0.55)));
            for ($i = 0; $i < 3; $i++) for ($j = 0; $j < 2; $j++) {
                скругл($im, $cx - 96 * S + $j * 100 * S, $cy - 150 * S + $i * 92 * S,
                       $cx - 16 * S + $j * 100 * S, $cy - 82 * S + $i * 92 * S, 12 * S,
                       ($i + $j) % 2 ? цв($im, $акц, 16) : цв($im, $золото, 34));
            }
            imagefilledrectangle($im, $cx - 34 * S, $cy - $h / 2 + 26 * S, $cx + 34 * S, $cy - $h / 2 + 38 * S, цв($im, $бел, 90));
            imagefilledellipse($im, $cx, $cy + $h / 2 - 24 * S, 30 * S, 30 * S, цв($im, $бел, 80));
            break;

        case 'форма':                                      // окно регистрации
            $w = 400 * S; $h = 380 * S;
            скругл($im, $cx - $w / 2 + 8 * S, $cy - $h / 2 + 10 * S, $cx + $w / 2 + 8 * S, $cy + $h / 2 + 10 * S, 22 * S, $тень);
            скругл($im, $cx - $w / 2, $cy - $h / 2, $cx + $w / 2, $cy + $h / 2, 22 * S, $стекло);
            imagefilledrectangle($im, $cx - $w / 2 + 30 * S, $cy - $h / 2 + 34 * S, $cx - $w / 2 + 170 * S, $cy - $h / 2 + 50 * S, цв($im, $бел, 64));
            for ($i = 0; $i < 3; $i++) {
                $y = $cy - 90 * S + $i * 84 * S;
                скругл($im, $cx - 160 * S, $y, $cx + 160 * S, $y + 54 * S, 12 * S, цв($im, $бел, 108));
                imagefilledrectangle($im, $cx - 140 * S, $y + 20 * S, $cx - 40 * S + $i * 40 * S, $y + 34 * S, цв($im, $бел, 70));
            }
            скругл($im, $cx - 160 * S, $cy + 118 * S, $cx + 160 * S, $cy + 172 * S, 14 * S, цв($im, $золото, 20));
            break;

        case 'ключ':                                       // ключ доступа
            $кx = $cx - 60 * S;
            свечение($im, $кx, $cy, 176 * S, $золото, 30, 122);
            imagefilledellipse($im, $кx + 8 * S, $cy + 10 * S, 200 * S, 200 * S, $тень);
            imagefilledellipse($im, $кx, $cy, 200 * S, 200 * S, цв($im, $золото));
            imagefilledellipse($im, $кx, $cy, 92 * S, 92 * S, imagecolorallocatealpha($im, 0, 0, 0, 127));
            imagefilledellipse($im, $кx - 30 * S, $cy - 34 * S, 74 * S, 52 * S, цв($im, $бел, 92));
            скругл($im, $кx + 26 * S, $cy - 26 * S, $кx + 300 * S, $cy + 26 * S, 12 * S, цв($im, $золото));
            скругл($im, $кx + 196 * S, $cy + 26 * S, $кx + 230 * S, $cy + 96 * S, 8 * S, цв($im, $золото));
            скругл($im, $кx + 258 * S, $cy + 26 * S, $кx + 292 * S, $cy + 82 * S, 8 * S, цв($im, $золото));
            break;

        case 'зеркало':                                    // два окна и переход между ними
            $w = 200 * S; $h = 340 * S;
            foreach ([[-140, 1.0], [140, 0.86]] as [$dx, $k]) {
                $x = $cx + (int) ($dx * S);
                скругл($im, $x - $w / 2 + 6 * S, $cy - $h / 2 + 8 * S, $x + $w / 2 + 6 * S, $cy + $h / 2 + 8 * S, 18 * S, $тень);
                скругл($im, $x - $w / 2, $cy - $h / 2, $x + $w / 2, $cy + $h / 2, 18 * S,
                       $k > 0.9 ? цв($im, $акц, 22) : $стекло);
                for ($i = 0; $i < 3; $i++) {
                    imagefilledrectangle($im, $x - $w / 2 + 24 * S, $cy - 108 * S + $i * 84 * S,
                                         $x + $w / 2 - 24 * S, $cy - 56 * S + $i * 84 * S, цв($im, $бел, 100));
                }
                imagefilledrectangle($im, $x - $w / 2 + 24 * S, $cy - $h / 2 + 26 * S, $x - $w / 2 + 96 * S, $cy - $h / 2 + 42 * S, цв($im, $бел, 70));
            }
            imagesetthickness($im, 10 * S);
            imageline($im, $cx - 24 * S, $cy, $cx + 24 * S, $cy, цв($im, $золото));
            imagesetthickness($im, 1);
            imagefilledpolygon($im, [$cx + 40 * S, $cy, $cx + 4 * S, $cy - 26 * S, $cx + 4 * S, $cy + 26 * S], 3, цв($im, $золото));
            break;
    }
}

/* ───────────────────────── обложка игры ─────────────────────────
 * Одна на комплект, дублируется во все карточки списка слотов.
 * Рисуем свой сюжет в духе жанра — без чужих логотипов и названий.
 */

const ОБЛОЖКИ = [
    ['сласти',  [318, 286], 'Сладкий каскад'],
    ['олимп',   [244, 210], 'Гром Олимпа'],
    ['египет',  [38,  22 ], 'Тайна свитка'],
    ['рыбалка', [192, 210], 'Большой улов'],
    ['звёзды',  [268, 232], 'Звёздная россыпь'],
    ['фрукты',  [352, 20 ], 'Классика на барабанах'],
];

function обложка(string $файл, int $индекс, int $сид): string {
    [$вид, [$т1, $т2], $имя] = ОБЛОЖКИ[$индекс % count(ОБЛОЖКИ)];
    $W = 640 * S; $H = 480 * S;
    $im = imagecreatetruecolor($W, $H);
    imagealphablending($im, true);
    $бел = [255, 255, 255];
    $золото = [255, 199, 88];

    фон($im, $W, $H, hsl($т1, 0.62, 0.16), hsl($т2, 0.58, 0.34));
    свечение($im, (int) ($W * 0.5), (int) ($H * 0.44), (int) ($W * 0.52), hsl($т2, 0.72, 0.60), 56, 120);

    $cx = (int) ($W / 2); $cy = (int) ($H / 2);
    mt_srand($сид * 17 + $индекс);

    switch ($вид) {
        case 'сласти':
            foreach ([[-190, -60, 96], [180, -84, 82], [-96, 128, 74], [126, 130, 88]] as [$dx, $dy, $r]) {
                $x = $cx + (int) ($dx * S); $y = $cy + (int) ($dy * S); $r = (int) ($r * S * 0.9);
                imagefilledellipse($im, $x, $y + 8 * S, $r * 2, $r * 2, imagecolorallocatealpha($im, 0, 0, 0, 100));
                imagefilledellipse($im, $x, $y, $r * 2, $r * 2, цв($im, hsl(330 + $dx % 40, 0.78, 0.62)));
                for ($k = 0; $k < 4; $k++) {
                    $a = $k * M_PI / 4 + 0.4;
                    imagesetthickness($im, (int) ($r * 0.26));
                    imageline($im, $x - (int) (cos($a) * $r * 0.92), $y - (int) (sin($a) * $r * 0.92),
                                   $x + (int) (cos($a) * $r * 0.92), $y + (int) (sin($a) * $r * 0.92), цв($im, $бел, 52));
                    imagesetthickness($im, 1);
                }
                imagefilledellipse($im, $x, $y, (int) ($r * 0.62), (int) ($r * 0.62), цв($im, hsl(48, 0.9, 0.66)));
                imagefilledellipse($im, $x - (int) ($r * 0.3), $y - (int) ($r * 0.34), (int) ($r * 0.6), (int) ($r * 0.44), цв($im, $бел, 74));
            }
            самоцвет($im, $cx, $cy - 10 * S, 110 * S, hsl(292, 0.72, 0.62), $бел);
            break;

        case 'олимп':
            $мрамор = hsl(42, 0.30, 0.84); $тёмн = hsl(232, 0.36, 0.16);
            for ($i = 0; $i < 5; $i++) {
                $x = $cx - 250 * S + $i * 125 * S;
                imagefilledrectangle($im, $x - 34 * S, $cy - 44 * S, $x + 38 * S, $cy + 196 * S, imagecolorallocatealpha($im, 0, 0, 0, 104));
                imagefilledrectangle($im, $x - 36 * S, $cy - 40 * S, $x + 36 * S, $cy + 190 * S, цв($im, $мрамор));
                for ($f = -2; $f <= 2; $f++) {
                    imagefilledrectangle($im, $x + $f * 14 * S - 3 * S, $cy - 34 * S, $x + $f * 14 * S + 3 * S, $cy + 184 * S,
                                         цв($im, смесь($мрамор, $тёмн, 0.26)));
                }
                imagefilledrectangle($im, $x - 50 * S, $cy - 66 * S, $x + 50 * S, $cy - 38 * S, цв($im, смесь($мрамор, $бел, 0.4)));
                imagefilledrectangle($im, $x - 50 * S, $cy + 186 * S, $x + 50 * S, $cy + 214 * S, цв($im, смесь($мрамор, $тёмн, 0.14)));
                imagefilledrectangle($im, $x + 22 * S, $cy - 40 * S, $x + 36 * S, $cy + 190 * S, цв($im, $тёмн, 96));
            }
            $мол = [$cx + 30 * S, $cy - 210 * S, $cx - 40 * S, $cy - 30 * S, $cx + 6 * S, $cy - 30 * S,
                    $cx - 46 * S, $cy + 160 * S, $cx + 70 * S, $cy - 60 * S, $cx + 16 * S, $cy - 60 * S,
                    $cx + 78 * S, $cy - 210 * S];
            свечение($im, $cx + 10 * S, $cy - 30 * S, 190 * S, $золото, 40, 118);
            imagefilledpolygon($im, $мол, 7, цв($im, $золото));
            imagefilledpolygon($im, $мол, 7, цв($im, $бел, 90));
            break;

        case 'египет':
            imagefilledpolygon($im, [$cx, $cy - 200 * S, $cx + 250 * S, $cy + 150 * S, $cx - 250 * S, $cy + 150 * S], 3,
                               цв($im, hsl(40, 0.56, 0.46)));
            imagefilledpolygon($im, [$cx, $cy - 200 * S, $cx + 250 * S, $cy + 150 * S, $cx, $cy + 150 * S], 3,
                               цв($im, hsl(36, 0.52, 0.34)));
            скругл($im, $cx - 120 * S, $cy - 40 * S, $cx + 120 * S, $cy + 130 * S, 14 * S, цв($im, hsl(30, 0.44, 0.24)));
            imagefilledrectangle($im, $cx - 100 * S, $cy - 22 * S, $cx + 100 * S, $cy + 112 * S, цв($im, hsl(44, 0.42, 0.82)));
            imagesetthickness($im, 6 * S);
            imageline($im, $cx, $cy - 22 * S, $cx, $cy + 112 * S, цв($im, hsl(30, 0.44, 0.24)));
            imagesetthickness($im, 1);
            for ($i = 0; $i < 4; $i++) {
                imagefilledrectangle($im, $cx - 78 * S, $cy + 4 * S + $i * 22 * S, $cx - 26 * S, $cy + 14 * S + $i * 22 * S, цв($im, hsl(30, 0.5, 0.4), 40));
                imagefilledrectangle($im, $cx + 26 * S, $cy + 4 * S + $i * 22 * S, $cx + 78 * S, $cy + 14 * S + $i * 22 * S, цв($im, hsl(30, 0.5, 0.4), 40));
            }
            монета($im, $cx - 200 * S, $cy + 120 * S, 52 * S, $золото, $бел);
            монета($im, $cx + 200 * S, $cy + 120 * S, 52 * S, $золото, $бел);
            break;

        case 'рыбалка':
            for ($i = 0; $i < 3; $i++) {
                $y = $cy + 90 * S + $i * 60 * S;
                imagefilledellipse($im, $cx, $y, $W, 90 * S, цв($im, hsl(196, 0.66, 0.44), 104 - $i * 6));
            }
            $rx = $cx - 40 * S; $ry = $cy - 20 * S;
            $обв = hsl(214, 0.60, 0.14);
            $тело = hsl(150, 0.56, 0.46); $брюхо = hsl(46, 0.86, 0.62);
            // хвост
            imagefilledpolygon($im, [$rx + 130 * S, $ry, $rx + 268 * S, $ry - 96 * S, $rx + 240 * S, $ry,
                                     $rx + 268 * S, $ry + 96 * S], 4, цв($im, $обв));
            imagefilledpolygon($im, [$rx + 136 * S, $ry, $rx + 254 * S, $ry - 80 * S, $rx + 228 * S, $ry,
                                     $rx + 254 * S, $ry + 80 * S], 4, цв($im, смесь($тело, $брюхо, 0.30)));
            // спинной и брюшной плавник
            imagefilledpolygon($im, [$rx - 10 * S, $ry - 66 * S, $rx + 80 * S, $ry - 150 * S, $rx + 96 * S, $ry - 40 * S], 3, цв($im, $обв));
            imagefilledpolygon($im, [$rx - 4 * S, $ry - 66 * S, $rx + 72 * S, $ry - 134 * S, $rx + 84 * S, $ry - 44 * S], 3, цв($im, смесь($тело, $брюхо, 0.42)));
            imagefilledpolygon($im, [$rx + 10 * S, $ry + 60 * S, $rx + 70 * S, $ry + 132 * S, $rx + 96 * S, $ry + 40 * S], 3, цв($im, $обв));
            // тело
            imagefilledellipse($im, $rx, $ry, 336 * S, 186 * S, цв($im, $обв));
            imagefilledellipse($im, $rx, $ry, 320 * S, 170 * S, цв($im, $тело));
            imagefilledellipse($im, $rx + 10 * S, $ry + 34 * S, 260 * S, 92 * S, цв($im, $брюхо, 34));
            imagefilledellipse($im, $rx - 30 * S, $ry - 40 * S, 190 * S, 62 * S, цв($im, $бел, 100));
            // чешуя
            for ($r = 0; $r < 3; $r++) for ($c = 0; $c < 5; $c++) {
                imageellipse($im, $rx - 60 * S + $c * 44 * S, $ry - 24 * S + $r * 34 * S, 40 * S, 40 * S, цв($im, $обв, 92));
            }
            // жабра и глаз
            imagesetthickness($im, 5 * S);
            imagearc($im, $rx - 74 * S, $ry, 90 * S, 150 * S, -60, 60, цв($im, $обв, 60));
            imagesetthickness($im, 1);
            imagefilledellipse($im, $rx - 108 * S, $ry - 30 * S, 46 * S, 46 * S, цв($im, $бел));
            imagefilledellipse($im, $rx - 112 * S, $ry - 30 * S, 22 * S, 22 * S, цв($im, [18, 18, 28]));
            imagefilledellipse($im, $rx - 118 * S, $ry - 36 * S, 9 * S, 9 * S, цв($im, $бел));
            imagesetthickness($im, 7 * S);
            imageline($im, $cx + 170 * S, $cy - 220 * S, $cx + 170 * S, $cy - 90 * S, цв($im, $бел, 40));
            imagesetthickness($im, 1);
            imagefilledpolygon($im, [$cx + 170 * S, $cy - 90 * S, $cx + 150 * S, $cy - 50 * S, $cx + 190 * S, $cy - 50 * S], 3, цв($im, $золото));
            for ($i = 0; $i < 7; $i++) {
                imagefilledellipse($im, $cx - 200 * S + mt_rand(0, 400) * S, $cy - 140 * S + mt_rand(0, 120) * S,
                                   mt_rand(10, 26) * S, mt_rand(10, 26) * S, цв($im, $бел, 100));
            }
            break;

        case 'звёзды':
            for ($i = 0; $i < 7; $i++) {
                $a = $i * M_PI * 2 / 7 - M_PI / 2;
                самоцвет($im, $cx + (int) (cos($a) * 190 * S), $cy + (int) (sin($a) * 130 * S), 56 * S,
                         hsl(200 + $i * 26, 0.74, 0.60), $бел);
            }
            свечение($im, $cx, $cy, 170 * S, hsl(268, 0.8, 0.66), 44, 118);
            самоцвет($im, $cx, $cy, 108 * S, hsl(48, 0.82, 0.62), $бел);
            break;

        case 'фрукты':
            $ш = 168 * S; $в = 320 * S;
            for ($i = 0; $i < 3; $i++) {
                $x = $cx + ($i - 1) * ($ш + 18 * S) - $ш / 2;
                скругл($im, (int) $x + 6 * S, $cy - $в / 2 + 8 * S, (int) $x + $ш + 6 * S, $cy + $в / 2 + 8 * S, 18 * S,
                       imagecolorallocatealpha($im, 0, 0, 0, 104));
                кант($im, (int) $x, $cy - $в / 2, (int) $x + $ш, $cy + $в / 2, 18 * S,
                     цв($im, $золото), цв($im, hsl(268, 0.40, 0.15)), 7 * S);
                скругл($im, (int) $x + 14 * S, $cy - $в / 2 + 14 * S, (int) $x + $ш - 14 * S, $cy - $в / 2 + 74 * S, 12 * S,
                       цв($im, $бел, 112));
                $ц = (int) $x + $ш / 2;
                if ($i === 0) {                               // вишня
                    imagefilledellipse($im, $ц - 30 * S, $cy + 30 * S, 76 * S, 76 * S, цв($im, hsl(354, 0.74, 0.50)));
                    imagefilledellipse($im, $ц + 32 * S, $cy + 44 * S, 76 * S, 76 * S, цв($im, hsl(354, 0.74, 0.44)));
                    imagesetthickness($im, 6 * S);
                    imageline($im, $ц - 30 * S, $cy + 10 * S, $ц + 10 * S, $cy - 80 * S, цв($im, hsl(120, 0.5, 0.36)));
                    imageline($im, $ц + 32 * S, $cy + 22 * S, $ц + 10 * S, $cy - 80 * S, цв($im, hsl(120, 0.5, 0.36)));
                    imagesetthickness($im, 1);
                } elseif ($i === 1) {                          // семёрка
                    $п = [$ц + 58 * S, $cy - 90 * S, $ц + 14 * S, $cy + 100 * S, $ц - 44 * S, $cy + 100 * S, $ц + 10 * S, $cy - 38 * S];
                    imagefilledrectangle($im, $ц - 58 * S, $cy - 90 * S, $ц + 58 * S, $cy - 38 * S, цв($im, hsl(354, 0.72, 0.42)));
                    imagefilledpolygon($im, $п, 4, цв($im, hsl(354, 0.72, 0.42)));
                    imagefilledrectangle($im, $ц - 50 * S, $cy - 82 * S, $ц + 50 * S, $cy - 44 * S, цв($im, $золото));
                    imagefilledpolygon($im, [$ц + 48 * S, $cy - 82 * S, $ц + 8 * S, $cy + 92 * S,
                                             $ц - 34 * S, $cy + 92 * S, $ц + 4 * S, $cy - 44 * S], 4, цв($im, $золото));
                } else {                                       // лимон
                    imagefilledellipse($im, $ц, $cy + 4 * S, 150 * S, 110 * S, цв($im, hsl(48, 0.86, 0.56)));
                    imagefilledellipse($im, $ц, $cy + 4 * S, 118 * S, 82 * S, цв($im, hsl(52, 0.90, 0.72)));
                    for ($k = 0; $k < 6; $k++) {
                        $a = $k * M_PI / 3;
                        imagesetthickness($im, 4 * S);
                        imageline($im, $ц, $cy + 4 * S, $ц + (int) (cos($a) * 56 * S), $cy + 4 * S + (int) (sin($a) * 38 * S),
                                  цв($im, hsl(46, 0.7, 0.44), 40));
                        imagesetthickness($im, 1);
                    }
                }
            }
            break;
    }

    искры($im, $W, $H, 26, $бел, $сид + $индекс);
    виньетка($im, $W, $H);
    // кант и уголки, чтобы плитка читалась как обложка игры
    imagesetthickness($im, 7 * S);
    imagerectangle($im, 10 * S, 10 * S, $W - 11 * S, $H - 11 * S, цв($im, $золото, 34));
    imagesetthickness($im, 2 * S);
    imagerectangle($im, 22 * S, 22 * S, $W - 23 * S, $H - 23 * S, imagecolorallocatealpha($im, 255, 255, 255, 88));
    imagesetthickness($im, 1);
    foreach ([[10, 10, 1, 1], [$W - 11, 10, -1, 1], [10, $H - 11, 1, -1], [$W - 11, $H - 11, -1, -1]] as [$ux, $uy, $sx, $sy]) {
        $ux = (int) ($ux * ($ux > 100 ? 1 : S)); $uy = (int) ($uy * ($uy > 100 ? 1 : S));
        imagefilledpolygon($im, [$ux, $uy, $ux + $sx * 62 * S, $uy, $ux, $uy + $sy * 62 * S], 3, цв($im, $золото, 40));
    }

    $out = imagecreatetruecolor((int) ($W / S), (int) ($H / S));
    imagecopyresampled($out, $im, 0, 0, 0, 0, (int) ($W / S), (int) ($H / S), $W, $H);
    imagewebp($out, $файл, 82);
    imagedestroy($im); imagedestroy($out);
    return $имя;
}

/* ───────────────────────── иллюстрация страницы ───────────────────────── */

function нарисовать(string $файл, string $вид, float $тон, array $строки, int $вар): void {
    global $шрифт, $шрифтТонкий;
    $W = ШИР * S; $H = ВЫС * S;
    $im = imagecreatetruecolor($W, $H);
    imagealphablending($im, true);

    $бел = [255, 255, 255];
    $золото = hsl(44, 0.86, 0.62);
    $акц    = hsl($тон + 30, 0.74, 0.56);
    $свет   = hsl($тон + 8, 0.40, 0.72);

    фон($im, $W, $H, hsl($тон - 6, 0.66, 0.10), hsl($тон - 26, 0.58, 0.24));

    $cx = (int) ($W * 0.72); $cy = (int) ($H * 0.50);
    свечение($im, $cx, $cy, (int) ($W * 0.21), hsl($тон + 6, 0.72, 0.50), 44, 122);
    свечение($im, (int) ($W * 0.10), (int) ($H * 0.16), (int) ($W * 0.13), hsl($тон - 34, 0.66, 0.44), 30, 123);

    // разреженная сетка и мягкий луч
    $сетка = imagecolorallocatealpha($im, 255, 255, 255, 120);
    for ($x = 0; $x < $W; $x += 72 * S) imageline($im, $x, 0, $x, $H, $сетка);
    for ($y = 0; $y < $H; $y += 72 * S) imageline($im, 0, $y, $W, $y, $сетка);
    imagefilledpolygon($im, [0, $H, 0, (int) ($H * 0.52), (int) ($W * 0.42) + $вар * 20 * S, 0,
                             (int) ($W * 0.18) + $вар * 20 * S, 0], 4, imagecolorallocatealpha($im, 255, 255, 255, 118));

    мотив($im, $вид, $акц, $свет, $золото, $вар, $cx, $cy);
    искры($im, $W, $H, 22, $бел, $вар * 97 + (int) $тон);
    виньетка($im, $W, $H);

    // подпись
    $чёрн = imagecolorallocatealpha($im, 0, 0, 0, 72);
    imagefilledrectangle($im, 78 * S, 208 * S, 166 * S, 216 * S, цв($im, $золото));
    $кегль = 46;
    while ($кегль > 26) {
        $bb = imagettfbbox($кегль * S, 0, $шрифт, $строки[0]);
        if (($bb[2] - $bb[0]) <= 512 * S) break;
        $кегль -= 2;
    }
    imagettftext($im, $кегль * S, 0, 78 * S + 3 * S, 306 * S + 3 * S, $чёрн, $шрифт, $строки[0]);
    imagettftext($im, $кегль * S, 0, 76 * S, 304 * S, imagecolorallocate($im, 248, 250, 255), $шрифт, $строки[0]);
    imagettftext($im, 23 * S, 0, 78 * S, 360 * S, imagecolorallocatealpha($im, 226, 232, 246, 30), $шрифтТонкий, $строки[1]);

    imagesetthickness($im, 3 * S);
    imagerectangle($im, 20 * S, 20 * S, $W - 21 * S, $H - 21 * S, imagecolorallocatealpha($im, 255, 255, 255, 108));
    imagesetthickness($im, 1);

    $out = imagecreatetruecolor(ШИР, ВЫС);
    imagecopyresampled($out, $im, 0, 0, 0, 0, ШИР, ВЫС, $W, $H);
    imagewebp($out, $файл, 80);
    imagedestroy($im); imagedestroy($out);
}

/* ───────────────────────── вставка в разметку ───────────────────────── */

/** Одна ведущая иллюстрация в начало страницы. Классов не добавляем —
 *  вёрстка комплекта их не знает, оформление задаётся инлайном.
 */
function вшить(string $файл, string $страница, string $alt): int {
    $html = file_get_contents($файл);
    $имя = $страница . '_img_1.webp';
    if (strpos($html, $имя) !== false) return 0;
    $тег = '<img src="' . $имя . '" alt="' . htmlspecialchars($alt, ENT_QUOTES, 'UTF-8')
         . '" width="1200" height="630" loading="lazy"'
         . ' style="display:block;width:100%;height:auto;margin:0 0 20px;border-radius:14px">';
    file_put_contents($файл, $тег . "\n" . $html);
    return 1;
}

/** Обложка игры в каждую карточку списка слотов. */
function вшитьОбложку(string $файл, string $страница, string $имяФайла, string $жанр): int {
    $строки = explode("\n", file_get_contents($файл));
    $итог = []; $n = 0;
    foreach ($строки as $л) {
        $итог[] = $л;
        if (strpos($л, 'class="slot-poster"') !== false) {
            $отступ = str_repeat(' ', strlen($л) - strlen(ltrim($л)) + 2);
            $alt = htmlspecialchars('обложка игрового автомата — ' . $жанр, ENT_QUOTES, 'UTF-8');
            $итог[] = $отступ . '<img src="' . $имяФайла . '" alt="' . $alt
                    . '" width="640" height="480" loading="lazy"'
                    . ' style="display:block;width:100%;height:auto;border-radius:10px">';
            $n++;
        }
    }
    if ($n) file_put_contents($файл, implode("\n", $итог));
    return $n;
}

/* ───────────────────────── прогон ───────────────────────── */

@mkdir($папка . '/images', 0777, true);
$всего = 0; $вшито = 0;
$в = $сид % 3;
foreach ($ТЕМЫ as $страница => [$тон, $мотивы, $подписи, $альты]) {
    $html = $папка . '/' . $страница . '.html';
    if (!is_file($html)) continue;
    $вар = ($сид + strlen($страница)) % 5;
    нарисовать($папка . '/images/' . $страница . '_img_1.webp',
               $мотивы[0], $тон + ($сид % 5) * 4 - 8, $подписи[$в], $вар);
    $всего++;
    $вшито += вшить($html, $страница, $альты[$в][0]);
}

// обложка игры — одна на комплект, повторяется во всех карточках списка слотов
$карточек = 0;
foreach (array_keys($ТЕМЫ) as $страница) {
    $html = $папка . '/' . $страница . '.html';
    if (!is_file($html) || strpos(file_get_contents($html), 'class="slot-poster"') === false) continue;
    $имяФайла = $страница . '_img_2.webp';
    $жанр = обложка($папка . '/images/' . $имяФайла, $сид, $сид);
    $всего++;
    $карточек += вшитьОбложку($html, $страница, $имяФайла, $жанр);
}
echo "картинок: $всего, ведущих в статьях: $вшито, карточек игр: $карточек\n";
