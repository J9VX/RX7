import os
import asyncio
import time
import requests
import yt_dlp
from youtube_search import YoutubeSearch
from urllib.parse import urlparse

from pyrogram import Client, filters
from pyrogram.types import Message

from Opus import app
from Opus.utils.extraction import extract_user

# Spam protection configuration
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5
user_last_message_time = {}
user_command_count = {}

async def check_spam(user_id: int) -> bool:
    """Check if user is spamming commands."""
    current_time = time.time()
    last_message_time = user_last_message_time.get(user_id, 0)
    
    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            return True
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time
    return False

async def delete_message_with_delay(message: Message, text: str, delay: int = 3):
    """Send a temporary message that deletes after delay."""
    msg = await message.reply_text(text)
    await asyncio.sleep(delay)
    await msg.delete()
    return

async def download_thumbnail(url: str, filename: str) -> bool:
    """Download thumbnail image from URL."""
    try:
        response = requests.get(url, allow_redirects=True, timeout=10)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Failed to download thumbnail: {e}")
        return False

@app.on_message(filters.command("song"))
async def download_song(_, message: Message):
    """Download and send YouTube song as audio."""
    user_id = message.from_user.id
    
    if await check_spam(user_id):
        await delete_message_with_delay(
            message,
            f"**{message.from_user.mention} Please don't spam, try again after {SPAM_WINDOW_SECONDS} sec**"
        )
        return

    if len(message.command) < 2:
        await message.reply_text("**Please provide a song name to search.**")
        return

    query = " ".join(message.command[1:])
    m = await message.reply("**🔄 Searching...**")
    
    ydl_opts = {
        "format": "bestaudio[ext=m4a]",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            await m.edit("**⚠️ No results found. Please check the song name.**")
            return

        video = results[0]
        link = f"https://youtube.com{video['url_suffix']}"
        title = video["title"][:40]
        thumbnail = video["thumbnails"][0]
        duration = video["duration"]
        views = video.get("views", "N/A")
        channel_name = video.get("channel", "N/A")

        thumb_name = f"{title}.jpg"
        await download_thumbnail(thumbnail, thumb_name)

        await m.edit("**📥 Downloading...**")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=False)
            audio_file = ydl.prepare_filename(info_dict)
            ydl.process_info(info_dict)

        # Convert duration to seconds
        duration_parts = duration.split(":")
        duration_sec = sum(int(part) * 60 ** i for i, part in enumerate(reversed(duration_parts)))

        await m.edit("**📤 Uploading...**")
        
        await message.reply_audio(
            audio_file,
            thumb=thumb_name,
            title=title,
            caption=(
                f"**{title}**\n"
                f"➤ Requested by: {message.from_user.mention}\n"
                f"➤ Views: {views}\n"
                f"➤ Channel: {channel_name}"
            ),
            duration=duration_sec,
        )
        await m.delete()

    except Exception as e:
        await m.edit("**❌ An error occurred while processing your request.**")
        print(f"Error in download_song: {e}")

    finally:
        # Cleanup files
        for filename in [audio_file, thumb_name]:
            try:
                if filename and os.path.exists(filename):
                    os.remove(filename)
            except Exception as e:
                print(f"Error removing file {filename}: {e}")

@app.on_message(filters.command(["ig", "reel"], prefixes=["/", "!", "."]))
async def download_instagram_reel(client: Client, message: Message):
    """Download and send Instagram reels."""
    user_id = message.from_user.id
    
    if await check_spam(user_id):
        await delete_message_with_delay(
            message,
            f"**{message.from_user.mention} Please don't spam, try again after {SPAM_WINDOW_SECONDS} sec**"
        )
        return

    if len(message.command) < 2:
        await message.reply_text("**Please provide an Instagram reel URL.**")
        return

    url = message.command[1]
    
    if not url.startswith(("https://www.instagram.com/reel/", "https://instagram.com/reel/")):
        await message.reply_text("**Please provide a valid Instagram reel URL.**")
        return

    try:
        # First try the direct method
        modified_url = url.split(".", 1)[0] + ".dd" + url.split(".", 1)[1]
        
        for method in ["video", "photo", "document"]:
            try:
                send_func = getattr(message, f"reply_{method}")
                await send_func(modified_url)
                return
            except Exception:
                continue

        # If direct methods fail, try API approach
        await message.reply_text("**🔍 Trying alternative method...**")
        
        api_url = f"https://lexica-api.vercel.app/download/instagram?url={url}"
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == 2:
            media_urls = data.get("content", {}).get("mediaUrls", [])
            if media_urls:
                video_url = media_urls[0].get("url")
                if video_url:
                    await message.reply_video(video_url)
                    return

        await message.reply_text("**❌ Could not download the reel. The account might be private.**")

    except requests.exceptions.RequestException as e:
        await message.reply_text("**❌ Failed to connect to the download service.**")
        print(f"Instagram download error: {e}")
    except Exception as e:
        await message.reply_text("**❌ An error occurred while processing the reel.**")
        print(f"Instagram download error: {e}")
