# requires: yt-dlp
# author: @negrmefedron && @Hairpin00
# version: 1.0.0-youtube
# description: YouTube video downloader

import asyncio
import os
import tempfile
from urllib.parse import urlparse

CUSTOM_EMOJI = {
    "success": '<tg-emoji emoji-id="5321304062715517873">🛰</tg-emoji>',
    "error": '<tg-emoji emoji-id="5433784166661513639">🎁</tg-emoji>',
    "download": '<tg-emoji emoji-id="5332654441508119011">🫥</tg-emoji>',
    "info": '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    "link": '<tg-emoji emoji-id="5377844313575150051">📎</tg-emoji>',
    "time": '<tg-emoji emoji-id="5350813992732338949">🐢</tg-emoji>',
    "disk": '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
}

LOCALIZATION = {
    "en": {
        "usage": "Usage: <code>.yt [URL]</code> or <code>.youtube [URL]</code>",
        "downloading": "Downloading YouTube video...",
        "success": "Video downloaded successfully!",
        "no_url": "Please provide a YouTube URL",
        "invalid_url": "Invalid YouTube URL",
        "download_failed": "Failed to download video",
        "file_too_large": "Video file is too large (Telegram limit)",
        "error": "An error occurred",
        "stats": "Video information:",
        "duration": "Duration:",
        "resolution": "Resolution:",
        "size": "Size:",
        "author": "Channel:",
        "title": "Title:",
        "views": "Views:",
        "upload_date": "Uploaded:",
        "processing": "Processing video...",
        "cleaning": "Cleaning temporary files...",
    },
    "ru": {
        "usage": "Использование: <code>.yt [URL]</code> или <code>.youtube [URL]</code>",
        "downloading": "Скачивание видео с YouTube...",
        "success": "Видео успешно скачано!",
        "no_url": "Пожалуйста, укажите ссылку на YouTube",
        "invalid_url": "Некорректная ссылка на YouTube",
        "download_failed": "Не удалось скачать видео",
        "file_too_large": "Файл видео слишком большой (лимит Telegram)",
        "error": "Произошла ошибка",
        "stats": "Информация о видео:",
        "duration": "Длительность:",
        "resolution": "Разрешение:",
        "size": "Размер:",
        "author": "Канал:",
        "title": "Название:",
        "views": "Просмотров:",
        "upload_date": "Загружено:",
        "processing": "Обработка видео...",
        "cleaning": "Очистка временных файлов...",
    },
}


def is_valid_youtube_url(url):
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False
        domain = parsed.netloc.lower()
        valid_domains = [
            "youtube.com",
            "www.youtube.com",
            "youtu.be",
            "m.youtube.com",
            "music.youtube.com",
            "youtube-nocookie.com",
        ]
        return any(d in domain for d in valid_domains)
    except Exception:
        return False


async def download_youtube_video(url, temp_dir):
    import yt_dlp

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "continuedl": True,
        "retries": 10,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            if not info:
                return None, None
            result = await asyncio.to_thread(ydl.extract_info, url, download=True)
            downloaded_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith((".mp4", ".mkv", ".webm")):
                        downloaded_files.append(os.path.join(root, file))
            if not downloaded_files:
                return None, result
            file_path = max(downloaded_files, key=os.path.getsize)
            return file_path, result
    except Exception:
        return None, None


def register(kernel):
    language = kernel.config.get("language", "en")
    lang_strings = LOCALIZATION.get(language, LOCALIZATION["en"])

    @kernel.register.command("yt", alias=["youtube", "ytdl", "видео"])
    async def youtube_downloader(event):
        try:
            args = event.text.split(maxsplit=1)
            if len(args) < 2:
                await kernel.edit_with_html(
                    event,
                    f"{CUSTOM_EMOJI['error']} <b>{lang_strings['no_url']}</b>\n\n"
                    f"{CUSTOM_EMOJI['info']} {lang_strings['usage']}",
                )
                return
            url = args[1].strip()
            if not is_valid_youtube_url(url):
                await kernel.edit_with_html(
                    event,
                    f"{CUSTOM_EMOJI['error']} <b>{lang_strings['invalid_url']}</b>\n"
                    f"{CUSTOM_EMOJI['link']} <code>{url}</code>",
                )
                return
            await kernel.edit_with_html(
                event,
                f"{CUSTOM_EMOJI['download']} <b>{lang_strings['downloading']}</b>\n\n"
                f"{CUSTOM_EMOJI['link']} <code>{url}</code>",
            )
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path, video_info = await download_youtube_video(url, temp_dir)
                if not file_path or not video_info:
                    await kernel.edit_with_html(
                        event,
                        f"{CUSTOM_EMOJI['error']} <b>{lang_strings['download_failed']}</b>",
                    )
                    return
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > 50:
                    await kernel.edit_with_html(
                        event,
                        f"{CUSTOM_EMOJI['error']} <b>{lang_strings['file_too_large']}</b>\n"
                        f"{CUSTOM_EMOJI['disk']} {file_size_mb:.1f} MB",
                    )

                caption_lines = [
                    f"{CUSTOM_EMOJI['success']} <b>{lang_strings['success']}</b>\n",
                    f"{CUSTOM_EMOJI['info']} <b>{lang_strings['stats']}</b>\n",
                ]
                if video_info.get("title"):
                    caption_lines.append(
                        f"🎬 <b>{lang_strings['title']}</b> {video_info['title']}\n"
                    )
                if video_info.get("duration"):
                    minutes = int(video_info["duration"] // 60)
                    seconds = int(video_info["duration"] % 60)
                    caption_lines.append(
                        f"{CUSTOM_EMOJI['time']} <b>{lang_strings['duration']}</b> "
                        f"{minutes}:{seconds:02d}\n"
                    )
                if video_info.get("resolution") or video_info.get("width"):
                    res = (
                        video_info.get("resolution")
                        or f"{video_info.get('width')}×{video_info.get('height')}"
                    )
                    caption_lines.append(
                        f"🖥 <b>{lang_strings['resolution']}</b> {res}\n"
                    )
                caption_lines.append(
                    f"{CUSTOM_EMOJI['disk']} <b>{lang_strings['size']}</b> {file_size_mb:.1f} MB\n"
                )
                if video_info.get("uploader") or video_info.get("channel"):
                    author = video_info.get("uploader") or video_info.get("channel")
                    caption_lines.append(
                        f"📺 <b>{lang_strings['author']}</b> {author}\n"
                    )
                if video_info.get("view_count"):
                    caption_lines.append(
                        f"👀 <b>{lang_strings['views']}</b> {video_info['view_count']:,}\n"
                    )
                if video_info.get("upload_date"):
                    caption_lines.append(
                        f"📅 <b>{lang_strings['upload_date']}</b> {video_info['upload_date']}\n"
                    )
                caption = "".join(caption_lines)
                try:
                    await event.edit(
                        text=caption,
                        file=file_path,
                        parse_mode="html",
                        link_preview=False,
                    )
                except Exception as send_error:
                    await kernel.edit_with_html(
                        event,
                        f"{CUSTOM_EMOJI['error']} <b>Не удалось отправить:</b>\n<code>{str(send_error)}</code>",
                    )
        except Exception as e:
            await kernel.handle_error(e, source="youtube_downloader", event=event)
            try:
                await kernel.edit_with_html(
                    event,
                    f"{CUSTOM_EMOJI['error']} <b>{lang_strings['error']}</b>\n<pre>{str(e)[:200]}</pre>",
                )
            except Exception:
                pass
