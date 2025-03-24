@echo off
echo Настройка окружения для AI Keynote Bot

REM Проверка наличия Python
python --version
if %ERRORLEVEL% NEQ 0 (
    echo Python не найден. Установите Python 3.9 или выше.
    exit /b 1
)

REM Создание виртуального окружения
echo Создание виртуального окружения...
python -m venv .venv

REM Активация виртуального окружения
echo Активация виртуального окружения...
call .venv\Scripts\activate.bat

REM Обновление pip
echo Обновление pip...
python -m pip install --upgrade pip

REM Установка зависимостей
echo Установка зависимостей...
pip install -r requirements.txt

REM Проверка ffmpeg (нужен для pydub)
where ffmpeg >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ffmpeg не найден. Рекомендуется установить ffmpeg для работы с аудио.
    echo Скачайте с https://ffmpeg.org/download.html и добавьте в PATH
)

REM Создание каталогов для временных файлов
echo Создание каталогов для временных файлов...
if not exist voice\temp mkdir voice\temp

echo Настройка завершена!
echo Для активации окружения используйте команду:
echo     .venv\Scripts\activate.bat
echo Заполните файл .env своими ключами API
echo Для запуска бота используйте:
echo     python -m bot.main

pause 