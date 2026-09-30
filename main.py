import asyncio
import hashlib
import os
import random
import re
from dataclasses import dataclass
from urllib.parse import quote

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN", "8970976053:AAH3V6gBMtuDcy98c2c16NpmP7F56c0o5KI")
UA = {"User-Agent": "iFlashFunBot/1.0 (telegram prank bot)"}

dp = Dispatcher()


# ---------------- база моделей ----------------

@dataclass
class Model:
    name: str
    idents: tuple      # идентификаторы вида iPhone14,5
    year: int
    chip: str
    min_ios: int       # с какой iOS вышел
    max_ios: int       # последняя поддерживаемая мажорная iOS (проверь актуальность!)
    wiki: str          # название статьи в англ. Википедии (для фото)


MODELS: list[Model] = [
    Model("iPhone 6", ("iPhone7,2",), 2014, "A8", 8, 12, "IPhone_6"),
    Model("iPhone 6 Plus", ("iPhone7,1",), 2014, "A8", 8, 12, "IPhone_6"),
    Model("iPhone 6s", ("iPhone8,1",), 2015, "A9", 9, 15, "IPhone_6S"),
    Model("iPhone 6s Plus", ("iPhone8,2",), 2015, "A9", 9, 15, "IPhone_6S"),
    Model("iPhone SE (1st gen)", ("iPhone8,4",), 2016, "A9", 9, 15, "IPhone_SE_(1st_generation)"),
    Model("iPhone 7", ("iPhone9,1", "iPhone9,3"), 2016, "A10 Fusion", 10, 15, "IPhone_7"),
    Model("iPhone 7 Plus", ("iPhone9,2", "iPhone9,4"), 2016, "A10 Fusion", 10, 15, "IPhone_7"),
    Model("iPhone 8", ("iPhone10,1", "iPhone10,4"), 2017, "A11 Bionic", 11, 16, "IPhone_8"),
    Model("iPhone 8 Plus", ("iPhone10,2", "iPhone10,5"), 2017, "A11 Bionic", 11, 16, "IPhone_8"),
    Model("iPhone X", ("iPhone10,3", "iPhone10,6"), 2017, "A11 Bionic", 11, 16, "IPhone_X"),
    Model("iPhone XR", ("iPhone11,8",), 2018, "A12 Bionic", 12, 18, "IPhone_XR"),
    Model("iPhone XS", ("iPhone11,2",), 2018, "A12 Bionic", 12, 18, "IPhone_XS"),
    Model("iPhone XS Max", ("iPhone11,4", "iPhone11,6"), 2018, "A12 Bionic", 12, 18, "IPhone_XS"),
    Model("iPhone 11", ("iPhone12,1",), 2019, "A13 Bionic", 13, 26, "IPhone_11"),
    Model("iPhone 11 Pro", ("iPhone12,3",), 2019, "A13 Bionic", 13, 26, "IPhone_11_Pro"),
    Model("iPhone 11 Pro Max", ("iPhone12,5",), 2019, "A13 Bionic", 13, 26, "IPhone_11_Pro"),
    Model("iPhone SE (2nd gen)", ("iPhone12,8",), 2020, "A13 Bionic", 13, 26, "IPhone_SE_(2nd_generation)"),
    Model("iPhone 12 mini", ("iPhone13,1",), 2020, "A14 Bionic", 14, 26, "IPhone_12"),
    Model("iPhone 12", ("iPhone13,2",), 2020, "A14 Bionic", 14, 26, "IPhone_12"),
    Model("iPhone 12 Pro", ("iPhone13,3",), 2020, "A14 Bionic", 14, 26, "IPhone_12_Pro"),
    Model("iPhone 12 Pro Max", ("iPhone13,4",), 2020, "A14 Bionic", 14, 26, "IPhone_12_Pro"),
    Model("iPhone 13 mini", ("iPhone14,4",), 2021, "A15 Bionic", 15, 26, "IPhone_13"),
    Model("iPhone 13", ("iPhone14,5",), 2021, "A15 Bionic", 15, 26, "IPhone_13"),
    Model("iPhone 13 Pro", ("iPhone14,2",), 2021, "A15 Bionic", 15, 26, "IPhone_13_Pro"),
    Model("iPhone 13 Pro Max", ("iPhone14,3",), 2021, "A15 Bionic", 15, 26, "IPhone_13_Pro"),
    Model("iPhone SE (3rd gen)", ("iPhone14,6",), 2022, "A15 Bionic", 15, 26, "IPhone_SE_(3rd_generation)"),
    Model("iPhone 14", ("iPhone14,7",), 2022, "A15 Bionic", 16, 26, "IPhone_14"),
    Model("iPhone 14 Plus", ("iPhone14,8",), 2022, "A15 Bionic", 16, 26, "IPhone_14"),
    Model("iPhone 14 Pro", ("iPhone15,2",), 2022, "A16 Bionic", 16, 26, "IPhone_14_Pro"),
    Model("iPhone 14 Pro Max", ("iPhone15,3",), 2022, "A16 Bionic", 16, 26, "IPhone_14_Pro"),
    Model("iPhone 15", ("iPhone15,4",), 2023, "A16 Bionic", 17, 26, "IPhone_15"),
    Model("iPhone 15 Plus", ("iPhone15,5",), 2023, "A16 Bionic", 17, 26, "IPhone_15"),
    Model("iPhone 15 Pro", ("iPhone16,1",), 2023, "A17 Pro", 17, 26, "IPhone_15_Pro"),
    Model("iPhone 15 Pro Max", ("iPhone16,2",), 2023, "A17 Pro", 17, 26, "IPhone_15_Pro"),
    Model("iPhone 16", ("iPhone17,3",), 2024, "A18", 18, 26, "IPhone_16"),
    Model("iPhone 16 Plus", ("iPhone17,4",), 2024, "A18", 18, 26, "IPhone_16"),
    Model("iPhone 16 Pro", ("iPhone17,1",), 2024, "A18 Pro", 18, 26, "IPhone_16_Pro"),
    Model("iPhone 16 Pro Max", ("iPhone17,2",), 2024, "A18 Pro", 18, 26, "IPhone_16_Pro"),
    Model("iPhone 16e", ("iPhone17,5",), 2025, "A18", 18, 26, "IPhone_16e"),
    Model("iPhone 17", (), 2025, "A19", 26, 26, "IPhone_17"),
    Model("iPhone Air", (), 2025, "A19 Pro", 26, 26, "IPhone_Air"),
    Model("iPhone 17 Pro", (), 2025, "A19 Pro", 26, 26, "IPhone_17_Pro"),
    Model("iPhone 17 Pro Max", (), 2025, "A19 Pro", 26, 26, "IPhone_17_Pro"),
]

VERSIONS_BY_MAJOR = {
    12: ["12.5.7"], 13: ["13.7"], 14: ["14.8.1"], 15: ["15.8.3"],
    16: ["16.7.10"], 17: ["17.7.2"], 18: ["18.0", "18.3"], 26: ["26.0"],
}


def versions_for(m: Model) -> list[str]:
    out: list[str] = []
    for major, vers in VERSIONS_BY_MAJOR.items():
        if max(m.min_ios, 12) <= major <= m.max_ios:
            out += vers
    return out[-6:]


COLORS = ["Space Gray", "Silver", "Gold", "Midnight", "Starlight", "Blue", "Black", "Pink", "Green"]
FACTORIES = ["Чжэнчжоу, Китай", "Шэньчжэнь, Китай", "Чэнду, Китай", "Ченнаи, Индия"]
SERIAL_RE = re.compile(r"[A-Za-z0-9]{8,14}")


def device_from_serial(serial: str) -> tuple[int, str]:
    """Из серийника получаем модель и доп. данные.
    Всё считается из хэша серийника, поэтому один и тот же серийник
    всегда даёт один и тот же результат (это имитация, не реальная база Apple)."""
    serial = serial.upper()
    h = int(hashlib.sha256(serial.encode()).hexdigest(), 16)
    idx = h % len(MODELS)
    m = MODELS[idx]
    caps = [16, 32, 64, 128] if m.year < 2017 else [64, 128, 256, 512]
    capacity = caps[(h >> 8) % 4]
    color = COLORS[(h >> 16) % len(COLORS)]
    week = 1 + (h >> 24) % 52
    factory = FACTORIES[(h >> 32) % len(FACTORIES)]
    extra = (
        f"\n🔢 Серийный номер: <code>{serial}</code>"
        f"\n💾 Память: {capacity} ГБ"
        f"\n🎨 Цвет: {color}"
        f"\n🏭 Произведён: {m.year}, неделя {week} ({factory})"
    )
    return idx, extra


def norm(s: str) -> str:
    s = s.lower().replace("айфон", "iphone").replace("apple", "")
    return "".join(s.split())


def find_models(query: str) -> tuple[list[int], bool]:
    """Возвращает (список индексов, точное ли совпадение)."""
    q = norm(query)
    if not q:
        return [], False
    if not q.startswith("iphone"):
        q = "iphone" + q
    exact = [
        i for i, m in enumerate(MODELS)
        if norm(m.name) == q or q in [x.lower() for x in m.idents]
    ]
    if exact:
        return exact[:1], True
    partial = [i for i, m in enumerate(MODELS) if q in norm(m.name)]
    return partial[:8], False


async def fetch_photo(title: str) -> bytes | None:
    """Фото модели из Википедии (или None, если не вышло)."""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(headers=UA, timeout=timeout) as s:
            api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}"
            async with s.get(api) as r:
                data = await r.json()
            src = (data.get("thumbnail") or {}).get("source") or (data.get("originalimage") or {}).get("source")
            if not src:
                return None
            async with s.get(src) as r:
                if r.status != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
                    return None
                return await r.read()
    except Exception:
        return None


# ---------------- клавиатуры ----------------

def kb_start() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔌 Начать прошивку", callback_data="connect")
    return b.as_markup()


def kb_connected() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подключил", callback_data="ask_model")
    return b.as_markup()


def kb_candidates(idxs: list[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in idxs:
        b.button(text=MODELS[i].name, callback_data=f"pick:{i}")
    b.adjust(2)
    return b.as_markup()


def kb_versions(idx: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for v in versions_for(MODELS[idx]):
        b.button(text=f"iOS {v}", callback_data=f"ver:{idx}:{v}")
    b.adjust(2)
    return b.as_markup()


def kb_jailbreak(idx: int, version: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔓 С джейлбрейком", callback_data=f"jb:1:{idx}:{version}")
    b.button(text="🔒 Без джейлбрейка", callback_data=f"jb:0:{idx}:{version}")
    b.adjust(1)
    return b.as_markup()


def kb_confirm(idx: int, version: str, jb: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚀 Прошить!", callback_data=f"flash:{jb}:{idx}:{version}")
    b.button(text="⬅️ Назад", callback_data=f"pick:{idx}")
    b.adjust(1)
    return b.as_markup()


# ---------------- логика ----------------

waiting_model: set[int] = set()   # кто сейчас должен ввести модель


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


@dp.callback_query(F.data == "ask_model")
async def ask_model(cb: CallbackQuery):
    waiting_model.add(cb.from_user.id)
    await cb.message.edit_text(
        "🔗 <b>Синхронизация с устройством</b>\n\n"
        "Введи <b>серийный номер</b> iPhone — я определю модель и все данные.\n"
        "Его можно найти в: Настройки → Основные → Об этом устройстве → Серийный номер.\n\n"
        "<i>Можно и просто написать модель, например iPhone 13 Pro.</i>",
        parse_mode="HTML",
    )
    await cb.answer()


async def show_device(target: Message, idx: int, extra: str = ""):
    """Красивое 'определение' устройства + фото + выбор версии."""
    m = MODELS[idx]
    status = await target.answer("📡 Считываю данные с устройства...")
    await asyncio.sleep(1.5)
    await status.edit_text("🧬 Определяю модель и версию системы...")
    photo_task = asyncio.create_task(fetch_photo(m.wiki))
    await asyncio.sleep(1.5)
    photo = await photo_task
    await status.delete()

    current = random.choice(versions_for(m))
    ident = m.idents[0] if m.idents else "—"
    caption = (
        "✅ <b>Устройство обнаружено!</b>\n\n"
        f"📱 Модель: <b>{m.name}</b>\n"
        f"🆔 Идентификатор: <code>{ident}</code>\n"
        f"🧠 Чип: {m.chip}\n"
        f"📅 Год выпуска: {m.year}\n"
        f"⚙️ Текущая iOS: {current}\n"
        f"🔝 Максимальная iOS: {'26+' if m.max_ios == 26 else m.max_ios}\n"
        "🔧 Режим: DFU"
        f"{extra}"
    )
    if photo:
        await target.answer_photo(BufferedInputFile(photo, "iphone.jpg"), caption=caption, parse_mode="HTML")
    else:
        await target.answer(caption, parse_mode="HTML")

    await target.answer(
        "<b>Шаг 2.</b> Выбери версию iOS для прошивки:",
        reply_markup=kb_versions(idx),
        parse_mode="HTML",
    )


@dp.message(F.text & ~F.text.startswith("/"))
async def got_model(message: Message):
    uid = message.from_user.id
    if uid not in waiting_model:
        return
    text = message.text.strip()
    idxs, exact = find_models(text)

    if exact:                                   # ввели название / идентификатор модели
        waiting_model.discard(uid)
        await show_device(message, idxs[0])
    elif SERIAL_RE.fullmatch(text):             # ввели серийный номер
        waiting_model.discard(uid)
        idx, extra = device_from_serial(text)
        await show_device(message, idx, extra)
    elif idxs:                                  # неоднозначное название
        await message.answer("🤔 Уточни, какая именно модель:", reply_markup=kb_candidates(idxs))
    else:
        await message.answer(
            "❌ Не удалось определить устройство.\n"
            "Серийный номер — это 8–14 символов (буквы и цифры), например <code>F2LXK3ABCD12</code>.",
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("pick:"))
async def pick(cb: CallbackQuery):
    idx = int(cb.data.split(":")[1])
    waiting_model.discard(cb.from_user.id)
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await show_device(cb.message, idx)


@dp.callback_query(F.data.startswith("ver:"))
async def choose_version(cb: CallbackQuery):
    _, idx, version = cb.data.split(":", 2)
    await cb.message.edit_text(
        f"📦 Выбрана: <b>iOS {version}</b>\n\n<b>Шаг 3.</b> Нужен ли джейлбрейк?",
        reply_markup=kb_jailbreak(int(idx), version),
        parse_mode="HTML",
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("jb:"))
async def choose_jb(cb: CallbackQuery):
    _, jb, idx, version = cb.data.split(":", 3)
    m = MODELS[int(idx)]
    jb_text = "с джейлбрейком 🔓" if jb == "1" else "без джейлбрейка 🔒"
    await cb.message.edit_text(
        "⚠️ <b>Подтверждение</b>\n\n"
        f"Устройство: <b>{m.name}</b>\n"
        f"Версия: <b>iOS {version}</b>\n"
        f"Режим: <b>{jb_text}</b>\n\n"
        "Не отключай устройство во время прошивки!",
        reply_markup=kb_confirm(int(idx), version, jb),
        parse_mode="HTML",
    )
    await cb.answer()


def progress_bar(percent: int, width: int = 12) -> str:
    filled = int(width * percent / 100)
    return "█" * filled + "░" * (width - filled) + f" {percent}%"


@dp.callback_query(F.data.startswith("flash:"))
async def flash(cb: CallbackQuery):
    _, jb, idx, version = cb.data.split(":", 3)
    m = MODELS[int(idx)]
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
        stages += ["Применение эксплойта", "Установка Cydia"]
    stages.append("Перезагрузка устройства")

    total = len(stages)
    for i, stage in enumerate(stages, start=1):
        percent = int(i / total * 100)
        if i < total:
            percent = max(1, percent - random.randint(0, 5))
        await cb.message.edit_text(
            f"⚙️ <b>Прошивка {m.name} → iOS {version}</b>\n\n"
            f"{stage}...\n<code>{progress_bar(percent)}</code>\n\n"
            "❗ Не отключай устройство!",
            parse_mode="HTML",
        )
        await asyncio.sleep(random.uniform(1.5, 3))

    await cb.message.edit_text(
        f"⚙️ <b>Прошивка {m.name} → iOS {version}</b>\n\n"
        f"Финальная проверка...\n<code>{progress_bar(100)}</code>",
        parse_mode="HTML",
    )
    await asyncio.sleep(2)

    again = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔁 Прошить ещё раз", callback_data="connect")]]
    )
    await cb.message.edit_text(
        "🎉 <b>Прошивка завершена!</b>\n\n"
        "...шутка 😄 Ничего не прошилось.\n"
        "Твой телефон просто нормально зарядился от зарядки, а «переходник» был лишним 🔋",
        reply_markup=again,
        parse_mode="HTML",
    )


async def main():
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
