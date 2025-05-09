import asyncio
import speedtest
from pyrogram import filters
from pyrogram.types import Message
from speedtest import ConfigRetrievalError, Speedtest

from Opus import app
from Opus.misc import SUDOERS
from Opus.utils.decorators.language import language

def get_readable_file_size(size_in_bytes):
    """Convert bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

async def run_speedtest(m: Message):
    try:
        st = Speedtest()
        await m.edit_text("<blockquote><b>ꜰɪɴᴅɪɴɢ ʙᴇꜱᴛ ꜱᴇʀᴠᴇʀ...</b></blockquote>")
        st.get_best_server()
        
        await m.edit_text("<blockquote><b>ᴛᴇꜱᴛɪɴɢ ᴅᴏᴡɴʟᴏᴀᴅ ꜱᴘᴇᴇᴅ...</b></blockquote>")
        st.download()
        
        await m.edit_text("<blockquote><b>ᴛᴇꜱᴛɪɴɢ ᴜᴘʟᴏᴀᴅ ꜱᴘᴇᴇᴅ...</b></blockquote>")
        st.upload()
        
        results = st.results.dict()
        return results, None
        
    except ConfigRetrievalError:
        return None, "<blockquote><b>ᴜɴᴀʙʟᴇ ᴛᴏ ᴄᴏɴɴᴇᴄᴛ ᴛᴏ ꜱᴇʀᴠᴇʀꜱ ᴛᴏ ᴛᴇꜱᴛ ʟᴀᴛᴇɴᴄʏ.</b></blockquote>"
    except Exception as e:
        return None, f"<blockquote><b>ᴇʀʀᴏʀ: {str(e)}</b></blockquote>"

@app.on_message(filters.command(["speedtest", "spt"]) & SUDOERS)
@language
async def speedtest_command(client, message: Message, _):
    m = await message.reply_text("<blockquote><b>ꜱᴛᴀʀᴛɪɴɢ ꜱᴘᴇᴇᴅᴛᴇꜱᴛ....</b></blockquote>")
    
    results, error = await run_speedtest(m)
    
    if error:
        await m.edit_text(error)
        return
    
    try:
        string_speed = f"""
<blockquote><b><u>ꜱᴘᴇᴇᴅᴛᴇꜱᴛ ɪɴꜰᴏ</u></b>
<b>ᴜᴘʟᴏᴀᴅ: <code>{get_readable_file_size(results['upload'] / 8)}/s</code></b>
<b>ᴅᴏᴡɴʟᴏᴀᴅ: <code>{get_readable_file_size(results['download'] / 8)}/s</code></b>
<b>ᴘɪɴɢ: <code>{results['ping']} ᴍꜱ</code></b>
<b>ᴅᴀᴛᴀ ꜱᴇɴᴛ: <code>{get_readable_file_size(int(results['bytes_sent']))}</code></b>
<b>ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ: <code>{get_readable_file_size(int(results['bytes_received']))}</code></b></blockquote>\n<blockquote><b><u>ꜱᴇʀᴠᴇʀ ɪɴꜰᴏ</u></b>
<b>ɴᴀᴍᴇ: <code>{results['server']['name']}</code></b>
<b>ᴄᴏᴜɴᴛʀʏ: <code>{results['server']['country']}, {results['server']['cc']}</code></b>
<b>ꜱᴘᴏɴꜱᴏʀ: <code>{results['server']['sponsor']}</code></b>
<b>ʟᴀᴛᴇɴᴄʏ: <code>{results['server']['latency']}</code></b>
<b>ʟᴀᴛɪᴛᴜᴅᴇ: <code>{results['server']['lat']}</code></b>
<b>ʟᴏɴɢɪᴛᴜᴅᴇ: <code>{results['server']['lon']}</code></b></blockquote>\n<blockquote><b><u>ᴄʟɪᴇɴᴛ ɪɴꜰᴏ</u></b>
<b>ɪᴘ ᴀᴅᴅʀᴇꜱꜱ: <code>ʜɪᴅᴅᴇɴ</code></b>
<b>ʟᴀᴛɪᴛᴜᴅᴇ: <code>{results['client']['lat']}</code></b>
<b>ʟᴏɴɢɪᴛᴜᴅᴇ: <code>{results['client']['lon']}</code></b>
<b>ᴄᴏᴜɴᴛʀʏ: <code>{results['client']['country']}</code></b>
<b>ɪꜱᴘ: <code>{results['client']['isp']}</code></b>
<b>ɪꜱᴘ ʀᴀᴛɪɴɢ: <code>{results['client']['isprating']}</code></b></blockquote>
"""
        await m.edit_text(string_speed)
        
    except Exception as e:
        await m.edit_text(f"<blockquote><b>ᴇʀʀᴏʀ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʀᴇꜱᴜʟᴛꜱ: {str(e)}</b></blockquote>")
