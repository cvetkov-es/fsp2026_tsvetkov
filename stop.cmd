@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Останавливаю стенд ФСП · Обратный найм...
docker compose down
echo.
echo Готово. Данные остались в томе: следующий запуск через start.cmd поднимет стенд как был.
pause
