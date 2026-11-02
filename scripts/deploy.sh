#!/bin/bash

set -euo pipefail

# В неинтерактивной SSH-сессии ~/.local/bin не в PATH — без этого uv
# переустанавливался бы при каждом деплое.
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

echo "Деплоим VPN бот..."

echo "Проверяем uv..."
if ! command -v uv &> /dev/null; then
    echo "Устанавливаем uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "Обновляем зависимости..."
uv sync --locked

# Падаем ДО остановки работающего бота, если .env невалиден.
echo "Проверяем конфигурацию (.env, AWG-параметры)..."
(cd src && uv run python -c "
from dotenv import load_dotenv
load_dotenv('../.env')
import config
assert config.SERVERS, 'не настроен ни один сервер'
print('Серверы:', ', '.join(config.SERVERS))
")

echo "Останавливаем бота..."
pkill -f "python.*src/main.py" || true
sleep 1

echo "Запускаем бота..."
nohup uv run python src/main.py > bot.log 2>&1 &

# Бот может упасть не сразу (ошибка токена, сети) — проверяем дольше 2 секунд.
sleep 10

if pgrep -f "python.*src/main.py" > /dev/null; then
    echo ""
    echo "✓ Бот успешно запущен!"
    echo "Логи: tail -f bot.log"
else
    echo ""
    echo "✗ Ошибка запуска! Последние строки bot.log:"
    tail -n 30 bot.log || true
    exit 1
fi
