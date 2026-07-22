import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ChatAction

import google.generativeai as genai

# ==================== НАСТРОЙКИ ====================
# Вставь свои ключи сюда или задай через переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8955044700:AAF1Qp8FiUyX7gDsZepd_lI3Uh7zNGrTxXo")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6KWL48SRL4TXB65HCFaFxwCIHZIJhQ7qQwBsQskfeQmEw")

# Системный промпт — характер бота можно менять здесь
SYSTEM_PROMPT = (
    "Ты — дружелюбный и полезный ассистент в Telegram. "
    "Отвечай кратко, понятно и по делу."
)

# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Храним историю диалога для каждого пользователя (в памяти)
user_chats: dict[int, list] = {}


def get_chat_session(user_id: int):
    """Возвращает (или создаёт) сессию чата Gemini для пользователя."""
    if user_id not in user_chats:
        user_chats[user_id] = model.start_chat(history=[])
    return user_chats[user_id]


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_chats.pop(message.from_user.id, None)  # сброс истории при старте
    await message.answer(
        "Привет! 👋 Я бот с ИИ на базе Gemini.\n"
        "Просто напиши мне что-нибудь, и я отвечу.\n\n"
        "Команды:\n"
        "/start — начать заново\n"
        "/reset — очистить историю диалога"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    user_chats.pop(message.from_user.id, None)
    await message.answer("История диалога очищена ✅")


@dp.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    user_text = message.text

    # Показываем "печатает..."
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        chat = get_chat_session(user_id)
        response = await asyncio.to_thread(chat.send_message, user_text)
        answer = response.text
    except Exception as e:
        logger.exception("Ошибка при обращении к Gemini")
        answer = f"Произошла ошибка при обращении к ИИ: {e}"

    await message.answer(answer)


async def main():
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
  
