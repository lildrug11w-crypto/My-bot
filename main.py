from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import asyncio
import sqlite3
import random
import time

# =========================================
# CONFIG
# =========================================

TOKEN = "8988450533:AAGdrsdjyrieWF-pqnls_WFinbntgiuzYYQ"
ADMIN_ID = 7738822030
CHANNEL_USERNAME = "@casesvaultbot"

# =========================================
# BOT
# =========================================

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()

# =========================================
# DATABASE
# =========================================

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    balance INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_daily INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    item_name TEXT,
    rarity TEXT
)
""")

conn.commit()

# =========================================
# NFT ITEMS
# =========================================

CASES = {
    "Бомж": [
        "Berry Box",
        "Happy Brownie",
        "Homemade Cake",
        "Ice Cream"
    ],

    "Обычный": [
        "Candy Cane",
        "Desk Calendar",
        "Case",
        "1 May"
    ],

    "Особый": [
        "Artisan Brick",
        "Crystal Ball",
        "Input Key",
        "Big Year"
    ],

    "Миллионер": [
        "Astral Shard",
        "Chill Flame"
    ]
}

RARITY = {
    "Berry Box": "Common",
    "Happy Brownie": "Common",
    "Homemade Cake": "Common",
    "Ice Cream": "Common",

    "Candy Cane": "Rare",
    "Desk Calendar": "Rare",
    "Case": "Rare",
    "1 May": "Rare",

    "Artisan Brick": "Epic",
    "Crystal Ball": "Epic",
    "Input Key": "Epic",
    "Big Year": "Epic",

    "Astral Shard": "Legendary",
    "Chill Flame": "Legendary"
}

# =========================================
# CASE PRICES
# =========================================

CASE_PRICES = {
    "Бомж": 5,
    "Обычный": 25,
    "Особый": 75,
    "Миллионер": 150
}

# =========================================
# KS PACKS
# =========================================

KS_PACKS = {
    15: 10,
    20: 50,
    50: 100,
    75: 65,
    100: 200
}

# =========================================
# MAIN MENU
# =========================================

def main_menu(user_id):

    buttons = [

        [
            InlineKeyboardButton(
                text="🎰 ОТКРЫТЬ КЕЙСЫ",
                callback_data="cases"
            )
        ],

        [
            InlineKeyboardButton(
                text="🎁 DAILY",
                callback_data="daily"
            ),

            InlineKeyboardButton(
                text="🪙 ПОПОЛНИТЬ",
                callback_data="deposit"
            )
        ],

        [
            InlineKeyboardButton(
                text="🎒 ИНВЕНТАРЬ",
                callback_data="inventory"
            ),

            InlineKeyboardButton(
                text="💳 ВЫВОД",
                callback_data="withdraw"
            )
        ],

        [
            InlineKeyboardButton(
                text="👥 РЕФЕРАЛЫ",
                callback_data="refs"
            ),

            InlineKeyboardButton(
                text="👤 ПРОФИЛЬ",
                callback_data="profile"
            )
        ]
    ]

    if user_id == ADMIN_ID:
        buttons.append([
            InlineKeyboardButton(
                text="⚙ АДМИН ПАНЕЛЬ",
                callback_data="admin"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

# =========================================
# CASES MENU
# =========================================

cases_kb = InlineKeyboardMarkup(
    inline_keyboard=[

        [
            InlineKeyboardButton(
                text="🗑 Бомж • 5 KS",
                callback_data="open_Бомж"
            )
        ],

        [
            InlineKeyboardButton(
                text="📦 Обычный • 25 KS",
                callback_data="open_Обычный"
            )
        ],

        [
            InlineKeyboardButton(
                text="💎 Особый • 75 KS",
                callback_data="open_Особый"
            )
        ],

        [
            InlineKeyboardButton(
                text="👑 Миллионер • 150 KS",
                callback_data="open_Миллионер"
            )
        ],

        [
            InlineKeyboardButton(
                text="⬅ НАЗАД",
                callback_data="back"
            )
        ]
    ]
)

# =========================================
# DEPOSIT MENU
# =========================================

deposit_kb = InlineKeyboardMarkup(
    inline_keyboard=[

        [
            InlineKeyboardButton(
                text="15⭐ • 10 KS",
                callback_data="pay_15"
            ),

            InlineKeyboardButton(
                text="20⭐ • 50 KS",
                callback_data="pay_20"
            )
        ],

        [
            InlineKeyboardButton(
                text="50⭐ • 100 KS",
                callback_data="pay_50"
            ),

            InlineKeyboardButton(
                text="75⭐ • 65 KS",
                callback_data="pay_75"
            )
        ],

        [
            InlineKeyboardButton(
                text="100⭐ • 200 KS",
                callback_data="pay_100"
            )
        ],

        [
            InlineKeyboardButton(
                text="⬅ НАЗАД",
                callback_data="back"
            )
        ]
    ]
)

# =========================================
# ADMIN MENU
# =========================================

admin_kb = InlineKeyboardMarkup(
    inline_keyboard=[

        [
            InlineKeyboardButton(
                text="💸 ВЫДАТЬ KS",
                callback_data="admin_ks"
            )
        ],

        [
            InlineKeyboardButton(
                text="🎁 ВЫДАТЬ NFT",
                callback_data="admin_nft"
            )
        ],

        [
            InlineKeyboardButton(
                text="⬆ ПОВЫСИТЬ LVL",
                callback_data="admin_lvl"
            )
        ],

        [
            InlineKeyboardButton(
                text="⬅ НАЗАД",
                callback_data="back"
            )
        ]
    ]
)

# =========================================
# FUNCTIONS
# =========================================

def get_user(user_id):
    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()

def create_user(user_id, username):
    cursor.execute(
        "INSERT INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()

# =========================================
# CHECK SUB
# =========================================

async def check_sub(user_id):

    try:

        member = await bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}",
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except:
        return False

# =========================================
# START
# =========================================

@dp.message(CommandStart())
async def start(message: Message):

    user_id = message.from_user.id
    username = message.from_user.username

    sub = await check_sub(user_id)

    if not sub:

        kb = InlineKeyboardMarkup(
            inline_keyboard=[

                [
                    InlineKeyboardButton(
                        text="📢 ПОДПИСАТЬСЯ",
                        url=f"https://t.me/{CHANNEL_USERNAME}"
                    )
                ],

                [
                    InlineKeyboardButton(
                        text="✅ ПРОВЕРИТЬ",
                        callback_data="check_sub"
                    )
                ]
            ]
        )

        await message.answer(
            "<b>❌ Для использования бота подпишитесь на канал</b>",
            reply_markup=kb
        )

        return

    args = message.text.split()

    if not get_user(user_id):

        create_user(user_id, username)

        if len(args) > 1:

            ref_id = int(args[1])

            if ref_id != user_id:

                cursor.execute(
                    "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
                    (ref_id,)
                )

                conn.commit()

    await message.answer(
        """
<b>🎰 ДОБРО ПОЖАЛОВАТЬ В VAULT CASE BOT</b>

<b>📦 Открывай кейсы</b>
<b>💎 Получай NFT</b>
<b>👥 Приглашай друзей</b>
<b>🪙 Покупай KS валюту</b>
<b>🏆 Собирай редкие предметы</b>
""",
        reply_markup=main_menu(user_id)
    )

# =========================================
# CHECK SUB BUTTON
# =========================================

@dp.callback_query(F.data == "check_sub")
async def check_sub_btn(callback: CallbackQuery):

    sub = await check_sub(callback.from_user.id)

    if not sub:

        await callback.answer(
            "❌ ВЫ НЕ ПОДПИСАЛИСЬ",
            show_alert=True
        )

        return

    await callback.message.edit_text(
        "<b>✅ ПОДПИСКА ПОДТВЕРЖДЕНА</b>",
        reply_markup=main_menu(callback.from_user.id)
    )

# =========================================
# BACK
# =========================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    await callback.message.edit_text(
        "<b>🏠 ГЛАВНОЕ МЕНЮ</b>",
        reply_markup=main_menu(callback.from_user.id)
    )

# =========================================
# CASES
# =========================================

@dp.callback_query(F.data == "cases")
async def cases(callback: CallbackQuery):

    await callback.message.edit_text(
        "<b>🎰 ВЫБЕРИТЕ КЕЙС</b>",
        reply_markup=cases_kb
    )

# =========================================
# OPEN CASE
# =========================================

@dp.callback_query(F.data.startswith("open_"))
async def open_case(callback: CallbackQuery):

    case_name = callback.data.split("_")[1]

    price = CASE_PRICES[case_name]

    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (callback.from_user.id,)
    )

    balance = cursor.fetchone()[0]

    if balance < price:

        await callback.answer(
            "❌ НЕДОСТАТОЧНО KS",
            show_alert=True
        )

        return

    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (price, callback.from_user.id)
    )

    conn.commit()

    chance = random.randint(1, 100)

    if chance <= 50:

        await callback.message.answer(
            "<b>❌ ВАМ НИЧЕГО НЕ ВЫПАЛО</b>"
        )

        return

    reward = random.choice(CASES[case_name])

    rarity = RARITY[reward]

    cursor.execute(
        "INSERT INTO inventory (user_id, item_name, rarity) VALUES (?, ?, ?)",
        (
            callback.from_user.id,
            reward,
            rarity
        )
    )

    conn.commit()

    await callback.message.answer(
        f"""
<b>🎉 ВАМ ВЫПАЛ NFT</b>

<b>🎁 {reward}</b>
<b>💎 {rarity}</b>
"""
    )

# =========================================
# PROFILE
# =========================================

@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):

    cursor.execute(
        "SELECT balance, referrals, level FROM users WHERE user_id = ?",
        (callback.from_user.id,)
    )

    data = cursor.fetchone()

    text = f"""
<b>👤 ПРОФИЛЬ</b>

<b>⭐ KS:</b> {data[0]}
<b>👥 РЕФЕРАЛЫ:</b> {data[1]}
<b>⬆ УРОВЕНЬ:</b> {data[2]}
"""

    await callback.message.edit_text(
        text,
        reply_markup=main_menu(callback.from_user.id)
    )

# =========================================
# INVENTORY
# =========================================

@dp.callback_query(F.data == "inventory")
async def inventory(callback: CallbackQuery):

    cursor.execute(
        "SELECT item_name, rarity FROM inventory WHERE user_id = ?",
        (callback.from_user.id,)
    )

    items = cursor.fetchall()

    if not items:

        await callback.answer(
            "❌ ИНВЕНТАРЬ ПУСТ",
            show_alert=True
        )

        return

    text = "<b>🎒 ИНВЕНТАРЬ</b>\n\n"

    for item in items:

        text += f"""
<b>🎁 {item[0]}</b>
<b>💎 {item[1]}</b>

"""

    await callback.message.edit_text(
        text,
        reply_markup=main_menu(callback.from_user.id)
    )

# =========================================
# DAILY
# =========================================

@dp.callback_query(F.data == "daily")
async def daily(callback: CallbackQuery):

    cursor.execute(
        "SELECT last_daily FROM users WHERE user_id = ?",
        (callback.from_user.id,)
    )

    last = cursor.fetchone()[0]

    now = int(time.time())

    if now - last < 86400:

        await callback.answer(
            "❌ DAILY УЖЕ ПОЛУЧЕН",
            show_alert=True
        )

        return

    cursor.execute(
        "UPDATE users SET balance = balance + 10, last_daily = ? WHERE user_id = ?",
        (
            now,
            callback.from_user.id
        )
    )

    conn.commit()

    await callback.answer(
        "🎁 ВЫ ПОЛУЧИЛИ 10 KS",
        show_alert=True
    )

# =========================================
# REFS
# =========================================

@dp.callback_query(F.data == "refs")
async def refs(callback: CallbackQuery):

    user_id = callback.from_user.id

    cursor.execute(
        "SELECT referrals FROM users WHERE user_id = ?",
        (user_id,)
    )

    refs = cursor.fetchone()[0]

    ref_link = f"https://t.me/YOUR_BOT?start={user_id}"

    text = f"""
<b>👥 РЕФЕРАЛЫ</b>

<b>👤 ВАШИ РЕФЕРАЛЫ:</b> {refs}/15

<b>🔗 ССЫЛКА:</b>
{ref_link}

<b>❗ ДЛЯ ВЫВОДА НУЖНО 15 РЕФЕРАЛОВ</b>
"""

    await callback.message.edit_text(
        text,
        reply_markup=main_menu(user_id)
    )

# =========================================
# WITHDRAW
# =========================================

@dp.callback_query(F.data == "withdraw")
async def withdraw(callback: CallbackQuery):

    cursor.execute(
        "SELECT referrals FROM users WHERE user_id = ?",
        (callback.from_user.id,)
    )

    refs = cursor.fetchone()[0]

    if refs < 15:

        await callback.answer(
            "❌ НУЖНО 15 РЕФЕРАЛОВ",
            show_alert=True
        )

        return

    await callback.message.answer(
        "<b>✅ ВЫ МОЖЕТЕ ВЫВОДИТЬ NFT</b>"
    )

# =========================================
# DEPOSIT
# =========================================

@dp.callback_query(F.data == "deposit")
async def deposit(callback: CallbackQuery):

    await callback.message.edit_text(
        "<b>🪙 ВЫБЕРИТЕ ПАКЕТ KS</b>",
        reply_markup=deposit_kb
    )

# =========================================
# BUY KS
# =========================================

@dp.callback_query(F.data.startswith("pay_"))
async def pay(callback: CallbackQuery):

    stars = int(callback.data.split("_")[1])

    ks = KS_PACKS[stars]

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (
            ks,
            callback.from_user.id
        )
    )

    conn.commit()

    await callback.message.answer(
        f"<b>✅ ВЫ КУПИЛИ {ks} KS ЗА {stars}⭐</b>"
    )

# =========================================
# ADMIN PANEL
# =========================================

@dp.callback_query(F.data == "admin")
async def admin(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.edit_text(
        "<b>⚙ АДМИН ПАНЕЛЬ</b>",
        reply_markup=admin_kb
    )

# =========================================
# ADMIN GIVE KS
# =========================================

@dp.callback_query(F.data == "admin_ks")
async def admin_ks(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    cursor.execute(
        "UPDATE users SET balance = balance + 1000 WHERE user_id = ?",
        (ADMIN_ID,)
    )

    conn.commit()

    await callback.answer(
        "✅ ВЫДАНО 1000 KS",
        show_alert=True
    )

# =========================================
# ADMIN GIVE NFT
# =========================================

@dp.callback_query(F.data == "admin_nft")
async def admin_nft(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    cursor.execute(
        "INSERT INTO inventory (user_id, item_name, rarity) VALUES (?, ?, ?)",
        (
            ADMIN_ID,
            "Astral Shard",
            "Legendary"
        )
    )

    conn.commit()

    await callback.answer(
        "✅ NFT ВЫДАН",
        show_alert=True
    )

# =========================================
# ADMIN LVL
# =========================================

@dp.callback_query(F.data == "admin_lvl")
async def admin_lvl(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    cursor.execute(
        "UPDATE users SET level = level + 1 WHERE user_id = ?",
        (ADMIN_ID,)
    )

    conn.commit()

    await callback.answer(
        "✅ УРОВЕНЬ ПОВЫШЕН",
        show_alert=True
    )

# =========================================
# START BOT
# =========================================

async def main():

    print("BOT STARTED")

    await dp.start_polling(bot)

asyncio.run(main())
