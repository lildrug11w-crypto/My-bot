import os
import requests
import telebot

# Ваши ключи
OPENROUTER_API_KEY = (
    "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"
)
TELEGRAM_BOT_TOKEN = os.getenv("8971663696:AAFkRfmZZGEz2o7O2MpXp1euh5X7jXVkrmI")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  try:
    # Запрос к API OpenRouter
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://t.me/",  # Обязательно для OpenRouter
            "X-Title": "Telegram AI Bot",  # Название вашего приложения
        },
        json={
            "model": "google/gemma-4-31b-it:free",
            "messages": [{"role": "user", "content": message.text}],
        },
    )

    data = response.json()

    # Проверяем ответ от OpenRouter
    if "choices" in data and len(data["choices"]) > 0:
      ai_reply = data["choices"][0]["message"]["content"]
      bot.reply_to(message, ai_reply)
    elif "error" in data:
      error_message = data["error"].get("message", "Неизвестная ошибка")
      bot.reply_to(message, f"Ошибка от OpenRouter: {error_message}")
    else:
      bot.reply_to(message, "Не удалось получить ответ от модели.")

  except Exception as e:
    bot.reply_to(message, f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
  print("Бот запущен через OpenRouter...")
  bot.infinity_polling()
