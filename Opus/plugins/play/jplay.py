import os
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import config
from config import BANNED_USERS
from Opus import app, LOGGER
from Opus.utils import seconds_to_min
from Opus.utils.logger import play_logs

# Dictionary to store pending download confirmations
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

@app.on_message(
    filters.command(["jsong"]) & filters.group & ~BANNED_USERS
)
async def jsong_command(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Please provide a song name or JioSaavn URL after the command.")
    
    query = message.text.split(None, 1)[1]
    user_id = message.from_user.id
    
    # Check if it's a URL
    if query.startswith(('http://', 'https://')) and 'jiosaavn.com' in query:
        if await Platform.saavn.valid(query) and await Platform.saavn.is_song(query):
            try:
                # Download the song to get details
                file_path, details = await Platform.saavn.download(query)
                
                # Create confirmation buttons
                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Download", callback_data=f"download_{user_id}_yes"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"download_{user_id}_no")
                    ]
                ])
                
                # Store the details temporarily
                pending_downloads[user_id] = {
                    "file_path": file_path,
                    "details": details,
                    "message_id": message.id
                }
                
                # Ask for confirmation
                await message.reply_photo(
                    photo=details.get("thumb"),
                    caption=f"🎵 **{details['title']}**\n🎤 {details.get('artist', 'Unknown Artist')}\n⏳ {details['duration_min']}",
                    reply_markup=buttons
                )
                
            except Exception as e:
                LOGGER(__name__).error(f"Error processing URL: {e}")
                return await message.reply_text("Failed to process this URL. Please try another song.")
        else:
            return await message.reply_text("Only single song URLs are supported.")
    else:
        # Search for songs by name
        try:
            search_msg = await message.reply_text("🔍 Searching for songs...")
            songs = await search_saavn_songs(query)
            
            if not songs:
                await search_msg.edit_text("No songs found. Please try a different search.")
                return
            
            buttons = []
            for song in songs[:5]:  # Show max 5 results
                buttons.append(
                    [InlineKeyboardButton(
                        f"{song.get('name', 'Unknown')} - {song.get('primaryArtists', 'Unknown')} ({seconds_to_min(song.get('duration', 0))}",
                        callback_data=f"song_select_{user_id}_{song['id']}"
                    )]
                )
            
            await search_msg.edit_text(
                f"🎵 Search Results for: {query}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
        except Exception as e:
            LOGGER(__name__).error(f"Search error: {e}")
            await message.reply_text("Failed to search for songs. Please try again later.")

@app.on_callback_query(filters.regex(r"^song_select_(\d+)_(.+)$"))
async def song_selected(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    song_id = callback_query.matches[0].group(2)
    original_user = callback_query.from_user.id
    
    if original_user != user_id:
        return await callback_query.answer("This selection isn't for you!", show_alert=True)
    
    await callback_query.answer("Fetching song details...")
    
    try:
        # Get song URL from ID
        song_url = f"https://www.jiosaavn.com/song/{song_id}"
        
        if not await Platform.saavn.valid(song_url) or not await Platform.saavn.is_song(song_url):
            return await callback_query.message.edit_text("Invalid song selection. Please try another.")
        
        # Download the song
        file_path, details = await Platform.saavn.download(song_url)
        
        # Create confirmation buttons
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Download", callback_data=f"download_{user_id}_yes"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"download_{user_id}_no")
            ]
        ])
        
        # Store the details temporarily
        pending_downloads[user_id] = {
            "file_path": file_path,
            "details": details,
            "message_id": callback_query.message.id
        }
        
        # Show confirmation
        await callback_query.message.edit_media(
            media=InputMediaPhoto(media=details.get("thumb")),
            caption=f"🎵 **{details['title']}**\n🎤 {details.get('artist', 'Unknown Artist')}\n⏳ {details['duration_min']}",
            reply_markup=buttons
        )
        
    except Exception as e:
        LOGGER(__name__).error(f"Song selection error: {e}")
        await callback_query.message.edit_text("Failed to process this song. Please try another.")

@app.on_callback_query(filters.regex(r"^download_(\d+)_(yes|no)$"))
async def download_confirmation(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    action = callback_query.matches[0].group(2)
    original_user = callback_query.from_user.id
    
    if original_user != user_id:
        return await callback_query.answer("This confirmation isn't for you!", show_alert=True)
    
    if action == "no":
        try:
            # Clean up files
            if user_id in pending_downloads:
                if os.path.exists(pending_downloads[user_id]["file_path"]):
                    os.remove(pending_downloads[user_id]["file_path"])
                if "thumb" in pending_downloads[user_id]["details"] and os.path.exists(pending_downloads[user_id]["details"]["thumb"]):
                    os.remove(pending_downloads[user_id]["details"]["thumb"])
                del pending_downloads[user_id]
            await callback_query.message.delete()
        except Exception as e:
            LOGGER(__name__).error(f"Cleanup error: {e}")
        return await callback_query.answer("Download cancelled.")
    
    await callback_query.answer("Preparing your song...")
    msg = await callback_query.message.edit_text("⬇️ Downloading... Please wait...")
    
    download_info = pending_downloads.get(user_id)
    if not download_info:
        return await msg.edit("Session expired. Please start over.")
    
    try:
        details = download_info["details"]
        file_path = download_info["file_path"]
        
        # Check duration limit
        if details["duration_sec"] > config.DURATION_LIMIT:
            os.remove(file_path)
            if "thumb" in details and os.path.exists(details["thumb"]):
                os.remove(details["thumb"])
            del pending_downloads[user_id]
            return await msg.edit(
                f"❌ Song too long (max {seconds_to_min(config.DURATION_LIMIT)})"
            )
        
        # Send the audio file
        await callback_query.message.reply_audio(
            audio=file_path,
            title=details["title"],
            duration=details["duration_sec"],
            performer=details.get("artist", "Unknown Artist"),
            thumb=details.get("thumb"),
            caption=f"🎧 **{details['title']}**\n🎤 {details.get('artist', 'Unknown')}\n⏳ {details['duration_min']}"
        )
        
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
        if "thumb" in details and os.path.exists(details["thumb"]):
            os.remove(details["thumb"])
        
        await msg.delete()
        await play_logs(callback_query.message, streamtype="JioSaavn Download")
        
    except Exception as e:
        LOGGER(__name__).error(f"Download error: {e}")
        await msg.edit("Failed to send song. Please try again.")
        
        # Clean up files if error occurs
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'details' in locals() and "thumb" in details and os.path.exists(details["thumb"]):
            os.remove(details["thumb"])
    
    # Remove the pending download
    if user_id in pending_downloads:
        del pending_downloads[user_id]
