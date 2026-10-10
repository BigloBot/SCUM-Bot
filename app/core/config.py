import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")