# requires: spotipy, aiohttp, pillow, musicdl
# author: @LoLpryvet && порт: @Hairpin00
# version: 1.0.2
# description: Слушай музыку в Spotify

import asyncio
import logging
import tempfile
import aiohttp
import os
import re
import io
from io import BytesIO

import spotipy
from PIL import Image, ImageDraw, ImageFont, ImageStat
import colorsys

from telethon import types

logger = logging.getLogger(__name__)

CUSTOM_EMOJI = {
    'link': '<tg-emoji emoji-id="5271604874419647061">🔗</tg-emoji>',
    'lock': '<tg-emoji emoji-id="5472308992514464048">🔐</tg-emoji>',
    'warning': '<tg-emoji emoji-id="5467890025217661107">‼️</tg-emoji>',
    'key': '<tg-emoji emoji-id="5330115548900501467">🔑</tg-emoji>',
    'computer': '<tg-emoji emoji-id="5431376038628171216">💻</tg-emoji>',
    'error': '<tg-emoji emoji-id="5854929766146118183">❌</tg-emoji>',
    'music': '<tg-emoji emoji-id="5870794890006237381">🎶</tg-emoji>',
    'loading': '<tg-emoji emoji-id="5334768819548200731">💻</tg-emoji>',
    'scroll': '<tg-emoji emoji-id="5956561916573782596">📜</tg-emoji>',
    'error2': '<tg-emoji emoji-id="5886285363869126932">❌</tg-emoji>',
    'headphone': '<tg-emoji emoji-id="5188705588925702510">🎶</tg-emoji>',
    'cd': '<tg-emoji emoji-id="5870794890006237381">💿</tg-emoji>',
    'heart': '<tg-emoji emoji-id="5872863028428410654">❤️</tg-emoji>',
    'list': '<tg-emoji emoji-id="5944809881029578897">📑</tg-emoji>',
    'chain': '<tg-emoji emoji-id="5902449142575141204">🔗</tg-emoji>',
}

def register(kernel):
    client = kernel.client
    prefix = kernel.custom_prefix

    kernel.config.setdefault('spots_client_id', None)
    kernel.config.setdefault('spots_client_secret', None)
    kernel.config.setdefault('spots_auth_token', None)
    kernel.config.setdefault('spots_refresh_token', None)
    kernel.config.setdefault('spots_scopes', 'user-read-playback-state user-library-read')
    kernel.config.setdefault('spots_genius_token', None)
    kernel.config.setdefault('spots_font_url', 'https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf')

    musicdl = None

    class MusicDL:
        def __init__(self, client):
            self.client = client
            self.timeout = 40
            self.retries = 3

        async def dl(self, full_name: str, only_document: bool = False):
            import requests
            from telethon.errors.rpcerrorlist import BotResponseTimeoutError

            bots = ["@vkm4bot", "@spotifysavebot", "@lybot"]
            document = None

            for bot in bots:
                try:
                    results = await self.client.inline_query(bot, full_name)
                    if results and results[0].document:
                        document = results[0].document
                        break
                except Exception as e:
                    logger.debug(f"Failed to get document from {bot}: {e}")
                    continue

            if not document:
                try:
                    q = await self.client.inline_query("@losslessrobot", full_name)
                    if q and q[0].document:
                        document = q[0].document
                except BotResponseTimeoutError:
                    logger.debug("BotResponseTimeoutError from @losslessrobot")
                except Exception as e:
                    logger.debug(f"Failed to get document from @losslessrobot: {e}")

            if not document:
                return None

            if only_document:
                return document

            file = io.BytesIO(await self.client.download_file(document, bytes))
            file.name = "audio.mp3"

            try:
                skynet = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: requests.post(
                        "https://siasky.net/skynet/skyfile",
                        files={"file": file},
                    )
                )
            except ConnectionError:
                return None

            return f"https://siasky.net/{skynet.json()['skylink']}"

    musicdl = MusicDL(client)

    async def _load_font(size):
        """Загружает шрифт по URL из конфигурации"""
        try:
            font_url = kernel.config.get('spots_font_url', 'https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf')
            async with aiohttp.ClientSession() as session:
                async with session.get(font_url) as response:
                    if response.status == 200:
                        font_data = await response.read()
                        return ImageFont.truetype(BytesIO(font_data), size)
        except Exception as e:
            logger.warning(f"Failed to load custom font, using fallback: {e}")

        # Fallback на системные шрифты
        try:
            return ImageFont.truetype("/System/Library/Fonts/Helvetica-Bold.ttc", size)
        except:
            try:
                return ImageFont.truetype("arial.ttf", size)
            except:
                try:
                    return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
                except:
                    return ImageFont.load_default()

    async def _get_lyrics_from_lrclib(artist, title, duration_ms=None):
        try:
            clean_title = re.sub(r'\([^)]*\)', '', title).strip()
            clean_artist = re.sub(r'\([^)]*\)', '', artist).strip()

            params = {'artist_name': clean_artist, 'track_name': clean_title}
            if duration_ms:
                params['duration'] = duration_ms // 1000

            url = "https://lrclib.net/api/search"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            track_data = data[0]
                            synced_lyrics = track_data.get('syncedLyrics')
                            plain_lyrics = track_data.get('plainLyrics')

                            if synced_lyrics:
                                return {'type': 'synced', 'lyrics': synced_lyrics, 'plain': plain_lyrics}
                            elif plain_lyrics:
                                return {'type': 'plain', 'lyrics': plain_lyrics}
            return None
        except Exception as e:
            logger.error(f"Error getting lyrics from LRCLib: {e}")
            return None

    async def _get_lyrics_from_genius(artist, title):
        if not kernel.config.get('spots_genius_token'):
            return None

        try:
            clean_title = re.sub(r'\([^)]*\)', '', title).strip()
            clean_artist = re.sub(r'\([^)]*\)', '', artist).strip()

            search_url = "https://api.genius.com/search"
            headers = {"Authorization": f"Bearer {kernel.config.get('spots_genius_token')}"}
            params = {"q": f"{clean_artist} {clean_title}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, params=params) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    hits = data.get('response', {}).get('hits', [])

                    if not hits:
                        return None

                    song_url = None
                    for hit in hits:
                        song = hit.get('result', {})
                        song_title = song.get('title', '').lower()
                        song_artist = song.get('primary_artist', {}).get('name', '').lower()

                        if (clean_title.lower() in song_title or song_title in clean_title.lower()) and \
                           (clean_artist.lower() in song_artist or song_artist in clean_artist.lower()):
                            song_url = song.get('url')
                            break

                    if not song_url:
                        song_url = hits[0].get('result', {}).get('url')

                    if not song_url:
                        return None

                    return await _scrape_genius_lyrics(song_url)
        except Exception as e:
            logger.error(f"Error getting lyrics from Genius: {e}")
            return None

    async def _scrape_genius_lyrics(url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None

                    html = await response.text()
                    lyrics_pattern = r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>'
                    matches = re.findall(lyrics_pattern, html, re.DOTALL | re.IGNORECASE)

                    if not matches:
                        lyrics_pattern = r'<div[^>]*class="[^"]*lyrics[^"]*"[^>]*>(.*?)</div>'
                        matches = re.findall(lyrics_pattern, html, re.DOTALL | re.IGNORECASE)

                    if matches:
                        lyrics = matches[0]
                        lyrics = re.sub(r'<br[^>]*>', '\n', lyrics)
                        lyrics = re.sub(r'<[^>]+>', '', lyrics)
                        lyrics = lyrics.strip()
                        lyrics = lyrics.replace('&amp;', '&')
                        lyrics = lyrics.replace('&lt;', '<')
                        lyrics = lyrics.replace('&gt;', '>')
                        lyrics = lyrics.replace('&quot;', '"')
                        lyrics = lyrics.replace('&#x27;', "'")
                        return lyrics if lyrics else None

                    return None
        except Exception as e:
            logger.error(f"Error scraping Genius lyrics: {e}")
            return None

    async def _get_lyrics_from_api(artist, title):
        try:
            url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        lyrics = data.get('lyrics')
                        if lyrics:
                            return {'type': 'plain', 'lyrics': lyrics}
                    return None
        except Exception as e:
            logger.error(f"Error getting lyrics from lyrics.ovh: {e}")
            return None

    def _format_synced_lyrics(synced_lyrics, current_progress_ms=None):
        if not synced_lyrics:
            return None

        lines = synced_lyrics.strip().split('\n')
        formatted_lines = []
        current_line_found = False

        for line in lines:
            time_match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\](.*)', line)
            if time_match:
                minutes = int(time_match.group(1))
                seconds = int(time_match.group(2))
                centiseconds = int(time_match.group(3))
                text = time_match.group(4).strip()
                line_time_ms = (minutes * 60 + seconds) * 1000 + centiseconds * 10

                if current_progress_ms and not current_line_found:
                    if line_time_ms <= current_progress_ms:
                        next_line_time = None
                        line_index = lines.index(line)
                        if line_index + 1 < len(lines):
                            next_match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\]', lines[line_index + 1])
                            if next_match:
                                next_minutes = int(next_match.group(1))
                                next_seconds = int(next_match.group(2))
                                next_centiseconds = int(next_match.group(3))
                                next_line_time = (next_minutes * 60 + next_seconds) * 1000 + next_centiseconds * 10

                        if next_line_time is None or current_progress_ms < next_line_time:
                            formatted_lines.append(f"<b>→ {text}</b>")
                            current_line_found = True
                        else:
                            formatted_lines.append(text)
                    else:
                        formatted_lines.append(text)
                else:
                    formatted_lines.append(text)
            else:
                if line.strip():
                    formatted_lines.append(line.strip())

        return '\n'.join(formatted_lines)

    async def _get_synced_lyrics_data(artist, title, duration_ms=None):
        try:
            clean_title = re.sub(r'\([^)]*\)', '', title).strip()
            clean_artist = re.sub(r'\([^)]*\)', '', artist).strip()

            params = {'artist_name': clean_artist, 'track_name': clean_title}
            if duration_ms:
                params['duration'] = duration_ms // 1000

            url = "https://lrclib.net/api/search"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            track_data = data[0]
                            synced_lyrics = track_data.get('syncedLyrics')
                            if synced_lyrics:
                                return _parse_synced_lyrics(synced_lyrics)
            return None
        except Exception as e:
            logger.error(f"Error getting synced lyrics from LRCLib: {e}")
            return None

    def _parse_synced_lyrics(synced_lyrics):
        if not synced_lyrics:
            return None

        lines = synced_lyrics.strip().split('\n')
        parsed_lines = []

        for line in lines:
            time_match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\](.*)', line)
            if time_match:
                minutes = int(time_match.group(1))
                seconds = int(time_match.group(2))
                centiseconds = int(time_match.group(3))
                text = time_match.group(4).strip()
                time_ms = (minutes * 60 + seconds) * 1000 + centiseconds * 10

                if text:
                    parsed_lines.append({
                        'time_ms': time_ms,
                        'text': text,
                        'timestamp': f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
                    })

        return parsed_lines

    def _get_current_lyric_line(lyrics_data, current_progress_ms):
        if not lyrics_data:
            return None, -1

        current_line = None
        current_index = -1

        for i, line in enumerate(lyrics_data):
            if line['time_ms'] <= current_progress_ms:
                if i + 1 < len(lyrics_data):
                    next_line = lyrics_data[i + 1]
                    if current_progress_ms < next_line['time_ms']:
                        current_line = line
                        current_index = i
                        break
                else:
                    current_line = line
                    current_index = i
                    break

        return current_line, current_index

    def _format_realtime_lyrics(lyrics_data, current_index, context_lines=2):
        if not lyrics_data or current_index == -1:
            return "🎵 Ожидание синхронизации..."

        formatted_lines = []
        start_index = max(0, current_index - context_lines)
        end_index = min(len(lyrics_data), current_index + context_lines + 1)

        for i in range(start_index, end_index):
            line = lyrics_data[i]
            if i == current_index:
                formatted_lines.append(f"<b>▶️ {line['text']}</b>")
            elif i < current_index:
                formatted_lines.append(f"<i>{line['text']}</i>")
            else:
                formatted_lines.append(line['text'])

        return '\n'.join(formatted_lines)

    async def _realtime_lyrics_loop():
        if not hasattr(kernel, '_realtime_lyrics_data') or not kernel._realtime_lyrics_data['active']:
            return

        try:
            data = kernel._realtime_lyrics_data
            update_count = 0
            max_updates = 600
            pause_count = 0
            max_pause_time = 120
            last_pause_message_count = -1

            while data['active'] and update_count < max_updates:
                try:
                    sp = spotipy.Spotify(auth=kernel.config.get('spots_auth_token'))
                    current_playback = sp.current_playback()

                    if not current_playback or not current_playback.get('item'):
                        pause_count += 1
                        if pause_count > 30:
                            break
                        await asyncio.sleep(1)
                        update_count += 1
                        continue

                    current_track_id = current_playback['item'].get('id', '')
                    if current_track_id != data['track_id']:
                        break

                    progress_ms = current_playback.get('progress_ms', 0)
                    is_playing = current_playback.get('is_playing', False)

                    if not is_playing:
                        pause_count += 1
                        if pause_count >= max_pause_time:
                            new_text = data['header'] + "⏸️ <i>Сеанс завершен из-за длительной паузы</i>"
                            try:
                                await client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                            except:
                                pass
                            break

                        if last_pause_message_count == -1 or pause_count - last_pause_message_count >= 10:
                            new_text = data['header'] + "⏸️ <i>Воспроизведение приостановлено</i>"
                            try:
                                await client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                                last_pause_message_count = pause_count
                            except Exception as edit_error:
                                logger.debug(f"Failed to edit pause message: {edit_error}")

                        await asyncio.sleep(1)
                        update_count += 1
                        continue
                    else:
                        if pause_count > 0:
                            pause_count = 0
                            last_pause_message_count = -1

                        current_line, current_index = _get_current_lyric_line(data['lyrics_data'], progress_ms)
                        if current_index != data['last_line_index']:
                            formatted_lyrics = _format_realtime_lyrics(data['lyrics_data'], current_index)
                            new_text = data['header'] + formatted_lyrics
                            data['last_line_index'] = current_index

                            try:
                                await client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                            except Exception as edit_error:
                                logger.debug(f"Failed to edit message: {edit_error}")
                                break

                    await asyncio.sleep(1)
                    update_count += 1
                except spotipy.exceptions.SpotifyException as e:
                    logger.debug(f"Spotify API error: {e}")
                    await asyncio.sleep(3)
                    update_count += 1
                    continue
                except Exception as e:
                    logger.error(f"Error in realtime lyrics loop: {e}")
                    await asyncio.sleep(2)
                    update_count += 1

            data['active'] = False
            try:
                final_text = data['header'] + "✅ <i>Сеанс синхронизации завершен</i>"
                await client.edit_message(
                    data['chat_id'],
                    data['message_id'],
                    final_text,
                    parse_mode='html'
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Critical error in realtime lyrics loop: {e}")
            if hasattr(kernel, '_realtime_lyrics_data'):
                kernel._realtime_lyrics_data['active'] = False


    async def _create_song_card(track_info):
        try:
            W, H = 600, 250  
            title_font = await _load_font(34)  
            artist_font = await _load_font(22)
            time_font = await _load_font(18)
    
            album_art_url = track_info['album_art']
            async with aiohttp.ClientSession() as session:
                async with session.get(album_art_url) as response:
                    art_data = await response.read()
                    album_art_original = Image.open(BytesIO(art_data))
    
            def get_dominant_color(image):
                small_image = image.resize((50, 50))
                stat = ImageStat.Stat(small_image)
                r, g, b = stat.mean
                return int(r), int(g), int(b)
    
            def create_darker_variant(r, g, b, factor=0.4):
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                v = max(0.15, v * factor)
                s = min(1.0, s * 1.1)
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return int(r * 255), int(g * 255), int(b * 255)
    
            dominant_r, dominant_g, dominant_b = get_dominant_color(album_art_original)
            bg_r, bg_g, bg_b = create_darker_variant(dominant_r, dominant_g, dominant_b)
    
            card = Image.new('RGB', (W, H), color=(bg_r, bg_g, bg_b))
            draw = ImageDraw.Draw(card)
    
            for y in range(H):
                factor = y / H
                r = int(bg_r * (1 - factor * 0.2))
                g = int(bg_g * (1 - factor * 0.2))
                b = int(bg_b * (1 - factor * 0.2))
                draw.line([(0, y), (W, y)], fill=(r, g, b))
    
            album_size = 180  
            album_art = album_art_original.resize((album_size, album_size), Image.Resampling.LANCZOS)
            mask = Image.new('L', (album_size, album_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, album_size, album_size], radius=15, fill=255)  # Меньший радиус
            album_art.putalpha(mask)
    
            art_x = 20  
            art_y = (H - album_size) // 2
            card.paste(album_art, (art_x, art_y), album_art)
    
            text_x = art_x + album_size + 20
            text_width = W - text_x - 20

            track_name = track_info['track_name']
            if len(track_name) > 25:  
                track_name = track_name[:25] + "..."
            
            import textwrap
            title_lines = textwrap.wrap(track_name, width=18)  
            title_y = art_y + 5
            
            for i, line in enumerate(title_lines[:2]): 
                draw.text((text_x, title_y + i*40), line, font=title_font, fill='white')
            
          
            artist_name = track_info['artist_name']
            if len(artist_name) > 30:
                artist_name = artist_name[:30] + "..."
            
            artist_y = title_y + (len(title_lines)*40 if len(title_lines) > 0 else 40)
            draw.text((text_x, artist_y), artist_name, font=artist_font, fill='#A0A0A0')
    
          
            progress_y = H - 45
            progress_width = W - text_x - 20
            progress_height = 5 
            progress_x = text_x
    
            draw.rounded_rectangle([progress_x, progress_y, progress_x + progress_width, progress_y + progress_height],
                                 radius=2, fill='#555555')
    
            current_time_str = track_info.get('current_time', '00:17')
            duration_str = track_info['duration']
    
            try:
                current_parts = current_time_str.split(':')
                current_seconds = int(current_parts[0]) * 60 + int(current_parts[1])
                duration_parts = duration_str.split(':')
                duration_seconds = int(duration_parts[0]) * 60 + int(duration_parts[1])
                if duration_seconds > 0:
                    progress_ratio = current_seconds / duration_seconds
                else:
                    progress_ratio = 0.1
            except:
                progress_ratio = 0.1
    
            progress_fill = int(progress_width * progress_ratio)
            draw.rounded_rectangle([progress_x, progress_y, progress_x + progress_fill, progress_y + progress_height],
                                 radius=2, fill='#1DB954')  
    
            draw.text((progress_x, progress_y + 10), current_time_str, font=time_font, fill='#A0A0A0')
    
            time_bbox = draw.textbbox((0, 0), duration_str, font=time_font)
            time_width = time_bbox[2] - time_bbox[0]
            draw.text((progress_x + progress_width - time_width, progress_y + 10), duration_str,
                     font=time_font, fill='#A0A0A0')
    
            card_path = os.path.join(tempfile.gettempdir(), f"spots_card_{track_info['track_id']}.png")
            card.save(card_path, "PNG")
            return card_path
        except Exception as e:
            logger.error(f"Error creating song card: {e}")
            return None
    
    async def _create_song_card_no_time(track_info):
        try:
            W, H = 600, 200  
            title_font = await _load_font(34)
            artist_font = await _load_font(22)
    
            album_art_url = track_info['album_art']
            async with aiohttp.ClientSession() as session:
                async with session.get(album_art_url) as response:
                    art_data = await response.read()
                    album_art_original = Image.open(BytesIO(art_data))
    
            def get_dominant_color(image):
                small_image = image.resize((50, 50))
                stat = ImageStat.Stat(small_image)
                r, g, b = stat.mean
                return int(r), int(g), int(b)
    
            def create_darker_variant(r, g, b, factor=0.4):
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                v = max(0.15, v * factor)
                s = min(1.0, s * 1.1)
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return int(r * 255), int(g * 255), int(b * 255)
    
            dominant_r, dominant_g, dominant_b = get_dominant_color(album_art_original)
            bg_r, bg_g, bg_b = create_darker_variant(dominant_r, dominant_g, dominant_b)
    
            card = Image.new('RGB', (W, H), color=(bg_r, bg_g, bg_b))
            draw = ImageDraw.Draw(card)
    
            for y in range(H):
                factor = y / H
                r = int(bg_r * (1 - factor * 0.15))
                g = int(bg_g * (1 - factor * 0.15))
                b = int(bg_b * (1 - factor * 0.15))
                draw.line([(0, y), (W, y)], fill=(r, g, b))
    
            album_size = 160 
            album_art = album_art_original.resize((album_size, album_size), Image.Resampling.LANCZOS)
            mask = Image.new('L', (album_size, album_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, album_size, album_size], radius=15, fill=255)
            album_art.putalpha(mask)
    
            art_x = 15
            art_y = (H - album_size) // 2
            card.paste(album_art, (art_x, art_y), album_art)
    
            text_x = art_x + album_size + 15
            text_width = W - text_x - 15
            
         
            track_name = track_info['track_name']
            if len(track_name) > 22:
                track_name = track_name[:22] + "..."
            
            title_y = H // 2 - 25
            draw.text((text_x, title_y), track_name, font=title_font, fill='white')
    
            artist_name = track_info['artist_name']
            if len(artist_name) > 25:
                artist_name = artist_name[:25] + "..."
            
            artist_y = H // 2 + 5
            draw.text((text_x, artist_y), artist_name, font=artist_font, fill='#A0A0A0')
    
            live_font = await _load_font(16)
            live_text = "LIVE"
            live_bbox = draw.textbbox((0, 0), live_text, font=live_font)
            live_width = live_bbox[2] - live_bbox[0]
            
            live_x = W - live_width - 20
            live_y = 20
            
           
            draw.ellipse([live_x - 20, live_y, live_x - 8, live_y + 12], fill='#FF0000')
            draw.text((live_x, live_y - 2), live_text, font=live_font, fill='#FF0000')
    
            card_path = os.path.join(tempfile.gettempdir(), f"playnow_card_{track_info['track_id']}.png")
            card.save(card_path, "PNG")
            return card_path
        except Exception as e:
            logger.error(f"Error creating song card without time: {e}")
            return None

    async def _update_playnow_for_new_track(data, current_playback):
        try:
            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            track_id = track.get('id', '')

            track_info = {
                'track_name': track_name,
                'artist_name': artist_name,
                'album_art': track['album']['images'][0]['url'],
                'track_id': track_id
            }

            card_path = await _create_song_card_no_time(track_info)
            lyrics_data = await _get_synced_lyrics_data(artist_name, track_name, duration_ms)

            if lyrics_data:
                initial_lyrics = "🎵 Ожидание синхронизации..."
                data['lyrics_data'] = lyrics_data
                data['last_line_index'] = -1
            else:
                initial_lyrics = f"❌ <i>Синхронизированный текст для трека не найден</i>\n\n<a href='{track_url}'>{artist_name} — {track_name}</a>"
                data['lyrics_data'] = None

            if card_path:
                try:
                    await client.delete_messages(data['chat_id'], data['message_id'])
                except:
                    pass

                new_message = await client.send_file(
                    data['chat_id'],
                    card_path,
                    caption=initial_lyrics,
                    parse_mode='html'
                )
                data['message_id'] = new_message.id
                try:
                    os.remove(card_path)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error updating playnow for new track: {e}")

    async def _playnow_loop():
        if not hasattr(kernel, '_playnow_data') or not kernel._playnow_data['active']:
            return

        try:
            data = kernel._playnow_data
            update_count = 0
            max_updates = 1200
            pause_count = 0
            max_pause_time = 120
            last_pause_message_count = -1
            current_track_id = data.get('current_track_id')

            while data['active'] and update_count < max_updates:
                try:
                    sp = spotipy.Spotify(auth=kernel.config.get('spots_auth_token'))
                    current_playback = sp.current_playback()

                    if not current_playback or not current_playback.get('item'):
                        pause_count += 1
                        if pause_count > 30:
                            break
                        await asyncio.sleep(1)
                        update_count += 1
                        continue

                    new_track_id = current_playback['item'].get('id', '')
                    progress_ms = current_playback.get('progress_ms', 0)
                    is_playing = current_playback.get('is_playing', False)
                    track_changed = new_track_id != current_track_id

                    if track_changed:
                        await _update_playnow_for_new_track(data, current_playback)
                        current_track_id = new_track_id
                        data['current_track_id'] = new_track_id
                        pause_count = 0
                        last_pause_message_count = -1
                        continue

                    if not is_playing:
                        pause_count += 1
                        if pause_count >= max_pause_time:
                            new_text = "⏸️ <i>Сеанс завершен из-за длительной паузы</i>"
                            try:
                                await client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                            except:
                                pass
                            break

                        if last_pause_message_count == -1 or pause_count - last_pause_message_count >= 10:
                            formatted_lyrics = "⏸️ <i>Воспроизведение приостановлено</i>"
                            try:
                                await client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    formatted_lyrics,
                                    parse_mode='html'
                                )
                                last_pause_message_count = pause_count
                            except Exception as edit_error:
                                logger.debug(f"Failed to edit pause message: {edit_error}")

                        await asyncio.sleep(1)
                        update_count += 1
                        continue
                    else:
                        if pause_count > 0:
                            pause_count = 0
                            last_pause_message_count = -1

                        if data.get('lyrics_data'):
                            current_line, current_index = _get_current_lyric_line(data['lyrics_data'], progress_ms)
                            if current_index != data.get('last_line_index', -1):
                                formatted_lyrics = _format_realtime_lyrics(data['lyrics_data'], current_index)
                                data['last_line_index'] = current_index
                                try:
                                    await client.edit_message(
                                        data['chat_id'],
                                        data['message_id'],
                                        formatted_lyrics,
                                        parse_mode='html'
                                    )
                                except Exception as edit_error:
                                    logger.debug(f"Failed to edit message: {edit_error}")
                                    break

                    await asyncio.sleep(1)
                    update_count += 1
                except spotipy.exceptions.SpotifyException as e:
                    logger.debug(f"Spotify API error: {e}")
                    await asyncio.sleep(3)
                    update_count += 1
                    continue
                except Exception as e:
                    logger.error(f"Error in playnow loop: {e}")
                    await asyncio.sleep(2)
                    update_count += 1

            data['active'] = False
            try:
                final_text = "✅ <i>Сеанс live-отображения завершен</i>"
                await client.edit_message(
                    data['chat_id'],
                    data['message_id'],
                    final_text,
                    parse_mode='html'
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Critical error in playnow loop: {e}")
            if hasattr(kernel, '_playnow_data'):
                kernel._playnow_data['active'] = False

    @kernel.register.command('lyrics')
    # Получить текст текущего трека
    async def lyrics_cmd(event):

        if not kernel.config.get('spots_auth_token'):
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            return

        try:
            sp = spotipy.Spotify(auth=kernel.config.get('spots_auth_token'))
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
                return

            await event.edit(f"{CUSTOM_EMOJI['loading']} <b>Ищу текст песни...</b>", parse_mode='html')

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            progress_ms = current_playback.get('progress_ms', 0)

            lyrics_data = await _get_lyrics_from_lrclib(artist_name, track_name, duration_ms)

            if not lyrics_data and kernel.config.get('spots_genius_token'):
                genius_lyrics = await _get_lyrics_from_genius(artist_name, track_name)
                if genius_lyrics:
                    lyrics_data = {'type': 'plain', 'lyrics': genius_lyrics}

            if not lyrics_data:
                lyrics_data = await _get_lyrics_from_api(artist_name, track_name)

            if lyrics_data:
                if lyrics_data['type'] == 'synced':
                    formatted_lyrics = _format_synced_lyrics(lyrics_data['lyrics'], progress_ms)
                    await event.edit(
                        f"{CUSTOM_EMOJI['scroll']} <b>Текст трека <a href=\"{track_url}\">{artist_name} — {track_name}</a>:</b>\n<blockquote expandable>{formatted_lyrics}</blockquote>",
                        parse_mode='html'
                    )
                else:
                    await event.edit(
                        f"{CUSTOM_EMOJI['scroll']} <b>Текст трека <a href=\"{track_url}\">{artist_name} — {track_name}</a>:</b>\n<blockquote expandable>{lyrics_data['lyrics']}</blockquote>",
                        parse_mode='html'
                    )
            else:
                await event.edit(
                    f"{CUSTOM_EMOJI['error2']} <b>Текст для трека <a href=\"{track_url}\">{artist_name} — {track_name}</a> не найден!</b>",
                    parse_mode='html'
                )
        except spotipy.oauth2.SpotifyOauthError as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Ошибка авторизации:</b> <code>{str(e)}</code>", parse_mode='html')
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            elif "NO_ACTIVE_DEVICE" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
            else:
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')
        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')

    @kernel.register.command('spauth')
    # Войти в свой аккаунт
    async def spauth_cmd(event):
        if not kernel.config.get('spots_client_id') or not kernel.config.get('spots_client_secret'):
            await event.edit(
                f"{CUSTOM_EMOJI['lock']} <b>Создай приложение по <a href=\"https://developer.spotify.com/dashboard\">этой ссылке</a></b>\n\n"
                f"{CUSTOM_EMOJI['warning']} <b>Важно:</b> redirect_url приложения должен быть <code>https://sp.fajox.one</code>\n\n"
                f"<b>{CUSTOM_EMOJI['key']} Заполни <code>client_id</code> и <code>client_secret</code> в конфигурации</b>\n\n"
                f"<b>{CUSTOM_EMOJI['computer']} И снова напиши <code>{prefix}spauth</code></b>",
                parse_mode='html'
            )
            return

        sp_oauth = spotipy.oauth2.SpotifyOAuth(
            client_id=kernel.config.get('spots_client_id'),
            client_secret=kernel.config.get('spots_client_secret'),
            redirect_uri="https://sp.fajox.one",
            scope=kernel.config.get('spots_scopes')
        )

        auth_url = sp_oauth.get_authorize_url()
        await event.edit(
            f"<b>{CUSTOM_EMOJI['link']} Ссылка для авторизации создана!\n\n🔐 Перейди по <a href='{auth_url}'>этой ссылке</a>.\n\n"
            f"✏️ Потом введи: <code>{prefix}spcode свой_auth_token</code></b>",
            parse_mode='html'
        )

    @kernel.register.command('spcode')
    # Ввести код авторизации
    async def spcode_cmd(event):
        if not kernel.config.get('spots_client_id') or not kernel.config.get('spots_client_secret'):
            await event.edit(
                f"{CUSTOM_EMOJI['lock']} <b>Создай приложение по <a href=\"https://developer.spotify.com/dashboard\">этой ссылке</a></b>\n\n"
                f"{CUSTOM_EMOJI['warning']} <b>Важно:</b> redirect_url приложения должен быть <code>https://sp.fajox.one</code>\n\n"
                f"<b>{CUSTOM_EMOJI['key']} Заполни <code>client_id</code> и <code>client_secret</code> в конфигурации</b>\n\n"
                f"<b>{CUSTOM_EMOJI['computer']} И снова напиши <code>{prefix}spauth</code></b>",
                parse_mode='html'
            )
            return

        args = event.text.split()
        if len(args) < 2:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Должно быть <code>{prefix}spcode код_авторизации</code></b>", parse_mode='html')
            return

        code = args[1]
        sp_oauth = spotipy.oauth2.SpotifyOAuth(
            client_id=kernel.config.get('spots_client_id'),
            client_secret=kernel.config.get('spots_client_secret'),
            redirect_uri="https://sp.fajox.one",
            scope=kernel.config.get('spots_scopes')
        )

        try:
            token_info = sp_oauth.get_access_token(code)
            kernel.config['spots_auth_token'] = token_info['access_token']
            kernel.config['spots_refresh_token'] = token_info['refresh_token']
            kernel.save_config()

            sp = spotipy.Spotify(auth=token_info['access_token'])
            current_playback = sp.current_playback()

            await event.edit(f"<b>{CUSTOM_EMOJI['key']} Код авторизации установлен!</b>\n\n{CUSTOM_EMOJI['music']} <b>Наслаждайся музыкой!</b>", parse_mode='html')
        except spotipy.oauth2.SpotifyOauthError as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Ошибка авторизации:</b> <code>{str(e)}</code>", parse_mode='html')
        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')

    @kernel.register.command('spnow')
    # Текущий трек
    async def spnow_cmd(event):
        if not kernel.config.get('spots_auth_token'):
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            return

        try:
            sp = spotipy.Spotify(auth=kernel.config.get('spots_auth_token'))
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
                return

            await event.edit(f"{CUSTOM_EMOJI['loading']} <b>Загружаю трек...</b>", parse_mode='html')

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            album_name = track['album'].get('name', 'Unknown Album')
            duration_ms = track.get('duration_ms', 0)

            playlist = current_playback.get('context', {}).get('uri', '').split(':')[-1] if current_playback.get('context') else None
            device_name = current_playback.get('device', {}).get('name', 'Unknown Device')+" "+current_playback.get('device', {}).get('type', '')

            user_profile = sp.current_user()
            user_name = user_profile['display_name']
            user_id = user_profile['id']

            track_url = track['external_urls']['spotify']
            user_url = f"https://open.spotify.com/user/{user_id}"
            playlist_url = f"https://open.spotify.com/playlist/{playlist}" if playlist else None

            track_info = (
                f"<b>🎧 Now Playing</b>\n\n"
                f"<b>{CUSTOM_EMOJI['headphone']} {track_name} - <code>{artist_name}</code>\n"
                f"<b>{CUSTOM_EMOJI['cd']} Album:</b> <code>{album_name}</code>\n\n"
                f"<b>🎧 Device:</b> <code>{device_name}</code>\n"
                + (("<b>{CUSTOM_EMOJI['heart']} From favorite tracks</b>\n" if "playlist/collection" in playlist_url else
                    f"<b>{CUSTOM_EMOJI['list']} From Playlist:</b> <a href='{playlist_url}'>View</a>\n") if playlist else "")
                + f"\n<b>{CUSTOM_EMOJI['chain']} Track URL:</b> <a href='{track_url}'>Open in Spotify</a>"
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                if musicdl and hasattr(musicdl, 'dl'):
                    try:
                        audio_path = await musicdl.dl(f"{artist_name} - {track_name}", only_document=True)
                        if not audio_path:
                            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Не удалось скачать трек. Попробуйте позже.</b>", parse_mode='html')
                            return
                    except Exception as e:
                        await event.edit(f"{CUSTOM_EMOJI['error']} <b>Ошибка при скачивании трека:</b> <code>{str(e)[:100]}</code>", parse_mode='html')
                        return
                else:
                    await event.edit(f"{CUSTOM_EMOJI['error']} <b>musicdl не загружен. Проверьте установку модуля.</b>", parse_mode='html')
                    return

                album_art_url = track['album']['images'][0]['url']
                async with aiohttp.ClientSession() as session:
                    async with session.get(album_art_url) as response:
                        art_path = os.path.join(temp_dir, "cover.jpg")
                        with open(art_path, "wb") as f:
                            f.write(await response.read())

            await client.send_file(
                event.chat_id,
                audio_path,
                parse_mode='html',
                caption=track_info,
                attributes=[
                    types.DocumentAttributeAudio(
                        duration=duration_ms//1000,
                        title=track_name,
                        performer=artist_name
                    )
                ],
                thumb=art_path,
                reply_to=event.reply_to_msg_id if event.is_reply else None
            )
            await event.delete()
        except spotipy.oauth2.SpotifyOauthError as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Ошибка авторизации:</b> <code>{str(e)}</code>", parse_mode='html')
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            elif "NO_ACTIVE_DEVICE" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
            else:
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')
        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')

    @kernel.register.command('now')
    # Красивая карточка с текущим треком
    async def now_cmd(event):
        if not kernel.config.get('spots_auth_token'):
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            return

        try:
            sp = spotipy.Spotify(auth=kernel.config.get('spots_auth_token'))
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
                return

            await event.edit(f"{CUSTOM_EMOJI['loading']} <b>Загружаю трек...</b>", parse_mode='html')

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            album_name = track['album'].get('name', 'Unknown Album')
            duration_ms = track.get('duration_ms', 0)
            progress_ms = current_playback.get('progress_ms', 0)
            track_id = track.get('id', '')

            duration_min, duration_sec = divmod(duration_ms // 1000, 60)
            duration_str = f"{duration_min}:{duration_sec:02d}"
            progress_min, progress_sec = divmod(progress_ms // 1000, 60)
            progress_str = f"{progress_min}:{progress_sec:02d}"

            track_url = track['external_urls']['spotify']
            song_link_url = f"https://song.link/s/{track_id}"

            track_info = {
                'track_name': track_name,
                'artist_name': artist_name,
                'album_name': album_name,
                'duration': duration_str,
                'current_time': progress_str,
                'album_art': track['album']['images'][0]['url'],
                'track_id': track_id
            }

            card_path = await _create_song_card(track_info)
            caption = f"🎵 | <a href='{track_url}'>Spotify</a> • <a href='{song_link_url}'>song.link</a>"

            if card_path:
                await client.send_file(
                    event.chat_id,
                    card_path,
                    caption=caption,
                    reply_to=event.reply_to_msg_id if event.is_reply else None,
                    parse_mode='html'
                )
                try:
                    os.remove(card_path)
                except:
                    pass
            else:
                album_art_url = track['album']['images'][0]['url']
                async with aiohttp.ClientSession() as session:
                    async with session.get(album_art_url) as response:
                        art_data = await response.read()

                await client.send_file(
                    event.chat_id,
                    art_data,
                    caption=f"<b>🎧 {track_name}</b>\n<b>👤 {artist_name}</b>\n<b>💿 {album_name}</b>\n\n" + caption,
                    reply_to=event.reply_to_msg_id if event.is_reply else None,
                    parse_mode='html'
                )
            await event.delete()
        except spotipy.oauth2.SpotifyOauthError as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Ошибка авторизации:</b> <code>{str(e)}</code>", parse_mode='html')
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            elif "NO_ACTIVE_DEVICE" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
            else:
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')
        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')

    @kernel.register.command('rlyrics')
    # Показать текст текущего трека в реальном времени
    async def rlyrics_cmd(event):
        if not kernel.config.get('spots_auth_token'):
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            return

        try:
            sp = spotipy.Spotify(auth=kernel.config.get('spots_auth_token'))
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
                return

            await event.edit(f"{CUSTOM_EMOJI['loading']} <b>Ищу текст песни...</b>", parse_mode='html')

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            track_id = track.get('id', '')

            lyrics_data = await _get_synced_lyrics_data(artist_name, track_name, duration_ms)

            if not lyrics_data:
                await event.edit(
                    f"{CUSTOM_EMOJI['error2']} <b>Синхронизированный текст для трека <a href=\"{track_url}\">{artist_name} — {track_name}</a> не найден!</b>\n\n"
                    f"<i>Попробуйте команду <code>{prefix}lyrics</code> для поиска обычного текста.</i>",
                    parse_mode='html'
                )
                return

            header = (
                f"{CUSTOM_EMOJI['scroll']} <b>Текст в реальном времени</b>\n"
                f"<a href=\"{track_url}\">{artist_name} — {track_name}</a>\n\n"
            )
            initial_text = header + "🎵 Ожидание синхронизации..."
            sent_message = await event.edit(initial_text, parse_mode='html')

            kernel._realtime_lyrics_data = {
                'message_id': sent_message.id,
                'chat_id': event.chat_id,
                'lyrics_data': lyrics_data,
                'track_id': track_id,
                'header': header,
                'last_line_index': -1,
                'active': True
            }

            asyncio.create_task(_realtime_lyrics_loop())
        except spotipy.oauth2.SpotifyOauthError as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Ошибка авторизации:</b> <code>{str(e)}</code>", parse_mode='html')
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            elif "NO_ACTIVE_DEVICE" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
            else:
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')
        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')

    @kernel.register.command('stoplyrics')
    # Остановить обновление текста в реальном времени
    async def stoplyrics_cmd(event):

        if hasattr(kernel, '_realtime_lyrics_data') and kernel._realtime_lyrics_data.get('active'):
            kernel._realtime_lyrics_data['active'] = False
            await event.edit("✅ <b>Обновление текста в реальном времени остановлено</b>", parse_mode='html')
        else:
            await event.edit("❌ <b>Сеанс синхронизации не активен</b>", parse_mode='html')

    @kernel.register.command('playnow')
    # Live-отображение текущего трека с текстом в реальном времени
    async def playnow_cmd(event):

        if not kernel.config.get('spots_auth_token'):
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            return

        try:
            sp = spotipy.Spotify(auth=kernel.config.get('spots_auth_token'))
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
                return

            await event.edit(f"{CUSTOM_EMOJI['loading']} <b>Загружаю трек...</b>", parse_mode='html')

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            track_id = track.get('id', '')

            track_info = {
                'track_name': track_name,
                'artist_name': artist_name,
                'album_art': track['album']['images'][0]['url'],
                'track_id': track_id
            }

            card_path = await _create_song_card_no_time(track_info)
            lyrics_data = await _get_synced_lyrics_data(artist_name, track_name, duration_ms)

            if lyrics_data:
                initial_caption = "🎵 Ожидание синхронизации..."
            else:
                initial_caption = f"❌ <i>Синхронизированный текст для трека не найден</i>\n\n<a href='{track_url}'>{artist_name} — {track_name}</a>"

            if card_path:
                sent_message = await client.send_file(
                    event.chat_id,
                    card_path,
                    caption=initial_caption,
                    parse_mode='html',
                    reply_to=event.reply_to_msg_id if event.is_reply else None
                )
                try:
                    os.remove(card_path)
                except:
                    pass
            else:
                sent_message = await event.edit(initial_caption, parse_mode='html')

            if hasattr(kernel, '_playnow_data') and kernel._playnow_data.get('active'):
                kernel._playnow_data['active'] = False

            kernel._playnow_data = {
                'message_id': sent_message.id,
                'chat_id': event.chat_id,
                'lyrics_data': lyrics_data,
                'current_track_id': track_id,
                'last_line_index': -1,
                'active': True
            }

            await event.delete()
            asyncio.create_task(_playnow_loop())
        except spotipy.oauth2.SpotifyOauthError as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Ошибка авторизации:</b> <code>{str(e)}</code>", parse_mode='html')
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Авторизуйся в свой аккаунт через <code>{prefix}spauth</code></b>", parse_mode='html')
            elif "NO_ACTIVE_DEVICE" in str(e):
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Сейчас ничего не играет.</b>", parse_mode='html')
            else:
                await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')
        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['error']} <b>Произошла ошибка:</b> <code>{str(e)}</code>", parse_mode='html')

    @kernel.register.command('stopplaynow')
    # Остановить live-отображение трека
    async def stopplaynow_cmd(event):
        if hasattr(kernel, '_playnow_data') and kernel._playnow_data.get('active'):
            kernel._playnow_data['active'] = False
            await event.edit("✅ <b>Live-отображение трека остановлено</b>", parse_mode='html')
        else:
            await event.edit("❌ <b>Сеанс live-отображения не активен</b>", parse_mode='html')
