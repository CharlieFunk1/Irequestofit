import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./requisitions.db")
DEFAULT_CRAFTER_ROLE_ID = os.getenv("DEFAULT_CRAFTER_ROLE_ID")
