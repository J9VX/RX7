import os
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
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
    """Search songs using Saavn API with better error handling"""
    url = f"https://saavn.dev/api/search/songs?query={query}&limit={limit}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # More robust data extraction
                    if isinstance(data, dict):
                        results = data.get('data', {}).get('results', [])
                        if isinstance(results, list):
                            return results
                    LOGGER.error(f"Unexpected API response format: {data}")
                return []
    except Exception as e:
        LOGGER.error(f"Search API error: {e}")
        return []

async def download_saavn_song(song_id: str):
    """Download song with better error handling"""
    try:
        song_url = f"https://www.jiosaavn.com/song/{song_id}"
        if await Platform.saavn.valid(song_url) and await Platform.saavn.is_song(song_url):
            file_path, details = await Platform.saavn.download(song_url)
            if file_path and os.path.exists(file_path):
                return file_path, details
        return None, None
    except Exception as e:
        LOGGER.error(f"Download error: {e}")
        return None, None

@app.on_message(
    filters.command(["jsong"]) & 
    filters.group & 
    ~BANNED_USERS
)
async def jsong_command(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Please provide a song name or JioSaavn URL")
    
    query = message.text.split(None, 1)[1].strip()
    if not query:
        return await message.reply_text("Please provide a valid search query")
    
    user_id = message.from_user.id
    
    # Handle direct URLs
    if query.startswith(('http://', 'https://')) and 'jiosaavn.com' in query:
        try:
            msg = await message.reply_text("⬇️ Processing your song...")
            
            if not (await Platform.saavn.valid(query) and await Platform.saavn.is_song(query)):
                return await msg.edit("⚠️ Invalid or unsupported JioSaavn URL")
            
            file_path, details = await Platform.saavn.download(query)
            if not file_path or not details:
                return await msg.edit("❌ Failed to download song")
            
            # Check duration
            if details.get("duration_sec", 0) > config.DURATION_LIMIT:
                os.remove(file_path)
                return await msg.edit(f"⏳ Song too long (max {seconds_to_min(config.DURATION_LIMIT)})")
            
            # Send audio
            await message.reply_audio(
                audio=file_path,
                title=details.get("title", "Unknown Track"),
                duration=details.get("duration_sec", 0),
                performer=details.get("artist", "Unknown Artist"),
                thumb=details.get("thumb"),
                caption=f"🎵 {details.get('title', 'Unknown Track')}\n🎤 {details.get('artist', 'Unknown Artist')}"
            )
            
            # Cleanup
            os.remove(file_path)
            if details.get("thumb") and os.path.exists(details["thumb"]):
                os.remove(details["thumb"])
            
            await msg.delete()
            await play_logs(message, streamtype="JioSaavn Download")
            
        except Exception as e:
            LOGGER.error(f"URL download error: {e}")
            await message.reply_text("❌ An error occurred while processing your request")
    
    # Handle song name searches
    else:
        try:
            msg = await message.reply_text("🔍 Searching for songs...")
            songs = await search_saavn_songs(query)
            
            if not songs:
                return await msg.edit("❌ No songs found. Try a different search term.")
            
            buttons = []
            for idx, song in enumerate(songs[:5], 1):
                try:
                    name = song.get('name', 'Unknown Track')
                    artist = song.get('primaryArtists', 'Unknown Artist')
                    duration = seconds_to_min(song.get('duration', 0))
                    buttons.append([
                        InlineKeyboardButton(
                            f"{idx}. {name[:20]} - {artist[:15]} ({duration})",
                            callback_data=f"dl_{user_id}_{song['id']}"
                        )
                    ])
                except Exception as e:
                    LOGGER.error(f"Error processing song {idx}: {e}")
                    continue
            
            if not buttons:
                return await msg.edit("❌ No valid songs found in results")
            
            await msg.edit_text(
                f"🎶 Search Results for: {query[:50]}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
        except Exception as e:
            LOGGER.error(f"Search error: {e}")
            await message.reply_text("❌ Failed to search for songs. Please try again.")

@app.on_callback_query(filters.regex(r"^dl_(\d+)_(.+)$"))
async def handle_song_download(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    song_id = callback_query.matches[0].group(2)
    
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("This action isn't for you!", show_alert=True)
    
    await callback_query.answer("Starting download...")
    msg = await callback_query.message.edit_text("⬇️ Downloading your song...")
    
    try:
        file_path, details = await download_saavn_song(song_id)
        if not file_path or not details:
            return await msg.edit("❌ Failed to download song")
        
        # Check duration
        if details.get("duration_sec", 0) > config.DURATION_LIMIT:
            os.remove(file_path)
            return await msg.edit(f"⏳ Song too long (max {seconds_to_min(config.DURATION_LIMIT)})")
        
        # Send audio
        await callback_query.message.reply_audio(
            audio=file_path,
            title=details.get("title", "Unknown Track"),
            duration=details.get("duration_sec", 0),
            performer=details.get("artist", "Unknown Artist"),
            thumb=details.get("thumb"),
            caption=f"🎵 {details.get('title', 'Unknown Track')}\n🎤 {details.get('artist', 'Unknown Artist')}"
        )
        
        # Cleanup
        os.remove(file_path)
        if details.get("thumb") and os.path.exists(details["thumb"]):
            os.remove(details["thumb"])
        
        await msg.delete()
        await play_logs(callback_query.message, streamtype="JioSaavn Download")
        
    except Exception as e:
        LOGGER.error(f"Download callback error: {e}")
        await msg.edit("❌ Failed to download song")
        
        # Cleanup if error occurred
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            os.remove(file_path)
        if 'details' in locals() and details and details.get("thumb") and os.path.exists(details["thumb"]):
            os.remove(details["thumb"])
