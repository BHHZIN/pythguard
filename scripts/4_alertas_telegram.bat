@echo off
echo.
echo ==========================================
echo   PythGuard - Monitor de Alertas Telegram
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

echo Iniciando monitor de alertas...
echo O monitor vai checar suas posicoes a cada 30 segundos.
echo Pressione Ctrl+C para parar.
echo.

python -m app.core.telegram_alerts
pause
