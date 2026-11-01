import os
import requests
import telebot
from openai import OpenAI

# Ambil token Telegram dari Secrets & API config dari screenshot
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE_URL = "https://9r.riihdyt.eu.cc/v1"
API_KEY = "sk-8e673f8a5ecbc3b7-gjs2d2-6970375c"
MODEL_NAME = "GLM-5.3_Uncensored"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(base_url=BASE_URL, api_key=9148476943:AAGzzLXRtSFmxS5qPvPBndBfWssAJm4GvhY)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Kamu adalah asisten AI yang ramah dan membantu."},
                {"role": "user", "content": message.text}
            ]
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

if __name__ == "__main__":
    print("Bot Telegram AI Aktif...")
    bot.infinity_polling()
