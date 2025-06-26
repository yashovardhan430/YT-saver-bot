import os
import time
import json
import asyncio
import yt_dlp
from telegram import Update, InputFile, Message
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "7914729347:AAHdw9k35eanDTQ1IFZH3wM7qWwXqk7sqFs"  # Replace with your real token
MAX_FILE_SIZE = 120 * 1024 * 1024  # 120 MB
AUTO_DELETE = True
HISTORY_FILE = "user_history.json"

# Load or initialize user history
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r") as f:
        user_history = json.load(f)
else:
    user_history = {}

def save_user_history(user_id, url):
    user_id = str(user_id)
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].insert(0, url)
    user_history[user_id] = user_history[user_id][:10]
    with open(HISTORY_FILE, "w") as f:
        json.dump(user_history, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Send a video link to download as MP4 (480p or lower, max 120MB).")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.message.from_user.id

    # Step 1: Show video info
    info_msg = await update.message.reply_text("🔍 Fetching video info...")

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get('title')
        duration = info.get('duration', 0)
        minutes = duration // 60
        seconds = duration % 60
        formats = [f"{f.get('format_note')} ({f.get('height')}p)" for f in info.get('formats', []) if f.get('height') and f.get('height') <= 480]
        unique_formats = sorted(set(formats))
        file_size_mb = info.get('filesize', 0)
        file_size_display = f"{file_size_mb / (1024 * 1024):.2f} MB" if file_size_mb else "Unknown"

        await info_msg.edit_text(
            f"🎞️ *Title:* {title}\n"
            f"⏱️ *Duration:* {minutes}:{seconds:02d} min\n"
            f"📺 *Resolutions:* {', '.join(unique_formats) or '480p or lower'}\n"
            f"💾 *Size:* {file_size_display}\n\n"
            f"⏬ Downloading now...",
            parse_mode="Markdown"
        )

        await download_and_send(update, url, user_id, info_msg)

    except Exception as e:
        await info_msg.edit_text(f"❌ Error fetching info: {e}")
        await update.message.reply_text("🔁 Please send another video link.")

async def download_and_send(update: Update, url, user_id, progress_msg):
    filename = f"{user_id}_{int(time.time())}.mp4"

    async def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            downloaded = d.get('_downloaded_bytes_str', '...')
            await progress_msg.edit_text(f"⏳ Downloading... [{downloaded} {percent}]")

    ydl_opts = {
        'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best[height<=480]',
        'merge_output_format': 'mp4',
        'outtmpl': filename,
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True,
        'progress_hooks': [lambda d: asyncio.create_task(progress_hook(d))],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(filename):
            await progress_msg.edit_text("❌ Download failed. Try another link.")
            await update.message.reply_text("🔁 Send another video link.")
            return

        file_size = os.path.getsize(filename)
        if file_size > MAX_FILE_SIZE:
            os.remove(filename)
            await progress_msg.edit_text("⚠️ File too large (120MB max). Try shorter/lower-quality video.")
            await update.message.reply_text("🔁 Send another video link.")
            return

        with open(filename, 'rb') as f:
            sent = await update.message.reply_video(
                InputFile(f),
                caption="🎞️ Your MP4 video is ready.\n📥 Tap ••• and 'Save to gallery'."
            )

        await progress_msg.delete()
        save_user_history(user_id, url)

        if AUTO_DELETE:
            await asyncio.sleep(180)
            await sent.delete()

        os.remove(filename)
        await update.message.reply_text("✅ Done! 🔁 Send another link.")

    except Exception as e:
        await progress_msg.edit_text(f"❌ Error: {str(e)}")
        await update.message.reply_text("🔁 Please send another video link.")

# Run the bot
app = ApplicationBuilder().token(BOT_TOKEN).read_timeout(180).write_timeout(180).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

print("🚀 Bot is running...")
app.run_polling()
