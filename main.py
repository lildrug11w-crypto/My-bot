import json
import urllib.request
import telebot

# Ваши ключи
OPENROUTER_API_KEY = (
    "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"
)
# Вставьте токен вашего бота прямо сюда в кавычках:
TELEGRAM_BOT_TOKEN = "8971663696:AAFkRfmZZGEz2o7O2MpXp1euh5X7jXVkrmI"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  try:
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "google/gemma-4-31b-it:free",
        "messages": [{"role": "user", "content": message.text}],
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
      else:
        bot.reply_to(message, "Не удалось получить ответ от модели.")

  except Exception as e:
    bot.reply_to(message, f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
  print("Бот успешно запущен!")
  bot.infinity_polling()
