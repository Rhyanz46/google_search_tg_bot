from os import getenv
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API = getenv("TELEGRAM_API")
GOOGLE_CX = getenv("GOOGLE_CX")
GOOGLE_API = getenv("GOOGLE_API")