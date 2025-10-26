# VPN Telegram Bot

[![Maintainability](https://qlty.sh/gh/inasekin/projects/tg-bot-vpn/maintainability.svg)](https://qlty.sh/gh/inasekin/projects/tg-bot-vpn)

Telegram-бот для управления VPN конфигурациями через AmneziaWG. Позволяет пользователям создавать, управлять и удалять VPN конфигурации для разных устройств с обфускацией трафика для обхода DPI блокировок.

## Возможности

- Создание нескольких VPN конфигураций (до 5) для одного пользователя
- Скачивание конфигураций в формате AmneziaWG с параметрами обфускации
- Обход DPI
- Просмотр профиля и списка конфигураций
- Управление конфигурациями
- Статистика для администратора
- Автоматическое распределение IP адресов
- Криптографическая генерация ключей X25519
- Настроен автоматический деплой на сервер, а так же CI для проверки линтера

## Требования

- Python 3.11 или выше
- AmneziaWG установлен на сервере
- Telegram Bot Token
- uv (менеджер пакетов Python)

## Установка

### 1. Установка AmneziaWG на сервере

```bash
# Установите зависимости
sudo apt update
sudo apt install -y build-essential git linux-headers-$(uname -r) pkg-config libmnl-dev

# Установите модуль ядра AmneziaWG
cd /root
git clone https://github.com/amnezia-vpn/amneziawg-linux-kernel-module
cd amneziawg-linux-kernel-module/src
sudo make && sudo make install
sudo modprobe amneziawg

# Установите awg-tools
cd /root
git clone https://github.com/amnezia-vpn/amneziawg-tools
cd amneziawg-tools/src
sudo make && sudo make install

# Создайте конфигурацию сервера
sudo mkdir -p /etc/amnezia/amneziawg
sudo nano /etc/amnezia/amneziawg/wg0.conf
```

Пример конфигурации сервера (замените PrivateKey на свой):

```ini
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = YOUR_PRIVATE_KEY_HERE
Jc = 5
Jmin = 50
Jmax = 1000
S1 = 86
S2 = 123
H1 = 1234567
H2 = 2345678
H3 = 3456789
H4 = 4567890
PostUp = sysctl -w net.ipv4.ip_forward=1
PostUp = iptables -I DOCKER-USER 1 -i wg0 -j ACCEPT
PostUp = iptables -I DOCKER-USER 1 -o wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o eth0 -j MASQUERADE
PostUp = iptables -t mangle -A FORWARD -i wg0 -o eth0 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
PostDown = iptables -D DOCKER-USER -i wg0 -j ACCEPT
PostDown = iptables -D DOCKER-USER -o wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -s 10.0.0.0/24 -o eth0 -j MASQUERADE
PostDown = iptables -t mangle -D FORWARD -i wg0 -o eth0 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
```

Запуск AmneziaWG:

```bash
# Запустите вручную
sudo awg-quick up /etc/amnezia/amneziawg/wg0.conf

# Или настройте автозапуск через systemd
sudo systemctl enable awg-quick@wg0
sudo systemctl start awg-quick@wg0
```

### 2. Установка бота

```bash
# Установите uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Клонируйте репозиторий
git clone https://github.com/yourusername/tg-bot-vpn
cd tg-bot-vpn

# Установите зависимости
uv sync
```

## Конфигурация

Создайте файл `.env` в корне проекта:

```env
BOT_TOKEN=your_telegram_bot_token_here
WG_SERVER_PUBLIC_KEY=your_server_public_key_here
WG_SERVER_ENDPOINT=your_server_ip:51820
ADMIN_ID=your_telegram_user_id
```

## Запуск

### Запуск в фоновом режиме

```bash
# Запустите бота
nohup uv run python src/main.py > bot.log 2>&1 &

# Проверьте логи
tail -f bot.log

# Остановите бота
pkill -f "python.*src/main.py"
```

### Быстрый деплой

```bash
# Используйте скрипт деплоя
bash scripts/deploy.sh
```

## Команды бота

- `/start` - Начать работу с ботом
- `Получить VPN` - Создать новую VPN конфигурацию
- `Мой профиль` - Просмотреть профиль и список конфигов
- `Управлять VPN` - Управлять существующими конфигурациями
- `/stats` - Просмотреть статистику (только для админа)

## Как это работает

1. Пользователь нажимает "Получить VPN"
2. Бот предлагает выбрать название конфигурации
3. Генерируются криптографические ключи X25519
4. Выделяется IP адрес из пула
5. Конфигурация с параметрами обфускации сохраняется в БД и добавляется на AmneziaWG сервер
6. Пользователю отправляется конфиг-файл для импорта в приложение Amnezia VPN

## Лимиты

- Максимум 5 конфигураций на пользователя
- Максимум 254 IP адреса в пуле (10.0.0.2 - 10.0.0.254)
- Уникальные имена конфигураций на пользователя
