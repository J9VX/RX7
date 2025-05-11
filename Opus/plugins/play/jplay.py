import random
import string

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from config import BANNED_USERS, lyrical
from strings import command
from Opus import app, LOGGER, Platform
from Opus.utils import seconds_to_min
from Opus.utils.decorators.play import PlayWrapper
from Opus.utils.inline.play import playlist_markup, track_markup
from Opus.utils.logger import play_logs

@app.on_message(
    command(
        "JPLAY_COMMAND",
        prefixes=["/"],
    )
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
async def jplay_command(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    mystic = await message.reply_text(_["jplay_2"].format(channel) if channel else _["jplay_1"])
    user_id = message.from_user.id
    user_name = message.from_user.mention
    
    # Check if it's a direct JioSaavn URL
    if url and await Platform.saavn.valid(url):
        if await Platform.saavn.is_song(url):
            try:
                file_path, details = await Platform.saavn.download(url)
            except Exception as e:
                ex_type = type(e).__name__
                LOGGER(__name__).error("An error occurred", exc_info=True)
                return await mystic.edit_text(_["jplay_3"])
            
            duration_sec = details["duration_sec"]
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
            
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="saavn_track",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                if ex_type == "AssistantErr":
                    err = e
                else:
                    err = _["jgeneral_3"].format(ex_type)
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                return await mystic.edit_text(err)
            return await mystic.delete()
        
        elif await Platform.saavn.is_playlist(url):
            try:
                details = await Platform.saavn.playlist(
                    url, limit=config.PLAYLIST_FETCH_LIMIT
                )
                streamtype = "saavn_playlist"
            except Exception as e:
                ex_type = type(e).__name__
                LOGGER(__name__).error("An error occurred", exc_info=True)
                return await mystic.edit_text(_["jplay_3"])

            if len(details) == 0:
                return await mystic.edit_text(_["jplay_3"])
            
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = url
            buttons = playlist_markup(
                _,
                ran_hash,
                message.from_user.id,
                "saavn",
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_photo(
                photo=details[0]["thumb"],
                caption=_["jplay_12"].format(message.from_user.first_name),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return await play_logs(message, streamtype=f"Playlist : Saavn")
    
    # Handle search queries for JioSaavn songs
    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["jplaylist_1"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        
        query = message.text.split(None, 1)[1]
        try:
            details = await Platform.saavn.info(query)
        except Exception:
            return await mystic.edit_text(_["jplay_3"])
        
        if not details:
            return await mystic.edit_text(_["jplay_3"])
        
        duration_sec = details["duration_sec"]
        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["jplay_6"].format(
                    config.DURATION_LIMIT_MIN,
                    details["duration_min"],
                )
            )
        
        try:
            file_path, details = await Platform.saavn.download(details["url"])
        except Exception as e:
            ex_type = type(e).__name__
            LOGGER(__name__).error("An error occurred", exc_info=True)
            return await mystic.edit_text(_["jplay_3"])
        
        buttons = track_markup(
            _,
            details["_id"],
            message.from_user.id,
            "c" if channel else "g",
            "f" if fplay else "d",
        )
        
        await mystic.delete()
        await message.reply_photo(
            photo=details["thumb"],
            caption=_["jplay_11"].format(
                details["title"],
                details["duration_min"],
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        
        try:
            await stream(
                _,
                None,  # No mystic needed here since we already sent the message
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                streamtype="saavn_track",
                forceplay=fplay,
            )
        except Exception as e:
            ex_type = type(e).__name__
            if ex_type == "AssistantErr":
                err = e
            else:
                err = _["jgeneral_3"].format(ex_type)
                LOGGER(__name__).error("An error occurred", exc_info=True)
            return await message.reply_text(err)
        
        return await play_logs(message, streamtype=f"Searched on JioSaavn")
