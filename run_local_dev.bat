@echo off
REM CoreDent Local Development Runner
REM Runs both backend and frontend in separate terminal windows

echo.
echo 🚀 Starting CoreDent Local Development...
echo.
echo Backend: http://localhost:8080
echo Frontend: http://localhost:5173
echo.
echo Login credentials:
echo   Email: admin@coredent.com
echo   Password: Admin123!@#
echo.

REM Start backend in a new window
echo 📦 Starting Backend...
start "CoreDent Backend" cmd /k "cd coredent-api && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"

REM Wait a moment for backend to start
timeout /t 3 /nobreak

REM Start frontend in a new window
echo 🎨 Starting Frontend...
start "CoreDent Frontend" cmd /k "cd coredent-style-main && npm run dev"

echo.
echo ✅ Both services are starting in separate windows!
echo.
echo Press Ctrl+C in each window to stop the services.
echo.
