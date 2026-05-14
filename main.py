import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8822832599:AAFtCOS32CnhS9n0EweeVzvFdyHzIV9ICbU"
ADMIN_USERNAME = "@tipo_lilhead"

# Сюда вставь ID премиум-эмодзи, которые ты получил по ссылкам
E_MAIN = "5314541620311030339"  # Пример ID (звезда/корона)
E_CASH = "5314541620311030338"  # Пример ID (деньги)
E_CART = "5314541620311030337"  # Пример ID (корзина)
E_USER = "5314541620311030336"  # Пример ID (профиль)

bot = Bot(token=TOKEN)
dp = Dispatcher()

def main_menu():
    builder = InlineKeyboardBuilder()
    # Используем <tg-emoji> для вставки премиум-иконок
    builder.row(InlineKeyboardButton(
        text=f"🛒 КАТАЛОГ", callback_data="catalog"))
    builder.row(
        InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="profile"),
        InlineKeyboardButton(text="💎 ПАРТНЕРКА", callback_data="refs")
    )
    builder.row(InlineKeyboardButton(text="🆘 ПОДДЕРЖКА", url=f"https://t.me/{ADMIN_USERNAME[1:]}"))
    return builder.as_markup()

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    # В тексте сообщения премиум-эмодзи вставляются так:
    await message.answer(
        f"<tg-emoji id='{E_MAIN}'>👑</tg-emoji> <b>PREMIUM STORE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji id='{E_CASH}'>💰</tg-emoji> <b>Лучшие лимиты на рынке</b>\n"
        f"<tg-emoji id='{E_CART}'>🛒</tg-emoji> <i>Аккаунты WB и Яндекс</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Выбирай нужный раздел:",
        reply_markup=main_menu(),
        parse_mode="HTML" # ОБЯЗАТЕЛЬНО HTML
    )

@dp.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟣 WB ЧАСТЯМИ", callback_data="list_wb"))
    builder.row(InlineKeyboardButton(text="🟡 ЯНДЕКС СПЛИТ", callback_data="list_ya"))
    builder.row(InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="start"))
    
    await call.message.edit_text(
        f"<tg-emoji id='{E_CART}'>🛍</tg-emoji> <b>ВЫБЕРИТЕ КАТЕГОРИЮ:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "list_wb")
async def show_wb(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    # Генерация кнопок лимитов
    for amount in [25000, 50000, 75000, 100000]:
        builder.row(InlineKeyboardButton(text=f"💳 {amount} ₽", callback_data=f"buy_wb_{amount}"))
    builder.row(InlineKeyboardButton(text="⬅️ НАЗАД", callback_data="catalog"))
    
    await call.message.edit_text("<b>🟣 ЛИМИТЫ WB ЧАСТЯМИ</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def confirm(call: CallbackQuery):
    data = call.data.split("_")
    limit_val = data[2]
    
    await call.message.edit_text(
        f"<b>🛒 ПОДТВЕРЖДЕНИЕ</b>\n"
        f"━━━━━━━━━━━━\n"
        f"📦 Товар: <code>{data[1].upper()}</code>\n"
        f"💰 Лимит: <code>{limit_val} ₽</code>\n"
        f"💵 Цена: <code>1 200 ₽</code>\n"
        f"━━━━━━━━━━━━\n"
        f"Для покупки нажми кнопку ниже:",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="✅ ОПЛАТИТЬ", callback_data="pay_final")
        ).row(InlineKeyboardButton(text="⬅️ ОТМЕНА", callback_data="catalog")).as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "pay_final")
async def pay_final(call: CallbackQuery):
    await call.message.answer(
        f"<b>🚀 ЗАЯВКА СОЗДАНА!</b>\n\n"
        f"Напиши админу для оплаты и получения SMS:\n"
        f"👉 <b>{ADMIN_USERNAME}</b>",
        parse_mode="HTML"
    )
    await call.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
