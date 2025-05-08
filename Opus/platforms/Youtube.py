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

# API Configuration
API_URL = "http://46.250.243.87:1470/youtube"
API_KEY = "1a873582a7c83342f961cc0a177b2b26"

def cookie_txt_file():
    folder_path = f"{os.getcwd()}/cookies"
    filename = f"{os.getcwd()}/cookies/logs.csv"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    cookie_txt_file = random.choice(txt_files)
    with open(filename, 'a') as file:
        file.write(f'Choosen File : {cookie_txt_file}\n')
    return f"""cookies/{str(cookie_txt_file).split("/")[-1]}"""

async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None

    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None

    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

async def get_stream_url(query, video=False):
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            params = {"query": query, "video": video, "api_key": API_KEY}
            response = await client.get(API_URL, params=params)
            if response.status_code != 200:
                return ""
            info = response.json()
            return info.get("stream_url")
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

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return text[offset:offset + length] if offset else None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = 0 if str(duration_min) == "None" else int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # First try to get Dolby Atmos video if available
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "-g",
                "-f",
                "bestvideo[ext=mp4][height<=1080]+bestaudio[acodec=ec-3]/bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
                f"{link}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                return 1, stdout.decode().split("\n")[0]
        except Exception as e:
            logging.warning(f"Dolby Atmos video fetch failed: {e}")
        
        # Fallback to regular quality formats
        quality_formats = [
            "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
            "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]",
            "bestvideo[height<=720][width<=1280]+bestaudio/best",
            "best[height<=720][width<=1280]"
        ]
        
        for quality in quality_formats:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", cookie_txt_file(),
                    "-g",
                    "-f",
                    quality,
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    return 1, stdout.decode().split("\n")[0]
            except Exception as e:
                logging.warning(f"Video fetch failed with {quality}: {e}")
        
        # Final fallback to API
        api_url = await get_stream_url(link, True)
        if api_url:
            return 1, api_url
        return 0, "Failed to fetch video URL"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
            
        try:
            playlist = await shell_cmd(
                f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
            )
            result = playlist.split("\n")
            return [key for key in result if key != ""]
        except Exception as e:
            logging.warning(f"Playlist fetch failed: {e}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }, result["id"]

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        formats_available = []
        try:
            ytdl_opts = {
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "extract_flat": False
            }
            ydl = yt_dlp.YoutubeDL(ytdl_opts)
            with ydl:
                r = ydl.extract_info(link, download=False)
                for format in r["formats"]:
                    try:
                        format_note = format.get("format_note", "").lower()
                        acodec = format.get("acodec", "").lower()
                        
                        # Detect Dolby Atmos (typically EC-3 or AC-4 codec with spatial audio)
                        is_dolby_atmos = (("dash" in format_note or "atmos" in format_note) and 
                                         acodec in ["ec-3", "ac-4"] and
                                         format.get("dynamic_range", "").lower() in ["dolby-vision", "dolby-atmos"])
                        
                        if "audio only" in format_note.lower():
                            formats_available.append({
                                "format": format.get("format"),
                                "filesize": format.get("filesize"),
                                "format_id": format.get("format_id"),
                                "ext": format.get("ext"),
                                "format_note": format.get("format_note"),
                                "abr": format.get("abr", 0),
                                "asr": format.get("asr", 0),
                                "yturl": link,
                                "is_dolby_atmos": is_dolby_atmos,
                                "acodec": acodec,
                                "dynamic_range": format.get("dynamic_range", ""),
                            })
                        else:
                            formats_available.append({
                                "format": format.get("format"),
                                "filesize": format.get("filesize"),
                                "format_id": format.get("format_id"),
                                "ext": format.get("ext"),
                                "format_note": format.get("format_note"),
                                "height": format.get("height", 0),
                                "width": format.get("width", 0),
                                "fps": format.get("fps", 0),
                                "yturl": link,
                                "is_dolby_atmos": is_dolby_atmos,
                                "acodec": acodec,
                                "dynamic_range": format.get("dynamic_range", ""),
                            })
                    except:
                        continue
        except Exception as e:
            logging.warning(f"Formats fetch failed: {e}")

        # Sort formats with Dolby Atmos first, then by quality
        formats_available.sort(
            key=lambda x: (
                -x.get("is_dolby_atmos", False),  # Dolby Atmos first
                x.get("height", 0) or x.get("abr", 0),
                x.get("width", 0),
                x.get("fps", 0),
                x.get("asr", 0)
            ),
            reverse=True
        )
        
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        result = (await VideosSearch(link, limit=10).next()).get("result")
        return (
            result[query_type]["title"],
            result[query_type]["duration"],
            result[query_type]["thumbnails"][0]["url"].split("?")[0],
            result[query_type]["id"],
        )

    async def download(self, link: str, mystic, video: Union[bool, str] = None, 
                     videoid: Union[bool, str] = None, songaudio: Union[bool, str] = None,
                     songvideo: Union[bool, str] = None, format_id: Union[bool, str] = None,
                     title: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
            
        loop = asyncio.get_running_loop()
        
        async def try_cookie_download():
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
                            "ffmpeg_location": "/usr/bin/ffmpeg"
                        }
                        yt_dlp.YoutubeDL(ydl_optssx).download([link])
                        return f"downloads/{title}.mp4"
                    
                    return await loop.run_in_executor(None, dl)
                
                elif songaudio:
                    def dl():
                        # First try to get Dolby Atmos audio if available
                        try:
                            ydl_optssx = {
                                "format": "bestaudio[acodec=ec-3]/bestaudio[abr>=320]/bestaudio/best",
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
                                "audio-quality": "0",
                            }
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            info = ydl.extract_info(link, download=False)
                            
                            # Check for Dolby Atmos (EC-3 codec)
                            if any(f.get('acodec', '').lower() == 'ec-3' for f in info.get('formats', [])):
                                ydl_optssx["format"] = "bestaudio[acodec=ec-3]"
                                ydl_optssx["postprocessors"][0]["preferredcodec"] = "m4a"  # Keep original format for Atmos
                                ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                path = os.path.join("downloads", f"{title}.m4a")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                            
                            # Fallback to high quality audio
                            if any(f.get('abr', 0) >= 320 for f in info.get('formats', [])):
                                ydl.download([link])
                                return f"downloads/{title}.mp3"
                            
                            # Final fallback
                            ydl_optssx["format"] = "bestaudio/best"
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            ydl.download([link])
                            return f"downloads/{title}.mp3"
                        except Exception as e:
                            logging.warning(f"Dolby Atmos audio download failed: {e}")
                            # Standard fallback
                            ydl_optssx = {
                                "format": "bestaudio/best",
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
                                    "preferredquality": "0",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg"
                            }
                            yt_dlp.YoutubeDL(ydl_optssx).download([link])
                            return f"downloads/{title}.mp3"
                    
                    return await loop.run_in_executor(None, dl)
                
                elif video:
                    if await is_on_off(1):
                        def dl():
                            # Try Dolby Atmos video first
                            try:
                                ydl_optssx = {
                                    "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[acodec=ec-3]/bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
                                    "outtmpl": "downloads/%(id)s.%(ext)s",
                                    "geo_bypass": True,
                                    "cookiefile": cookie_txt_file(),
                                    "nocheckcertificate": True,
                                    "quiet": True,
                                    "no_warnings": True,
                                    "ffmpeg_location": "/usr/bin/ffmpeg",
                                    "merge_output_format": "mp4"
                                }
                                x = yt_dlp.YoutubeDL(ydl_optssx)
                                info = x.extract_info(link, False)
                                path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                                if not os.path.exists(path):
                                    x.download([link])
                                return path, True
                            except Exception as e:
                                logging.warning(f"Dolby Atmos video download failed, falling back to standard: {e}")
                                ydl_optssx = {
                                    "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
                                    "outtmpl": "downloads/%(id)s.%(ext)s",
                                    "geo_bypass": True,
                                    "cookiefile": cookie_txt_file(),
                                    "nocheckcertificate": True,
                                    "quiet": True,
                                    "no_warnings": True,
                                    "ffmpeg_location": "/usr/bin/ffmpeg"
                                }
                                x = yt_dlp.YoutubeDL(ydl_optssx)
                                info = x.extract_info(link, False)
                                path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                                if not os.path.exists(path):
                                    x.download([link])
                                return path, True
                        
                        return await loop.run_in_executor(None, dl)
                    else:
                        # Try to get Dolby Atmos stream first
                        proc = await asyncio.create_subprocess_exec(
                            "yt-dlp",
                            "--cookies", cookie_txt_file(),
                            "-g",
                            "-f",
                            "bestvideo[ext=mp4][height<=1080]+bestaudio[acodec=ec-3]/bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
                            f"{link}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        if stdout:
                            return stdout.decode().split("\n")[0], False
                        
                        file_size = await check_file_size(link)
                        if file_size and (file_size / (1024 * 1024)) <= 250:
                            def dl():
                                ydl_optssx = {
                                    "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
                                    "outtmpl": "downloads/%(id)s.%(ext)s",
                                    "geo_bypass": True,
                                    "cookiefile": cookie_txt_file(),
                                    "nocheckcertificate": True,
                                    "quiet": True,
                                    "no_warnings": True,
                                    "ffmpeg_location": "/usr/bin/ffmpeg"
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
                        # Try Dolby Atmos audio first
                        try:
                            ydl_optssx = {
                                "format": "bestaudio[acodec=ec-3]/bestaudio[abr>=320]/bestaudio/best",
                                "outtmpl": "downloads/%(id)s.%(ext)s",
                                "geo_bypass": True,
                                "cookiefile": cookie_txt_file(),
                                "nocheckcertificate": True,
                                "quiet": True,
                                "no_warnings": True,
                                "postprocessors": [{
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "m4a",  # Keep original format for Atmos
                                    "preferredquality": "0",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                                "audio-quality": "0",
                            }
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            info = ydl.extract_info(link, download=False)
                            
                            # Check for Dolby Atmos
                            if any(f.get('acodec', '').lower() == 'ec-3' for f in info.get('formats', [])):
                                path = os.path.join("downloads", f"{info['id']}.m4a")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                            
                            # Fallback to high quality audio
                            if any(f.get('abr', 0) >= 320 for f in info.get('formats', [])):
                                ydl_optssx["postprocessors"][0]["preferredcodec"] = "mp3"
                                ydl_optssx["postprocessors"][0]["preferredquality"] = "320"
                                ydl = yt_dlp.YoutubeDL(ydl_optssx)
                                path = os.path.join("downloads", f"{info['id']}.mp3")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                            
                            # Final fallback
                            ydl_optssx["format"] = "bestaudio/best"
                            ydl_optssx["postprocessors"][0]["preferredquality"] = "0"
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            path = os.path.join("downloads", f"{info['id']}.mp3")
                            if not os.path.exists(path):
                                ydl.download([link])
                            return path, True
                        except Exception as e:
                            logging.warning(f"Dolby Atmos audio download failed: {e}")
                            ydl_optssx = {
                                "format": "bestaudio/best",
                                "outtmpl": "downloads/%(id)s.%(ext)s",
                                "geo_bypass": True,
                                "cookiefile": cookie_txt_file(),
                                "nocheckcertificate": True,
                                "quiet": True,
                                "no_warnings": True,
                                "postprocessors": [{
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3",
                                    "preferredquality": "0",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg"
                            }
                            x = yt_dlp.YoutubeDL(ydl_optssx)
                            info = x.extract_info(link, False)
                            path = os.path.join("downloads", f"{info['id']}.mp3")
                            if not os.path.exists(path):
                                x.download([link])
                            return path, True
                    
                    return await loop.run_in_executor(None, dl)
            
            except Exception as e:
                logging.warning(f"Cookie-based download failed: {e}")
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
