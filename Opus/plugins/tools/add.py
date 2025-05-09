import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import LOGGER_ID as LOG_GROUP_ID
from Opus import app
from Opus.core.userbot import Userbot
from Opus.utils.database import delete_served_chat, add_served_chat, get_assistant
from strings.__init__ import LOGGERS


@app.on_message(filters.new_chat_members, group=2)
async def join_watcher(_, message: Message):
    try:
        userbot = await get_assistant(message.chat.id)
        chat = message.chat
        for members in message.new_chat_members:
            if members.id == app.id:
                count = await app.get_chat_members_count(chat.id)
                username = (
                    message.chat.username if message.chat.username else "ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ"
                )
                msg = (
                    "<blockquote><b>● ᴊᴏɪɴᴇᴅ ᴀ ɴᴇᴡ ɢʀᴏᴜᴘ ●</b>\n\n"
                    f"<b>ᴄʜᴀᴛ ɴᴀᴍᴇ:</b> {message.chat.title}\n"
                    f"<b>ᴄʜᴀᴛ ɪᴅ:</b> {message.chat.id}\n"
                    f"<b>ᴄʜᴀᴛ ᴍᴇᴍʙᴇʀꜱ:</b> {count}</blockquote>"
                )
                await app.send_message(
                    LOG_GROUP_ID,
                    text=msg,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "ᴀᴅᴅ ᴍᴇ",
                                    url="https://t.me/StormMusicPlayer_bot?startgroup=true&admin=delete_messages+invite_users",
                                )
                            ]
                        ]
                    ),
                )
                await add_served_chat(message.chat.id)
                await userbot.join_chat(f"{username}")
                oks = await userbot.send_message(LOGGERS, "/start")
                ok = await userbot.send_message(LOGGERS, f"#{app.username}\n@{app.username}")
                await oks.delete()
                await asyncio.sleep(2)
                await ok.delete()

    except Exception as e:
        print(f"Error: {e}")
