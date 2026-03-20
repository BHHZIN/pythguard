@echo off
echo.
echo ==========================================
echo   PythGuard - Frontend Setup (Windows)
echo ==========================================
echo.

cd /d "%~dp0..\frontend"

echo [1/3] Verificando Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Node.js nao encontrado. Instale em https://nodejs.org (versao LTS)
    pause
    exit /b 1
)

echo [2/3] Instalando dependencias...
npm install
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias npm.
    pause
    exit /b 1
)

echo [3/3] Criando .env do frontend...
if not exist .env (
    echo VITE_BACKEND_URL=http://localhost:8000 > .env
    echo .env criado com sucesso.
)

echo.
echo ==========================================
echo   Frontend rodando em http://localhost:3000
echo   Abrindo no browser...
echo   Pressione Ctrl+C para parar
echo ==========================================
echo.

start http://localhost:3000
npm run dev
pause
