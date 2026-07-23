import json
import time
import urllib.request
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# Ваши ключи OpenRouter (распределяем модели по ключам)
API_KEYS = {
    1: "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",
    2: "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",
    3: "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",
}

# Список всех доступных моделей (пополняемый) с привязкой к ключам
MODELS_CONFIG = {
    "model_1": {
        "name": "🔮 Gemma 4",
        "model": "google/gemma-4-31b-it:free",
        "key_id": 1,
    },
    "model_2": {
        "name": "🚀 Laguna S 2.1",
        "model": "poolside/laguna-s-2.1:free",
        "key_id": 2,
    },
    "model_3": {
        "name": "🌟 Nvidia Nemotron",
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "key_id": 3,
    },
    "model_4": {
        "name": "⚡ Nemotron 3 Nano",
        "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        "key_id": 1,
    },
    "model_5": {
        "name": "🌊 Laguna XS 2.1",
        "model": "poolside/laguna-xs-2.1:free",
        "key_id": 2,
    },
    "model_6": {
        "name": "🤖 GPT OSS 20B",
        "model": "openai/gpt-oss-20b:free",
        "key_id": 3,
    },
}

TELEGRAM_BOT_TOKEN = "8608679731:AAEMzBjQP_t1RBolGRZh7q8JaLRyM1ZjYxw"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Базы данных в памяти
user_selected_model = {}  # chat_id -> ключ модели в MODELS_CONFIG
user_coins = {}  # chat_id -> количество монет
user_last_bonus = {}  # chat_id -> таймстамп последней ежедневной награды


def get_main_keyboard():
  keyboard = InlineKeyboardMarkup(row_width=2)
  keyboard.add(
      InlineKeyboardButton("🤖 Выбрать модель", callback_data="menu_models"),
      InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
  )
  keyboard.add(
      InlineKeyboardButton("💰 Монеты и Награда", callback_data="menu_coins"),
      InlineKeyboardButton("🎁 Рефералы", callback_data="menu_refs"),
  )
  return keyboard


# Обработчик команды /start
@bot.message_handler(commands=["start"])
def send_welcome(message):
  chat_id = message.chat.id

  # Инициализация пользователя
  if chat_id not in user_selected_model:
    user_selected_model[chat_id] = "model_1"
  if chat_id not in user_coins:
    user_coins[chat_id] = 5  # Сразу даем 5 стартовых монет

  current_model = MODELS_CONFIG[user_selected_model[chat_id]]["name"]

  welcome_text = (
      "Привет! Я многофункциональный бот на базе ИИ "
      '<tg-emoji emoji-id="4956591756519932897">✨</tg-emoji>\n'
      "Мой создатель: @flashgram_kryt "
      '<tg-emoji emoji-id="4956214413578207998">🔥</tg-emoji>\n\n'
      f"<b>Текущая модель:</b> {current_model}\n"
      f"<b>Ваш баланс:</b> {user_coins[chat_id]} 🪙 (1 запрос = 1 монета)\n\n"
      "Выберите нужный раздел в меню ниже:"
  )

  bot.send_message(
      chat_id, welcome_text, parse_mode="HTML", reply_markup=get_main_keyboard()
  )


# Обработчик всех инлайн-кнопок меню
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
  chat_id = call.message.chat.id
  data = call.data

  if chat_id not in user_coins:
    user_coins[chat_id] = 5
  if chat_id not in user_selected_model:
    user_selected_model[chat_id] = "model_1"

  # Главное меню: Выбор моделей
  if data == "menu_models":
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for m_key, m_info in MODELS_CONFIG.items():
      prefix = "✅ " if user_selected_model.get(chat_id) == m_key else ""
      buttons.append(
          InlineKeyboardButton(
              f"{prefix}{m_info['name']}", callback_data=f"select_{m_key}"
          )
      )

    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_home"))

    bot.edit_message_text(
        "📋 **Все доступные модели в данный момент:**\n*(Список пополняется)*\n\nВыберите модель:",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

  # Обработка выбора конкретной модели
  elif data.startswith("select_"):
    m_key = data.split("_", 1)[1]
    if m_key in MODELS_CONFIG:
      user_selected_model[chat_id] = m_key
      model_name = MODELS_CONFIG[m_key]["name"]
      bot.answer_callback_query(call.id, f"Успешно выбрана: {model_name}")

      current_model = model_name
      welcome_text = (
          "Привет! Я многофункциональный бот на базе ИИ "
          '<tg-emoji emoji-id="4956591756519932897">✨</tg-emoji>\n'
          "Мой создатель: @flashgram_kryt "
          '<tg-emoji emoji-id="4956214413578207998">🔥</tg-emoji>\n\n'
          f"<b>Текущая модель:</b> {current_model}\n"
          f"<b>Ваш баланс:</b> {user_coins[chat_id]} 🪙 (1 запрос = 1 монета)\n\n"
          "Выберите нужный раздел в меню ниже:"
      )
      bot.edit_message_text(
          welcome_text,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=get_main_keyboard(),
      )

  # Раздел: Профиль
  elif data == "menu_profile":
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_home"))

    profile_text = (
        "👤 **Ваш профиль:**\n\n"
        f"🆔 **Telegram ID:** `{chat_id}`\n"
        f"🤖 **Активная модель:** {MODELS_CONFIG[user_selected_model[chat_id]]['name']}\n"
        f"💰 **Баланс монет:** {user_coins[chat_id]} 🪙\n"
        "📈 **Статус:** Пользователь"
    )
    bot.edit_message_text(
        profile_text,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

  # Раздел: Монеты и Ежедневная награда
  elif data == "menu_coins":
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            "🎁 Забрать ежедневную награду (+5 🪙)", callback_data="claim_bonus"
        )
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_home"))

    coins_text = (
        "💰 **Система монет:**\n\n"
        f"Ваш текущий баланс: **{user_coins[chat_id]} 🪙**\n"
        "• Каждый текстовый запрос к ИИ списывает **1 монету**.\n"
        "• Вы можете забирать ежедневный бонус каждые 24 часа!"
    )
    bot.edit_message_text(
        coins_text,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

  # Получение ежедневного бонуса (+5 монет)
  elif data == "claim_bonus":
    now = time.time()
    last_time = user_last_bonus.get(chat_id, 0)

    if now - last_time < 86400:
      remaining = int((86400 - (now - last_time)) / 3600)
      bot.answer_callback_query(
          call.id,
          f"⏳ Награда уже получена! Следующая будет доступна через {remaining} ч.",
          show_alert=True,
      )
    else:
      user_last_bonus[chat_id] = now
      user_coins[chat_id] += 5
      bot.answer_callback_query(
          call.id,
          "🎉 Вы успешно получили ежедневную награду: +5 монет!",
          show_alert=True,
      )

      keyboard = InlineKeyboardMarkup()
      keyboard.add(
          InlineKeyboardButton(
              "🎁 Забрать ежедневную награду (+5 🪙)", callback_data="claim_bonus"
          )
      )
      keyboard.add(
          InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_home")
      )

      coins_text = (
          "💰 **Система монет:**\n\n"
          f"Ваш текущий баланс: **{user_coins[chat_id]} 🪙**\n"
          "• Каждый текстовый запрос к ИИ списывает **1 монету**.\n"
          "• Вы успешно забрали бонус сегодня!"
      )
      bot.edit_message_text(
          coins_text,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="Markdown",
          reply_markup=keyboard,
      )

  # Раздел: Рефералы
  elif data == "menu_refs":
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_home"))

    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start=ref_{chat_id}"

    refs_text = (
        "🎁 **Реферальная система:**\n\n"
        "Приглашайте друзей и получайте бонусы за каждого приглашенного!\n\n"
        f"🔗 Ваша реферальная ссылка:\n`{ref_link}`"
    )
    bot.edit_message_text(
        refs_text,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

  # Кнопка возврата в главное меню
  elif data == "back_home":
    current_model = MODELS_CONFIG[user_selected_model[chat_id]]["name"]
    welcome_text = (
        "Привет! Я многофункциональный бот на базе ИИ "
        '<tg-emoji emoji-id="4956591756519932897">✨</tg-emoji>\n'
        "Мой создатель: @flashgram_kryt "
        '<tg-emoji emoji-id="4956214413578207998">🔥</tg-emoji>\n\n'
        f"<b>Текущая модель:</b> {current_model}\n"
        f"<b>Ваш баланс:</b> {user_coins[chat_id]} 🪙 (1 запрос = 1 монета)\n\n"
        "Выберите нужный раздел в меню ниже:"
    )
    bot.edit_message_text(
        welcome_text,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


# Обработчик обычных текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
  chat_id = message.chat.id

  if chat_id not in user_coins:
    user_coins[chat_id] = 5
  if chat_id not in user_selected_model:
    user_selected_model[chat_id] = "model_1"

  if user_coins[chat_id] < 1:
    bot.reply_to(
        message,
        "⚠️ У вас закончились монеты! Заберите ежедневную награду в меню"
        " /start, чтобы продолжить общение.",
    )
    return

  user_coins[chat_id] -= 1

  model_key = user_selected_model[chat_id]
  current_model_info = MODELS_CONFIG[model_key]
  api_key = API_KEYS[current_model_info["key_id"]]

  url = "https://openrouter.ai/api/v1/chat/completions"
  payload = {
      "model": current_model_info["model"],
      "messages": [{"role": "user", "content": message.text}],
  }
  data = json.dumps(payload).encode("utf-8")

  for attempt in range(3):
    try:
      req = urllib.request.Request(
          url,
          data=data,
          headers={
              "Authorization": f"Bearer {api_key}",
              "Content-Type": "application/json",
              "HTTP-Referer": "https://t.me/",
              "X-Title": "Telegram AI Bot",
          },
          method="POST",
      )

      with urllib.request.urlopen(req) as response:
        response_data = json.loads(response.read().decode("utf-8"))
        if "choices" in response_data and len(response_data["choices"]) > 0:
          ai_reply = response_data["choices"][0]["message"]["content"]
          bot.reply_to(
              message,
              f"{ai_reply}\n\n*(Списана 1 монета 🪙. Остаток: {user_coins[chat_id]})*",
          )
          return
        else:
          bot.reply_to(message, "Не удалось получить ответ от модели.")
          return

    except urllib.error.HTTPError as e:
      if e.code == 429 and attempt < 2:
        time.sleep(3)
        continue
      elif e.code == 429:
        user_coins[chat_id] += 1
        bot.reply_to(
            message,
            "⚠️ Превышен лимит запросов выбранной модели. Монета возвращена на"
            " баланс. Попробуйте другую модель.",
        )
        return
      else:
        user_coins[chat_id] += 1
        bot.reply_to(message, f"Ошибка HTTP {e.code}: {e.reason}")
        return
    except Exception as e:
      user_coins[chat_id] += 1
      bot.reply_to(message, f"Произошла ошибка: {str(e)}")
      return


if __name__ == "__main__":
  print("Бот успешно запущен со всеми функциями!")
  bot.infinity_polling()
