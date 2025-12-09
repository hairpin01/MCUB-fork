from telethon import events
import os
import asyncio

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.3gp$'))
    async def convert_3gp(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на видео')
            return
        
        reply = await event.get_reply_message()
        
        if not reply.video and not reply.file:
            await event.edit('❌ Это не видео файл')
            return
        
        await event.edit('📥 Скачивание видео...')
        
        input_file = await reply.download_media('temp_video')
        output_file = 'converted.3gp'
        
        try:
            await event.edit('🔄 Конвертация в .3gp...')
            
            process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-i', input_file, 
                '-s', '176x144',
                '-r', '15',
                '-vcodec', 'h263',
                '-acodec', 'amr_nb',
                '-ar', '8000',
                '-ac', '1',
                '-ab', '12.2k',
                '-y', output_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode != 0:
                await event.edit('❌ Ошибка конвертации. Установите ffmpeg')
                return
            
            await event.edit('📤 Отправка...')
            await client.send_file(event.chat_id, output_file, caption='📱 Конвертировано в .3gp')
            await event.delete()
            
        except FileNotFoundError:
            await event.edit('❌ ffmpeg не установлен\n\nУстановите: apt install ffmpeg')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
        finally:
            if os.path.exists(input_file):
                os.remove(input_file)
            if os.path.exists(output_file):
                os.remove(output_file)
