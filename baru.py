from __future__ import annotations
from dataclasses import dataclass
from uuid import uuid4

import asyncio
import logging
from typing import TypedDict, Any, Type

from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import Command
from aiogram.fsm.scene import After, Scene, SceneRegistry, on, SceneWizard, FSMContext
from aiogram.methods import SendMessage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from aiogram.utils.keyboard import ReplyKeyboardBuilder

from aiogram.utils.formatting import (
    Bold,
    as_key_value,
    as_list,
    as_numbered_list,
    as_section,
    Code
)

from aiogram.filters.state import State, StatesGroup

import errors
from database import (
    get_all_users, get_active_user, save_user, active_user,
    add_user_command, remove_user_command, CommandSearch, my_search_commands,
    is_user_command_exist, get_user_command, update_user
)

BUTTON_CANCEL = KeyboardButton(text="❌ Cancel")
BUTTON_BACK = KeyboardButton(text="🔙 Back")
BUTTON_STOP_COMMAND = KeyboardButton(text="✋ Stop ⏹")

import settings
from main import search_google, mobile_agent, desktop_agent

bot = Bot(settings.TELEGRAM_API)

basic_commands = [
    "/cari",
    "/tambah_perintah",
    "/hapus_perintah",
    "/daftar_pengguna",
    "/daftar_pengguna_terblokir",
]


class FSMData(TypedDict, total=False):
    code: str
    command: str


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


class VerifyScene(Scene, state="verify_state"):

    @on.message.enter()
    async def on_enter(self, message: Message):
        await message.answer(
            "Masuukkan Kode Penggunaan",
            reply_markup=ReplyKeyboardRemove(),
        )

    @on.message()
    async def input_like_bots(self, message: Message):
        await message.answer("Mengecek Kode . . .")
        try:
            active_user(message.from_user.id, message.text)
            await message.answer("Kode benar 🥳")
            await self.wizard.goto(MainScene)
        except errors.VerifyCodeWrong as e:
            await message.answer("Kode salah, silahkan masukkan lagi : ")


class UserListScene(Scene, state="user_list_state"):

    @on.message.enter()
    async def on_enter(self, message: Message):
        try:
            get_active_user(message.from_user.id)
        except Exception as _:
            await self.wizard.goto(DefaultScene)
        await message.answer("Mengambil daftar pengguna . . . ")
        all_user = get_all_users()
        if len(all_user) == 0:
            await message.answer("masih belum ada pengguna :( ")
            return
        content = as_list(
            as_section(
                Bold("Daftar Pengguna Saat ini:\n"),
                as_numbered_list(*all_user),
            ),
            "\nSilahkan pilih action"
        )

        markup = ReplyKeyboardBuilder()
        markup.button(text="Delete")
        markup.button(text="Blacklist")
        markup.button(text="🔙 Back")
        await self.wizard.update_data(command="/daftar_pengguna")
        await message.answer(**content.as_kwargs(), reply_markup = markup.adjust(2).as_markup(resize_keyboard=True))

    @on.message(F.text == "🔙 Back")
    async def back(self, message: Message) -> None:
        return await self.wizard.goto(MainScene)

    @on.message()
    async def input_action(self, message: Message):
        await message.answer("saya tidak mengerti")


class RemoveCommandScene(Scene, state="remove_command_state"):

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | 0 = 0):
        await self.wizard.update_data(command="/hapus_perintah")
        data = await state.get_data()
        answers = data.get("answers", {})
        await state.update_data(step=step)
        markup = ReplyKeyboardBuilder()
        await state.update_data(step=step)
        question = "Masukkan perintah yang ingin anda hapus : "
        if step == 1:
            question = f"apakah anda yakin ingin menghapus perintah {answers['cmd']}? "
        markup.button(text="🚫 Cancel")
        if step > 0:
            markup.button(text="🔙 Back")
        if step == 1:
            markup.button(text="🗑 Hapus")
        await message.answer(
            question,
            reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
        )
    @on.message(F.text == "🚫 Cancel")
    async def exit(self, message: Message) -> None:
        await self.wizard.goto(MainScene)

    @on.message(F.text == "🔙 Back")
    async def back(self, message: Message, state: FSMContext) -> None:
        """
        Method triggered when the user selects the "Back" button.

        It allows the user to go back to the previous question.

        :param message:
        :param state:
        :return:
        """
        data = await state.get_data()
        step = data["step"]

        previous_step = step - 1
        if previous_step < 0:
            # In case when the user tries to go back from the first question,
            # we just exit the quiz
            return await self.wizard.exit()
        return await self.wizard.back(step=previous_step)

    @on.message(F.text)
    async def answer(self, message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        step = data["step"]
        answers = data.get("answers", {})
        if step == 0:
            await message.answer("Memeriksa Command sebelum di hapus . . .")
            answers["cmd"] = message.text
            try:
                exist = is_user_command_exist(message.from_user.id, message.text)
                if not exist:
                    await message.answer("command ini tidak ada")
                    return
            except Exception as e:
                await message.answer(f"Error : {e} ")
                return
        if step == 1:
            if message.text == "🗑 Hapus":
                await message.answer("Sedang menghapus . .")
                try:
                    remove_user_command(message.from_user.id, answers["cmd"])
                    await message.answer("Berhasil Menghapus")
                    return await self.wizard.goto(MainScene)
                except Exception as e:
                    await message.answer(f"Error : {e}")
                    return
            else:
                await message.answer("jawaban tidak di ketahui")
            return
        print(step)
        await state.update_data(answers=answers)
        await self.wizard.retake(step=step + 1)


@dataclass
class Question:
    text: str


class AddCommandScene(Scene, state="add_command_state"):
    def __init__(self, wizard: SceneWizard):
        super().__init__(wizard)
        self.QUESTIONS = [
            Question(
                text="Masukkan Perintah Baru : (contoh: /adele)",
            ),
            Question(
                text="Masukkan kata kunci : ",
            ),
            Question(
                text="Masukkan deskripsi (boleh kosong) : ",
            ),
        ]

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | 0 = 0) -> Any:
        max_step = len(self.QUESTIONS)
        try:
            markup = ReplyKeyboardBuilder()
            await state.update_data(step=step)
            if step < max_step:
                if step > 0:
                    markup.button(text="🔙 Back")
                if step + 1 == max_step:
                    markup.button(text="➡️ Skip")
                markup.button(text="🚫 Cancel")
                return await message.answer(
                    text=self.QUESTIONS[step].text,
                    reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
                )
            else:
                if step >= max_step:
                    markup.button(text="📔 Save")
                markup.button(text="🚫 Cancel")
                data = await state.get_data()
                answers = data.get("answers", {})
                content = as_list(
                    as_section(
                        Bold("Informasi Perintah:\n"),
                        as_numbered_list(*[
                            f"Perintah \t\t\t: {answers['cmd']}",
                            f"Keyword \t\t\t: {answers['keyword']}",
                            f"Description \t: {answers['desc']}",
                        ]),
                    ),
                    "",
                    Bold("Save ?")
                )
                return await message.answer(
                    **content.as_kwargs(),
                    reply_markup=markup.adjust(2).as_markup(resize_keyboard=True),
                )
        except Exception as e:
            print(e)
            return await self.wizard.goto(MainScene)

    @on.message(F.text == "🔙 Back")
    async def back(self, message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        step = data["step"]

        previous_step = step - 1
        if previous_step < 0:
            return await self.wizard.exit()
        return await self.wizard.back(step=previous_step)

    @on.message(F.text == "🚫 Cancel")
    async def exit(self, message: Message) -> None:
        await self.wizard.goto(MainScene)

    @on.message(F.text)
    async def answer(self, message: Message, state: FSMContext) -> None:
        """
        Method triggered when the user selects an answer.

        It stores the answer and proceeds to the next question.

        :param message:
        :param state:
        :return:
        """
        data = await state.get_data()
        step = data["step"]
        answers = data.get("answers", {})
        if step == 0:
            if message.text[0] != "/":
                await message.answer("perintah harus di awali dengan /")
                return
            for cmd in basic_commands:
                if cmd == message.text.lower():
                    await message.answer("tidak boleh menggunakan perintah ini")
                    return
            if is_user_command_exist(message.from_user.id, message.text):
                await message.answer("command ini sudah ada, gunakan command lain")
                return
            answers["cmd"] = message.text
        elif step == 1:
            answers["keyword"] = message.text
        elif step == 2:
            answers["desc"] = message.text
            if message.text == "➡️ Skip":
                answers["desc"] = None
        else:
            if message.text == "📔 Save":
                try:
                    cmd = CommandSearch()
                    cmd.command = answers["cmd"]
                    cmd.keyword = answers["keyword"]
                    cmd.desc = answers["desc"]
                    add_user_command(message.from_user.id, cmd)
                    await message.answer("Sukses menambah perintah baru")
                    await self.wizard.goto(MainScene)
                    return
                except errors.CommandIsAlreadyExist as e:
                    await message.answer("command ini sudah ada, gunakan command lain")
                    return
                except Exception as e:
                    await message.answer(f"error : {str(e)}")
                    return
            answers[step] = message.text
        await state.update_data(answers=answers)
        await self.wizard.retake(step=step + 1)


class SearchScene(Scene, state="search_state"):
    @on.message.enter()
    async def on_enter(self, message: Message):
        await self.wizard.update_data(command="/cari")
        await message.answer(
            "Masukkan Kata Kunci : ",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[BUTTON_CANCEL]],
                resize_keyboard=True,
            ),
        )

    @on.message(F.text.casefold() == BUTTON_STOP_COMMAND.text.casefold(), )
    async def handle_stop(self, message: Message):
        await self.wizard.goto(MainScene, reply_markup=ReplyKeyboardRemove())
        await self.wizard.update_data(command=None)

    @on.message(F.text.casefold() == BUTTON_CANCEL.text.casefold())
    async def handle_cancel(self, message: Message):
        await self.wizard.goto(MainScene, reply_markup=ReplyKeyboardRemove())
        await self.wizard.update_data(command=None)

    @on.message()
    async def input_search_keyword(self, message: Message):
        try:
            get_active_user(message.from_user.id)
            await message.answer("Mencari . . .")
            mobile_search_result = await search_google(message.text, mobile_agent)
            desktop_search_result = await search_google(message.text, desktop_agent)
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
            await message.answer(**content.as_kwargs(), reply_markup=ReplyKeyboardMarkup(
                keyboard=[[BUTTON_STOP_COMMAND]],
                resize_keyboard=True,
            ), )
        except errors.VerifyCodeWrong as e:
            await self.wizard.goto(VerifyScene)


class MainScene(CancellableScene, state="code"):

    @on.message.enter()  # Marker for handler that should be called when a user enters the scene.
    async def on_enter(self, message: Message):
        my_commands = my_search_commands(telegram_id=message.from_user.id)
        content = [
            as_section(
                Bold("Perintah Dasar:\n"),
                as_numbered_list(*basic_commands),
            ),
        ]

        if len(my_commands) > 0:
            content.append("")
            content.append(as_section(
                Bold("Perintah Pencarian :\n"),
                as_numbered_list(*[cmd.get_as_string() for cmd in my_commands])
            ))

        # "",
        # as_section(
        #     Bold("Perintah Pencarian :\n"),
        #     as_numbered_list(
        #         *[f"{cmd.command} = {cmd.desc}" for cmd in )],
        # )
        content.append("\nSilahkan pilih perintah")
        try:
            get_active_user(message.from_user.id)
            await message.answer(**as_list(*content).as_kwargs(), reply_markup=ReplyKeyboardRemove())
        except Exception as _:
            await self.wizard.back()

    @on.message(F.text.casefold() == "/cari")
    async def handle_cari(self, message: Message):
        try:
            get_active_user(message.from_user.id)
            await self.wizard.goto(SearchScene)
        except Exception as _:
            await self.wizard.goto(DefaultScene)

    @on.message(F.text.casefold() == "/start")
    async def handle_start(self, message: Message):
        await self.wizard.goto(DefaultScene)

    @on.message(F.text.casefold() == "/tambah_perintah")
    async def tambah_perintah(self, message: Message):
        try:
            get_active_user(message.from_user.id)
            await self.wizard.goto(AddCommandScene)
        except Exception as _:
            await self.wizard.goto(DefaultScene)

    @on.message(F.text.casefold() == "/hapus_perintah")
    async def hapus_perintah(self, message: Message):
        try:
            get_active_user(message.from_user.id)
            await self.wizard.goto(RemoveCommandScene)
        except Exception as _:
            await self.wizard.goto(DefaultScene)

    @on.message(F.text.casefold() == "/daftar_pengguna")
    async def daftar_pengguna_perintah(self, message: Message):
        try:
            get_active_user(message.from_user.id)
            await self.wizard.goto(UserListScene)
        except Exception as _:
            await self.wizard.goto(DefaultScene)

    @on.message(F.text.casefold() == BUTTON_STOP_COMMAND.text.casefold(), )
    async def handle_stop(self, message: Message):
        await self.wizard.update_data(command=None)
        await self.wizard.goto(MainScene)

    @on.message()
    async def handle_all_command(self, message: Message):
        cmd: Type[CommandSearch] | None = None
        if message.text[0] == "/":
            try:
                cmd = get_user_command(message.from_user.id, message.text)
            except Exception as e:
                await message.answer(f"Error : {e}")
                return

        if cmd is None:
            await message.answer("Perintah tidak di ketahui")
            return

        try:
            get_active_user(message.from_user.id)
            await message.answer("Mencari . . .")
            mobile_search_result = await search_google(cmd.keyword, mobile_agent)
            desktop_search_result = await search_google(cmd.keyword, desktop_agent)
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
        except errors.VerifyCodeWrong as e:
            await self.wizard.goto(VerifyScene)


    # @on.message.leave()  # Marker for handler that should be called when a user leaves the scene.
    # async def on_leave(self, message: Message):
    #     await message.answer(f"Terimakasih telah menggunakan, {message.from_user.full_name}!")

    # @on.message(after=After.goto(LikeBotsScene))
    # async def input_code(self, message: Message):
    #     await self.wizard.update_data(code=message.text)


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

    # start_bot_search = on.message(F.text.casefold() != code_token, after=After.goto(MainScene))
    # cancel_bot_search = on.message(
    #     F.text.casefold() != code and F.text.casefold() != 'start' and F.text.casefold() != '/start',
    #     after=After.goto(WrongMainScene))

    # @on.callback_query(F.data == "start", after=After.goto(MainScene))
    # async def demo_callback(self, callback_query: CallbackQuery):
    #     await callback_query.answer(cache_time=0)
    #     await callback_query.message.delete_reply_markup()

    @on.message.enter()  # Mark that this handler should be called when a user enters the scene.
    @on.message()
    async def default_handler(self, message: Message):
        if message.text != "/start":
            await message.answer(
                "kamu harus /start terlebih dahulu", reply_markup=ReplyKeyboardRemove()
            )
            return
        try:
            update_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
            await self.wizard.goto(MainScene)
        except errors.UserNotFound as e:
            confirm_code = str(uuid4())
            confirm_code = confirm_code.replace("-", "")
            save_user(message.from_user.id, message.from_user.full_name, message.from_user.username, confirm_code)
            await bot(SendMessage(chat_id=settings.ADMIN_USER_ID,
                                  text=f"this is code for @{message.from_user.username}\n{confirm_code}"))
            await message.answer(
                f"Selamat Datang {message.from_user.full_name} :) ", reply_markup=ReplyKeyboardRemove()
            )
            await self.wizard.goto(VerifyScene)
        except errors.UserNotActive as e:
            await message.answer(
                "akun anda belum aktif :( ", reply_markup=ReplyKeyboardRemove()
            )
            await self.wizard.goto(VerifyScene)


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()

    # Scene registry should be the only one instance in your application for proper work.
    # It stores all available scenes.
    # You can use any router for scenes, not only `Dispatcher`.
    registry = SceneRegistry(dispatcher)
    # All scenes at register time converts to Routers and includes into specified router.
    registry.add(
        DefaultScene,
        VerifyScene,
        MainScene,
        SearchScene,
        AddCommandScene,
        RemoveCommandScene,
        UserListScene
    )

    return dispatcher


async def main():
    dispatcher = create_dispatcher()
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
    # Alternatively, you can use aiogram-cli:
    # `aiogram run polling quiz_scene:create_dispatcher --log-level info --token BOT_TOKEN`
