import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from dotenv import load_dotenv

from database import db
from wireguard import generate_keys, create_client_config
from server import add_peer_to_server, remove_peer_from_server

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

SERVER_PUBLIC_KEY = os.getenv("WG_SERVER_PUBLIC_KEY")
SERVER_ENDPOINT = os.getenv("WG_SERVER_ENDPOINT")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

PREDEFINED_NAMES = ["Компьютер", "Телефон", "Планшет", "Ноутбук", "Другое"]


def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Получить VPN")],
            [KeyboardButton(text="Мой профиль")],
            [KeyboardButton(text="Управлять VPN")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def get_name_selection_keyboard():
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"select_name_{name}")]
        for name in PREDEFINED_NAMES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_config_management_keyboard(user_id, configs):
    buttons = []
    for config in configs:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"Скачать {config['name']}", callback_data=f"download_{config['name']}"
                ),
                InlineKeyboardButton(text="Удалить", callback_data=f"delete_{config['name']}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    db.add_user(user_id, username, first_name)
    logger.info(f"User {user_id} ({username}) started bot")

    await message.answer(
        f"Привет, {first_name}!\n\n"
        f"Я VPN бот. Нажми кнопку ниже чтобы получить VPN конфигурацию.",
        reply_markup=get_main_keyboard(),
    )


@dp.message(F.text == "Получить VPN")
async def get_vpn_start(message: types.Message):
    logger.info(f"User {message.from_user.id} pressed 'Получить VPN'")
    user_id = message.from_user.id
    configs = db.get_all_vpn_configs(user_id)

    if len(configs) >= 5:
        await message.answer(
            "Вы уже создали максимум конфигов (5). Удалите один из них чтобы создать новый."
        )
        return

    await message.answer(
        "Выбери название для конфигурации:", reply_markup=get_name_selection_keyboard()
    )


@dp.callback_query(F.data.startswith("select_name_"))
async def select_name(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        name = callback.data.replace("select_name_", "")

        existing_config = db.get_vpn_config(user_id, name)
        if existing_config:
            await callback.answer("Конфиг с таким названием уже существует", show_alert=True)
            return

        await callback.answer()
        await callback.message.edit_text("Создаю VPN конфигурацию...")

        private_key, public_key = generate_keys()
        client_ip = db.get_next_ip()

        db.add_vpn_config(user_id, name, private_key, public_key, client_ip)

        success = add_peer_to_server(public_key, client_ip)
        if not success:
            logger.warning(f"Не удалось связать пользователя с сервером {user_id}")

        config_text = create_client_config(
            private_key=private_key,
            server_public_key=SERVER_PUBLIC_KEY,
            server_endpoint=SERVER_ENDPOINT,
            client_ip=client_ip,
        )

        config_file = types.BufferedInputFile(
            config_text.encode("utf-8"), filename=f"vpn_{name.lower()}.conf"
        )

        await callback.message.edit_text(
            f"Конфиг '{name}' готов!\n\nIP: {client_ip}\n\n"
            f"Скачайте файл и импортируйте в приложение WireGuard"
        )

        await callback.message.answer_document(
            config_file, caption=f"Ваша VPN конфигурация для {name}"
        )

        logger.info(f"Создан VPN config для user {user_id}, название: {name}, IP: {client_ip}")
    except Exception as e:
        logger.error(f"Ошибка при создании конфига: {e}")
        await callback.answer("Произошла ошибка при создании конфига", show_alert=True)
        try:
            await callback.message.edit_text("Произошла ошибка. Попробуйте снова.")
        except Exception:
            pass


@dp.message(F.text == "Управлять VPN")
async def manage_vpn(message: types.Message):
    try:
        logger.info(f"User {message.from_user.id} pressed 'Управлять VPN'")
        user_id = message.from_user.id
        configs = db.get_all_vpn_configs(user_id)

        if not configs:
            await message.answer(
                "У вас нет созданных VPN конфигураций. Создайте новый, нажав 'Получить VPN'."
            )
            return

        config_list = "\n".join(
            [
                f"• {cfg['name']} (IP: {cfg['ip_address']})"
                for cfg in configs
            ]
        )

        await message.answer(
            f"Ваши VPN конфигурации:\n\n{config_list}\n\nВыберите действие:",
            reply_markup=get_config_management_keyboard(user_id, configs),
        )
    except Exception as e:
        logger.error(f"Ошибка в manage_vpn: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")


@dp.callback_query(F.data.startswith("download_"))
async def download_config(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        name = callback.data.replace("download_", "")

        config = db.get_vpn_config(user_id, name)
        if not config:
            await callback.answer("Конфиг не найден", show_alert=True)
            return

        config_text = create_client_config(
            private_key=config["private_key"],
            server_public_key=SERVER_PUBLIC_KEY,
            server_endpoint=SERVER_ENDPOINT,
            client_ip=config["ip_address"],
        )

        config_file = types.BufferedInputFile(
            config_text.encode("utf-8"), filename=f"vpn_{name.lower()}.conf"
        )

        await callback.message.answer_document(
            config_file, caption=f"Конфиг '{name}' (IP: {config['ip_address']})"
        )
        await callback.answer()
        logger.info(f"User {user_id} downloaded config {name}")
    except Exception as e:
        logger.error(f"Ошибка при скачивании конфига: {e}")
        await callback.answer("Произошла ошибка при скачивании", show_alert=True)


@dp.callback_query(F.data.startswith("delete_"))
async def delete_config(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        name = callback.data.replace("delete_", "")

        config = db.get_vpn_config(user_id, name)
        if not config:
            await callback.answer("Конфиг не найден", show_alert=True)
            return

        success = remove_peer_from_server(config["public_key"])
        db.delete_vpn_config(user_id, name)

        logger.info(f"Удален VPN конфиг {user_id}: {name}")

        if success:
            await callback.answer("Конфиг удален с сервера и из базы", show_alert=True)
        else:
            await callback.answer(
                "Конфиг удален из базы (ошибка удаления с сервера)", show_alert=True
            )

        configs = db.get_all_vpn_configs(user_id)
        if configs:
            config_list = "\n".join(
                [
                    f"• {cfg['name']} (IP: {cfg['ip_address']})"
                    for cfg in configs
                ]
            )
            await callback.message.edit_text(
                f"Ваши VPN конфигурации:\n\n{config_list}\n\nВыберите действие:",
                reply_markup=get_config_management_keyboard(user_id, configs),
            )
        else:
            await callback.message.edit_text("Больше нет созданных конфигов.")
    except Exception as e:
        logger.error(f"Ошибка при удалении конфига: {e}")
        await callback.answer("Произошла ошибка при удалении", show_alert=True)


@dp.message(F.text == "Мой профиль")
async def show_profile(message: types.Message):
    try:
        logger.info(f"User {message.from_user.id} pressed 'Мой профиль'")
        user_id = message.from_user.id

        db.add_user(user_id, message.from_user.username, message.from_user.first_name)

        user = db.get_user(user_id)
        configs = db.get_all_vpn_configs(user_id)

        if not user:
            await message.answer("Ошибка получения профиля")
            return

        profile_text = "<b>Ваш профиль</b>\n\n"
        profile_text += f"ID: <code>{user_id}</code>\n"
        profile_text += f"Username: @{user.get('username', 'нет')}\n"

        created_at = user.get('created_at', 'Неизвестно')
        if created_at and created_at != 'Неизвестно':
            profile_text += f"Регистрация: {created_at}\n\n"
        else:
            profile_text += "Регистрация: Неизвестно\n\n"

        if configs:
            profile_text += "<b>Ваши VPN конфигурации:</b>\n"
            for cfg in configs:
                profile_text += f"• {cfg['name']} (IP: {cfg['ip_address']})\n"
        else:
            profile_text += "VPN конфигурация не создана\n\n"
            profile_text += "Нажмите 'Получить VPN' чтобы создать"

        await message.answer(profile_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в show_profile: {e}")
        await message.answer("Произошла ошибка при получении профиля. Попробуйте снова.")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    try:
        if message.from_user.id != ADMIN_ID:
            return

        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vpn_configs")
            total_configs = cursor.fetchone()[0]

        stats_text = "<b>Статистика</b>\n\n"
        stats_text += f"Всего пользователей: {total_users}\n"
        stats_text += f"VPN конфигураций: {total_configs}"

        await message.answer(stats_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в cmd_stats: {e}")
        await message.answer("Произошла ошибка при получении статистики.")


@dp.callback_query()
async def unknown_callback_handler(callback: types.CallbackQuery):
    logger.warning(f"Необработанный callback от {callback.from_user.id}: '{callback.data}'")
    await callback.answer("Неизвестное действие", show_alert=True)


@dp.message()
async def echo_handler(message: types.Message):
    logger.info(f"Необработанное сообщение от {message.from_user.id}: '{message.text}'")
    await message.answer(
        "Используйте кнопки ниже для управления VPN", reply_markup=get_main_keyboard()
    )


async def main():
    logger.info("Бот запускается...")
    logger.info(f"Server endpoint: {SERVER_ENDPOINT}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
