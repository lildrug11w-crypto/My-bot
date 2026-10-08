import asyncio
import logging
import os
import re
import sqlite3
from contextlib import closing
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, MessageEntity
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Set BOT_TOKEN as an environment variable, or replace the empty value below.
BOT_TOKEN = os.getenv("8748390816:AAFp_ydyiwPeBIHJqIXuAJvI14DNn4OPe8E", "").strip()
ADMIN_ID = 7738822030
DB_PATH = os.getenv("BOT_DB_PATH", "database.db")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("crmp_samp_shop")

DEFAULT_MESSAGES = {
    "welcome": "<b>Добро пожаловать в магазин LILHEAD SHOP!</b>\nВыберите нужный раздел ниже.",
    "development": "Отдел разработки сейчас не работает.",
    "advertising": "Стоимость рекламы: 500 ₽.\n\nДля заказа рекламы напишите администратору.",
    "free_intro": "Бесплатные проекты доступны ниже.",
    "submit_intro": "Отправьте одним сообщением информацию о предложении: текст, ссылку, фото или документ.",
    "admin_help": "Панель управления магазином.",
}
DEFAULT_BUTTONS = [
    ("🛒 Приобрести проект", "projects", "", "🛒"),
    ("🆓 Бесплатный проект", "free_projects", "", "🆓"),
    ("📢 Приобрести рекламу", "message", "advertising", "📢"),
    ("💾 Предложить слив", "submit", "", "💾"),
    ("🛠️ Разработка", "message", "development", "🛠️"),
]

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with closing(connect()) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (key TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, emoji_id TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS menu_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, emoji TEXT DEFAULT '',
            action TEXT NOT NULL, payload TEXT DEFAULT '', emoji_id TEXT DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL,
            price REAL NOT NULL, url TEXT NOT NULL, emoji TEXT DEFAULT '📦',
            emoji_id TEXT DEFAULT '', position INTEGER NOT NULL DEFAULT 0, is_free INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT DEFAULT '',
            full_name TEXT DEFAULT '', kind TEXT NOT NULL, text TEXT DEFAULT '',
            file_id TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'new'
        );
        """)
        for key, value in DEFAULT_MESSAGES.items():
            db.execute("INSERT OR IGNORE INTO messages(key,title,body) VALUES(?,?,?)", (key, key, value))
        count = db.execute("SELECT COUNT(*) FROM menu_buttons").fetchone()[0]
        if count == 0:
            for pos, (title, action, payload, emoji) in enumerate(DEFAULT_BUTTONS):
                db.execute("INSERT INTO menu_buttons(title,action,payload,emoji,position) VALUES(?,?,?,?,?)",
                           (title, action, payload, emoji, pos))
        db.commit()
        db.close()

def q_one(sql, params=()):
    with closing(connect()) as db:
        row = db.execute(sql, params).fetchone()
        return dict(row) if row else None

def q_all(sql, params=()):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute(sql, params).fetchall()]

def execute(sql, params=()):
    with closing(connect()) as db:
        cur = db.execute(sql, params)
        db.commit()
        return cur.lastrowid

def get_message(key):
    row = q_one("SELECT * FROM messages WHERE key=?", (key,))
    return row

def set_message(key, title, body, emoji_id=""):
    execute("""INSERT INTO messages(key,title,body,emoji_id) VALUES(?,?,?,?)
    ON CONFLICT(key) DO UPDATE SET title=excluded.title,body=excluded.body,emoji_id=excluded.emoji_id""",
            (key, title, body, emoji_id))

def is_admin(user_id):
    return user_id == ADMIN_ID

def admin_only(handler):
    async def wrapped(event, *args, **kwargs):
        uid = event.from_user.id if getattr(event, "from_user", None) else None
        if not is_admin(uid):
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("⛔ Доступ запрещён.")
            return
        return await handler(event, *args, **kwargs)
    wrapped.__name__ = handler.__name__
    return wrapped

class Flow(StatesGroup):
    button_title = State()
    button_emoji = State()
    button_action = State()
    button_payload = State()
    button_edit_value = State()
    button_delete = State()
    button_order = State()
    message_key = State()
    message_title = State()
    message_body = State()
    message_emoji = State()
    project_title = State()
    project_description = State()
    project_price = State()
    project_url = State()
    project_emoji = State()
    project_order = State()
    project_select_edit = State()
    project_field = State()
    project_field_value = State()
    free_title = State()
    free_description = State()
    free_url = State()
    free_emoji = State()
    free_select = State()
    free_field = State()
    free_field_value = State()
    emoji_target = State()
    emoji_id = State()
    settings_key = State()
    settings_value = State()

dp = Dispatcher()

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def inline(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_home_kb():
    return inline([
        [InlineKeyboardButton(text="📝 Сообщения", callback_data="adm:messages"),
         InlineKeyboardButton(text="🔘 Кнопки", callback_data="adm:buttons")],
        [InlineKeyboardButton(text="📦 Проекты", callback_data="adm:projects"),
         InlineKeyboardButton(text="🆓 Бесплатные проекты", callback_data="adm:free")],
        [InlineKeyboardButton(text="⭐ Premium Emoji", callback_data="adm:emoji"),
         InlineKeyboardButton(text="📢 Реклама", callback_data="adm:advertising")],
        [InlineKeyboardButton(text="💾 Заявки", callback_data="adm:submissions"),
         InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm:settings")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")]
    ])

def back_admin():
    return inline([[InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="adm:home")]])

def buttons_menu():
    return inline([
        [InlineKeyboardButton(text="➕ Создать кнопку", callback_data="btn:create"),
         InlineKeyboardButton(text="✏️ Изменить кнопку", callback_data="btn:editlist")],
        [InlineKeyboardButton(text="🗑️ Удалить кнопку", callback_data="btn:dellist"),
         InlineKeyboardButton(text="🔀 Изменить порядок", callback_data="btn:orderlist")],
        [InlineKeyboardButton(text="⭐ Изменить Premium Emoji", callback_data="btn:emojilist")],
        [InlineKeyboardButton(text="📋 Список кнопок", callback_data="btn:list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]
    ])

def main_menu_markup():
    rows = []
    for b in q_all("SELECT * FROM menu_buttons WHERE enabled=1 ORDER BY position,id"):
        title = b["title"]
        # Telegram's button-icon field supports custom emoji IDs on current Bot API.
        kwargs = {"text": title, "callback_data": f"menu:{b['id']}"}
        if b.get("emoji_id"):
            kwargs["icon_custom_emoji_id"] = b["emoji_id"]
        rows.append([InlineKeyboardButton(**kwargs)])
    if not rows:
        rows = [[InlineKeyboardButton(text="Меню пока пусто", callback_data="noop")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def projects_markup(is_free=False):
    rows = []
    for p in q_all("SELECT * FROM projects WHERE is_free=? ORDER BY position,id", (1 if is_free else 0,)):
        label = f"{p['emoji'] or '📦'} {p['title']}"[:60]
        rows.append([InlineKeyboardButton(text=label, callback_data=f"p:view:{p['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="home")])
    return inline(rows)

def valid_url(value):
    try:
        u = urlparse(value.strip())
        return u.scheme in ("http", "https") and bool(u.netloc)
    except Exception:
        return False

async def safe_edit(call: CallbackQuery, text, reply_markup=None, parse_mode="HTML"):
    try:
        await call.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            await call.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

async def show_admin(message_or_call, text="⚙️ <b>Админ-панель</b>"):
    kb = admin_home_kb()
    if isinstance(message_or_call, CallbackQuery):
        await safe_edit(message_or_call, text, kb)
    else:
        await message_or_call.answer(text, reply_markup=kb)

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    welcome = get_message("welcome")
    text = welcome["body"] if welcome else DEFAULT_MESSAGES["welcome"]
    await message.answer(text, reply_markup=main_menu_markup())
    if is_admin(message.from_user.id):
        await message.answer("Администратор: /admin — панель управления.")

@dp.message(Command("admin"))
@admin_only
async def admin_command(message: Message, state: FSMContext):
    await state.clear()
    await show_admin(message)

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_markup())

@dp.message(F.text == "❌ Отмена")
async def cancel_button(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_markup())
    if is_admin(message.from_user.id):
        await message.answer("⚙️ Админ-панель", reply_markup=admin_home_kb())

@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()

@dp.callback_query(F.data == "home")
async def home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome = get_message("welcome")
    await safe_edit(call, welcome["body"] if welcome else DEFAULT_MESSAGES["welcome"], main_menu_markup())
    await call.answer()

@dp.callback_query(F.data == "adm:home")
@admin_only
async def admin_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_admin(call)
    await call.answer()

@dp.callback_query(F.data.startswith("adm:"))
@admin_only
async def admin_sections(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    if key == "buttons":
        await safe_edit(call, "🔘 <b>Управление кнопками</b>", buttons_menu())
    elif key == "messages":
        rows = q_all("SELECT key,title,body FROM messages ORDER BY key")
        kb = [[InlineKeyboardButton(text=f"✏️ {r['title']}"[:60], callback_data=f"msg:edit:{r['key']}"),
               InlineKeyboardButton(text="👁️", callback_data=f"msg:view:{r['key']}"),
               InlineKeyboardButton(text="🗑️", callback_data=f"msg:delask:{r['key']}")] for r in rows]
        kb += [[InlineKeyboardButton(text="➕ Создать сообщение", callback_data="msg:create")],
               [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]]
        await safe_edit(call, "📝 <b>Управление сообщениями</b>\nВыберите сообщение:", inline(kb))
    elif key in ("projects", "free"):
        is_free = 1 if key == "free" else 0
        title = "🆓 Бесплатные проекты" if is_free else "📦 Управление проектами"
        prefix = "free" if is_free else "proj"
        kb = [[InlineKeyboardButton(text="➕ Добавить", callback_data=f"{prefix}:create"),
               InlineKeyboardButton(text="✏️ Изменить", callback_data=f"{prefix}:editlist")],
              [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"{prefix}:dellist"),
               InlineKeyboardButton(text="📋 Список", callback_data=f"{prefix}:list")],
              [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]]
        await safe_edit(call, title, inline(kb))
    elif key == "emoji":
        await safe_edit(call, "⭐ <b>Premium Emoji</b>\nОтправьте /getemoji, затем пришлите сообщение с Premium Emoji.\nДля назначения используйте раздел «Кнопки» или редактирование проекта/сообщения.", inline([
            [InlineKeyboardButton(text="⭐ Получить ID Premium Emoji", callback_data="emoji:get")],
            [InlineKeyboardButton(text="📋 Список текущих ID", callback_data="emoji:list")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]]))
    elif key == "advertising":
        r = get_message("advertising")
        await safe_edit(call, "📢 <b>Текст рекламы</b>\n\n" + (r["body"] if r else ""), inline([
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="msg:edit:advertising")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]]))
    elif key == "submissions":
        rows = q_all("SELECT * FROM submissions ORDER BY id DESC LIMIT 20")
        kb = [[InlineKeyboardButton(text=f"#{r['id']} {r['full_name'] or r['user_id']} — {r['status']}", callback_data=f"sub:view:{r['id']}")] for r in rows]
        kb += [[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]]
        await safe_edit(call, "💾 <b>Последние заявки</b>", inline(kb))
    elif key == "settings":
        await safe_edit(call, "⚙️ <b>Настройки</b>\nID администратора зафиксирован в конфигурации: 7738822030.\nТокен задаётся переменной окружения BOT_TOKEN.", inline([
            [InlineKeyboardButton(text="📊 Статистика", callback_data="settings:stats")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]]))
    await call.answer()

# Dynamic user menu actions
@dp.callback_query(F.data.startswith("menu:"))
async def dynamic_menu(call: CallbackQuery, state: FSMContext):
    try:
        bid = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("Некорректная кнопка.", show_alert=True); return
    b = q_one("SELECT * FROM menu_buttons WHERE id=? AND enabled=1", (bid,))
    if not b:
        await call.answer("Эта кнопка больше недоступна.", show_alert=True); return
    action, payload = b["action"], b["payload"]
    if action == "projects":
        await safe_edit(call, "🛒 <b>Каталог проектов</b>\nВыберите проект:", projects_markup(False))
    elif action == "free_projects":
        await safe_edit(call, "🆓 <b>Бесплатные проекты</b>\nВыберите проект:", projects_markup(True))
    elif action == "message":
        r = get_message(payload)
        await safe_edit(call, r["body"] if r else "Сообщение пока не настроено.", inline([[InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]]))
    elif action == "url":
        if valid_url(payload):
            await safe_edit(call, f"Ссылка: {payload}", inline([[InlineKeyboardButton(text="🔗 Открыть ссылку", url=payload)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]]))
        else:
            await call.answer("Ссылка не настроена корректно.", show_alert=True)
    elif action == "admin":
        await safe_edit(call, "Связаться с администратором: @username не задан.\nНапишите администратору по ID 7738822030.", inline([
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]]))
    elif action == "back":
        await safe_edit(call, "Главное меню", main_menu_markup())
    elif action == "submit":
        await state.set_state(Flow.settings_value)
        await state.update_data(flow="submission")
        await safe_edit(call, get_message("submit_intro")["body"], inline([[InlineKeyboardButton(text="❌ Отмена", callback_data="home")]]))
    else:
        await call.answer("Неизвестное действие кнопки.", show_alert=True)
    await call.answer()

@dp.callback_query(F.data.startswith("p:view:"))
async def project_view(call: CallbackQuery):
    try: pid = int(call.data.split(":")[2])
    except Exception:
        await call.answer("Некорректный проект.", show_alert=True); return
    p = q_one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        await call.answer("Проект не найден или удалён.", show_alert=True); return
    price = "Бесплатно" if p["is_free"] else f"{p['price']:g} ₽"
    text = f"{p['emoji'] or '📦'} <b>{p['title']}</b>\n\n{p['description']}\n\n<b>Цена:</b> {price}"
    rows = []
    if valid_url(p["url"]):
        rows.append([InlineKeyboardButton(text="🔗 Скачать" if p["is_free"] else "💰 Купить", url=p["url"])])
    rows += [[InlineKeyboardButton(text="📄 Подробнее", callback_data=f"p:detail:{pid}")],
             [InlineKeyboardButton(text="⬅️ Назад", callback_data="p:list:{0}".format(1 if p["is_free"] else 0))]]
    await safe_edit(call, text, inline(rows))
    await call.answer()

@dp.callback_query(F.data.startswith("p:detail:"))
async def project_detail(call: CallbackQuery):
    pid = int(call.data.split(":")[2])
    p = q_one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        await call.answer("Проект не найден.", show_alert=True); return
    await safe_edit(call, f"<b>{p['title']}</b>\n\n{p['description']}\n\nID проекта: <code>{pid}</code>",
                    inline([[InlineKeyboardButton(text="⬅️ К проекту", callback_data=f"p:view:{pid}")]]))
    await call.answer()

@dp.callback_query(F.data.startswith("p:list:"))
async def project_list_back(call: CallbackQuery):
    is_free = int(call.data.split(":")[2])
    await safe_edit(call, "🆓 Бесплатные проекты:" if is_free else "🛒 Каталог проектов:", projects_markup(bool(is_free)))
    await call.answer()

# Button builder
@dp.callback_query(F.data == "btn:list")
@admin_only
async def button_list(call: CallbackQuery):
    rows = q_all("SELECT * FROM menu_buttons ORDER BY position,id")
    text = "\n".join(f"{r['position']}. ID {r['id']} — {r['title']} | {r['action']} | payload={r['payload'] or '—'} | emoji_id={r['emoji_id'] or '—'}" for r in rows) or "Кнопок нет."
    await safe_edit(call, text, buttons_menu()); await call.answer()

@dp.callback_query(F.data == "btn:create")
@admin_only
async def button_create(call: CallbackQuery, state: FSMContext):
    await state.clear(); await state.set_state(Flow.button_title)
    await call.message.answer("Введите название кнопки:", reply_markup=cancel_kb()); await call.answer()

@dp.message(Flow.button_title)
@admin_only
async def button_title(message: Message, state: FSMContext):
    if not message.text or not message.text.strip(): await message.answer("Название не должно быть пустым."); return
    await state.update_data(title=message.text.strip())
    await state.set_state(Flow.button_emoji)
    await message.answer("Введите обычный emoji (например 🛒) или '-' без emoji. Premium Emoji назначается отдельно.", reply_markup=cancel_kb())

@dp.message(Flow.button_emoji)
@admin_only
async def button_emoji(message: Message, state: FSMContext):
    if message.text is None: await message.answer("Отправьте emoji или '-'."); return
    await state.update_data(emoji="" if message.text.strip()=="-" else message.text.strip())
    await state.set_state(Flow.button_action)
    await message.answer("Выберите действие:", reply_markup=inline([
        [InlineKeyboardButton(text="Отправить сообщение", callback_data="btn:action:message")],
        [InlineKeyboardButton(text="Открыть ссылку", callback_data="btn:action:url")],
        [InlineKeyboardButton(text="Список проектов", callback_data="btn:action:projects")],
        [InlineKeyboardButton(text="Бесплатные проекты", callback_data="btn:action:free_projects")],
        [InlineKeyboardButton(text="Написать администратору", callback_data="btn:action:admin")],
        [InlineKeyboardButton(text="Предложить слив", callback_data="btn:action:submit")],
        [InlineKeyboardButton(text="Вернуться назад", callback_data="btn:action:back")],
    ]))

@dp.callback_query(F.data.startswith("btn:action:"))
@admin_only
async def button_action(call: CallbackQuery, state: FSMContext):
    action = call.data.split(":")[2]
    await state.update_data(action=action)
    if action in ("message", "url"):
        await state.set_state(Flow.button_payload)
        if action == "message":
            rows = q_all("SELECT key,title FROM messages ORDER BY key")
            kb = [[InlineKeyboardButton(text=f"{r['title']} ({r['key']})", callback_data=f"btn:payloadmsg:{r['key']}")] for r in rows]
            kb.append([InlineKeyboardButton(text="➕ Создать новое сообщение", callback_data="msg:create")])
            await call.message.answer("Выберите сообщение для кнопки:", reply_markup=inline(kb))
        else:
            await call.message.answer("Введите полную ссылку, начинающуюся с http:// или https://:", reply_markup=cancel_kb())
    else:
        data = await state.get_data()
        execute("INSERT INTO menu_buttons(title,emoji,action,payload,position) VALUES(?,?,?,?,?)",
                (data["title"], data.get("emoji",""), action, "", (q_one("SELECT COALESCE(MAX(position),-1)+1 AS n FROM menu_buttons") or {}).get("n",0)))
        await state.clear()
        await call.message.answer("Кнопка успешно создана ✅", reply_markup=buttons_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("btn:payloadmsg:"))
@admin_only
async def button_payload_message(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":",2)[2]
    data = await state.get_data()
    execute("INSERT INTO menu_buttons(title,emoji,action,payload,position) VALUES(?,?,?,?,?)",
            (data["title"], data.get("emoji",""), "message", key,
             (q_one("SELECT COALESCE(MAX(position),-1)+1 AS n FROM menu_buttons") or {}).get("n",0)))
    await state.clear(); await safe_edit(call, "Кнопка создана ✅", buttons_menu()); await call.answer()

@dp.message(Flow.button_payload)
@admin_only
async def button_payload(message: Message, state: FSMContext):
    data = await state.get_data()
    value = (message.text or "").strip()
    if data.get("action") == "url" and not valid_url(value):
        await message.answer("Некорректная ссылка. Пример: https://example.com"); return
    if not value: await message.answer("Значение не должно быть пустым."); return
    execute("INSERT INTO menu_buttons(title,emoji,action,payload,position) VALUES(?,?,?,?,?)",
            (data["title"], data.get("emoji",""), data["action"], value,
             (q_one("SELECT COALESCE(MAX(position),-1)+1 AS n FROM menu_buttons") or {}).get("n",0)))
    await state.clear(); await message.answer("Кнопка создана ✅", reply_markup=buttons_menu())

@dp.callback_query(F.data.in_({"btn:editlist","btn:dellist","btn:orderlist","btn:emojilist"}))
@admin_only
async def button_lists(call: CallbackQuery, state: FSMContext):
    mode = call.data.split(":")[1]
    rows = q_all("SELECT id,title FROM menu_buttons ORDER BY position,id")
    kb = [[InlineKeyboardButton(text=f"{r['id']} — {r['title']}"[:60], callback_data=f"btn:{mode}:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:buttons")])
    await safe_edit(call, "Выберите кнопку:", inline(kb)); await call.answer()

@dp.callback_query(F.data.startswith("btn:dellist:"))
@admin_only
async def button_delete_ask(call: CallbackQuery):
    bid = int(call.data.split(":")[2]); b = q_one("SELECT * FROM menu_buttons WHERE id=?", (bid,))
    if not b: await call.answer("Кнопка не найдена.", show_alert=True); return
    await safe_edit(call, f"Удалить кнопку «{b['title']}»?", inline([
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"btn:delete:{bid}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="adm:buttons")]])); await call.answer()

@dp.callback_query(F.data.startswith("btn:delete:"))
@admin_only
async def button_delete(call: CallbackQuery):
    bid = int(call.data.split(":")[2]); execute("DELETE FROM menu_buttons WHERE id=?", (bid,))
    await safe_edit(call, "Кнопка удалена ✅", buttons_menu()); await call.answer()

@dp.callback_query(F.data.startswith("btn:editlist:"))
@admin_only
async def button_edit_select(call: CallbackQuery, state: FSMContext):
    bid = int(call.data.split(":")[2]); b = q_one("SELECT * FROM menu_buttons WHERE id=?", (bid,))
    if not b: await call.answer("Кнопка не найдена.", show_alert=True); return
    await state.update_data(button_id=bid)
    await safe_edit(call, f"Редактирование «{b['title']}»", inline([
        [InlineKeyboardButton(text="✏️ Название", callback_data="btn:field:title"),
         InlineKeyboardButton(text="🎨 Emoji", callback_data="btn:field:emoji")],
        [InlineKeyboardButton(text="🔗 Действие/ссылка", callback_data="btn:field:payload")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:buttons")]])); await call.answer()

@dp.callback_query(F.data.startswith("btn:field:"))
@admin_only
async def button_field(call: CallbackQuery, state: FSMContext):
    field = call.data.split(":")[2]; await state.update_data(button_field=field)
    await state.set_state(Flow.button_edit_value)
    await call.message.answer("Введите новое значение. Для ссылки используйте https://...; для emoji можно ввести '-'.", reply_markup=cancel_kb())
    await call.answer()

@dp.message(Flow.button_edit_value)
@admin_only
async def button_field_save(message: Message, state: FSMContext):
    data = await state.get_data(); value = (message.text or "").strip()
    if not value: await message.answer("Значение не может быть пустым."); return
    field = data["button_field"]; bid = data["button_id"]
    if field == "payload":
        b = q_one("SELECT action FROM menu_buttons WHERE id=?", (bid,))
        if b and b["action"] == "url" and not valid_url(value):
            await message.answer("Некорректная ссылка."); return
        execute("UPDATE menu_buttons SET payload=? WHERE id=?", (value,bid))
    elif field == "emoji":
        execute("UPDATE menu_buttons SET emoji=? WHERE id=?", ("" if value=="-" else value,bid))
    else:
        execute("UPDATE menu_buttons SET title=? WHERE id=?", (value,bid))
    await state.clear(); await message.answer("Изменения сохранены ✅", reply_markup=buttons_menu())

@dp.callback_query(F.data.startswith("btn:orderlist:"))
@admin_only
async def button_order_select(call: CallbackQuery, state: FSMContext):
    bid = int(call.data.split(":")[2]); await state.update_data(button_id=bid); await state.set_state(Flow.button_order)
    await call.message.answer("Введите новое место в меню (число, начиная с 1):", reply_markup=cancel_kb()); await call.answer()

@dp.message(Flow.button_order)
@admin_only
async def button_order_save(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit() or int(message.text) < 1:
        await message.answer("Введите целое число от 1."); return
    data = await state.get_data(); bid = data["button_id"]; pos = int(message.text)-1
    execute("UPDATE menu_buttons SET position=? WHERE id=?", (pos,bid))
    rows = q_all("SELECT id FROM menu_buttons ORDER BY position,id")
    for i,r in enumerate(rows): execute("UPDATE menu_buttons SET position=? WHERE id=?", (i,r["id"]))
    await state.clear(); await message.answer("Порядок обновлён ✅", reply_markup=buttons_menu())

@dp.callback_query(F.data.startswith("btn:emojilist:"))
@admin_only
async def button_emoji_select(call: CallbackQuery, state: FSMContext):
    bid = int(call.data.split(":")[2]); await state.update_data(button_id=bid); await state.set_state(Flow.emoji_id)
    await call.message.answer("Введите custom_emoji_id или '-' чтобы убрать Premium Emoji:", reply_markup=cancel_kb()); await call.answer()

@dp.message(Flow.emoji_id)
@admin_only
async def emoji_id_save(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if value != "-" and not re.fullmatch(r"\d{5,25}", value):
        await message.answer("ID должен состоять из 5–25 цифр. Отправьте корректный ID или '-'."); return
    data = await state.get_data()
    if data.get("button_id"):
        execute("UPDATE menu_buttons SET emoji_id=? WHERE id=?", ("" if value=="-" else value, data["button_id"]))
    elif data.get("project_id"):
        execute("UPDATE projects SET emoji_id=? WHERE id=?", ("" if value=="-" else value, data["project_id"]))
    await state.clear(); await message.answer("Premium Emoji ID сохранён ✅", reply_markup=buttons_menu())

# Messages editor
@dp.callback_query(F.data == "msg:create")
@admin_only
async def message_create(call: CallbackQuery, state: FSMContext):
    await state.clear(); await state.set_state(Flow.message_key)
    await call.message.answer("Введите уникальный ключ латиницей (например, support):", reply_markup=cancel_kb()); await call.answer()

@dp.message(Flow.message_key)
@admin_only
async def message_key(message: Message, state: FSMContext):
    key = (message.text or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{2,40}", key):
        await message.answer("Используйте 2–40 символов: a-z, 0-9, _ или -."); return
    if get_message(key): await message.answer("Такой ключ уже существует."); return
    await state.update_data(message_key=key); await state.set_state(Flow.message_title)
    await message.answer("Введите название сообщения:", reply_markup=cancel_kb())

@dp.message(Flow.message_title)
@admin_only
async def message_title(message: Message, state: FSMContext):
    title=(message.text or "").strip()
    if not title: await message.answer("Название не может быть пустым."); return
    await state.update_data(message_title=title); await state.set_state(Flow.message_body)
    await message.answer("Отправьте текст сообщения. Поддерживается HTML Telegram; не отправляйте пустой текст.", reply_markup=cancel_kb())

@dp.callback_query(F.data.startswith("msg:edit:"))
@admin_only
async def message_edit_start(call: CallbackQuery, state: FSMContext):
    key=call.data.split(":",2)[2]; r=get_message(key)
    if not r: await call.answer("Сообщение не найдено.", show_alert=True); return
    await state.clear(); await state.update_data(message_key=key, message_title=r["title"])
    await state.set_state(Flow.message_body)
    await call.message.answer(f"Текущее сообщение «{r['title']}»:\n\n{r['body']}\n\nОтправьте новый текст (HTML поддерживается).", reply_markup=cancel_kb())
    await call.answer()

@dp.message(Flow.message_body)
@admin_only
async def message_body_save(message: Message, state: FSMContext, bot: Bot):
    body = message.text or message.caption
    if not body or not body.strip():
        await message.answer("Сообщение не должно быть пустым."); return
    data=await state.get_data()
    # Validate HTML before persisting, so a typo doesn't break the live menu.
    try:
        validation_message = await bot.send_message(chat_id=message.chat.id, text=body, disable_notification=True)
        # Remove only the temporary validation message; preserve the submitted text.
        try:
            await validation_message.delete()
        except TelegramBadRequest:
            pass
    except TelegramBadRequest as e:
        await message.answer(f"Telegram не принял HTML-разметку: {e}\nИсправьте текст и отправьте ещё раз."); return
    key=data.get("message_key")
    if not key:
        await message.answer("Ошибка состояния. Начните создание сообщения заново."); await state.clear(); return
    set_message(key, data.get("message_title", key), body)
    await state.clear(); await message.answer("Сообщение сохранено ✅", reply_markup=admin_home_kb())

@dp.callback_query(F.data.startswith("msg:view:"))
@admin_only
async def message_view(call: CallbackQuery):
    key=call.data.split(":",2)[2]; r=get_message(key)
    if not r: await call.answer("Сообщение не найдено.", show_alert=True); return
    await safe_edit(call, f"<b>{r['title']}</b> (<code>{key}</code>)\n\n{r['body']}", inline([
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"msg:edit:{key}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:messages")]])); await call.answer()

@dp.callback_query(F.data.startswith("msg:delask:"))
@admin_only
async def message_delete_ask(call: CallbackQuery):
    key=call.data.split(":",2)[2]
    await safe_edit(call, f"Удалить сообщение «{key}»? Кнопки, ссылающиеся на него, останутся, но покажут резервный текст.", inline([
        [InlineKeyboardButton(text="✅ Удалить", callback_data=f"msg:delete:{key}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:messages")]])); await call.answer()

@dp.callback_query(F.data.startswith("msg:delete:"))
@admin_only
async def message_delete(call: CallbackQuery):
    key=call.data.split(":",2)[2]
    if key in ("welcome","development","advertising","submit_intro"):
        await call.answer("Это системное сообщение нельзя удалить; его можно изменить.", show_alert=True); return
    execute("DELETE FROM messages WHERE key=?", (key,))
    await safe_edit(call, "Сообщение удалено ✅", inline([[InlineKeyboardButton(text="⬅️ К сообщениям", callback_data="adm:messages")]]))
    await call.answer()

# Project management
@dp.callback_query(F.data == "proj:create")
@admin_only
async def project_create(call: CallbackQuery, state: FSMContext):
    await state.clear(); await state.update_data(is_free=0); await state.set_state(Flow.project_title)
    await call.message.answer("Название проекта:", reply_markup=cancel_kb()); await call.answer()

@dp.message(Flow.project_title)
@admin_only
async def project_title(message: Message, state: FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("Название не может быть пустым."); return
    await state.update_data(title=v); await state.set_state(Flow.project_description)
    await message.answer("Описание проекта:", reply_markup=cancel_kb())

@dp.message(Flow.project_description)
@admin_only
async def project_description(message: Message, state: FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("Описание не может быть пустым."); return
    await state.update_data(description=v); await state.set_state(Flow.project_price)
    await message.answer("Цена в рублях (например 1500 или 499.90):", reply_markup=cancel_kb())

@dp.message(Flow.project_price)
@admin_only
async def project_price(message: Message, state: FSMContext):
    try: v=float((message.text or "").replace(",", ".").strip())
    except ValueError: await message.answer("Цена должна быть числом."); return
    if v < 0 or v > 100000000: await message.answer("Цена должна быть от 0 до 100 000 000."); return
    await state.update_data(price=v); await state.set_state(Flow.project_url)
    await message.answer("Ссылка на покупку (http:// или https://):", reply_markup=cancel_kb())

@dp.message(Flow.project_url)
@admin_only
async def project_url(message: Message, state: FSMContext):
    v=(message.text or "").strip()
    if not valid_url(v): await message.answer("Некорректная ссылка. Нужен http:// или https://"); return
    await state.update_data(url=v); await state.set_state(Flow.project_emoji)
    await message.answer("Emoji проекта (например 🎮) или '-':", reply_markup=cancel_kb())

@dp.message(Flow.project_emoji)
@admin_only
async def project_emoji(message: Message, state: FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("Введите emoji или '-'."); return
    await state.update_data(emoji="" if v=="-" else v)
    data=await state.get_data()
    pos=(q_one("SELECT COALESCE(MAX(position),-1)+1 AS n FROM projects WHERE is_free=0") or {}).get("n",0)
    execute("INSERT INTO projects(title,description,price,url,emoji,position,is_free) VALUES(?,?,?,?,?,?,0)",
            (data["title"],data["description"],data["price"],data["url"],data["emoji"] or "📦",pos))
    await state.clear(); await message.answer("Проект добавлен ✅", reply_markup=inline([
        [InlineKeyboardButton(text="📦 Управление проектами", callback_data="adm:projects")],
        [InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="adm:home")]]))

@dp.callback_query(F.data.in_({"proj:list","proj:editlist","proj:dellist"}))
@admin_only
async def project_lists(call: CallbackQuery, state: FSMContext):
    mode=call.data.split(":")[1]; rows=q_all("SELECT id,title FROM projects WHERE is_free=0 ORDER BY position,id")
    kb=[[InlineKeyboardButton(text=f"{r['id']} — {r['title']}"[:60], callback_data=f"proj:{mode}:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:projects")])
    await safe_edit(call, "Проекты не добавлены." if not rows else "Выберите проект:", inline(kb)); await call.answer()

@dp.callback_query(F.data.startswith("proj:list:"))
@admin_only
async def project_list_view(call: CallbackQuery):
    pid=int(call.data.split(":")[2]); p=q_one("SELECT * FROM projects WHERE id=? AND is_free=0",(pid,))
    if not p: await call.answer("Проект не найден.",show_alert=True); return
    await safe_edit(call, f"ID {pid}: <b>{p['title']}</b>\nЦена: {p['price']:g} ₽\nСсылка: {p['url']}\nОписание: {p['description']}", inline([
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:projects")]])); await call.answer()

@dp.callback_query(F.data.startswith("proj:dellist:"))
@admin_only
async def project_delete_ask(call: CallbackQuery):
    pid=int(call.data.split(":")[2]); p=q_one("SELECT title FROM projects WHERE id=? AND is_free=0",(pid,))
    if not p: await call.answer("Проект не найден.",show_alert=True); return
    await safe_edit(call, f"Удалить проект «{p['title']}»?", inline([
        [InlineKeyboardButton(text="✅ Удалить", callback_data=f"proj:delete:{pid}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:projects")]])); await call.answer()

@dp.callback_query(F.data.startswith("proj:delete:"))
@admin_only
async def project_delete(call: CallbackQuery):
    execute("DELETE FROM projects WHERE id=? AND is_free=0",(int(call.data.split(":")[2]),))
    await safe_edit(call,"Проект удалён ✅",inline([[InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:projects")]])); await call.answer()

@dp.callback_query(F.data.startswith("proj:editlist:"))
@admin_only
async def project_edit_select(call: CallbackQuery, state: FSMContext):
    pid=int(call.data.split(":")[2]); p=q_one("SELECT * FROM projects WHERE id=? AND is_free=0",(pid,))
    if not p: await call.answer("Проект не найден.",show_alert=True); return
    await state.update_data(project_id=pid)
    await safe_edit(call, f"Редактирование проекта: {p['title']}", inline([
        [InlineKeyboardButton(text="Название",callback_data="proj:field:title"),
         InlineKeyboardButton(text="Описание",callback_data="proj:field:description")],
        [InlineKeyboardButton(text="Цена",callback_data="proj:field:price"),
         InlineKeyboardButton(text="Ссылка",callback_data="proj:field:url")],
        [InlineKeyboardButton(text="Emoji",callback_data="proj:field:emoji"),
         InlineKeyboardButton(text="Premium Emoji ID",callback_data="proj:field:emoji_id")],
        [InlineKeyboardButton(text="Порядок",callback_data="proj:field:position")],
        [InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:projects")]])); await call.answer()

@dp.callback_query(F.data.startswith("proj:field:"))
@admin_only
async def project_field(call: CallbackQuery, state: FSMContext):
    field=call.data.split(":")[2]; await state.update_data(project_field=field); await state.set_state(Flow.project_field_value)
    await call.message.answer("Введите новое значение:",reply_markup=cancel_kb()); await call.answer()

@dp.message(Flow.project_field_value)
@admin_only
async def project_field_save(message: Message, state: FSMContext):
    data=await state.get_data(); field=data["project_field"]; value=(message.text or "").strip(); pid=data["project_id"]
    if not value: await message.answer("Значение не может быть пустым."); return
    allowed={"title":"title","description":"description","url":"url","emoji":"emoji","emoji_id":"emoji_id","position":"position","price":"price"}
    if field not in allowed: await message.answer("Неизвестное поле."); return
    if field=="url" and not valid_url(value): await message.answer("Некорректная ссылка."); return
    if field=="price":
        try: value=float(value.replace(",","."))
        except ValueError: await message.answer("Цена должна быть числом."); return
        if value<0: await message.answer("Цена не может быть отрицательной."); return
    if field=="position":
        if not value.isdigit() or int(value)<1: await message.answer("Порядок — целое число от 1."); return
        value=int(value)-1
    if field=="emoji_id" and value!="-" and not re.fullmatch(r"\d{5,25}",value):
        await message.answer("ID должен состоять из 5–25 цифр."); return
    if field=="emoji_id" and value=="": value=""
    if field=="emoji_id" and value=="-": value=""
    execute(f"UPDATE projects SET {allowed[field]}=? WHERE id=?",(value,pid))
    await state.clear(); await message.answer("Проект обновлён ✅",reply_markup=inline([
        [InlineKeyboardButton(text="📦 Управление проектами",callback_data="adm:projects")],
        [InlineKeyboardButton(text="⚙️ Админ-панель",callback_data="adm:home")]]))

# Free project flow and CRUD
@dp.callback_query(F.data == "free:create")
@admin_only
async def free_create(call: CallbackQuery,state: FSMContext):
    await state.clear(); await state.set_state(Flow.free_title)
    await call.message.answer("Название бесплатного проекта:",reply_markup=cancel_kb()); await call.answer()

@dp.message(Flow.free_title)
@admin_only
async def free_title(message: Message,state: FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("Название не может быть пустым."); return
    await state.update_data(title=v); await state.set_state(Flow.free_description)
    await message.answer("Описание:",reply_markup=cancel_kb())

@dp.message(Flow.free_description)
@admin_only
async def free_description(message: Message,state: FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("Описание не может быть пустым."); return
    await state.update_data(description=v); await state.set_state(Flow.free_url)
    await message.answer("Ссылка на скачивание (https://...):",reply_markup=cancel_kb())

@dp.message(Flow.free_url)
@admin_only
async def free_url(message: Message,state: FSMContext):
    v=(message.text or "").strip()
    if not valid_url(v): await message.answer("Некорректная ссылка."); return
    await state.update_data(url=v); await state.set_state(Flow.free_emoji)
    await message.answer("Emoji (или '-'): ",reply_markup=cancel_kb())

@dp.message(Flow.free_emoji)
@admin_only
async def free_emoji(message: Message,state: FSMContext):
    v=(message.text or "").strip()
    data=await state.get_data()
    pos=(q_one("SELECT COALESCE(MAX(position),-1)+1 AS n FROM projects WHERE is_free=1") or {}).get("n",0)
    execute("INSERT INTO projects(title,description,price,url,emoji,position,is_free) VALUES(?,?,?,?,?,?,1)",
            (data["title"],data["description"],0,data["url"],"📦" if v=="-" or not v else v,pos))
    await state.clear(); await message.answer("Бесплатный проект добавлен ✅",reply_markup=inline([
        [InlineKeyboardButton(text="🆓 Бесплатные проекты",callback_data="adm:free")],
        [InlineKeyboardButton(text="⚙️ Админ-панель",callback_data="adm:home")]]))

@dp.callback_query(F.data.in_({"free:list","free:editlist","free:dellist"}))
@admin_only
async def free_lists(call: CallbackQuery,state: FSMContext):
    mode=call.data.split(":")[1]; rows=q_all("SELECT id,title FROM projects WHERE is_free=1 ORDER BY position,id")
    kb=[[InlineKeyboardButton(text=f"{r['id']} — {r['title']}"[:60],callback_data=f"free:{mode}:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:free")])
    await safe_edit(call,"Бесплатных проектов нет." if not rows else "Выберите проект:",inline(kb)); await call.answer()

@dp.callback_query(F.data.startswith("free:list:"))
@admin_only
async def free_list_view(call: CallbackQuery):
    pid=int(call.data.split(":")[2]); p=q_one("SELECT * FROM projects WHERE id=? AND is_free=1",(pid,))
    if not p: await call.answer("Проект не найден.",show_alert=True); return
    await safe_edit(call,f"ID {pid}: <b>{p['title']}</b>\n{p['description']}\n{p['url']}",inline([[InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:free")]])); await call.answer()

@dp.callback_query(F.data.startswith("free:dellist:"))
@admin_only
async def free_delete_ask(call: CallbackQuery):
    pid=int(call.data.split(":")[2]); p=q_one("SELECT title FROM projects WHERE id=? AND is_free=1",(pid,))
    if not p: await call.answer("Проект не найден.",show_alert=True); return
    await safe_edit(call,f"Удалить «{p['title']}»?",inline([
        [InlineKeyboardButton(text="✅ Удалить",callback_data=f"free:delete:{pid}")],
        [InlineKeyboardButton(text="❌ Отмена",callback_data="adm:free")]])); await call.answer()

@dp.callback_query(F.data.startswith("free:delete:"))
@admin_only
async def free_delete(call: CallbackQuery):
    execute("DELETE FROM projects WHERE id=? AND is_free=1",(int(call.data.split(":")[2]),))
    await safe_edit(call,"Бесплатный проект удалён ✅",inline([[InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:free")]])); await call.answer()

@dp.callback_query(F.data.startswith("free:editlist:"))
@admin_only
async def free_edit_select(call: CallbackQuery,state: FSMContext):
    pid=int(call.data.split(":")[2]); p=q_one("SELECT * FROM projects WHERE id=? AND is_free=1",(pid,))
    if not p: await call.answer("Проект не найден.",show_alert=True); return
    await state.update_data(project_id=pid)
    await safe_edit(call,f"Редактирование бесплатного проекта: {p['title']}",inline([
        [InlineKeyboardButton(text="Название",callback_data="free:field:title"),
         InlineKeyboardButton(text="Описание",callback_data="free:field:description")],
        [InlineKeyboardButton(text="Ссылка",callback_data="free:field:url"),
         InlineKeyboardButton(text="Emoji",callback_data="free:field:emoji")],
        [InlineKeyboardButton(text="Premium Emoji ID",callback_data="free:field:emoji_id")],
        [InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:free")]])); await call.answer()

@dp.callback_query(F.data.startswith("free:field:"))
@admin_only
async def free_field(call: CallbackQuery,state: FSMContext):
    field=call.data.split(":")[2]; await state.update_data(project_field=field, project_is_free=True); await state.set_state(Flow.project_field_value)
    await call.message.answer("Введите новое значение:",reply_markup=cancel_kb()); await call.answer()

# Emoji ID extraction
@dp.callback_query(F.data == "emoji:get")
@admin_only
async def emoji_get_start(call: CallbackQuery,state: FSMContext):
    await state.clear(); await state.set_state(Flow.emoji_target)
    await call.message.answer("Теперь отправьте сообщение, содержащее Premium Emoji. Я прочитаю custom_emoji_id из entities.",reply_markup=cancel_kb()); await call.answer()

@dp.message(Command("getemoji"))
@admin_only
async def emoji_command(message: Message,state: FSMContext):
    await state.set_state(Flow.emoji_target)
    await message.answer("Отправьте сообщение с Premium Emoji. Я попробую прочитать custom_emoji_id из entities.",reply_markup=cancel_kb())

@dp.message(Flow.emoji_target)
@admin_only
async def emoji_extract(message: Message,state: FSMContext):
    entities=(message.entities or [])+(message.caption_entities or [])
    ids=[e.custom_emoji_id for e in entities if e.type=="custom_emoji" and e.custom_emoji_id]
    if ids:
        await message.answer("⭐ <b>Premium Emoji</b>\n\nID:\n<code>"+ids[0]+"</code>\n\nСкопируйте ID и вставьте его в редактор кнопки/проекта.",reply_markup=admin_home_kb())
    else:
        await message.answer("В этом сообщении Telegram не передал entity типа custom_emoji. Попробуйте отправить именно Premium Emoji как текстовое сообщение, а не стикер/изображение. Если ID всё равно не приходит, используйте совместимый бот для определения ID и вставьте его вручную.",reply_markup=cancel_kb())
    await state.clear()

@dp.callback_query(F.data == "emoji:list")
@admin_only
async def emoji_list(call: CallbackQuery):
    rows=q_all("SELECT id,title,emoji_id FROM menu_buttons WHERE emoji_id<>''")
    projs=q_all("SELECT id,title,emoji_id FROM projects WHERE emoji_id<>''")
    lines=["<b>Текущие Premium Emoji ID</b>"]
    lines += [f"Кнопка #{r['id']} {r['title']}: <code>{r['emoji_id']}</code>" for r in rows]
    lines += [f"Проект #{r['id']} {r['title']}: <code>{r['emoji_id']}</code>" for r in projs]
    lines += [f"Сообщение {r['key']}: <code>{r['emoji_id']}</code>" for r in q_all("SELECT key,emoji_id FROM messages WHERE emoji_id<>''")]
    await safe_edit(call,"\n".join(lines) if len(lines)>1 else "Premium Emoji ID пока не назначены.",inline([[InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:emoji")]]))
    await call.answer()

@dp.callback_query(F.data == "settings:stats")
@admin_only
async def stats(call: CallbackQuery):
    text=(f"Кнопок: {q_one('SELECT COUNT(*) n FROM menu_buttons')['n']}\n"
          f"Платных проектов: {q_one('SELECT COUNT(*) n FROM projects WHERE is_free=0')['n']}\n"
          f"Бесплатных проектов: {q_one('SELECT COUNT(*) n FROM projects WHERE is_free=1')['n']}\n"
          f"Заявок: {q_one('SELECT COUNT(*) n FROM submissions')['n']}")
    await safe_edit(call,text,inline([[InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:settings")]])); await call.answer()

@dp.callback_query(F.data.startswith("sub:view:"))
@admin_only
async def submission_view(call: CallbackQuery):
    sid=int(call.data.split(":")[2]); s=q_one("SELECT * FROM submissions WHERE id=?",(sid,))
    if not s: await call.answer("Заявка не найдена.",show_alert=True); return
    text=f"<b>Заявка #{s['id']}</b>\nПользователь: {s['full_name']} (@{s['username'] or 'нет'})\nID: <code>{s['user_id']}</code>\nТип: {s['kind']}\nДата: {s['created_at']}\nСтатус: {s['status']}\n\n{s['text'] or '(без текста)'}"
    await safe_edit(call,text,inline([
        [InlineKeyboardButton(text="✅ Принять",callback_data=f"sub:status:{sid}:accepted"),
         InlineKeyboardButton(text="❌ Отклонить",callback_data=f"sub:status:{sid}:rejected")],
        [InlineKeyboardButton(text="⬅️ Назад",callback_data="adm:submissions")]])); await call.answer()

@dp.callback_query(F.data.startswith("sub:status:"))
@admin_only
async def submission_status(call: CallbackQuery):
    _,_,sid,status=call.data.split(":"); execute("UPDATE submissions SET status=? WHERE id=?",(status,int(sid)))
    await safe_edit(call,f"Статус заявки #{sid}: {status}",inline([[InlineKeyboardButton(text="⬅️ К заявкам",callback_data="adm:submissions")]])); await call.answer("Сохранено")

# User submissions: accepts text, photo, documents, archives, links and forwards metadata.
@dp.message(Flow.settings_value)
async def submission_receive(message: Message,state: FSMContext,bot: Bot):
    data=await state.get_data()
    if data.get("flow")!="submission": return
    user=message.from_user
    text=message.text or message.caption or ""
    kind="text"
    file_id=""
    if message.photo:
        kind="photo"; file_id=message.photo[-1].file_id
    elif message.document:
        kind="document/archive"; file_id=message.document.file_id
    elif message.video:
        kind="video"; file_id=message.video.file_id
    elif message.animation:
        kind="animation"; file_id=message.animation.file_id
    elif message.text and re.search(r"https?://\S+",message.text):
        kind="link"
    sid=execute("INSERT INTO submissions(user_id,username,full_name,kind,text,file_id) VALUES(?,?,?,?,?,?)",
        (user.id,user.username or "",user.full_name,kind,text,file_id))
    admin_text=(f"💾 <b>Новая заявка #{sid}</b>\n"
        f"Пользователь: {user.full_name} (@{user.username or 'нет'})\n"
        f"ID: <code>{user.id}</code>\nТип: {kind}\n\n"
        f"{text or '(текст не приложен)'}")
    try:
        await bot.send_message(ADMIN_ID,admin_text)
        if message.photo: await bot.send_photo(ADMIN_ID,file_id,caption=f"Заявка #{sid}")
        elif message.document: await bot.send_document(ADMIN_ID,file_id,caption=f"Заявка #{sid}")
        elif message.video: await bot.send_video(ADMIN_ID,file_id,caption=f"Заявка #{sid}")
        elif message.animation: await bot.send_animation(ADMIN_ID,file_id,caption=f"Заявка #{sid}")
    except (TelegramForbiddenError,TelegramBadRequest) as e:
        log.warning("Could not deliver submission %s to admin: %s",sid,e)
    await state.clear()
    await message.answer("Спасибо! Заявка сохранена и отправлена администратору ✅",reply_markup=main_menu_markup())

# Admin-only custom emoji assignment for message entries.
@dp.callback_query(F.data.startswith("msg:emoji:"))
@admin_only
async def message_emoji_start(call: CallbackQuery,state: FSMContext):
    key=call.data.split(":",2)[2]; await state.update_data(message_key=key); await state.set_state(Flow.emoji_id)
    await call.message.answer("Введите custom_emoji_id или '-' чтобы убрать ID:",reply_markup=cancel_kb()); await call.answer()

async def main():
    if not BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Установите переменную окружения BOT_TOKEN с токеном от @BotFather.")
    init_db()
    bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt,SystemExit):
        pass
