# requires: shazamio
import asyncio
from shazamio import Shazam
from telethon import events

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.shazam$'))
    async def shazam_handler(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на аудио/видео/голосовое сообщение')
            return
        
        reply = await event.get_reply_message()
        if not (reply.audio or reply.voice or reply.video):
            await event.edit('❌ Сообщение должно содержать аудио/видео')
            return
        
        await event.edit('🎵 Распознавание музыки...')
        
        try:
            file_path = await reply.download_media()
            
            shazam = Shazam()
            result = await shazam.recognize_song(file_path)
            
            import os
            os.remove(file_path)
            
            if 'track' in result:
                track = result['track']
                title = track.get('title', 'Неизвестно')
                artist = track.get('subtitle', 'Неизвестен')
                
                text = f"🎵 **{title}**\n"
                text += f"👤 Исполнитель: {artist}\n"
                
                if 'sections' in track:
                    for section in track['sections']:
                        if section['type'] == 'SONG':
                            metadata = section.get('metadata', [])
                            for item in metadata:
                                if item['title'] == 'Альбом':
                                    text += f"💿 Альбом: {item['text']}\n"
                                elif item['title'] == 'Выпущено':
                                    text += f"📅 Год: {item['text']}\n"
                
                if 'share' in track:
                    text += f"\n🔗 [Открыть в Shazam]({track['share']['href']})"
                
                await event.edit(text)
            else:
                await event.edit('❌ Не удалось распознать музыку')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
