#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Настройка окружения для AI Keynote Bot${NC}"

# Проверка наличия Python 3.9+
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${YELLOW}Обнаружена версия Python: ${python_version}${NC}"

# Создание виртуального окружения
echo -e "${GREEN}Создание виртуального окружения...${NC}"
python3 -m venv .venv

# Активация виртуального окружения
echo -e "${GREEN}Активация виртуального окружения...${NC}"
source .venv/bin/activate

# Обновление pip
echo -e "${GREEN}Обновление pip...${NC}"
pip install --upgrade pip

# Установка зависимостей
echo -e "${GREEN}Установка зависимостей...${NC}"
pip install -r requirements.txt

# Проверка ffmpeg (нужен для pydub)
echo -e "${GREEN}Проверка наличия ffmpeg...${NC}"
if command -v ffmpeg &> /dev/null; then
    echo -e "${GREEN}ffmpeg установлен${NC}"
else
    echo -e "${YELLOW}ffmpeg не найден. Рекомендуется установить ffmpeg для работы с аудио:${NC}"
    echo -e "    На macOS: brew install ffmpeg"
    echo -e "    На Ubuntu: sudo apt-get install ffmpeg"
    echo -e "    На Windows: скачайте с https://ffmpeg.org/download.html"
fi

# Создание каталогов для временных файлов
echo -e "${GREEN}Создание каталогов для временных файлов...${NC}"
mkdir -p voice/temp

echo -e "${GREEN}Настройка завершена!${NC}"
echo -e "${YELLOW}Для активации окружения используйте команду:${NC}"
echo -e "    source .venv/bin/activate"
echo -e "${YELLOW}Заполните файл .env своими ключами API${NC}"
echo -e "${YELLOW}Для запуска бота используйте:${NC}"
echo -e "    python -m bot.main" 