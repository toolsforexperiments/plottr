@set "APPPATH=c:\your\path\to\plottr\apps"
@activate qcodes & python %APPPATH%\autoplot_ddh5.py --filepath %1
pause