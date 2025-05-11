import os
import aiohttp
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    Message,
    InputMediaPhoto
)
from pyrogram.errors import BadRequest
import config
from config import BANNED_USERS
from Opus import app, LOGGER
from Opus.utils import seconds_to_min
from Opus.utils.logger import play_logs
from Opus import Platform

# Dictionary to store pending downloads
pending_downloads = {}

async def search_saavn_songs(query: str, limit: int = 5):
    """Search songs using Saavn API"""
    url = f"https://saavn.dev/api/search/songs?query={query}&limit={limit}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', {}).get('results', [])
            return []

async def download_saavn_song(song_id: str):
    """Download song using Platform.saavn"""
    song_url = f"https://www.jiosaavn.com/song/{song_id}"
    if await Platform.saavn.valid(song_url) and await Platform.saavn.is_song(song_url):
        return await Platform.saavn.download(song_url)
    return None, None

@app.on_message(
    filters.command(["jsong"]) & 
    filters.group & 
    ~BANNED_USERS
)
async def jsong_command(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Please provide a song name or JioSaavn URL")
    
    query = message.text.split(None, 1)[1]
    user_id = message.from_user.id
    
    # Handle direct URLs
    if query.startswith(('http://', 'https://')) and 'jiosaavn.com' in query:
        try:
            if not (await Platform.saavn.valid(query) and await Platform.saavn.is_song(query)):
                return await message.reply_text("Invalid song URL")
            
            # Show downloading status
            msg = await message.reply_text("⬇️ Downloading song...")
            
            # Download the song
            file_path, details = await Platform.saavn.download(query)
            if not file_path:
                return await msg.edit("Failed to download song")
            
            # Send the audio file
            await message.reply_audio(
                audio=file_path,
                title=details["title"],
                duration=details["duration_sec"],
                performer=details.get("artist", "Unknown Artist"),
                thumb=details.get("thumb"),
                caption=f"🎧 **{details['title']}**\n🎤 {details.get('artist', 'Unknown')}"
            )
            
            # Clean up
            os.remove(file_path)
            if details.get("thumb") and os.path.exists(details["thumb"]):
                os.remove(details["thumb"])
            
            await msg.delete()
            await play_logs(message, streamtype="JioSaavn Download")
            
        except Exception as e:
            LOGGER(__name__).error(f"URL download error: {e}")
            await message.reply_text("Failed to process this URL")
    
    # Handle song name searches
    else:
        try:
            msg = await message.reply_text("🔍 Searching songs...")
            songs = await search_saavn_songs(query)
            
            if not songs:
                return await msg.edit_text("No songs found")
            
            # Create inline buttons for results
            buttons = []
            for song in songs[:5]:  # Show max 5 results
                duration = seconds_to_min(song.get('duration', 0))
                buttons.append([
                    InlineKeyboardButton(
                        f"{song.get('name', 'Unknown')} - {song.get('primaryArtists', 'Unknown')} ({duration})",
                        callback_data=f"dl_{user_id}_{song['id']}"
                    )
                ])
            
            await msg.edit_text(
                f"🎵 Search Results for: {query}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
        except Exception as e:
            LOGGER(__name__).error(f"Search error: {e}")
            await message.reply_text("Failed to search songs")

@app.on_callback_query(filters.regex(r"^dl_(\d+)_(.+)$"))
async def song_download_handler(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    song_id = callback_query.matches[0].group(2)
    
    # Verify user
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("This isn't for you!", show_alert=True)
    
    await callback_query.answer("Downloading...")
    msg = await callback_query.message.edit_text("⬇️ Downloading song...")
    
    try:
        # Download the song
        file_path, details = await download_saavn_song(song_id)
        if not file_path:
            return await msg.edit("Failed to download song")
        
        # Check duration limit
        if details["duration_sec"] > config.DURATION_LIMIT:
            os.remove(file_path)
            if details.get("thumb"):
                os.remove(details["thumb"])
            return await msg.edit(
                f"Song too long (max {seconds_to_min(config.DURATION_LIMIT)})"
            )
        
        # Send the audio file
        await callback_query.message.reply_audio(
            audio=file_path,
            title=details["title"],
            duration=details["duration_sec"],
            performer=details.get("artist", "Unknown Artist"),
            thumb=details.get("thumb"),
            caption=f"🎧 **{details['title']}**\n🎤 {details.get('artist', 'Unknown')}"
        )
        
        # Clean up
        os.remove(file_path)
        if details.get("thumb") and os.path.exists(details["thumb"]):
            os.remove(details["thumb"])
        
        await msg.delete()
        await play_logs(callback_query.message, streamtype="JioSaavn Download")
        
    except Exception as e:
        LOGGER(__name__).error(f"Download error: {e}")
        await msg.edit("Failed to download song")
        
        # Clean up if error occurred
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'details' in locals() and details.get("thumb") and os.path.exists(details["thumb"]):
            os.remove(details["thumb"])
