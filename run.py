import os
import threading
from api import app
from bot import bot

def run_bot():
    print("🌙 TaskMoon Bot Started...")
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
