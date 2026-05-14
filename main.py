import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8822832599:AAFtCOS32CnhS9n0EweeVzvFdyHzIV9ICbU" # Или используй os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "@tipo_lilhead"

# Твои Premium ID
E_STAR = "5197476530619455017"
E_MONEY = "5197244864378478397"
E_CART = "5197709777408400398"
E_USER = "5197440173721299530"
E_LOCK = "5197226941479953900"
E_GEAR = "5197424273752367882"

bot = Bot(token=TOKEN)
dp = Dispatcher()

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎁 КАТАЛОГ ТОВАРОВ", callback_data="catalog"))
    builder.row(
        InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="profile"),
        InlineKeyboardButton(text="👥 РЕФЕРАЛЫ", callback_data="refs")
    )
    builder.row(InlineKeyboardButton(text="👨‍💻 ТЕХ.ПОДДЕРЖКА", url=f"https://t.me/{ADMIN_USERNAME[1:]}"))
    return builder.as_markup()

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(
        f"<tg-emoji id='{E_STAR}'>⭐️</tg-emoji> <b>OFFICIAL PREMIUM STORE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji id='{E_MONEY}'>💰</tg-emoji> <b>Лучшие аккаунты с лимитами</b>\n"
        f"<tg-emoji id='{E_LOCK}'>🔒</tg-emoji> <b>Гарантия безопасного входа</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Добро пожаловать! Выберите раздел:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "start")
async def back_to_start(call: CallbackQuery):
    await call.message.edit_text(
        f"<tg-emoji id='{E_STAR}'>⭐️</tg-emoji> <b>ГЛАВНОЕ МЕНЮ</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟣 WB ЧАСТЯМИ", callback_data="list_wb"))
    builder.row(InlineKeyboardButton(text="🟡 ЯНДЕКС СПЛИТ", callback_data="list_ya"))
    builder.row(InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="start"))
    
    await call.message.edit_text(
        f"<tg-emoji id='{E_CART}'>🛒</tg-emoji> <b>ВЫБЕРИТЕ СЕРВИС:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "list_wb")
async def show_wb(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for amount in [25000, 50000, 75000, 100000]:
        builder.row(InlineKeyboardButton(text=f"💳 {amount} ₽", callback_data=f"buy_wb_{amount}"))
    builder.row(InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="catalog"))
    
    await call.message.edit_text("<b>🟣 ЛИМИТЫ WB ЧАСТЯМИ</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "list_ya")
async def show_ya(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for amount in range(10000, 110000, 10000):
        builder.row(InlineKeyboardButton(text=f"💳 {amount} ₽", callback_data=f"buy_ya_{amount}"))
    builder.row(InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="catalog"))
    
    await call.message.edit_text("<b>🟡 ЛИМИТЫ ЯНДЕКС СПЛИТ</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def confirm(call: CallbackQuery):
    data = call.data.split("_")
    service = "WB" if data[1] == "wb" else "Яндекс"
    
    await call.message.edit_text(
        f"<tg-emoji id='{E_GEAR}'>⚙️</tg-emoji> <b>ПОДТВЕРЖДЕНИЕ</b>\n"
        f"━━━━━━━━━━━━\n"
        f"📦 Товар: <b>{service}</b>\n"
        f"💰 Лимит: <b>{data[2]} ₽</b>\n"
        f"💵 Цена: <b>1 200 ₽</b>\n"
        f"━━━━━━━━━━━━\n",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="💳 ОПЛАТИТЬ", callback_data="pay_final")
        ).row(InlineKeyboardButton(text="⬅️ НАЗАД", callback_data=f"list_{data[1]}")).as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "pay_final")
async def pay_final(call: CallbackQuery):
    await call.message.answer(
        f"<b>🚀 ЗАЯВКА ПРИНЯТА!</b>\n\n"
        f"Для оплаты и получения SMS напишите админу:\n"
        f"👉 <b>{ADMIN_USERNAME}</b>",
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    await call.message.edit_text(
        f"<tg-emoji id='{E_USER}'>👤</tg-emoji> <b>ВАШ ПРОФИЛЬ</b>\n"
        f"──────────────────\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"💰 Баланс: 0.00 ₽\n"
        f"🛒 Покупок: 0\n"
        f"──────────────────",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
