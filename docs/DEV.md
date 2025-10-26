## Локальная разработка

### Быстрый старт

1. Клонируйте репозиторий:
```bash
git clone https://github.com/inasekin/tg-bot-vpn.git
cd tg-bot-vpn
```

2. Инициализируйте проект:
```bash
bash scripts/init.sh
```

3. Отредактируйте `.env`:
```bash
vim .env
```

Добавьте ваши данные:
```
BOT_TOKEN=ваш_токен_от_бота
WG_SERVER_PUBLIC_KEY=публичный_ключ_сервера
WG_SERVER_ENDPOINT=ip_сервера:51820
ADMIN_ID=ваш_telegram_id
```

4. Запустите бота:
```bash
uv run python src/main.py
```

Если у вас нет uv, используйте pip:

```bash
pip install -r requirements.txt
python main.py
```

### AmneziaWG сервер

Для локальной разработки вам нужен AmneziaWG сервер. Вы можете использовать:

1. Реальный VPS с AmneziaWG
2. Docker контейнер с AmneziaWG (линвх/нижний уровень)
3. Virtualbox виртуальную машину

### Структура БД

Проект использует SQLite. При первом запуске автоматически создается база данных в `data/bot.db`.

Схема включает две таблицы:
- users: информация о пользователях
- vpn_configs: конфигурации VPN с названиями

### Отладка

Для отладки включите логирование:

В main.py уже настроено логирование уровня INFO. Для более подробных логов измените в main.py:

```python
logging.basicConfig(level=logging.DEBUG)
```
