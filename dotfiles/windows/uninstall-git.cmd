@echo off
rem uninstall-git.cmd - run windows\uninstall-git.ps1 from cmd.exe (arguments are passed through).
rem ASCII only: cmd.exe reads batch files in the OEM code page.
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall-git.ps1" %*
exit /b %ERRORLEVEL%
