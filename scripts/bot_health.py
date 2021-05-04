from dotenv import load_dotenv
import os
from os.path import join, dirname
import importlib
tel = importlib.util.find_spec("telegram")
use_telegram = tel is not None

if use_telegram is False:
    print("could not find telegram library")

dotenv_path = join(dirname(dirname(__file__)), '.env')
load_dotenv(dotenv_path)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if BOT_TOKEN is None or CHAT_ID is None:
    use_telegram = False
    print("env variables not available")

if use_telegram:
    import telegram
    bot = telegram.Bot(token=BOT_TOKEN)

def telegram_send_initialise():
    if use_telegram:
        print("init telegram")
        bot.send_message(chat_id=CHAT_ID, text="Apex Bot is NOW ONLINE")

def telegram_send_update_health(**data):
    if use_telegram:
        print("send telegram update")
        bot.send_message(chat_id=CHAT_ID, text="-Health Status-")
        bot.send_message(chat_id=CHAT_ID, text="Current outstanding orders: %s"%data['numOrders'])
