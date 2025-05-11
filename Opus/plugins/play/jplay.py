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
    if len(message.command) < 2:
        return await message.reply_text("Please provide a JioSaavn song URL or search query after the command.")
    
    query = message.text.split(None, 1)[1]
    user_id = message.from_user.id
    
    # Check if it's a URL
    if await Platform.saavn.valid(query):
        if await Platform.saavn.is_song(query):
            try:
                # Download the song to get details (since get_info isn't available)
                file_path, details = await Platform.saavn.download(query)
                
                # Create confirmation buttons
                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Yes", callback_data=f"download_{user_id}_yes"),
                        InlineKeyboardButton("❌ No", callback_data=f"download_{user_id}_no")
                    ]
                ])
                
                # Store the details temporarily
                pending_downloads[user_id] = {
                    "file_path": file_path,
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
        # Search functionality not available since Platform.saavn.search doesn't exist
        return await message.reply_text("Please provide a direct JioSaavn song URL. Search functionality is not available.")

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
            # Clean up the downloaded file if user cancels
            if user_id in pending_downloads:
                if os.path.exists(pending_downloads[user_id]["file_path"]):
                    os.remove(pending_downloads[user_id]["file_path"])
                if "thumb" in pending_downloads[user_id]["details"] and os.path.exists(pending_downloads[user_id]["details"]["thumb"]):
                    os.remove(pending_downloads[user_id]["details"]["thumb"])
                del pending_downloads[user_id]
            await callback_query.message.delete()
        except Exception as e:
            LOGGER(__name__).error(f"Error cleaning up: {e}")
        return await callback_query.answer("Download cancelled.")
    
    await callback_query.answer("Starting download...")
    msg = await callback_query.message.edit_text("⬇️ Preparing song...")
    
    # Get the stored details
    download_info = pending_downloads.get(user_id)
    if not download_info:
        return await msg.edit("Session expired. Please try again.")
    
    try:
        details = download_info["details"]
        file_path = download_info["file_path"]
        
        # Check duration limit
        if details["duration_sec"] > config.DURATION_LIMIT:
            os.remove(file_path)
            if os.path.exists(details.get("thumb", "")):
                os.remove(details["thumb"])
            del pending_downloads[user_id]
            return await msg.edit(
                f"Song is too long. Max allowed: {seconds_to_min(config.DURATION_LIMIT)}"
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
        await msg.edit("Failed to send the song. Please try again later.")
        
        # Clean up if any partial files exist
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'details' in locals() and "thumb" in details and os.path.exists(details["thumb"]):
            os.remove(details["thumb"])
    
    # Remove the pending download
    if user_id in pending_downloads:
        del pending_downloads[user_id]
