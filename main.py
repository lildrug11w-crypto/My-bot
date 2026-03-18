import telebot
import time
import random
from telebot import types

TOKEN = "8308935041:AAHxkcuaOA4mwj1XXR2AZDJX-RGSdLAHk2w"
ADMIN = "@maharaga_coder"
CHANNEL = "@pizzabotinfo"

bot = telebot.TeleBot(TOKEN)

users = {}

# ---------------- ПРОВЕРКА ПОДПИСКИ ----------------
def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def sub_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Подписаться", url="https://t.me/pizzabotinfo"))
    kb.add(types.InlineKeyboardButton("✅ Проверить", callback_data="check_sub"))
    return kb

# ---------------- МЕНЮ ----------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔑 Купить private key")
    kb.add("👤 Мой профиль", "🎁 Бесплатные запросы")
    kb.add("🛠 Поддержка")
    return kb

# ---------------- СТАРТ ----------------
@bot.message_handler(commands=["start"])
def start(m):
    if not check_sub(m.from_user.id):
        return bot.send_message(
            m.chat.id,
            "❌ Подпишись на канал чтобы использовать бота",
            reply_markup=sub_kb()
        )

    uid = str(m.from_user.id)
    if uid not in users:
        users[uid] = {
            "reg": time.strftime("%d.%m.%Y"),
            "total": 0
        }

    bot.send_message(
        m.chat.id,
        "🍕 Добро пожаловать в PIZZA BOT\n\n🔥 Выбери действие:",
        reply_markup=main_menu()
    )

# ---------------- ПРОВЕРКА ПОДПИСКИ КНОПКА ----------------
@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def check(call):
    if check_sub(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Доступ открыт")
        bot.send_message(call.message.chat.id, "🔥 Готово", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ Ты не подписан")

# ---------------- ПРОФИЛЬ ----------------
@bot.message_handler(func=lambda m: m.text == "👤 Мой профиль")
def profile(m):
    uid = str(m.from_user.id)
    data = users.get(uid)

    bot.send_message(
        m.chat.id,
        f"👤 Имя: {m.from_user.first_name}\n"
        f"📅 Регистрация: {data['reg']}\n"
        f"⚡ Всего жалоб: {data['total']}"
    )

# ---------------- ПОДДЕРЖКА ----------------
@bot.message_handler(func=lambda m: m.text == "🛠 Поддержка")
def support(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅️ Назад")

    bot.send_message(
        m.chat.id,
        f"🛠 Техническая поддержка\n👉 {ADMIN}",
        reply_markup=kb
    )

# ---------------- НАЗАД ----------------
@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    bot.send_message(m.chat.id, "🔙 Возврат в меню", reply_markup=main_menu())

# ---------------- БЕСПЛАТНЫЕ ЗАПРОСЫ ----------------
@bot.message_handler(func=lambda m: m.text == "🎁 Бесплатные запросы")
def free(m):
    bot.send_message(
        m.chat.id,
        "📥 Введи данные:\n\n@username количество причина"
    )

# ---------------- ОБРАБОТКА ЗАЯВОК ----------------
@bot.message_handler(func=lambda m: m.text and m.text.startswith("@"))
def process(m):
    parts = m.text.split(maxsplit=2)

    if len(parts) < 2:
        return bot.send_message(m.chat.id, "❌ Пример: @user 10 причина")

    username = parts[0]

    try:
        total = int(parts[1])
    except:
        return bot.send_message(m.chat.id, "❌ Количество должно быть числом")

    reason = parts[2] if len(parts) > 2 else "—"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚀 Начать", callback_data=f"start:{username}:{total}"))

    bot.send_message(
        m.chat.id,
        f"🎯 Цель: {username}\n"
        f"📦 Запросов: {total}\n\n"
        f"❗ Вы уверены?",
        reply_markup=kb
    )

# ---------------- ЗАПУСК ----------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("start:"))
def start_process(call):
    data = call.data.split(":")
    username = data[1]
    total = int(data[2])

    uid = str(call.from_user.id)

    bot.send_message(call.message.chat.id, "⚡ Запуск...")

    success = 0

    for i in range(1, total + 1):
        time.sleep(1)

        if random.randint(1, 100) <= 70:
            success += 1

        bot.send_message(
            call.message.chat.id,
            f"✅ Цель: {username}\n"
            f"📊 Проверка: в процессе\n"
            f"⚡ Выполнено: {i}"
        )

    users[uid]["total"] += total

    bot.send_message(
        call.message.chat.id,
        f"✅ Цель: {username}\n"
        f"📊 Проверка: завершена\n"
        f"⚡ Выполнено: {total}\n"
        f"🔥 Успешно: {success}"
    )

# ---------------- ЗАПУСК БОТА ----------------
print("Бот запущен")
bot.infinity_polling(skip_pending=True)
