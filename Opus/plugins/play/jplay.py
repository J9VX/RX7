import random
import string
import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import BadRequest
import config
from config import BANNED_USERS, lyrical
from Opus import app, LOGGER
from Opus import Platform
from Opus.utils import seconds_to_min
from Opus.utils.logger import play_logs

# Dictionary to store pending download confirmations
pending_downloads = {}

@app.on_message(
    filters.command(["jsong"]) & filters.group & ~BANNED_USERS
)
async def jsong_command(client, message: Message):
    # Get translation function if needed (replace with your actual translation system)
    _ = lambda x: x
    
    if len(message.command) < 2:
        return await message.reply_text("Please provide a JioSaavn song URL or search query after the command.")
    
    query = message.text.split(None, 1)[1]
    user_id = message.from_user.id
    
    # Check if it's a URL
    if await Platform.saavn.valid(query):
        if await Platform.saavn.is_song(query):
            try:
                # Get song details without downloading
                details = await Platform.saavn.get_info(query)
                if not details:
                    return await message.reply_text("Could not fetch song details.")
                
                # Create confirmation buttons
                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Yes", callback_data=f"download_{user_id}_yes"),
                        InlineKeyboardButton("❌ No", callback_data=f"download_{user_id}_no")
                    ]
                ])
                
                # Store the details temporarily
                pending_downloads[user_id] = {
                    "url": query,
                    "details": details,
                    "message_id": message.id
                }
                
                # Ask for confirmation
                await message.reply_text(
                    f"Do you want to download:\n\n🎵 **{details['title']}**\n🎤 {details.get('artist', 'Unknown Artist')}\n⏳ {details['duration_min']}",
                    reply_markup=buttons
                )
                
            except Exception as e:
                LOGGER(__name__).error(f"Error getting song info: {e}")
                return await message.reply_text("Failed to get song information.")
        else:
            return await message.reply_text("Only single song URLs are supported.")
    else:
        # Handle search query
        try:
            search_results = await Platform.saavn.search(query, limit=5)
            if not search_results:
                return await message.reply_text("No results found for your search.")
            
            # Create buttons for search results
            buttons = []
            for i, result in enumerate(search_results[:5], start=1):
                buttons.append(
                    [InlineKeyboardButton(
                        f"{i}. {result['title']} - {result.get('artist', 'Unknown')} ({result['duration_min']})",
                        callback_data=f"song_select_{user_id}_{result['url']}"
                    )]
                )
            
            await message.reply_text(
                "🔍 Search Results:\nSelect a song to download:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
        except Exception as e:
            LOGGER(__name__).error(f"Search error: {e}")
            return await message.reply_text("Failed to search for songs.")

@app.on_callback_query(filters.regex(r"^download_(\d+)_(yes|no)$"))
async def download_confirmation(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    action = callback_query.matches[0].group(2)
    original_user = callback_query.from_user.id
    
    # Verify the user clicking is the same who requested
    if original_user != user_id:
        return await callback_query.answer("This confirmation isn't for you!", show_alert=True)
    
    if action == "no":
        try:
            await callback_query.message.delete()
        except:
            pass
        return await callback_query.answer("Download cancelled.")
    
    await callback_query.answer("Starting download...")
    msg = await callback_query.message.edit_text("⬇️ Downloading song...")
    
    # Get the stored details
    download_info = pending_downloads.get(user_id)
    if not download_info:
        return await msg.edit("Session expired. Please try again.")
    
    try:
        # Download the song
        file_path, full_details = await Platform.saavn.download(download_info["url"])
        
        # Check duration limit
        if full_details["duration_sec"] > config.DURATION_LIMIT:
            os.remove(file_path)
            return await msg.edit(
                f"Song is too long. Max allowed: {seconds_to_min(config.DURATION_LIMIT)}"
            )
        
        # Send the audio file
        await callback_query.message.reply_audio(
            audio=file_path,
            title=full_details["title"],
            duration=full_details["duration_sec"],
            performer=full_details.get("artist", "Unknown Artist"),
            thumb=full_details["thumb"],
            caption=f"🎧 **{full_details['title']}**\n🎤 {full_details.get('artist', 'Unknown')}\n⏳ {full_details['duration_min']}"
        )
        
        # Clean up
        os.remove(file_path)
        if os.path.exists(full_details["thumb"]):
            os.remove(full_details["thumb"])
        
        await msg.delete()
        await play_logs(callback_query.message, streamtype="JioSaavn Download")
        
    except Exception as e:
        LOGGER(__name__).error(f"Download error: {e}")
        await msg.edit("Failed to download the song. Please try again later.")
        
        # Clean up if any partial files exist
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'full_details' in locals() and os.path.exists(full_details.get("thumb", "")):
            os.remove(full_details["thumb"])
    
    # Remove the pending download
    if user_id in pending_downloads:
        del pending_downloads[user_id]

@app.on_callback_query(filters.regex(r"^song_select_(\d+)_(.+)$"))
async def song_selection(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    song_url = callback_query.matches[0].group(2)
    original_user = callback_query.from_user.id
    
    if original_user != user_id:
        return await callback_query.answer("This selection isn't for you!", show_alert=True)
    
    await callback_query.answer("Getting song info...")
    
    try:
        details = await Platform.saavn.get_info(song_url)
        if not details:
            return await callback_query.message.edit_text("Could not fetch song details.")
        
        # Create confirmation buttons
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"download_{user_id}_yes"),
                InlineKeyboardButton("❌ No", callback_data=f"download_{user_id}_no")
            ]
        ])
        
        # Store the details temporarily
        pending_downloads[user_id] = {
            "url": song_url,
            "details": details,
            "message_id": callback_query.message.id
        }
        
        # Edit the message with confirmation
        await callback_query.message.edit_text(
            f"Do you want to download:\n\n🎵 **{details['title']}**\n🎤 {details.get('artist', 'Unknown Artist')}\n⏳ {details['duration_min']}",
            reply_markup=buttons
        )
        
    except Exception as e:
        LOGGER(__name__).error(f"Song selection error: {e}")
        await callback_query.message.edit_text("Failed to process your selection. Please try again.")
