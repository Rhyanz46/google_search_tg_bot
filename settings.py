from os import getenv
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API = getenv("TELEGRAM_API")
GOOGLE_CX = getenv("GOOGLE_CX")
GOOGLE_API = getenv("GOOGLE_API")

DB_HOST = getenv("DB_HOST")
DB_PORT = getenv("DB_PORT")
DB_NAME = getenv("DB_NAME")
DB_USER = getenv("DB_USER")
DB_PASSWORD = getenv("DB_PASSWORD")

ADMIN_USER_ID = getenv("ADMIN_USER_ID")
