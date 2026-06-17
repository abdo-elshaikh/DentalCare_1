@echo off
SETLOCAL EnableDelayedExpansion
TITLE DentalCare - Launcher
echo ================================================================
echo       DentalCare - Launcher
echo ================================================================

:: 1. Check for required tools (Python, .NET)
echo [1/4] Checking for required tools and dependencies...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.8+ and ensure it's in your PATH.
    exit /b 1
)

where dotnet >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ .NET SDK is not installed. Please install the .NET SDK and ensure it's in your PATH.
    exit /b 1
)

:: Check for virtual environment in AI service (aligned to 'env' directory)
if not exist "ai_service\env\Scripts\activate" (
    echo ❌ Virtual environment not found in ai_service\env.
    echo Please set up the virtual environment before running this launcher:
    echo   cd ai_service
    echo   python -m venv env
    echo   .\env\Scripts\activate
    echo   pip install -r requirements.txt
    exit /b 1
)



echo.
echo ================================================================
echo       Starting DentalCare Microservices...
echo ================================================================

:: 2. Start AI Microservice
echo [2/4] Starting AI Microservice (FastAPI)...
start "AI Microservice" /D "ai_service" cmd /k "call .\env\Scripts\activate && python api\main.py"

:: 3. Start .Net Microservice
echo [3/4] Starting .Net Microservice...
start " .Net Microservice" /D "DentalCare" cmd /k "dotnet watch run"

echo.
echo ================================================================
echo   ✅ ALL SERVICES STARTED SUCCESSFULLY!
echo ================================================================
echo   - Python  API:  http://localhost:8000/docs
echo   - .Net API:  http://localhost:5192/
echo ================================================================
echo   Keep this launcher open to monitor startup logs or close if done.
echo ================================================================
pause