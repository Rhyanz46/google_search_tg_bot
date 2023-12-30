from __future__ import annotations
from aiogram.enums import ParseMode

import asyncio
import logging
from os import getenv
from typing import TypedDict

from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import Command
from aiogram.fsm.scene import After, Scene, SceneRegistry, on
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from aiogram.utils.formatting import (
    Bold,
    as_key_value,
    as_list,
    as_numbered_list,
    as_section,
)

import settings
from main import search_google, mobile_agent, desktop_agent

BUTTON_CANCEL = KeyboardButton(text="❌ Cancel")
BUTTON_BACK = KeyboardButton(text="🔙 Back")


class FSMData(TypedDict, total=False):
    name: str
    language: str


class CancellableScene(Scene):
    """
    This scene is used to handle cancel and back buttons,
    can be used as a base class for other scenes that needs to support cancel and back buttons.
    """

    @on.message(F.text.casefold() == BUTTON_CANCEL.text.casefold(), after=After.exit())
    async def handle_cancel(self, message: Message):
        await message.answer("Cancelled.", reply_markup=ReplyKeyboardRemove())

    @on.message(F.text.casefold() == BUTTON_BACK.text.casefold(), after=After.back())
    async def handle_back(self, message: Message):
        await message.answer("Back.")


class LanguageScene(CancellableScene, state="language"):
    """
    This scene is used to ask user what language he prefers.
    """

    @on.message.enter()
    async def on_enter(self, message: Message):
        await message.answer(
            "What language do you prefer?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[BUTTON_BACK, BUTTON_CANCEL]],
                resize_keyboard=True,
            ),
        )

    @on.message(F.text.casefold() == "python", after=After.exit())
    async def process_python(self, message: Message):
        await message.answer(
            "Python, you say? That's the language that makes my circuits light up! 😉"
        )
        await self.input_language(message)

    @on.message(after=After.exit())
    async def input_language(self, message: Message):
        data: FSMData = await self.wizard.get_data()
        await self.show_results(message, language=message.text, **data)

    async def show_results(self, message: Message, name: str, language: str) -> None:
        await message.answer(
            text=f"I'll keep in mind that, {html.quote(name)}, "
            f"you like to write bots with {html.quote(language)}.",
            reply_markup=ReplyKeyboardRemove(),
        )


class LikeBotsScene(CancellableScene, state="like_bots"):
    """
    This scene is used to ask user if he likes to write bots.
    """

    @on.message.enter()
    async def on_enter(self, message: Message):
        await message.answer(
            "Pilih Aksi selanjutnya",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [BUTTON_BACK,],
                ],
                resize_keyboard=True,
            ),
            # reply_markup=ReplyKeyboardMarkup(
            #     keyboard=[
            #         [KeyboardButton(text="Yes"), KeyboardButton(text="No")],
            #         [BUTTON_BACK, BUTTON_CANCEL],
            #     ],
            #     resize_keyboard=True,
            # ),
        )

    @on.message(F.text.casefold() == "yes", after=After.goto(LanguageScene))
    async def process_like_write_bots(self, message: Message):
        await message.reply("Cool! I'm too!")

    @on.message(F.text.casefold() == "no", after=After.exit())
    async def process_dont_like_write_bots(self, message: Message):
        await message.answer(
            "Not bad not terrible.\nSee you soon.",
            reply_markup=ReplyKeyboardRemove(),
        )

    @on.message()
    async def input_like_bots(self, message: Message):
        await message.answer("I don't understand you :(")


class NameScene(CancellableScene, state="name"):
    """
    This scene is used to ask user's name.
    """

    @on.message.enter()  # Marker for handler that should be called when a user enters the scene.
    async def on_enter(self, message: Message):
        await message.answer(
            "Tuliskan Kata Kunci Pencarian",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[BUTTON_CANCEL]], resize_keyboard=True),
        )

    @on.callback_query.enter()  # different types of updates that start the scene also supported.
    async def on_enter_callback(self, callback_query: CallbackQuery):
        await callback_query.answer()
        await self.on_enter(callback_query.message)

    @on.message.leave()  # Marker for handler that should be called when a user leaves the scene.
    async def on_leave(self, message: Message):
        data: FSMData = await self.wizard.get_data()
        name = data.get("name", "Anonymous")
        await message.answer("Sedang mencari . . . ")
        mobile_search_result = await search_google(name, mobile_agent)
        desktop_search_result = await search_google(name, desktop_agent)
        print("mencari : ", name)

        if not mobile_search_result and not mobile_search_result:
            await message.answer("Tidak ada hasil ")
            return

        content = as_list(
            as_section(
                Bold("Mobile Result:\n"),
                as_numbered_list(*mobile_search_result),
            ),
            "",
            as_section(
                Bold("Desktop Result:\n"),
                as_numbered_list(*desktop_search_result),
            ),
            "",
        )
        await message.answer(**content.as_kwargs(), reply_markup=ReplyKeyboardRemove())

    @on.message(after=After.goto(LikeBotsScene))
    async def input_name(self, message: Message):
        await self.wizard.update_data(name=message.text)


class DefaultScene(
    Scene,
    reset_data_on_enter=True,  # Reset state data
    reset_history_on_enter=True,  # Reset history
    callback_query_without_state=True,  # Handle callback queries even if user in any scene
):
    """
    Default scene for the bot.

    This scene is used to handle all messages that are not handled by other scenes.
    """

    start_search = on.message(F.text.casefold() == "search", after=After.goto(NameScene))

    @on.message(Command("search"))
    async def search(self, message: Message):
        await message.answer(
            "Demo started",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Go to form", callback_data="start")]]
            ),
        )

    @on.callback_query(F.data == "start", after=After.goto(NameScene))
    async def search_callback(self, callback_query: CallbackQuery):
        await callback_query.answer(cache_time=0)
        await callback_query.message.delete_reply_markup()

    @on.message.enter()  # Mark that this handler should be called when a user enters the scene.
    @on.message()
    async def default_handler(self, message: Message):
        await message.answer(
            "Pilih Fitur : ",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Search")], [KeyboardButton(text="DDOS!")]],
                resize_keyboard=True,
            ),
        )


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()

    # Scene registry should be the only one instance in your application for proper work.
    # It stores all available scenes.
    # You can use any router for scenes, not only `Dispatcher`.
    registry = SceneRegistry(dispatcher)
    # All scenes at register time converts to Routers and includes into specified router.
    registry.add(
        DefaultScene,
        NameScene,
        LikeBotsScene,
        LanguageScene,
    )

    return dispatcher


async def main():
    dispatcher = create_dispatcher()
    bot = Bot(settings.TELEGRAM_API)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
    # Alternatively, you can use aiogram-cli:
    # `aiogram run polling quiz_scene:create_dispatcher --log-level info --token BOT_TOKEN`