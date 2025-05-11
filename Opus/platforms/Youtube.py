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

APIS = [
    {"url": "http://46.250.243.87:1470/youtube", "key": "1a873582a7c83342f961cc0a177b2b26"},
    {"url": "http://yt.sanatanixtech.site", "key": "SANATANIxTECH"}
]

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

async def get_stream_url(query, video=False):
    api = random.choice(APIS)  # Randomly select an API
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            params = {"query": query, "video": video, "api_key": api["key"]}
            response = await client.get(api["url"], params=params)
            if response.status_code != 200:
                return ""
            info = response.json()
            return info.get("stream_url", "")
    except Exception as e:
        logging.error(f"API Error with {api['url']}: {e}")
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
            
        # First try with cookies (EXACT CODE FROM PROVIDED EXAMPLE)
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                f"{link}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                return 1, stdout.decode().split("\n")[0]
        except Exception as e:
            logging.warning(f"Cookie-based video fetch failed: {e}")
        
        # Fallback to API
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
            logging.warning(f"[PLY] Failed to fetch playlist: {e}")
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
                        
                        # Prioritize high-quality audio formats
                        is_high_quality_audio = (
                            "audio only" in format_note and 
                            acodec in ["opus", "flac", "alac"] or
                            format.get("abr", 0) >= 256
                        )
                        
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
                                "is_high_quality": is_high_quality_audio,
                                "acodec": acodec,
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
                            })
                    except:
                        continue
        except Exception as e:
            logging.warning(f"[FMT] Failed to fetch formats: {e}")

        # Sort formats - prioritize high quality audio and standard video
        formats_available.sort(
            key=lambda x: (
                -x.get("is_high_quality", False),
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
                            "format": f"{format_id}+bestaudio[acodec=opus]/best",
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
                        # First try highest quality audio formats
                        try:
                            ydl_optssx = {
                                "format": "bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[abr>=320]/bestaudio/best",
                                "outtmpl": f"downloads/{title}.%(ext)s",
                                "geo_bypass": True,
                                "cookiefile": cookie_txt_file(),
                                "nocheckcertificate": True,
                                "quiet": True,
                                "no_warnings": True,
                                "prefer_ffmpeg": True,
                                "postprocessors": [{
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "opus",
                                    "preferredquality": "0",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                            }
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            info = ydl.extract_info(link, download=False)
                            
                            # Check for Opus (highest quality)
                            if any(f.get('acodec', '').lower() == 'opus' for f in info.get('formats', [])):
                                path = os.path.join("downloads", f"{title}.opus")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                            
                            # Fallback to 320kbps MP3
                            ydl_optssx["postprocessors"][0]["preferredcodec"] = "mp3"
                            ydl_optssx["postprocessors"][0]["preferredquality"] = "320"
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            path = os.path.join("downloads", f"{title}.mp3")
                            if not os.path.exists(path):
                                ydl.download([link])
                            return path, True
                        except Exception as e:
                            logging.warning(f"[AUDIO] Failed to get high quality audio: {e}")
                            # Final fallback
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
                                    "preferredquality": "192",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg"
                            }
                            yt_dlp.YoutubeDL(ydl_optssx).download([link])
                            return f"downloads/{title}.mp3", True
                    
                    return await loop.run_in_executor(None, dl)
                
                elif video:
                    if await is_on_off(1):
                        def dl():
                            ydl_optssx = {
                                "format": "bestvideo[height<=480][ext=mp4]+bestaudio[acodec=opus]/bestvideo[height<=480]+bestaudio/best",
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
                        
                        return await loop.run_in_executor(None, dl)
                    else:
                        proc = await asyncio.create_subprocess_exec(
                            "yt-dlp",
                            "--cookies", cookie_txt_file(),
                            "-g",
                            "-f",
                            "best[height<=?720][width<=?1280]",
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
                                    "format": "bestvideo[height<=480][ext=mp4]+bestaudio/best",
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
                        # Audio-only download with highest quality priority
                        try:
                            ydl_optssx = {
                                "format": "bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[abr>=320]/bestaudio/best",
                                "outtmpl": "downloads/%(id)s.%(ext)s",
                                "geo_bypass": True,
                                "cookiefile": cookie_txt_file(),
                                "nocheckcertificate": True,
                                "quiet": True,
                                "no_warnings": True,
                                "postprocessors": [{
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "opus",
                                    "preferredquality": "0",
                                }],
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                            }
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            info = ydl.extract_info(link, download=False)
                            
                            # Check for Opus (highest quality)
                            if any(f.get('acodec', '').lower() == 'opus' for f in info.get('formats', [])):
                                path = os.path.join("downloads", f"{info['id']}.opus")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                            
                            # Fallback to 320kbps MP3
                            ydl_optssx["postprocessors"][0]["preferredcodec"] = "mp3"
                            ydl_optssx["postprocessors"][0]["preferredquality"] = "320"
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            path = os.path.join("downloads", f"{info['id']}.mp3")
                            if not os.path.exists(path):
                                ydl.download([link])
                            return path, True
                        except Exception as e:
                            logging.warning(f"[AUDIO] Failed to get high quality audio: {e}")
                            # Final fallback
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
                                    "preferredquality": "192",
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
                logging.warning(f"[DL] Download failed: {e}")
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

this is my youtube.py can you add jiosaavan-mu.vercel.app url to fetch tracks only and can you make th youtube.py like faster fetch like faster switch cookies to api api too cookies anf else jiosaavan-mu.vercel.app


here it the example to fetch songs from this jiosaavan-mu.vercel.app

import os

import aiohttp
import yt_dlp

from io import BytesIO
from PIL import Image

from config import seconds_to_time
from Opus.utils.decorators import asyncify


class Saavn:

    @staticmethod
    async def valid(url: str) -> bool:
        return "jiosaavn.com" in url

    @staticmethod
    async def is_song(url: str) -> bool:
        return "song" in url and not "/featured/" in url and "/album/" not in url

    @staticmethod
    async def is_playlist(url: str) -> bool:
        return "/featured/" in url or "/album" in url

    def clean_url(self, url: str) -> str:
        if "#" in url:
            url = url.split("#")[0]
        return url

    @asyncify
    def playlist(self, url, limit):
        clean_url = self.clean_url(url)
        ydl_opts = {
            "extract_flat": True,
            "force_generic_extractor": True,
            "quiet": True,
        }
        song_info = []
        count = 0
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                playlist_info = ydl.extract_info(clean_url, download=False)
                for entry in playlist_info["entries"]:
                    if count == limit:
                        break
                    duration_sec = entry.get("duration", 0)
                    info = {
                        "title": entry["title"],
                        "duration_sec": duration_sec,
                        "duration_min": seconds_to_time(duration_sec),
                        "thumb": entry.get("thumbnail", ""),
                        "url": self.clean_url(entry["webpage_url"]),
                    }
                    song_info.append(info)
                    count += 1
            except Exception:
                pass
        return song_info

    async def info(self, url):
        url = self.clean_url(url)

        async with aiohttp.ClientSession() as session:
            if "jiosaavn.com" in url:
                api_url = "https://saavn.dev/api/songs"
                params = {"link": url, "limit": 1}
            else:
                api_url = "https://saavn.dev/api/search/songs"
                params = {"query": url, "limit": 1}

            async with session.get(api_url, params=params) as response:
                data = await response.json()

                if "jiosaavn.com" in url:
                    info = data["data"][0]  # For Saavn URLs
                else:
                    info = data["data"]["results"][0]  # For search queries

                thumb_url = info["image"][-1]["url"]
                thumb_path = await self._resize_thumb(thumb_url, info["id"])

                return {
                    "title": info["name"],
                    "duration_sec": info.get("duration", 0),
                    "duration_min": seconds_to_time(info.get("duration", 0)),
                    "thumb": thumb_path,
                    "url": self.clean_url(info["url"]),
                    "_download_url": info["downloadUrl"][-1]["url"],
                    "_id": info["id"],
                }

    async def download(self, url):
        details = await self.info(url)
        file_path = os.path.join("downloads", f"Saavn_{details['_id']}.mp3")

        if not os.path.exists(file_path):
            async with aiohttp.ClientSession() as session:
                async with session.get(details["_download_url"]) as resp:
                    if resp.status == 200:
                        with open(file_path, "wb") as f:
                            while chunk := await resp.content.read(1024):
                                f.write(chunk)
                        print(f"Downloaded: {file_path}")
                    else:
                        raise ValueError(
                            f"Failed to download {details['_download_url']}. HTTP Status: {resp.status}"
                        )

        details["filepath"] = file_path
        return file_path, details

    async def _resize_thumb(self, thumb_url, _id, size=(1280, 720)):
        thumb_path = os.path.join("cache", f"Thumb_{_id}.jpg")

        if os.path.exists(thumb_path):
            return thumb_path

        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as response:
                img_data = await response.read()

        img = Image.open(BytesIO(img_data))
        scale_factor = size[1] / img.height
        new_width = int(img.width * scale_factor)
        new_height = size[1]

        resized_img = img.resize((new_width, new_height), Image.LANCZOS)
        new_img = Image.new("RGB", size, (0, 0, 0))
        new_img.paste(resized_img, ((size[0] - new_width) // 2, 0))

        new_img.save(thumb_path, format="JPEG")
        return thumb_path
