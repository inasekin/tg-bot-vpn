#!/bin/bash

echo "Инициализация VPN бота..."

if [ ! -f .env ]; then
    echo "Создаю .env из .env.example..."
    cp .env.example .env
    echo "Пожалуйста, заполните .env своими данными"
else
    echo ".env уже существует"
fi

echo "Установка зависимостей..."
if command -v uv &> /dev/null; then
    uv sync
else
    pip install -r requirements.txt
fi

echo "Создание директории data..."
mkdir -p data

echo "Готово! Заполните .env и запустите: make run"
