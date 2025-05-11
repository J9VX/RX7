import random
import string

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from config import BANNED_USERS, lyrical
# from strings import command
from Opus import app, LOGGER, JioSavan
from Opus.utils import seconds_to_min
from Opus.utils.decorators.play import PlayWrapper
from Opus.utils.inline.play import playlist_markup, track_markup
from Opus.utils.logger import play_logs
from Opus.utils.stream.stream import stream

@app.on_message(
    filters.command(
        [
            "jplay"
        ]
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
    mystic = await message.reply_text(
        _["jplay_2"].format(channel) if channel else _["jplay_1"]
    )
    user_id = message.from_user.id
    user_name = message.from_user.mention
    
    # Check if it's a URL or search query
    if url:
        if not await Platform.saavn.valid(url):
            return await mystic.edit_text("This is not a valid JioSaavn URL")  # ""
        
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
                return await mystic.edit_text(
                    _["jplay_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
            
            # Prepare track details
            track_details = {
                "title": details["title"],
                "duration_min": details["duration_min"],
                "thumb": details["thumb"],
                "filepath": file_path,
                "vidid": f"saavn_{details['_id']}",
                "dur": duration_sec,
            }
            
            # Send track info
            buttons = track_markup(
                _,
                details["_id"],
                user_id,
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
            
            # Start streaming
            try:
                await stream(
                    _,
                    None,  # No mystic needed as we already sent the message
                    user_id,
                    track_details,
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
                    LOGGER(__name__).error("Stream error", exc_info=True)
                return await message.reply_text(err)
            
            return await play_logs(message, streamtype="JioSaavn Track")
        
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
            return await mystic.edit_text("podcasts are not supported")  # "Shows/podcasts are not supported"
    
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
                return await mystic.edit_text(
                    _["jplay_6"].format(
                        config.DURATION_LIMIT_MIN,
                        full_details["duration_min"],
                    )
                )
            
            # Prepare track details
            track_details = {
                "title": full_details["title"],
                "duration_min": full_details["duration_min"],
                "thumb": full_details["thumb"],
                "filepath": file_path,
                "vidid": f"saavn_{full_details['_id']}",
                "dur": duration_sec,
            }
            
            # Send track info
            buttons = track_markup(
                _,
                full_details["_id"],
                user_id,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_photo(
                photo=full_details["thumb"],
                caption=_["jplay_11"].format(
                    full_details["title"],
                    full_details["duration_min"],
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            
            # Start streaming
            try:
                await stream(
                    _,
                    None,
                    user_id,
                    track_details,
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
                    LOGGER(__name__).error("Stream error", exc_info=True)
                return await message.reply_text(err)
            
            return await play_logs(message, streamtype="JioSaavn Search")
        
        except Exception as e:
            ex_type = type(e).__name__
            LOGGER(__name__).error("Saavn search error", exc_info=True)
            return await mystic.edit_text(_["jplay_3"])
