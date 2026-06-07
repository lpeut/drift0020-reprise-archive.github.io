@echo off
echo Starting local web server...
echo Please open http://localhost:8000 in your browser.
echo Press Ctrl+C to stop the server.

:: Change directory to the root (one level up from scripts)
cd /d "%~dp0.."

start http://localhost:8000
python -m http.server 8000
pause
