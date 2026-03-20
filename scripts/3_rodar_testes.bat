@echo off
echo.
echo ==========================================
echo   PythGuard - Rodando Testes
echo ==========================================
echo.

cd /d "%~dp0..\backend"

if not exist venv (
    echo AVISO: Ambiente virtual nao encontrado.
    echo Execute primeiro: 1_rodar_backend.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

pip install pytest pytest-asyncio pytest-cov -q

echo.
echo Rodando suite completa de testes...
echo.

pytest tests/ -v --cov=app/core --cov-report=term-missing

echo.
pause
