<?php
declare(strict_types=1);
// Генератор тестовых фикстур: 7 связанных HTML-страниц.
$dir = __DIR__ . '/fixtures';
@mkdir($dir, 0777, true);

$nav = function (array $links): string {
    $items = array_map(fn($l) => "<a href=\"{$l[0]}\">{$l[1]}</a>", $links);
    return '<nav>' . implode(' · ', $items) . '</nav>';
};

$pages = [
    'index.html' => ['Пластиковые окна в Москве — купить с установкой', 'купить пластиковые окна',
        ['пластиковые','монтаж','остекление'], [['uslugi.html','Услуги'],['montazh.html','Монтаж'],['about.html','О нас'],['blog.html','Блог'],['cases.html','Кейсы'],['contacts.html','Контакты']]],
    'uslugi.html' => ['Услуги по остеклению — пластиковые окна под ключ', 'остекление под ключ',
        ['окна','балкон','лоджия'], [['index.html','Главная'],['montazh.html','Монтаж'],['contacts.html','Контакты']]],
    'montazh.html' => ['Монтаж пластиковых окон — профессиональная установка', 'монтаж окон',
        ['установка','замер','гарантия'], [['index.html','Главная'],['uslugi.html','Услуги'],['contacts.html','Контакты']]],
    'about.html' => ['О компании — опыт остекления с 2005 года', 'компания остекление',
        ['опыт','команда','качество'], [['index.html','Главная'],['cases.html','Кейсы'],['contacts.html','Контакты']]],
    'blog.html' => ['Как выбрать пластиковые окна — подробный гайд', 'как выбрать окна',
        ['профиль','стеклопакет','фурнитура'], [['index.html','Главная'],['uslugi.html','Услуги'],['montazh.html','Монтаж'],['cases.html','Кейсы']]],
    'cases.html' => ['Наши кейсы остекления квартир и домов', 'кейсы остекления',
        ['проект','объект','результат'], [['index.html','Главная'],['about.html','О нас'],['contacts.html','Контакты']]],
    // contacts — намеренный тупик: нет исходящих внутренних ссылок
    'contacts.html' => ['Контакты — как нас найти', 'контакты компании',
        ['адрес','телефон','почта'], []],
];

$para = function (string $topic, array $lsi, int $sentences): string {
    $tpl = [
        "Наша компания предлагает {$topic} на выгодных условиях.",
        "Мы используем современный {$lsi[0]} и качественные материалы.",
        "Опытные специалисты выполнят {$lsi[1]} в согласованные сроки.",
        "Каждый {$lsi[2]} проходит контроль качества перед сдачей.",
        "Клиенты ценят наш подход за внимание к деталям и честные цены.",
        "Обращайтесь, и мы подберём оптимальное решение под ваш запрос.",
    ];
    $out = [];
    for ($i = 0; $i < $sentences; $i++) { $out[] = $tpl[$i % count($tpl)]; }
    return implode(' ', $out);
};

foreach ($pages as $file => [$title, $kw, $lsi, $links]) {
    $body = "<h1>{$title}</h1>\n";
    $body .= $nav($links) . "\n";
    $body .= '<p>' . $para($kw, $lsi, 6) . "</p>\n";
    $body .= "<h2>Почему выбирают нас</h2>\n";
    $body .= "<ul><li>{$lsi[0]}</li><li>{$lsi[1]}</li><li>{$lsi[2]}</li></ul>\n";
    $body .= '<p>' . $para($kw, $lsi, 5) . "</p>\n";
    $body .= "<h2>Как мы работаем</h2>\n";
    $body .= '<p><strong>' . $kw . '</strong> — ' . $para($kw, $lsi, 4) . "</p>\n";
    $body .= '<img src="photo.jpg" alt="' . $title . '">' . "\n";

    // uslugi и montazh — специально похожи (для проверки шинглов/дублей)
    if ($file === 'montazh.html') {
        $body .= '<p>' . $para('остекление под ключ', ['окна','балкон','лоджия'], 6) . "</p>\n";
    }

    $html = "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"UTF-8\">\n"
        . "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        . "<title>{$title}</title>\n"
        . "<meta name=\"description\" content=\"{$title}. Звоните — поможем с выбором и установкой.\">\n"
        . '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article"}</script>' . "\n"
        . "</head>\n<body>\n{$body}</body>\n</html>\n";

    file_put_contents("{$dir}/{$file}", $html);
}

echo "Создано " . count($pages) . " страниц в {$dir}\n";
