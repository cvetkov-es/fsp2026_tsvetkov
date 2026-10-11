@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ================================================
echo   ФСП · Обратный найм — локальный стенд
echo ================================================
echo.

where docker >nul 2>nul
if errorlevel 1 goto no_docker

docker info >nul 2>nul
if errorlevel 1 goto docker_off

if exist ".env" goto up

echo [1/2] Файла .env нет — создаю из .env.example и генерирую секрет...
copy /y ".env.example" ".env" >nul
for /f %%k in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"') do set NEWKEY=%%k
powershell -NoProfile -Command "(Get-Content .env -Raw).Replace('SECRET_KEY=change-me','SECRET_KEY=%NEWKEY%') | Set-Content -Encoding UTF8 .env"

:up
echo [2/2] Собираю и запускаю стенд.
echo       Первый запуск занимает несколько минут: образы, миграции, банк заданий, засев.
echo.
docker compose up -d --build --wait
if errorlevel 1 goto failed

echo.
echo Готово. Стенд открывается на http://localhost:8080
echo В шапке — переключатель демо-персон: кандидат, работодатель, модератор.
echo Остановить стенд: stop.cmd
echo.
start "" "http://localhost:8080"
pause
exit /b 0

:no_docker
echo Docker не найден. Установите Docker Desktop и запустите его:
echo   https://www.docker.com/products/docker-desktop/
echo.
pause
exit /b 1

:docker_off
echo Docker установлен, но не запущен. Откройте Docker Desktop и повторите запуск.
echo.
pause
exit /b 1

:failed
echo.
echo Не удалось поднять стенд. Посмотреть журнал: docker compose logs
echo.
pause
exit /b 1
