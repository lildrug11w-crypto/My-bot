import telebot
import time
from telebot import types

TOKEN = "8308935041:AAHxkcuaOA4mwj1XXR2AZDJX-RGSdLAHk2w"
ADMIN = 7738822030  # сюда свой ID
CHANNEL = "@pizzabotinfo"

bot = telebot.TeleBot(TOKEN)

users = {}
keys = {}

# ===== ПРОВЕРКА ПОДПИСКИ =====
def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===== КНОПКИ =====
def sub_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Подписаться", url="https://t.me/pizzabotinfo"))
    kb.add(types.InlineKeyboardButton("✅ Проверить", callback_data="check_sub"))
    return kb

def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔑 Купить private key", callback_data="buy"),
        types.InlineKeyboardButton("👤 Мой профиль", callback_data="profile"),
        types.InlineKeyboardButton("🎁 Бесплатные запросы", callback_data="free"),
        types.InlineKeyboardButton("💰 Платные запросы", callback_data="paid"),
        types.InlineKeyboardButton("🛠 Поддержка", callback_data="support")
    )
    return kb

# ===== СТАРТ =====
@bot.message_handler(commands=['start'])
def start(m):
    if not check_sub(m.from_user.id):
        return bot.send_message(m.chat.id, "❌ Подпишись на канал", reply_markup=sub_kb())

    uid = str(m.from_user.id)

    if uid not in users:
        users[uid] = {
            "reg": time.strftime("%d.%m.%Y"),
            "free": 3,
            "paid": 0
        }

    bot.send_message(m.chat.id, "🍕 Добро пожаловать!", reply_markup=main_menu())

# ===== ВЫДАЧА КЛЮЧА =====
@bot.message_handler(commands=['givebuykey'])
def give_key(m):
    if m.from_user.id != ADMIN:
        return bot.send_message(m.chat.id, "❌ Нет доступа")

    args = m.text.split()

    if len(args) < 3:
        return bot.send_message(m.chat.id, "Использование: /givebuykey id количество")

    uid = args[1]
    amount = int(args[2])

    if uid not in users:
        users[uid] = {"reg": time.strftime("%d.%m.%Y"), "free": 0, "paid": 0}

    users[uid]["paid"] += amount

    bot.send_message(m.chat.id, f"✅ Выдано {amount} платных запросов")

# ===== CALLBACK =====
@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    uid = str(call.from_user.id)

    if uid not in users:
        users[uid] = {"reg": time.strftime("%d.%m.%Y"), "free": 3, "paid": 0}

    # подписка
    if call.data == "check_sub":
        if check_sub(call.from_user.id):
            bot.edit_message_text("✅ Доступ открыт", call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Подпишись")

    # профиль
    elif call.data == "profile":
        u = users[uid]
        bot.edit_message_text(
            f"👤 Имя: {call.from_user.first_name}\n"
            f"📅 Регистрация: {u['reg']}\n"
            f"🎁 Бесплатных: {u['free']}\n"
            f"💰 Платных: {u['paid']}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Назад", callback_data="menu")
            )
        )

    # бесплатные
    elif call.data == "free":
        if users[uid]["free"] <= 0:
            bot.answer_callback_query(call.id, "❌ Нет бесплатных запросов")
        else:
            users[uid]["free"] -= 1
            bot.edit_message_text(
                "📩 Введи данные:\n\n@username количество причина",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("⬅️ Назад", callback_data="menu")
                )
            )

    # платные
    elif call.data == "paid":
        if users[uid]["paid"] <= 0:
            bot.answer_callback_query(call.id, "❌ Нет платных запросов")
        else:
            users[uid]["paid"] -= 1
            bot.edit_message_text(
                "💰 Платный запрос активирован\n\nВведи:\n@username количество причина",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("⬅️ Назад", callback_data="menu")
                )
            )

    # купить
    elif call.data == "buy":
        bot.answer_callback_query(call.id, "Напиши администратору")

    # поддержка
    elif call.data == "support":
        bot.answer_callback_query(call.id, f"Связь: @{ADMIN}")

    # назад
    elif call.data == "menu":
        bot.edit_message_text("🍕 Главное меню", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

# ===== ЗАПУСК =====
bot.infinity_polling()        m.chat.id,
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
