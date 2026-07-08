@echo off
setlocal
cd /d "%~dp0"
where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "" pythonw "%~dp0tools\launch_config_ui.py"
) else (
  start "" python "%~dp0tools\launch_config_ui.py"
)
