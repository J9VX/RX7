import asyncio
import os
import re
import json
from typing import Union
import glob
import random
import logging
import httpx
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds

API_URL = "http://46.250.243.87:1470/youtube"
API_KEY = "1a873582a7c83342f961cc0a177b2b26"
CONCURRENT_DOWNLOADS = 4  # Number of parallel downloads
CONNECT_TIMEOUT = 10  # Seconds
READ_TIMEOUT = 30  # Seconds

_cookie_file_cache = None

def cookie_txt_file():
    global _cookie_file_cache
    if _cookie_file_cache:
        return _cookie_file_cache
        
    folder_path = f"{os.getcwd()}/cookies"
    filename = f"{os.getcwd()}/cookies/logs.csv"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    
    cookie_txt_file = random.choice(txt_files)
    with open(filename, 'a') as file:
        file.write(f'Choosen File : {cookie_txt_file}\n')
    
    _cookie_file_cache = f"cookies/{str(cookie_txt_file).split('/')[-1]}"
    return _cookie_file_cache

async def check_file_size(link):
    async def get_format_info(link):
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "--no-check-certificates",
                "--quiet",
                "--no-warnings",
                "-J",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode != 0:
                logging.warning(f'Format check error:\n{stderr.decode()}')
                return None
            return json.loads(stdout.decode())
        except asyncio.TimeoutError:
            logging.warning("Format check timed out")
            return None
        except Exception as e:
            logging.warning(f"Format check failed: {e}")
            return None

    info = await get_format_info(link)
    if info is None:
        return None

    formats = info.get('formats', [])
    if not formats:
        logging.warning("No formats found.")
        return None

    return sum(f.get('filesize', 0) for f in formats if 'filesize' in f)

async def shell_cmd(cmd):
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, errorz = await asyncio.wait_for(proc.communicate(), timeout=30)
        if errorz:
            if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
                return out.decode("utf-8")
            return errorz.decode("utf-8")
        return out.decode("utf-8")
    except asyncio.TimeoutError:
        logging.warning("Shell command timed out")
        return ""
    except Exception as e:
        logging.error(f"Shell command failed: {e}")
        return ""

async def get_stream_url(query, video=False):
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
            limits=httpx.Limits(max_connections=CONCURRENT_DOWNLOADS)
        ) as client:
            params = {"query": query, "video": video, "api_key": API_KEY}
            response = await client.get(API_URL, params=params)
            if response.status_code != 200:
                return ""
            return response.json().get("stream_url")
    except Exception as e:
        logging.error(f"API Error: {e}")
        return ""

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self._semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset:entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            duration_sec = 0 if str(result["duration"]) == "None" else int(time_to_seconds(result["duration"]))
            return (
                result["title"],
                result["duration"],
                duration_sec,
                result["thumbnails"][0]["url"].split("?")[0],
                result["id"]
            )
        except Exception as e:
            logging.error(f"Failed to get video details: {e}")
            return None, None, None, None, None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        quality_formats = [
            "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]",
            "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]",
            "bestvideo[height<=720][width<=1280]+bestaudio/best",
            "best[height<=720][width<=1280]"
        ]
        
        async with self._semaphore:
            for quality in quality_formats:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "yt-dlp",
                        "--cookies", cookie_txt_file(),
                        "--no-check-certificates",
                        "--quiet",
                        "--no-warnings",
                        "-g",
                        "-f",
                        quality,
                        link,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                    if stdout:
                        return 1, stdout.decode().split("\n")[0]
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logging.warning(f"Video fetch failed with {quality}: {e}")
                    continue
        
            # Fallback
            api_url = await get_stream_url(link, True)
            if api_url:
                return 1, api_url
            return 0, "Failed to fetch video URL"

    async def download(self, link: str, mystic, video: Union[bool, str] = None, 
                     videoid: Union[bool, str] = None, songaudio: Union[bool, str] = None,
                     songvideo: Union[bool, str] = None, format_id: Union[bool, str] = None,
                     title: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
            
        loop = asyncio.get_running_loop()
        
        async def try_cookie_download():
            async with self._semaphore:
                try:
                    if songvideo:
                        def dl():
                            ydl_optssx = {
                                "format": f"{format_id}+bestaudio/best",
                                "outtmpl": f"downloads/{title}",
                                "geo_bypass": True,
                                "cookiefile": cookie_txt_file(),
                                "nocheckcertificate": True,
                                "quiet": True,
                                "no_warnings": True,
                                "prefer_ffmpeg": True,
                                "merge_output_format": "mp4",
                                "postprocessors": [{
                                    "key": "FFmpegVideoConvertor",
                                    "preferedformat": "mp4"
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                                "concurrent-fragments": CONCURRENT_DOWNLOADS,
                                "http-chunk-size": "1M",
                                "retries": 3,
                                "fragment-retries": 3,
                                "skip-unavailable-fragments": True,
                                "extractor-retries": 3,
                                "buffersize": "1024K",
                                "no-part": True,
                            }
                            yt_dlp.YoutubeDL(ydl_optssx).download([link])
                            return f"downloads/{title}.mp4"
                        
                        return await loop.run_in_executor(None, dl)
                    
                    elif songaudio:
                        def dl():
                            ydl_optssx = {
                                "format": "bestaudio[abr>=320]/bestaudio/best",
                                "outtmpl": f"downloads/{title}.%(ext)s",
                                "geo_bypass": True,
                                "cookiefile": cookie_txt_file(),
                                "nocheckcertificate": True,
                                "quiet": True,
                                "no_warnings": True,
                                "prefer_ffmpeg": True,
                                "postprocessors": [{
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3",
                                    "preferredquality": "320",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                                "concurrent-fragments": CONCURRENT_DOWNLOADS,
                                "http-chunk-size": "1M",
                                "retries": 3,
                                "fragment-retries": 3,
                                "extractor-retries": 3,
                                "buffersize": "1024K",
                                "no-part": True,
                            }
                            try:
                                ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                info = ydl.extract_info(link, download=False)
                                
                                if not any(f.get('abr', 0) >= 320 for f in info.get('formats', [])):
                                    ydl_optssx["format"] = "bestaudio/best"
                                
                                ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                ydl.download([link])
                                return f"downloads/{title}.mp3"
                            except Exception:
                                ydl_optssx["format"] = "bestaudio/best"
                                ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                ydl.download([link])
                                return f"downloads/{title}.mp3"
                        
                        return await loop.run_in_executor(None, dl)
                    
                    elif video:
                        if await is_on_off(1):
                            def dl():
                                ydl_optssx = {
                                    "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]",
                                    "outtmpl": "downloads/%(id)s.%(ext)s",
                                    "geo_bypass": True,
                                    "cookiefile": cookie_txt_file(),
                                    "nocheckcertificate": True,
                                    "quiet": True,
                                    "no_warnings": True,
                                    "ffmpeg_location": "/usr/bin/ffmpeg",
                                    "concurrent-fragments": CONCURRENT_DOWNLOADS,
                                    "http-chunk-size": "1M",
                                    "retries": 3,
                                    "fragment-retries": 3,
                                    "extractor-retries": 3,
                                    "buffersize": "1024K",
                                    "no-part": True,
                                }
                                x = yt_dlp.YoutubeDL(ydl_optssx)
                                info = x.extract_info(link, False)
                                path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                                if not os.path.exists(path):
                                    x.download([link])
                                return path, True
                            
                            return await loop.run_in_executor(None, dl)
                        else:
                            proc = await asyncio.create_subprocess_exec(
                                "yt-dlp",
                                "--cookies", cookie_txt_file(),
                                "--no-check-certificates",
                                "--quiet",
                                "--no-warnings",
                                "-g",
                                "-f",
                                "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]",
                                link,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                            if stdout:
                                return stdout.decode().split("\n")[0], False
                            
                            file_size = await check_file_size(link)
                            if file_size and (file_size / (1024 * 1024)) <= 250:
                                def dl():
                                    ydl_optssx = {
                                        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]",
                                        "outtmpl": "downloads/%(id)s.%(ext)s",
                                        "geo_bypass": True,
                                        "cookiefile": cookie_txt_file(),
                                        "nocheckcertificate": True,
                                        "quiet": True,
                                        "no_warnings": True,
                                        "ffmpeg_location": "/usr/bin/ffmpeg",
                                        "concurrent-fragments": CONCURRENT_DOWNLOADS,
                                        "http-chunk-size": "1M",
                                        "retries": 3,
                                        "fragment-retries": 3,
                                        "extractor-retries": 3,
                                        "buffersize": "1024K",
                                        "no-part": True,
                                    }
                                    x = yt_dlp.YoutubeDL(ydl_optssx)
                                    info = x.extract_info(link, False)
                                    path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                                    if not os.path.exists(path):
                                        x.download([link])
                                    return path, True
                                
                                return await loop.run_in_executor(None, dl)
                    
                    else:  
                        def dl():
                            ydl_optssx = {
                                "format": "bestaudio[abr>=320]/bestaudio/best",
                                "outtmpl": "downloads/%(id)s.%(ext)s",
                                "geo_bypass": True,
                                "cookiefile": cookie_txt_file(),
                                "nocheckcertificate": True,
                                "quiet": True,
                                "no_warnings": True,
                                "postprocessors": [{
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3",
                                    "preferredquality": "320",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                                "concurrent-fragments": CONCURRENT_DOWNLOADS,
                                "http-chunk-size": "1M",
                                "retries": 3,
                                "fragment-retries": 3,
                                "extractor-retries": 3,
                                "buffersize": "1024K",
                                "no-part": True,
                            }
                            try:
                                ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                info = ydl.extract_info(link, download=False)
                                
                                if not any(f.get('abr', 0) >= 320 for f in info.get('formats', [])):
                                    ydl_optssx["format"] = "bestaudio/best"
                                
                                path = os.path.join("downloads", f"{info['id']}.mp3")
                                if not os.path.exists(path):
                                    ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                    ydl.download([link])
                                return path, True
                            except Exception:
                                ydl_optssx["format"] = "bestaudio/best"
                                ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                path = os.path.join("downloads", f"{info['id']}.mp3")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                        
                        return await loop.run_in_executor(None, dl)
                
                except Exception as e:
                    logging.warning(f"[Cookies] download failed: {e}")
                    return None
        
        result = await try_cookie_download()
        if result is not None:
            return result
        
        if songvideo:
            return f"downloads/{title}.mp4", True
        elif songaudio:
            return f"downloads/{title}.mp3", True
        else:
            stream_url = await get_stream_url(link, video)
            return stream_url, False if video else None
