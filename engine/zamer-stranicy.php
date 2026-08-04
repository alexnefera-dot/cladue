<?php
require_once "/home/user/cladue/engine/src/PageMetrics.php";
$t=$argv[1]; $dir=$argv[2]??"/home/user/cladue/samples/v3-final/ruchnoy-227";
$a=new Analyzer(); $F=PageMetrics::fields(true);
$R=PageMetrics::measure($a,$t,file_get_contents("/home/user/cladue/samples/dorgen-reference/set227/$t.html"),["ru"=>"","en"=>""]);
$O=PageMetrics::measure($a,$t,file_get_contents("$dir/$t.html"),["ru"=>"","en"=>""]);
$h=0;$c=0;
foreach($F as $k=>[$lab,$rate]){ $c++; $bad=PageMetrics::off($O[$k],$R[$k],(bool)$rate); if(!$bad)$h++;
  printf("%-22s %8s %8s  %s\n",$k,is_float($O[$k])?round($O[$k],1):$O[$k],is_float($R[$k])?round($R[$k],1):$R[$k],$bad?"XXXX":"ok"); }
printf("\n%s: %d/%d = %d%%\n",$t,$h,$c,round($h/$c*100));
