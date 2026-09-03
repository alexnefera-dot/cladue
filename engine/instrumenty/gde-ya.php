<?php
// Где у доноров семьи B живёт «я»: в теле страницы или в ответах FAQ
chdir('/home/user/cladue');
require 'engine/src/PageMetrics.php';
const YA = '~\b(?:я|меня|мне|мной|мой|моя|мои|моих|моей|моего)\b~ui';
function slov(string $s): int { return max(1, preg_match_all('~[А-Яа-яЁёA-Za-z0-9]+~u', $s)); }
function semya(string $d): string {
    $f="$d/main.html"; if(!is_file($f)) return 'A';
    $t=preg_replace('~\s+~u',' ',strip_tags((string)file_get_contents($f)));
    return 1000*preg_match_all(YA,$t)/slov($t) > 8 ? 'B':'A';
}
$tip = $argv[1] ?? 'app';
$telo=0;$telon=0;$faq=0;$faqn=0;$n=0;
foreach (glob('samples/v5-donors/*', GLOB_ONLYDIR) as $d) {
    if (semya($d)!=='B') continue;
    $f="$d/$tip.html"; if(!is_file($f)) continue;
    $h=(string)file_get_contents($f);
    $fq=''; if(preg_match_all('~<details.*?</details>~is',$h,$m)) $fq=implode(' ',$m[0]);
    $tl=preg_replace('~<details.*?</details>~is',' ',$h);
    $tl=preg_replace('~\s+~u',' ',strip_tags($tl)); $fq=preg_replace('~\s+~u',' ',strip_tags($fq));
    $telo+=preg_match_all(YA,$tl); $telon+=slov($tl);
    $faq +=preg_match_all(YA,$fq); $faqn+=slov($fq);
    $n++;
}
printf("%s: доноров семьи B %d\n", $tip, $n);
printf("  тело:   %d «я» на %d слов = %.1f на 1000\n", $telo,$telon, 1000*$telo/max(1,$telon));
printf("  ответы: %d «я» на %d слов = %.1f на 1000\n", $faq,$faqn, 1000*$faq/max(1,$faqn));
printf("  доля ответов в объёме: %.0f %%\n", 100*$faqn/max(1,$telon+$faqn));
