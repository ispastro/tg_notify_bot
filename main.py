import asyncio
import asyncpg
import logging 


from aiogram import Bot, Dispatcher, types 
from aiogram.filters import CommandObject
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup , KeyboardButton
from dotenv import load_dotenv
import os
from datetime import datetime


#load Enoviroment varaibales 


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv('SUPER_ADMIN_ID'))

DATABASE_URL = os.getenv("DATABASE_URL")



bot = Bot(token= BOT_TOKEN , parse_mode = ParseMode.HTML)
dp = Dispatcher()




