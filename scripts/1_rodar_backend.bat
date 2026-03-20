@echo off
echo.
echo ==========================================
echo   PythGuard - Backend Setup (Windows)
echo ==========================================
echo.

cd /d "%~dp0..\backend"

echo [1/4] Criando ambiente virtual Python...
python -m venv venv
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale em https://python.org/downloads
    pause
    exit /b 1
)

echo [2/4] Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo [3/4] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo [4/4] Copiando arquivo .env...
if not exist .env (
    if exist ..\.env (
        copy ..\.env .env
        echo .env copiado com sucesso.
    ) else (
        echo AVISO: .env nao encontrado. Crie o arquivo .env na pasta pythguard/
        pause
        exit /b 1
    )
)

echo.
echo ==========================================
echo   Backend rodando em http://localhost:8000
echo   Swagger docs: http://localhost:8000/docs
echo   Pressione Ctrl+C para parar
echo ==========================================
echo.

uvicorn app.main:application --reload --port 8000
pause
