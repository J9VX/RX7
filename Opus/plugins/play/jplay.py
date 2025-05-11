import os
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import config
from config import BANNED_USERS
from Opus import app
from Opus.utils import seconds_to_min
import asyncio
import aiohttp

SPOTIFY_CLIENT_ID = "2d3fd5ccdd3d43dda6f17864d8eb7281"
SPOTIFY_CLIENT_SECRET = "48d311d8910a4531ae81205e1f754d27"

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Path to cookies file (downloaded from GitHub)
COOKIES_PATH = "cookies.txt"

# Ensure cookies file exists
if not os.path.exists(COOKIES_PATH):
    # Download cookies file from GitHub
    async def download_cookies():
        url = "https://raw.githubusercontent.com/J9VX/RX7/main/cookies/cookies.txt"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(COOKIES_PATH, 'wb') as f:
                        f.write(await response.read())
    
    asyncio.run(download_cookies())

# YouTube download options with cookies
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
    'cookiefile': COOKIES_PATH,
    'extract_flat': True,
    'retries': 10,
    'fragment-retries': 10,
    'extractor-retries': 10,
    'ignoreerrors': True,
    'no-check-certificate': True,
    'geo-bypass': True,
    'force-ipv4': True,
    'noplaylist': True,
    'socket-timeout': 10,
    'source_address': '0.0.0.0'
}

async def search_spotify(query, limit=5):
    """Search songs on Spotify"""
    try:
        results = sp.search(q=query, limit=limit, type='track')
        return results['tracks']['items']
    except Exception as e:
        print(f"Spotify search error: {e}")
        return []

async def download_youtube_audio(query):
    """Download audio from YouTube with cookies"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            if 'entries' in info and info['entries']:
                entry = info['entries'][0]
                return {
                    'filepath': ydl.prepare_filename(entry),
                    'title': entry.get('title', 'Unknown Track'),
                    'duration': entry.get('duration', 0),
                    'artist': entry.get('uploader', 'Unknown Artist'),
                    'thumbnail': entry.get('thumbnail', '')
                }
    except Exception as e:
        print(f"YouTube download error: {e}")
    return None

@app.on_message(filters.command(["song"]) & filters.group & ~BANNED_USERS)
async def song_search(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Please provide a song name to search")
    
    query = " ".join(message.command[1:])
    msg = await message.reply_text(f"🔍 Searching for: {query}")
    
    try:
        results = await search_spotify(query)
        if not results:
            return await msg.edit_text("No results found")
        
        buttons = []
        for idx, track in enumerate(results, 1):
            artists = ", ".join([a['name'] for a in track['artists']])
            duration = seconds_to_min(track['duration_ms']//1000)
            buttons.append([
                InlineKeyboardButton(
                    f"{idx}. {track['name'][:20]} - {artists[:15]} ({duration})",
                    callback_data=f"dl_{track['id']}"
                )
            ])
        
        await msg.edit_text(
            f"🎵 Search Results for: {query}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await msg.edit_text("Failed to search for songs")
        print(f"Search error: {e}")

@app.on_callback_query(filters.regex(r"^dl_(.+)$"))
async def download_handler(client, callback_query):
    track_id = callback_query.matches[0].group(1)
    await callback_query.answer("Preparing download...")
    
    try:
        track = sp.track(track_id)
        query = f"{track['name']} {track['artists'][0]['name']}"
        
        msg = await callback_query.message.reply_text(f"⬇️ Downloading: {query}")
        
        # Download from YouTube with cookies
        audio_info = await download_youtube_audio(query)
        if not audio_info:
            return await msg.edit_text("Failed to download song")
        
        # Send audio file
        await callback_query.message.reply_audio(
            audio=audio_info['filepath'],
            title=track['name'],
            duration=audio_info['duration'],
            performer=track['artists'][0]['name'],
            thumb=track['album']['images'][0]['url'] if track['album']['images'] else None,
            caption=f"🎵 {track['name']}\n🎤 {', '.join(a['name'] for a in track['artists'])}"
        )
        
        # Cleanup
        if os.path.exists(audio_info['filepath']):
            os.remove(audio_info['filepath'])
        await msg.delete()
        
    except Exception as e:
        await callback_query.message.reply_text("Failed to process download")
        print(f"Download error: {e}")
