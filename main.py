import os
import html
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# НАСТРОЙКИ
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Создай НОВЫЕ ключи OpenRouter
ROBLOX_API_KEY = os.getenv("OPENROUTER_KEY_ROBLOX")
SAMP_API_KEY = os.getenv("OPENROUTER_KEY_SAMP")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ROBLOX_MODEL = "poolside/laguna-xs-2.1:free"

# Укажи здесь актуальный ID модели Nemotron,
# если в OpenRouter он отличается от выбранного тобой.
SAMP_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

# Выбранный пользователем режим
user_modes = {}


# =========================
# КЛАВИАТУРЫ
# =========================

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎮 Roblox Studio",
                callback_data="mode_roblox"
            )
        ],
        [
            InlineKeyboardButton(
                "🛠 SA-MP / CRMP",
                callback_data="mode_samp"
            )
        ]
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔄 Сменить режим",
                callback_data="change_mode"
            )
        ]
    ])


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    text = (
        "👋 <b>Привет!</b>\n\n"
        "Я — AI-помощник для разработчиков.\n\n"

        "🎮 <b>Roblox Studio</b>\n"
        "Помогу с Luau, скриптами, GUI, "
        "RemoteEvent, механиками и ошибками Output.\n\n"

        "🛠 <b>SA-MP / CRMP</b>\n"
        "Помогу с Pawn, серверными ошибками, "
        "логами и исправлением кода.\n\n"

        "👇 <b>Выбери, с чем тебе нужна помощь:</b>\n\n"

        "👨‍💻 Разработчик: <b>@BiteByDay</b>"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )


# =========================
# ВЫБОР РЕЖИМА
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "mode_roblox":
        user_modes[user_id] = "roblox"

        await query.edit_message_text(
            "🎮 <b>Режим Roblox Studio включён!</b>\n\n"
            "Отправь мне:\n"
            "• ошибку из Output;\n"
            "• свой скрипт;\n"
            "• описание проблемы;\n"
            "• или спроси, как сделать определённую механику.\n\n"
            "Я постараюсь найти причину и предложить решение.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )

    elif query.data == "mode_samp":
        user_modes[user_id] = "samp"

        await query.edit_message_text(
            "🛠 <b>Режим SA-MP / CRMP включён!</b>\n\n"
            "Отправь мне:\n"
            "• ошибку компиляции;\n"
            "• серверный лог;\n"
            "• Pawn-код;\n"
            "• описание проблемы.\n\n"
            "Я помогу разобраться и предложу исправление.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )

    elif query.data == "change_mode":
        user_modes.pop(user_id, None)

        await query.edit_message_text(
            "🔄 <b>Выбери новый режим помощи:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )


# =========================
# ЗАПРОС К OPENROUTER
# =========================

def ask_ai(api_key, model, user_text, system_prompt):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_text
            }
        ],
        "temperature": 0.2,
    }

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=data,
        timeout=120
    )

    if response.status_code != 200:
        try:
            error = response.json()
        except Exception:
            error = response.text

        raise Exception(
            f"OpenRouter error {response.status_code}: {error}"
        )

    result = response.json()

    return result["choices"][0]["message"]["content"]


# =========================
# СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ
# =========================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    mode = user_modes.get(user_id)

    if not mode:
        await update.message.reply_text(
            "👋 Сначала выбери тип помощи:",
            reply_markup=main_keyboard()
        )
        return

    await update.message.chat.send_action("typing")

    try:

        if mode == "roblox":

            if not ROBLOX_API_KEY:
                await update.message.reply_text(
                    "❌ API-ключ Roblox не настроен."
                )
                return

            system_prompt = """
Ты профессиональный помощник по Roblox Studio.

Основная специализация:
- Luau / Lua
- Roblox Studio
- ServerScriptService
- StarterPlayer
- StarterGui
- ReplicatedStorage
- RemoteEvent / RemoteFunction
- GUI
- игровые механики
- ошибки Output
- оптимизация скриптов

Отвечай на русском языке.

Если пользователь прислал ошибку:
1. Определи причину.
2. Объясни её простыми словами.
3. Покажи исправленный код.
4. Объясни, куда его поместить.

Если пользователь просит создать систему,
дай готовый рабочий пример и объясни установку.

Не выдумывай API Roblox.
"""

            answer = ask_ai(
                ROBLOX_API_KEY,
                ROBLOX_MODEL,
                text,
                system_prompt
            )

        else:

            if not SAMP_API_KEY:
                await update.message.reply_text(
                    "❌ API-ключ SA-MP/CRMP не настроен."
                )
                return

            system_prompt = """
Ты профессиональный помощник по разработке SA-MP и CRMP.

Основная специализация:
- Pawn
- SA-MP
- CRMP
- серверные скрипты
- компиляция
- ошибки Pawn
- server_log
- плагины и include
- игровые системы

Отвечай на русском языке.

Если пользователь прислал ошибку:
1. Определи возможную причину.
2. Объясни ошибку.
3. Покажи исправленный вариант.
4. Объясни, куда вставить код.

Если информации недостаточно,
скажи, какой файл или фрагмент кода нужен.
"""

            answer = ask_ai(
                SAMP_API_KEY,
                SAMP_MODEL,
                text,
                system_prompt
            )

        # Ограничение Telegram
        if len(answer) > 4000:
            answer = answer[:3950] + "\n\n…"

        await update.message.reply_text(
            answer,
            reply_markup=back_keyboard()
        )

    except requests.exceptions.Timeout:
        await update.message.reply_text(
            "⏳ Нейросеть слишком долго отвечает. "
            "Попробуй отправить запрос ещё раз."
        )

    except Exception as e:
        print("ERROR:", e)

        await update.message.reply_text(
            "❌ Произошла ошибка при обращении к нейросети.\n\n"
            "Попробуй повторить запрос позже."
        )


# =========================
# ЗАПУСК
# =========================

def main():

    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "Не найден TELEGRAM_TOKEN"
        )

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )

    print("Bot started!")

    app.run_polling()


if __name__ == "__main__":
    main()
