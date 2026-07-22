import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ChatAction

from openai import OpenAI

# ==================== НАСТРОЙКИ ====================
# Вставь свои ключи сюда или задай через переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8955044700:AAF1Qp8FiUyX7gDsZepd_lI3Uh7zNGrTxXo")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

# Модель OpenRouter. "openrouter/free" — автороутер, сам подбирает
# доступную бесплатную модель (список бесплатных моделей у них меняется).
# Можно указать и конкретную, например "meta-llama/llama-3.3-70b-instruct:free"
AI_MODEL = "openrouter/free"

# Системный промпт — характер бота можно менять здесь
SYSTEM_PROMPT = (
    "Ты — дружелюбный и полезный ассистент в Telegram. "
    "Отвечай кратко, понятно и по делу."
)

# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "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":
    raise RuntimeError(
        "OPENROUTER_API_KEY не задан! Укажи переменную окружения OPENROUTER_API_KEY на хостинге."
    )
logger.info(f"OpenRouter API key загружен, длина: {len(OPENROUTER_API_KEY)} символов")

client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Храним историю диалога для каждого пользователя (в памяти)
# Формат: {user_id: [{"role": "user"/"assistant", "content": "..."}]}
user_chats: dict[int, list] = {}
MAX_HISTORY_MESSAGES = 20  # ограничение, чтобы не раздувать контекст


def get_history(user_id: int) -> list:
    """Возвращает (или создаёт) историю диалога пользователя."""
    if user_id not in user_chats:
        user_chats[user_id] = []
    return user_chats[user_id]


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_chats.pop(message.from_user.id, None)  # сброс истории при старте
    await message.answer(
        "Привет! 👋 Я бот с ИИ на базе grok.\n"
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
        history = get_history(user_id)
        history.append({"role": "user", "content": user_text})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=AI_MODEL,
            messages=messages,
        )
        answer = response.choices[0].message.content
        history.append({"role": "assistant", "content": answer})

        # обрезаем историю, чтобы не росла бесконечно
        if len(history) > MAX_HISTORY_MESSAGES:
            del history[:-MAX_HISTORY_MESSAGES]
    except Exception as e:
        logger.exception("Ошибка при обращении к OpenRouter")
        answer = f"Произошла ошибка при обращении к ИИ: {e}"

    await message.answer(answer)


async def main():
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
      
