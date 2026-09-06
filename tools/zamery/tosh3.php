<?php
foreach (glob(__DIR__ . '/../../engine/src/*.php') as $f) require_once $f;
$raw = NicheLexicon::unplaceholder(file_get_contents($argv[1]));
$parser = Parser::fromHtml($raw);
$tm = new TextMetrics($parser->text);
$r = new ReflectionClass($tm);
$m = $r->getMethod('contentFreq'); $m->setAccessible(true);
$f = $m->invoke($tm);
$n = $tm->wordCount();
$rep = 0; foreach ($f as $c) if ($c>1) $rep += $c;
echo "слов $n, повторов $rep, тошнота ".round($rep/$n*100,1)."\n";
arsort($f);
$i=0; foreach ($f as $w=>$c) { if ($c>1) { echo "  $w $c\n"; } }
