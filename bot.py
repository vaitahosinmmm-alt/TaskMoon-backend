import os
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN পাওয়া যায়নি")

bot = telebot.TeleBot(TOKEN)

APP_URL = "https://task-moon.vercel.app/"


@bot.message_handler(commands=["start"])
def start(message):

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🌙 Open TaskMoon App",
            web_app=types.WebAppInfo(url=APP_URL)
        )
    )

    bot.send_message(
        message.chat.id,
        "🌙 Welcome to TaskMoon!\n\n"
        "TaskMoon App-এ প্রবেশ করতে নিচের button-এ চাপুন। ❤️",
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: True)
def other_messages(message):

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🌙 Open TaskMoon App",
            web_app=types.WebAppInfo(url=APP_URL)
        )
    )

    bot.send_message(
        message.chat.id,
        "🌙 TaskMoon App ব্যবহার করতে নিচের button-এ চাপুন।",
        reply_markup=markup
    )


print("🌙 TaskMoon App Bot Started...")

if __name__ == "__main__":
    bot.infinity_polling()
