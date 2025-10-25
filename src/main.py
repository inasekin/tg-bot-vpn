import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from database import db
from wireguard import generate_keys, create_client_config
from server import add_peer_to_server, remove_peer_from_server

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

SERVER_PUBLIC_KEY = os.getenv('WG_SERVER_PUBLIC_KEY')
SERVER_ENDPOINT = os.getenv('WG_SERVER_ENDPOINT')
ADMIN_ID = int(os.getenv('ADMIN_ID'))


def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Получить VPN")],
            [KeyboardButton(text="Мой профиль")],
            [KeyboardButton(text="Удалить VPN")],
        ],
        resize_keyboard=True
    )
    return keyboard


@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    db.add_user(user_id, username, first_name)
    logger.info(f"User {user_id} ({username}) started bot")

    await message.answer(
        f"Привет, {first_name}!\n\n"
        f"Я VPN бот. Нажми кнопку ниже чтобы получить VPN конфигурацию.",
        reply_markup=get_main_keyboard()
    )


@dp.message(lambda message: message.text == "Получить VPN")
async def get_vpn_config(message: types.Message):
    user_id = message.from_user.id

    existing_config = db.get_vpn_config(user_id)
    if existing_config:
        await message.answer("У вас уже есть VPN конфигурация!\n\nОтправляю её заново...")

        config_text = create_client_config(
            private_key=existing_config['private_key'],
            server_public_key=SERVER_PUBLIC_KEY,
            server_endpoint=SERVER_ENDPOINT,
            client_ip=existing_config['ip_address']
        )
    else:
        await message.answer("Создаю VPN конфигурацию...")

        private_key, public_key = generate_keys()

        client_ip = db.get_next_ip()

        db.add_vpn_config(user_id, private_key, public_key, client_ip)

        success = add_peer_to_server(public_key, client_ip)
        if not success:
            logger.warning(f"Не удалось связать пользователя с сервером {user_id}")

        config_text = create_client_config(
            private_key=private_key,
            server_public_key=SERVER_PUBLIC_KEY,
            server_endpoint=SERVER_ENDPOINT,
            client_ip=client_ip
        )

        logger.info(f"Создан VPN config для user {user_id}, IP: {client_ip}")

    config_file = types.BufferedInputFile(
        config_text.encode('utf-8'),
        filename=f"vpn_{user_id}.conf"
    )

    vpn_config = db.get_vpn_config(user_id)

    await message.answer_document(
        config_file,
        caption=f"Ваша VPN конфигурация готова!\n\n"
                f"IP: {vpn_config['ip_address']}\n\n"
                f"Скачайте файл и импортируйте в приложение WireGuard"
    )


@dp.message(lambda message: message.text == "Мой профиль")
async def show_profile(message: types.Message):
    """Показать профиль пользователя"""
    user_id = message.from_user.id

    db.add_user(user_id, message.from_user.username, message.from_user.first_name)

    user = db.get_user(user_id)
    vpn_config = db.get_vpn_config(user_id)

    if not user:
        await message.answer("Ошибка получения профиля")
        return

    profile_text = f"<b>Ваш профиль</b>\n\n"
    profile_text += f"ID: <code>{user_id}</code>\n"
    profile_text += f"Username: @{user.get('username', 'нет')}\n"
    profile_text += f"Регистрация: {user['created_at']}\n\n"

    if vpn_config:
        profile_text += f"<b>VPN конфигурация:</b>\n"
        profile_text += f"IP: <code>{vpn_config['ip_address']}</code>\n"
        profile_text += f"Создана: {vpn_config['created_at']}"
    else:
        profile_text += "VPN конфигурация не создана\n\n"
        profile_text += "Нажмите 'Получить VPN' чтобы создать"

    await message.answer(profile_text, parse_mode="HTML")


@dp.message(lambda message: message.text == "Удалить VPN")
async def delete_vpn_config(message: types.Message):
    """Удаление VPN конфигурации"""
    user_id = message.from_user.id

    vpn_config = db.get_vpn_config(user_id)

    if not vpn_config:
        await message.answer("У вас нет VPN конфигурации")
        return

    success = remove_peer_from_server(vpn_config['public_key'])

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM vpn_configs WHERE user_id = ?', (user_id,))
        conn.commit()

    logger.info(f"Удаляем VPN конфиг {user_id}")

    if success:
        await message.answer("VPN конфигурация удалена с сервера и из базы!")
    else:
        await message.answer("VPN конфигурация удалена из базы\n (не удалось удалить с сервера)")

@dp.message(Command('stats'))
async def cmd_stats(message: types.Message):
    """Статистика (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        return

    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM vpn_configs')
        total_configs = cursor.fetchone()[0]

    stats_text = f"<b>Статистика</b>\n\n"
    stats_text += f"Всего пользователей: {total_users}\n"
    stats_text += f"VPN конфигураций: {total_configs}"

    await message.answer(stats_text, parse_mode="HTML")


async def main():
    logger.info("Бот запускается...")
    logger.info(f"Server endpoint: {SERVER_ENDPOINT}")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())