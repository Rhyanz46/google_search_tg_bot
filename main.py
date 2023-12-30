import logging, sys
import asyncio

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode

from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold

import settings

dp = Dispatcher()

mobile_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
desktop_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36'


async def search_google(query, user_agent):
    base_url = "https://www.googleapis.com/customsearch/v1"

    params = {
        "key": settings.GOOGLE_API,
        "cx": settings.GOOGLE_CX,
        "q": query,
        "gl": "id",
        "userAgent": user_agent,
        "lr": "lang_id",
        # "cr": "countryID",
    }

    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        items = data.get("items", [])

        titles = [item.get("title", "") + " \nlink :" + item.get("link", "") for item in items]
        return titles
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        return None


#
# @dp.message_handler(commands=['start', 'help'])
# async def send_welcome(message: types.Message):
#     welcome_text = "Halo! Saya bot pencarian sederhana.\n" \
#                    "Ketik /search <kata_kunci> untuk mencari di Google."
#
#     await message.reply(welcome_text)
#
#
# @dp.message_handler(commands=['search'])
# async def handle_search_command(message: types.Message):
#     query = message.get_args()
#
#     if not query:
#         await message.reply("Silakan ketik /search <kata_kunci> untuk mencari di Google.")
#         return
#
#     results = search_google(query)
#
#     if results:
#         response_text = "Hasil Pencarian:\n"
#         for result in results:
#             response_text += f"{result['title']}\n{result['link']}\n\n"
#     else:
#         response_text = "Maaf, tidak ada hasil yang ditemukan untuk pencarian ini."
#
#     await message.reply(response_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Hello, {hbold(message.from_user.full_name)}!") @ dp.message(CommandStart())


@dp.callback_query()
async def callback_data(query: types.CallbackQuery):
    print(f"ada callback : {query.message}")


@dp.message(Command(commands=["search"]))
async def command_handler(message: Message) -> None:
    await message.answer(f"Search yahh: {message.text} :::, {hbold(message.from_user.full_name)}!")


@dp.message()
async def echo_handler(message: types.Message) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    try:
        # Send a copy of the received message
        print(message.text)
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")


async def main() -> None:
    # Initialize Bot instance with a default parse mode which will be passed to all API calls
    bot = Bot(settings.TELEGRAM_API, parse_mode=ParseMode.HTML)
    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
