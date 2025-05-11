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

# Configuration
APIS = [
    {"url": "http://46.250.243.87:1470/youtube", "key": "1a873582a7c83342f961cc0a177b2b26"},
    {"url": "http://yt.sanatanixtech.site", "key": "SANATANIxTECH"}
]
JIOSAAVN_API = "https://jiosaavan-mu.vercel.app"

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
    # First try JioSaavn if it's a music query
    if "saavn.com" in query.lower():
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {"query": query}
                response = await client.get(f"{JIOSAAVN_API}/song", params=params)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("media_url", "")
        except Exception as e:
            logging.warning(f"JioSaavn API Error: {e}")

    # Fallback to YouTube APIs
    api = random.choice(APIS)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params = {"query": query, "video": video, "api_key": api["key"]}
            response = await client.get(api["url"], params=params)
            if response.status_code == 200:
                info = response.json()
                return info.get("stream_url", "")
    except Exception as e:
        logging.error(f"API Error with {api['url']}: {e}")
    return ""

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|saavn\.com)"
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
        if "saavn.com" in link.lower():
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    params = {"query": link}
                    response = await client.get(f"{JIOSAAVN_API}/song", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        return (
                            data.get("title", "Unknown"),
                            data.get("duration", "0:00"),
                            int(time_to_seconds(data.get("duration", "0:00"))),
                            data.get("thumbnail", ""),
                            data.get("id", "")
                        )
            except Exception as e:
                logging.warning(f"JioSaavn API Error: {e}")

        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        # Parallel execution for faster response
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return (
                result["title"],
                result["duration"],
                int(time_to_seconds(result["duration"])),
                result["thumbnails"][0]["url"].split("?")[0],
                result["id"],
            )
        except Exception as e:
            logging.error(f"Error getting details: {e}")
            return "Unknown", "0:00", 0, "", ""

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if "saavn.com" in link.lower():
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    params = {"query": link}
                    response = await client.get(f"{JIOSAAVN_API}/song", params=params)
                    if response.status_code == 200:
                        return response.json().get("title", "Unknown")
            except Exception:
                pass

        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        try:
            results = VideosSearch(link, limit=1)
            return (await results.next())["result"][0]["title"]
        except Exception:
            return "Unknown"

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if "saavn.com" in link.lower():
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    params = {"query": link}
                    response = await client.get(f"{JIOSAAVN_API}/song", params=params)
                    if response.status_code == 200:
                        return response.json().get("duration", "0:00")
            except Exception:
                pass

        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        try:
            results = VideosSearch(link, limit=1)
            return (await results.next())["result"][0]["duration"]
        except Exception:
            return "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if "saavn.com" in link.lower():
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    params = {"query": link}
                    response = await client.get(f"{JIOSAAVN_API}/song", params=params)
                    if response.status_code == 200:
                        return response.json().get("thumbnail", "")
            except Exception:
                pass

        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        try:
            results = VideosSearch(link, limit=1)
            return (await results.next())["result"][0]["thumbnails"][0]["url"].split("?")[0]
        except Exception:
            return ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        # Try JioSaavn first if it's a Saavn link
        if "saavn.com" in link.lower():
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    params = {"query": link}
                    response = await client.get(f"{JIOSAAVN_API}/song", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        return 1, data.get("media_url", "")
            except Exception as e:
                logging.warning(f"JioSaavn API Error: {e}")

        # Parallel execution for faster response
        tasks = [
            self._try_cookie_download(link),
            self._try_api_download(link, True)
        ]
        
        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                return result
        
        return 0, "Failed to fetch video URL"

    async def _try_cookie_download(self, link):
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
        return None

    async def _try_api_download(self, link, video):
        api_url = await get_stream_url(link, video)
        if api_url:
            return 1, api_url
        return None

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if "saavn.com" in link.lower() and ("/album/" in link.lower() or "/featured/" in link.lower()):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    params = {"query": link, "limit": limit}
                    response = await client.get(f"{JIOSAAVN_API}/playlist", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        return [song["id"] for song in data.get("songs", [])]
            except Exception as e:
                logging.warning(f"JioSaavn Playlist Error: {e}")
                return []

        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
            
        try:
            playlist = await shell_cmd(
                f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
            )
            return [key for key in playlist.split("\n") if key != ""]
        except Exception as e:
            logging.warning(f"[PLY] Failed to fetch playlist: {e}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if "saavn.com" in link.lower():
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    params = {"query": link}
                    response = await client.get(f"{JIOSAAVN_API}/song", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "title": data.get("title", "Unknown"),
                            "link": link,
                            "vidid": data.get("id", ""),
                            "duration_min": data.get("duration", "0:00"),
                            "thumb": data.get("thumbnail", ""),
                        }, data.get("id", "")
            except Exception as e:
                logging.warning(f"JioSaavn API Error: {e}")

        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }, result["id"]
        except Exception as e:
            logging.error(f"Error getting track info: {e}")
            return {
                "title": "Unknown",
                "link": link,
                "vidid": "",
                "duration_min": "0:00",
                "thumb": "",
            }, ""

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
            
        # Try JioSaavn first if it's a Saavn link
        if "saavn.com" in link.lower():
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    params = {"query": link}
                    response = await client.get(f"{JIOSAAVN_API}/download", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        file_path = os.path.join("downloads", f"Saavn_{data.get('id', '')}.mp3")
                        
                        if not os.path.exists(file_path):
                            async with httpx.AsyncClient() as download_client:
                                async with download_client.stream("GET", data["download_url"]) as resp:
                                    with open(file_path, "wb") as f:
                                        async for chunk in resp.aiter_bytes():
                                            f.write(chunk)
                        
                        return file_path, True
            except Exception as e:
                logging.warning(f"JioSaavn Download Error: {e}")

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
                            
                            if any(f.get('acodec', '').lower() == 'opus' for f in info.get('formats', [])):
                                path = os.path.join("downloads", f"{title}.opus")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                            
                            ydl_optssx["postprocessors"][0]["preferredcodec"] = "mp3"
                            ydl_optssx["postprocessors"][0]["preferredquality"] = "320"
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            path = os.path.join("downloads", f"{title}.mp3")
                            if not os.path.exists(path):
                                ydl.download([link])
                            return path, True
                        except Exception as e:
                            logging.warning(f"[AUDIO] Failed to get high quality audio: {e}")
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
                            
                            if any(f.get('acodec', '').lower() == 'opus' for f in info.get('formats', [])):
                                path = os.path.join("downloads", f"{info['id']}.opus")
                                if not os.path.exists(path):
                                    ydl.download([link])
                                return path, True
                            
                            ydl_optssx["postprocessors"][0]["preferredcodec"] = "mp3"
                            ydl_optssx["postprocessors"][0]["preferredquality"] = "320"
                            ydl = yt_dlp.YoutubeDL(ydl_optssx)
                            path = os.path.join("downloads", f"{info['id']}.mp3")
                            if not os.path.exists(path):
                                ydl.download([link])
                            return path, True
                        except Exception as e:
                            logging.warning(f"[AUDIO] Failed to get high quality audio: {e}")
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
        
        # Try cookie download first
        result = await try_cookie_download()
        if result is not None:
            return result
        
        # Fallback to API
        if songvideo:
            return f"downloads/{title}.mp4", True
        elif songaudio:
            return f"downloads/{title}.mp3", True
        else:
            stream_url = await get_stream_url(link, video)
            return stream_url, False if video else None
