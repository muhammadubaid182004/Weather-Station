@echo off
echo Starting Weather Station Services...

:: Start API Server
start "API Server" cmd /k "cd /d %~dp0server && python weather_api_ota.py"

:: Wait a bit for the API to start
timeout /t 5

:: Start Weather Dashboard
start "Weather Dashboard" cmd /k "cd /d %~dp0dashboard && streamlit run dashboard.py --server.port=8501 --logger.level=debug"

:: Start Firmware Manager
start "Firmware Manager" cmd /k "cd /d %~dp0dashboard && streamlit run firmware_manager.py --server.port=8502 --logger.level=debug"


echo All services started!
echo.
echo API Server: http://localhost:5000
echo Weather Dashboard: http://localhost:8501  
echo Firmware Manager: http://localhost:8502
echo.
pause