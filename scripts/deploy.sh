#!/bin/bash

echo "Деплоим..."

docker-compose down

docker-compose build

docker-compose up -d

echo "Хоп, собрался!"