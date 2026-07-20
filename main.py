import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)

# =========================== НАСТРОЙКИ ===========================

BOT_TOKEN = "8804748206:AAH2NvoNqMT6EFb2v9_9NLF30QejL82AyQY"   # получить у @BotFather
ADMIN_ID = 7738822030                   # сюда будут приходить заявки

# ==================================================================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Храним заявки в памяти: {app_id: {...}}
# Для продакшена лучше заменить на БД (SQLite/PostgreSQL)
applications: dict[int, dict] = {}
app_counter = 0


class ApplicationForm(StatesGroup):
    nickname = State()
    static_id = State()
    age = State()
    experience = State()
    reason = State()
    confirm = State()


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📝 Подать заявку")]],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def confirm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Отправить"), KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def admin_decision_kb(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"accept:{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{app_id}"),
            ]
        ]
    )


# ============================ СТАРТ ============================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Здесь вы можете подать заявку. Нажмите кнопку ниже, чтобы начать.",
        reply_markup=main_menu_kb(),
    )


# ======================= ОТМЕНА НА ЛЮБОМ ШАГЕ =====================

@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена.", reply_markup=main_menu_kb())


# ========================== АНКЕТА ==============================

@router.message(F.text == "📝 Подать заявку")
async def start_application(message: Message, state: FSMContext):
    await state.set_state(ApplicationForm.nickname)
    await message.answer("Введите ваш игровой ник:", reply_markup=cancel_kb())


@router.message(ApplicationForm.nickname)
async def get_nickname(message: Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await state.set_state(ApplicationForm.static_id)
    await message.answer("Введите ваш Static ID:")


@router.message(ApplicationForm.static_id)
async def get_static_id(message: Message, state: FSMContext):
    await state.update_data(static_id=message.text)
    await state.set_state(ApplicationForm.age)
    await message.answer("Введите ваш реальный возраст:")


@router.message(ApplicationForm.age)
async def get_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await state.set_state(ApplicationForm.experience)
    await message.answer("Есть ли у вас опыт игры на подобных проектах? Если да — укажите каких:")


@router.message(ApplicationForm.experience)
async def get_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(ApplicationForm.reason)
    await message.answer("Почему мы должны принять именно вас? (коротко опишите)")


@router.message(ApplicationForm.reason)
async def get_reason(message: Message, state: FSMContext):
    await state.update_data(reason=message.text)
    data = await state.get_data()

    preview = (
        "📋 <b>Проверьте вашу заявку:</b>\n\n"
        f"🎮 Ник: {data['nickname']}\n"
        f"🆔 Static ID: {data['static_id']}\n"
        f"🎂 Возраст: {data['age']}\n"
        f"⭐ Опыт: {data['experience']}\n"
        f"💬 Причина: {data['reason']}\n\n"
        "Всё верно?"
    )
    await state.set_state(ApplicationForm.confirm)
    await message.answer(preview, reply_markup=confirm_kb())


@router.message(ApplicationForm.confirm, F.text == "✅ Отправить")
async def confirm_application(message: Message, state: FSMContext):
    global app_counter
    data = await state.get_data()
    app_counter += 1
    app_id = app_counter

    applications[app_id] = {
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "data": data,
        "status": "pending",
    }

    admin_text = (
        f"🆕 <b>Новая заявка #{app_id}</b>\n"
        f"👤 От: @{message.from_user.username or 'нет юзернейма'} "
        f"(ID: <code>{message.from_user.id}</code>)\n"
        f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"🎮 Ник: {data['nickname']}\n"
        f"🆔 Static ID: {data['static_id']}\n"
        f"🎂 Возраст: {data['age']}\n"
        f"⭐ Опыт: {data['experience']}\n"
        f"💬 Причина: {data['reason']}"
    )

    await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_decision_kb(app_id))

    await state.clear()
    await message.answer(
        "✅ Ваша заявка отправлена на рассмотрение! Ожидайте ответа.",
        reply_markup=main_menu_kb(),
    )


# ==================== ОБРАБОТКА РЕШЕНИЯ АДМИНОМ ====================

@router.callback_query(F.data.startswith("accept:"))
async def accept_application(callback: CallbackQuery):
    app_id = int(callback.data.split(":")[1])
    app = applications.get(app_id)
    if not app or app["status"] != "pending":
        await callback.answer("Заявка уже обработана или не найдена.", show_alert=True)
        return

    app["status"] = "accepted"
    await bot.send_message(
        app["user_id"],
        "🎉 Поздравляем! Ваша заявка была <b>одобрена</b>.",
    )
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>ПРИНЯТА</b>",
        reply_markup=None,
    )
    await callback.answer("Заявка принята")


@router.callback_query(F.data.startswith("reject:"))
async def reject_application(callback: CallbackQuery):
    app_id = int(callback.data.split(":")[1])
    app = applications.get(app_id)
    if not app or app["status"] != "pending":
        await callback.answer("Заявка уже обработана или не найдена.", show_alert=True)
        return

    app["status"] = "rejected"
    await bot.send_message(
        app["user_id"],
        "😔 К сожалению, ваша заявка была <b>отклонена</b>.",
    )
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ОТКЛОНЕНА</b>",
        reply_markup=None,
    )
    await callback.answer("Заявка отклонена")


# ============================ ЗАПУСК ============================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    
