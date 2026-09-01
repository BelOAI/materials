$ENV{'TEXINPUTS'} = './latex/tex/latex//:' . ($ENV{'TEXINPUTS'} // '');
$pdf_mode = 1;
$pdflatex = 'pdflatex -file-line-error -halt-on-error -interaction=nonstopmode %O %S';
