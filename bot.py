import asyncio
import os
from datetime import datetime
import time

import youtube_dl
from pornhub_api import PornhubApi
from pornhub_api.backends.aiohttp import AioHttpBackend
from pyrogram import Client, filters
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, InlineQuery,
                            InlineQueryResultArticle, InputTextMessageContent,
                            Message)
from youtube_dl.utils import DownloadError

from config import Config
from helpers import download_progress_hook

# বট কনফিগারেশন
app = Client("pornhub_bot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            log_channel_id=Config.LOG_CHANNEL_ID)

# লগ চ্যানেলের আইডি


if not os.path.exists("downloads"):
    os.makedirs("downloads")


# টাইম সিঙ্ক্রোনাইজ করার জন্য একটি ফাংশন
async def sync_time():
    try:
        os.system("ntpdate time.google.com")
    except Exception as e:
        print(f"Time Sync Error: {e}")


btn1 = InlineKeyboardButton("Search Here", switch_inline_query_current_chat="")
btn2 = InlineKeyboardButton("Go Inline", switch_inline_query="")

active_list = []


async def send_log(action, details, client):
    """Send logs to the log channel."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"**[{timestamp}]**\n**Action:** {action}\n**Details:** {details}"
    await client.send_message(LOG_CHANNEL_ID, log_msg)


async def run_async(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)


@app.on_inline_query()
async def search(client, inline_query: InlineQuery):
    query = inline_query.query
    backend = AioHttpBackend()
    api = PornhubApi(backend=backend)
    results = []

    try:
        src = await api.search.search(query)
    except ValueError:
        results.append(InlineQueryResultArticle(
            title="No Such Videos Found!",
            description="No Results Found. Please Try Again.",
            input_message_content=InputTextMessageContent(
                message_text="No Such Videos Found!"
            )
        ))
        await inline_query.answer(results, switch_pm_text="Search Results", switch_pm_parameter="start")
        return

    videos = src.videos
    await backend.close()

    for vid in videos:
        try:
            pornstars = ", ".join(v for v in vid.pornstars)
            categories = ", ".join(v for v in vid.categories)
            tags = ", #".join(v for v in vid.tags)
        except:
            pornstars = "N/A"
            categories = "N/A"
            tags = "N/A"

        msg = (f"**TITLE** : `{vid.title}`\n"
               f"**DURATION** : `{vid.duration}`\n"
               f"VIEWS : `{vid.views}`\n\n"
               f"**{pornstars}**\n"
               f"Categories : {categories}\n\n"
               f"{tags}"
               f"Link : {vid.url}")

        results.append(InlineQueryResultArticle(
            title=vid.title,
            input_message_content=InputTextMessageContent(
                message_text=msg,
            ),
            description=f"Duration : {vid.duration}\nViews : {vid.views}\nRating : {vid.rating}",
            thumb_url=vid.thumb,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Watch online", url=vid.url),
                btn1
            ]]),
        ))

    await inline_query.answer(results, switch_pm_text="Search Results", switch_pm_parameter="start")


@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(f"Hello @{message.from_user.username},\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        "I am a bot for searching & downloading Pornhub videos.\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        "Click the buttons below to search.\n\n"
                        "**Credits:**\n"
                        "- Created by [Rahat](https://t.me/RahatMx)\n"
                        "- Powered by [RM Movie Flix](https://t.me/RM_Movie_Flix)",
                        reply_markup=InlineKeyboardMarkup([[btn1, btn2]]))
    await send_log("Start Command", f"Started by @{message.from_user.username}", client)


@app.on_message(filters.regex(r'www\.pornhub\.com'))
async def options(client, message: Message):
    await message.reply("What would you like to do?",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Download", f"d_{message.text}"),
                             InlineKeyboardButton("Watch Video", url=message.text)]
                        ]))
    await send_log("Link Detected", f"URL: {message.text} by @{message.from_user.username}", client)


@app.on_callback_query(filters.regex("^d"))
async def download_video(client, callback: CallbackQuery):
    url = callback.data.split("_", 1)[1]
    msg = await callback.message.edit("Downloading...")
    user_id = callback.from_user.id

    if user_id in active_list:
        await callback.message.edit("You can only download one video at a time.")
        return
    else:
        active_list.append(user_id)
        await send_log("Download Started", f"URL: {url} by @{callback.from_user.username}", client)

    ydl_opts = {
        "progress_hooks": [lambda d: download_progress_hook(d, callback.message, client)],
        "outtmpl": "downloads/%(title)s.%(ext)s"
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            await run_async(ydl.download, [url])
    except DownloadError:
        await callback.message.edit("There was a problem with this video.")
        await send_log("Download Failed", f"URL: {url} by @{callback.from_user.username}", client)
        return

    for file in os.listdir("downloads"):
        if file.endswith(".mp4"):
            video_path = os.path.join("downloads", file)
            await callback.message.reply_video(video_path,
                                               caption=f"Here is your requested video.\n\n**Credits:**\n"
                                                       "- Created by [Rahat](https://t.me/RahatMx)\n"
                                                       "- Powered by [RM Movie Flix](https://t.me/RM_Movie_Flix)")
            await send_log("Download Completed", f"File: {file} by @{callback.from_user.username}", client)
            os.remove(video_path)
            break

    await msg.delete()
    active_list.remove(user_id)
