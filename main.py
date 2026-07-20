from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)
import asyncio

# ==========================
# ВСТАВЬ СЮДА ТОКЕН БОТА
BOT_TOKEN = "8804748206:AAH2NvoNqMT6EFb2v9_9NLF30QejL82AyQY"
# ==========================

ADMIN_ID = 7738822030

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

users = {}
reports = []

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📄 Подать заявку")],
        [KeyboardButton(text="📊 Статус заявки")],
        [KeyboardButton(text="🐞 Баг-репорт")],
        [KeyboardButton(text="ℹ️ Информация")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Все заявки")],
        [KeyboardButton(text="🐞 Все баги")]
    ],
    resize_keyboard=True
)


@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"👋 Привет, Администратор!\n\nID: <code>{message.from_user.id}</code>",
            reply_markup=admin_menu
        )
    else:
        users[message.from_user.id] = "Не отправлена"
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Это бот bet mobile.",
            reply_markup=menu
        )


@dp.message(F.text == "📄 Подать заявку")
async def apply(message: Message):
    users[message.from_user.id] = "На рассмотрении"

    await message.answer(
        "✅ Заявка успешно отправлена!\n\n"
        "Ожидайте решения администрации."
    )

    await bot.send_message(
        ADMIN_ID,
        f"📄 Новая заявка\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username}"
    )


@dp.message(F.text == "📊 Статус заявки")
async def status(message: Message):
    status = users.get(message.from_user.id, "Не отправлена")

    await message.answer(
        f"📊 Статус заявки:\n\n<b>{status}</b>"
    )


@dp.message(F.text == "🐞 Баг-репорт")
async def bug(message: Message):
    await message.answer(
        "✍️ Отправьте сообщение с описанием бага."
    )


@dp.message(F.text == "ℹ️ Информация")
async def info(message: Message):
    await message.answer(
        "ℹ️ TEST HUB Bot\n\n"
        "Версия: 1.0\n"
        "Создан на aiogram 3."
    )


@dp.message(F.text == "📋 Все заявки")
async def applications(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not users:
        await message.answer("Заявок нет.")
        return

    text = "📄 Все заявки:\n\n"

    for uid, stat in users.items():
        text += f"ID: <code>{uid}</code>\nСтатус: {stat}\n\n"

    await message.answer(text)


@dp.message(F.text == "🐞 Все баги")
async def bugs(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not reports:
        await message.answer("Багов нет.")
        return

    text = "🐞 Баг-репорты:\n\n"

    for bug in reports:
        text += bug + "\n\n"

    await message.answer(text)


@dp.message()
async def all_messages(message: Message):
    if message.text.startswith("/"):
        return

    if message.text in [
        "📄 Подать заявку",
        "📊 Статус заявки",
        "🐞 Баг-репорт",
        "ℹ️ Информация",
        "📋 Все заявки",
        "🐞 Все баги"
    ]:
        return

    reports.append(
        f"👤 {message.from_user.id}\n"
        f"🐞 {message.text}"
    )

    await bot.send_message(
        ADMIN_ID,
        f"🐞 Новый баг\n\n"
        f"ID: <code>{message.from_user.id}</code>\n\n"
        f"{message.text}"
    )

    await message.answer("✅ Баг-репорт отправлен.")


async def main():
    print("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
