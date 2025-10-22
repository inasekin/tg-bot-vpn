#!/bin/bash

set -e

echo "Деплоим..."

echo "Останавливаем контейнер..."
docker-compose down
echo "Собираем образ..."
docker-compose build
echo "Запускаем ..."
docker-compose up -d
echo ""
echo "Хоп, собрался!"