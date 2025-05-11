import random
import string
import os

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message
from pyrogram.errors import BadRequest

import config
from config import BANNED_USERS, lyrical
from Opus import app, LOGGER
from Opus import Platform
from Opus.utils import seconds_to_min
from Opus.utils.decorators.play import PlayWrapper
from Opus.utils.inline.play import playlist_markup, track_markup
from Opus.utils.logger import play_logs

@app.on_message(
    filters.command(["jsong"]) & filters.group & ~BANNED_USERS
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
    mystic = await message.reply_text(
        _["jplay_2"].format(channel) if channel else _["jplay_1"]
    )
    user_id = message.from_user.id
    user_name = message.from_user.mention
    
    # Check if it's a URL or search query
    if url:
        if not await Platform.saavn.valid(url):
            return await mystic.edit_text("This is not a valid JioSaavn URL")
        
        if await Platform.saavn.is_song(url):
            # Handle single track
            try:
                file_path, details = await Platform.saavn.download(url)
            except Exception as e:
                ex_type = type(e).__name__
                LOGGER(__name__).error("Saavn download error", exc_info=True)
                return await mystic.edit_text(_["jplay_3"])
            
            # Check duration limit
            duration_sec = details["duration_sec"]
            if duration_sec > config.DURATION_LIMIT:
                os.remove(file_path)  # Clean up the downloaded file
                return await mystic.edit_text(
                    _["jplay_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
            
            try:
                # Send the audio file directly
                await mystic.delete()
                await message.reply_audio(
                    audio=file_path,
                    title=details["title"],
                    duration=duration_sec,
                    performer=details.get("artist", "Unknown Artist"),
                    thumb=details["thumb"],
                    caption=f"🎧 **Title:** {details['title']}\n⏳ **Duration:** {details['duration_min']}",
                )
                
                # Clean up the file after sending
                os.remove(file_path)
                if os.path.exists(details["thumb"]):
                    os.remove(details["thumb"])
                    
                return await play_logs(message, streamtype="JioSaavn Download")
                
            except Exception as e:
                # Clean up files if something went wrong
                if os.path.exists(file_path):
                    os.remove(file_path)
                if "thumb" in details and os.path.exists(details["thumb"]):
                    os.remove(details["thumb"])
                    
                ex_type = type(e).__name__
                LOGGER(__name__).error("File sending error", exc_info=True)
                return await message.reply_text(_["jgeneral_3"].format(ex_type))
        
        elif await Platform.saavn.is_playlist(url):
            # Handle playlist
            try:
                playlist_details = await Platform.saavn.playlist(
                    url, limit=config.PLAYLIST_FETCH_LIMIT
                )
            except Exception as e:
                ex_type = type(e).__name__
                LOGGER(__name__).error("Saavn playlist error", exc_info=True)
                return await mystic.edit_text(_["jplay_3"])
            
            if not playlist_details:
                return await mystic.edit_text(_["jplay_3"])
            
            # Generate unique hash for playlist
            ran_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            lyrical[ran_hash] = url
            
            # Send playlist info
            buttons = playlist_markup(
                _,
                ran_hash,
                user_id,
                "saavn",
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_photo(
                photo=playlist_details[0]["thumb"],
                caption=_["jplay_12"].format(message.from_user.first_name),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            
            return await play_logs(message, streamtype="JioSaavn Playlist")
        else:
            return await mystic.edit_text("Podcasts are not supported")
    
    else:
        # Handle search query
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["jplaylist_1"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        
        query = message.text.split(None, 1)[1]
        
        try:
            # Search for track on Saavn
            details = await Platform.saavn.info(query)
            if not details:
                return await mystic.edit_text(_["jplay_3"])
            
            # Download the track
            file_path, full_details = await Platform.saavn.download(details["url"])
            
            # Check duration
            duration_sec = full_details["duration_sec"]
            if duration_sec > config.DURATION_LIMIT:
                os.remove(file_path)
                return await mystic.edit_text(
                    _["jplay_6"].format(
                        config.DURATION_LIMIT_MIN,
                        full_details["duration_min"],
                    )
                )
            
            try:
                # Send the audio file directly
                await mystic.delete()
                await message.reply_audio(
                    audio=file_path,
                    title=full_details["title"],
                    duration=duration_sec,
                    performer=full_details.get("artist", "Unknown Artist"),
                    thumb=full_details["thumb"],
                    caption=f"🎧 **Title:** {full_details['title']}\n⏳ **Duration:** {full_details['duration_min']}",
                )
                
                # Clean up the file after sending
                os.remove(file_path)
                if os.path.exists(full_details["thumb"]):
                    os.remove(full_details["thumb"])
                    
                return await play_logs(message, streamtype="JioSaavn Search Download")
                
            except Exception as e:
                # Clean up files if something went wrong
                if os.path.exists(file_path):
                    os.remove(file_path)
                if "thumb" in full_details and os.path.exists(full_details["thumb"]):
                    os.remove(full_details["thumb"])
                    
                ex_type = type(e).__name__
                LOGGER(__name__).error("File sending error", exc_info=True)
                return await message.reply_text(_["jgeneral_3"].format(ex_type))
        
        except Exception as e:
            ex_type = type(e).__name__
            LOGGER(__name__).error("Saavn search error", exc_info=True)
            return await mystic.edit_text(_["jplay_3"])
