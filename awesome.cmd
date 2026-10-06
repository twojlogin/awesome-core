@echo off
REM awesome.cmd — launcher na Windows (PowerShell, cmd, albo podwójne kliknięcie).
REM Plik awesome jest skryptem basha, więc na Windowsie potrzebna jest ta nakładka.
setlocal
set "HERE=%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%HERE%cli\awesome_cli.py" %*
) else (
  python "%HERE%cli\awesome_cli.py" %*
)
endlocal
