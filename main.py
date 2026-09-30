import asyncio
import os
import random
 
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
 
TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")
 
IOS_VERSIONS = ["15.8.3", "16.7.10", "17.6.1", "18.0", "18.3", "26.0"]
 
dp = Dispatcher()
 
 
# ---------- клавиатуры ----------
 
def kb_start() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔌 Начать прошивку", callback_data="connect")
    return b.as_markup()
 
 
def kb_connected() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подключил", callback_data="detect")
    return b.as_markup()
 
 
def kb_versions() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for v in IOS_VERSIONS:
        b.button(text=f"iOS {v}", callback_data=f"ver:{v}")
    b.adjust(2)
    return b.as_markup()
 
 
def kb_jailbreak(version: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔓 С джейлбрейком", callback_data=f"jb:1:{version}")
    b.button(text="🔒 Без джейлбрейка", callback_data=f"jb:0:{version}")
    b.adjust(1)
    return b.as_markup()
 
 
def kb_confirm(version: str, jb: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚀 Прошить!", callback_data=f"flash:{jb}:{version}")
    b.button(text="⬅️ Назад", callback_data="detect")
    b.adjust(1)
    return b.as_markup()
 
 
# ---------- хендлеры ----------
 
@dp.message(CommandStart())
async def start(message: Message):
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "Я <b>iFlash Pro</b> — профессиональный инструмент для прошивки iPhone.\n"
        "Поддерживаю все модели, любые версии iOS и джейлбрейк.\n\n"
        "Нажми кнопку ниже, чтобы начать 👇",
        reply_markup=kb_start(),
        parse_mode="HTML",
    )
 
 
@dp.callback_query(F.data == "connect")
async def connect(cb: CallbackQuery):
    await cb.message.edit_text(
        "📱 <b>Шаг 1. Подключение</b>\n\n"
        "Подключи iPhone к устройству через <b>USB-переходник</b> "
        "(Lightning / USB-C → OTG).\n\n"
        "Когда подключишь — нажми кнопку.",
        reply_markup=kb_connected(),
        parse_mode="HTML",
    )
    await cb.answer()
 
 
@dp.callback_query(F.data == "detect")
async def detect(cb: CallbackQuery):
    await cb.message.edit_text("🔍 Ищу устройство...")
    await asyncio.sleep(2)
    await cb.message.edit_text(
        "✅ <b>Устройство обнаружено!</b>\n"
        "Модель: iPhone\n"
        "Режим: DFU\n\n"
        "<b>Шаг 2.</b> Выбери версию iOS для прошивки:",
        reply_markup=kb_versions(),
        parse_mode="HTML",
    )
    await cb.answer()
 
 
@dp.callback_query(F.data.startswith("ver:"))
async def choose_version(cb: CallbackQuery):
    version = cb.data.split(":", 1)[1]
    await cb.message.edit_text(
        f"📦 Выбрана: <b>iOS {version}</b>\n\n"
        "<b>Шаг 3.</b> Нужен ли джейлбрейк?",
        reply_markup=kb_jailbreak(version),
        parse_mode="HTML",
    )
    await cb.answer()
 
 
@dp.callback_query(F.data.startswith("jb:"))
async def choose_jb(cb: CallbackQuery):
    _, jb, version = cb.data.split(":", 2)
    jb_text = "с джейлбрейком 🔓" if jb == "1" else "без джейлбрейка 🔒"
    await cb.message.edit_text(
        "⚠️ <b>Подтверждение</b>\n\n"
        f"Версия: <b>iOS {version}</b>\n"
        f"Режим: <b>{jb_text}</b>\n\n"
        "Не отключай устройство во время прошивки!",
        reply_markup=kb_confirm(version, jb),
        parse_mode="HTML",
    )
    await cb.answer()
 
 
def progress_bar(percent: int, width: int = 12) -> str:
    filled = int(width * percent / 100)
    return "█" * filled + "░" * (width - filled) + f" {percent}%"
 
 
@dp.callback_query(F.data.startswith("flash:"))
async def flash(cb: CallbackQuery):
    _, jb, version = cb.data.split(":", 2)
    await cb.answer()
 
    stages = [
        "Проверка устройства",
        "Скачивание прошивки",
        "Проверка подписи IPSW",
        "Распаковка образа",
        "Стирание раздела /System",
        "Запись ядра",
        "Установка iOS",
    ]
    if jb == "1":
        stages.append("Применение эксплойта")
        stages.append("Установка Cydia")
    stages.append("Перезагрузка устройства")
 
    total = len(stages)
    for i, stage in enumerate(stages, start=1):
        percent = int(i / total * 100)
        # чуть рандома, чтобы выглядело правдоподобнее
        if i < total:
            percent = max(1, percent - random.randint(0, 5))
        await cb.message.edit_text(
            f"⚙️ <b>Прошивка iOS {version}</b>\n\n"
            f"{stage}...\n"
            f"<code>{progress_bar(percent)}</code>\n\n"
            "❗ Не отключай устройство!",
            parse_mode="HTML",
        )
        await asyncio.sleep(random.uniform(1.5, 3))
 
    await cb.message.edit_text(
        f"⚙️ <b>Прошивка iOS {version}</b>\n\n"
        "Финальная проверка...\n"
        f"<code>{progress_bar(100)}</code>",
        parse_mode="HTML",
    )
    await asyncio.sleep(2)
 
    again = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔁 Прошить ещё раз", callback_data="connect")]]
    )
    await cb.message.edit_text(
        "🎉 <b>Прошивка завершена!</b>\n\n"
        "...шутка 😄 Ничего не прошилось.\n"
        "Твой телефон просто нормально зарядился от зарядки, "
        "а «переходник» был лишним 🔋",
        reply_markup=again,
        parse_mode="HTML",
    )
 
 
async def main():
    bot = Bot(TOKEN)
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())
