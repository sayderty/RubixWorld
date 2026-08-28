import os
import asyncio
import logging
import re
import aiomysql
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# Получаем настройки из хостинга BotHost (переменные окружения)
# Если переменная не задана на хостинге, используется значение по умолчанию
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_ЕСЛИ_БЕЗ_ПЕРЕМЕННЫХ")

DB_HOST = os.getenv("DB_HOST", "sql.myhost.ru")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "u12345_rubix")
DB_PASSWORD = os.getenv("DB_PASSWORD", "твой_пароль_бд")
DB_NAME = os.getenv("DB_NAME", "db_rubixworld")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Функция подключения к базе данных MySQL
async def create_db_pool():
    return await aiomysql.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

# Создание нужных таблиц в базе
async def init_db(pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_codes (
                    code VARCHAR(6) PRIMARY KEY,
                    mc_username VARCHAR(32) NOT NULL
                )
            """)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS linked_accounts (
                    mc_username VARCHAR(32) PRIMARY KEY,
                    tg_id BIGINT DEFAULT NULL,
                    vk_id BIGINT DEFAULT NULL
                )
            """)

# Обработка команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Привет! Это официальный бот сервера RubixWorld.**\n\n"
        "Чтобы привязать свой аккаунт Minecraft:\n"
        "1. Зайди на сервер RubixWorld в игре.\n"
        "2. Введи команду `/link` и получи 6-значный код.\n"
        "3. Отправь полученный код сюда в чат!"
    )

# Обработка 6 цифр (кода привязки)
@dp.message(F.text.regexp(r"^\d{6}$"))
async def process_code(message: types.Message):
    code = message.text
    tg_id = message.from_user.id
    pool = dp["db_pool"]

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Ищем код в базе данных
            await cursor.execute("SELECT mc_username FROM pending_codes WHERE code = %s", (code,))
            row = await cursor.fetchone()

            if row:
                mc_username = row[0]

                # Привязываем Telegram ID к нику в Minecraft
                await cursor.execute("""
                    INSERT INTO linked_accounts (mc_username, tg_id) VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE tg_id = VALUES(tg_id)
                """, (mc_username, tg_id))

                # Удаляем код, так как он одноразовый
                await cursor.execute("DELETE FROM pending_codes WHERE code = %s", (code,))

                await message.answer(f"✅ Успешно! Твой Telegram привязан к аккаунту **{mc_username}** на RubixWorld.")
            else:
                await message.answer("❌ Неверный код или его срок действия истек. Получи новый код командой `/link` на сервере.")

# Ответ на любой другой текст
@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("Отправь мне 6-значный код из игры (например, `123456`) для привязки аккаунта.")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Запуск бота RubixWorld...")

    # Создаем подключение к базе данных
    pool = await create_db_pool()
    await init_db(pool)
    dp["db_pool"] = pool

    # Запускаем постоянное прослушивание сообщений
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())