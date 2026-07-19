@echo off
echo ===================================================
echo             PIXELPDF WEB SERVER LAUNCHER
echo ===================================================
echo.
echo Installing python dependencies...
python -m pip install -r "%~dp0requirements.txt"
echo.
echo Starting Flask Development Server...
echo Open your browser and navigate to: http://127.0.0.1:5000
echo.
python "%~dp0app.py"
pause
