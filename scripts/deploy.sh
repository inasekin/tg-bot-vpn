#!/bin/bash

set -e

echo "Деплоим VPN бот..."

echo "Останавливаем бота..."
pkill -f "python.*src/main.py" || true

echo "Обновляем зависимости..."
uv sync

echo "Запускаем бота..."
nohup uv run python src/main.py > bot.log 2>&1 &

sleep 2

if pgrep -f "python.*src/main.py" > /dev/null; then
    echo ""
    echo "✓ Бот успешно запущен!"
    echo "Логи: tail -f bot.log"
else
    echo ""
    echo "✗ Ошибка запуска! Проверьте логи: cat bot.log"
    exit 1
fi