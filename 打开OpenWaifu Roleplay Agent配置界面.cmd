@echo off
setlocal
where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "" pythonw "%~dp0roleplay-agent\tools\launch_config_ui.py"
) else (
  start "" python "%~dp0roleplay-agent\tools\launch_config_ui.py"
)
