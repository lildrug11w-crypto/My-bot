import json
import time
import urllib.request
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# Конфигурация всех трех моделей и ключей
BOT_CONFIGS = {
    1: {
        "name": "🔮 Gemma 4 (Основная)",
        "model": "google/gemma-4-31b-it:free",
        "key": (
            "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"
        ),
    },
    2: {
        "name": "🚀 Laguna S 2.1(запасная)",
        "model": "poolside/laguna-s-2.1:free",
        "key": (
            "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"
        ),
    },
    3: {
        "name": "🌟 Nvidia Nemotron(если не работают остальные)",
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "key": (
            "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"
        ),
    },
}

TELEGRAM_BOT_TOKEN = "8971663696:AAFbn6WOIgXcg9qfF74mpU8G8nxYLwnlDso"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Словарь для хранения выбранной модели пользователем (ключ: chat_id, значение: ID конфигурации)
user_selected_model = {}


# Обработчик команды /start
@bot.message_handler(commands=["start"])
def send_welcome(message):
  chat_id = message.chat.id
  if chat_id not in user_selected_model:
    user_selected_model[chat_id] = 1

  current_model_name = BOT_CONFIGS[user_selected_model[chat_id]]["name"]

  welcome_text = (
      "Привет! Я бот на основе ИИ "
      '<tg-emoji emoji-id="4956591756519932897">✨</tg-emoji>\n'
      "Мой создатель: @flashgram_kryt "
      '<tg-emoji emoji-id="4956214413578207998">🔥</tg-emoji>\n\n'
      f"<b>Текущая модель:</b> {current_model_name}\n\n"
      "Выберите модель кнопками ниже или просто спросите меня о чем-нибудь! "
      '<tg-emoji emoji-id="4956492465465984073">🤖</tg-emoji>'
  )

  # Создаем инлайн-клавиатуру для выбора моделей
  keyboard = InlineKeyboardMarkup()
  for config_id, conf in BOT_CONFIGS.items():
    keyboard.add(
        InlineKeyboardButton(conf["name"], callback_data=f"set_model_{config_id}")
    )

  bot.send_message(
      chat_id, welcome_text, parse_mode="HTML", reply_markup=keyboard
  )


# Обработчик нажатий на инлайн-кнопки (переключение моделей)
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_model_"))
def handle_model_selection(call):
  chat_id = call.message.chat.id
  config_id = int(call.data.split("_")[2])

  if config_id in BOT_CONFIGS:
    user_selected_model[chat_id] = config_id
    model_name = BOT_CONFIGS[config_id]["name"]

    bot.answer_callback_query(call.id, f"Выбрана: {model_name}")

    new_text = (
        "Привет! Я бот на основе ИИ "
        '<tg-emoji emoji-id="4956591756519932897">✨</tg-emoji>\n'
        "Мой создатель: @flashgram_kryt "
        '<tg-emoji emoji-id="4956214413578207998">🔥</tg-emoji>\n\n'
        f"<b>Текущая модель:</b> {model_name}\n\n"
        "Можете задать мне вопрос! "
        '<tg-emoji emoji-id="4956492465465984073">🤖</tg-emoji>'
    )

    keyboard = InlineKeyboardMarkup()
    for conf_id, conf in BOT_CONFIGS.items():
      keyboard.add(
          InlineKeyboardButton(
              conf["name"], callback_data=f"set_model_{conf_id}"
          )
      )

    bot.edit_message_text(
        new_text,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# Обработчик обычных текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
  chat_id = message.chat.id

  config_id = user_selected_model.get(chat_id, 1)
  current_config = BOT_CONFIGS[config_id]

  url = "https://openrouter.ai/api/v1/chat/completions"
  payload = {
      "model": current_config["model"],
      "messages": [{"role": "user", "content": message.text}],
  }
  data = json.dumps(payload).encode("utf-8")

  for attempt in range(3):
    try:
      req = urllib.request.Request(
          url,
          data=data,
          headers={
              "Authorization": f"Bearer {current_config['key']}",
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
          bot.reply_to(message, ai_reply)
          return
        else:
          bot.reply_to(message, "Не удалось получить ответ от модели.")
          return

    except urllib.error.HTTPError as e:
      if e.code == 429 and attempt < 2:
        time.sleep(3)
        continue
      elif e.code == 429:
        bot.reply_to(
            message,
            "⚠️ Превышен лимит запросов выбранной модели. Попробуйте переключить"
            " модель кнопкой или подождите минуту.",
        )
        return
      else:
        bot.reply_to(
            message,
            f"Ошибка HTTP {e.code} ({current_config['name']}): {e.reason}",
        )
        return
    except Exception as e:
      bot.reply_to(message, f"Произошла ошибка: {str(e)}")
      return


if __name__ == "__main__":
  print("Бот успешно запущен!")
  bot.infinity_polling()
