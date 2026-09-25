@echo off
rem agents-scaffold Windows launcher (#58).
rem Runs bin/agents-scaffold.sh with Git Bash (Git for Windows). Works offline:
rem when started from an extracted bundle nothing is downloaded.
rem WSL's C:\Windows\System32\bash.exe is deliberately NOT used (different filesystem view).
rem Override detection with AGENTS_SCAFFOLD_BASH=<path to Git\bin\bash.exe>.
setlocal

set "GITBASH="
if defined AGENTS_SCAFFOLD_BASH if exist "%AGENTS_SCAFFOLD_BASH%" set "GITBASH=%AGENTS_SCAFFOLD_BASH%"
if not defined GITBASH if defined CLAUDE_CODE_GIT_BASH_PATH if exist "%CLAUDE_CODE_GIT_BASH_PATH%" set "GITBASH=%CLAUDE_CODE_GIT_BASH_PATH%"
if not defined GITBASH if exist "%ProgramFiles%\Git\bin\bash.exe" set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined GITBASH if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "GITBASH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
if not defined GITBASH for /f "delims=" %%G in ('where git.exe 2^>nul') do if not defined GITBASH if exist "%%~dpG..\bin\bash.exe" set "GITBASH=%%~dpG..\bin\bash.exe"

if not defined GITBASH (
  echo [agents-scaffold] Git Bash not found. Install Git for Windows ^(offline installer^),
  echo [agents-scaffold] or set AGENTS_SCAFFOLD_BASH to the full path of Git\bin\bash.exe.
  exit /b 1
)

rem Hooks call python3. The WindowsApps "python3" is a Store stub that fails, so run it.
"%GITBASH%" -c "python3 -c 'import sys' >/dev/null 2>&1"
if errorlevel 1 (
  echo [agents-scaffold] WARNING: python3 is not runnable from Git Bash. Install continues,
  echo [agents-scaffold] but observe-lite / stop-memory-remind hooks need it. See docs/OFFLINE_INSTALL.en.md.
)

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_SH=%SCRIPT_DIR:\=/%agents-scaffold.sh"
"%GITBASH%" "%SCRIPT_SH%" %*
exit /b %ERRORLEVEL%
