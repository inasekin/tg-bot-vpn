#!/bin/bash

set -e

echo "Деплоим VPN бот..."

echo "Останавливаем бота..."
pkill -f "python.*src/main.py" || true

echo "Проверяем uv..."
if ! command -v uv &> /dev/null; then
    echo "Устанавливаем uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

echo "Обновляем зависимости..."
uv sync

echo "Запускаем бота..."
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
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