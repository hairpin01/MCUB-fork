from telethon import events
import speech_recognition as sr
import os
import asyncio

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.v2t$'))
    async def voice_to_text(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на голосовое сообщение')
            return

        reply = await event.get_reply_message()

        if not reply.voice and not reply.audio:
            await event.edit('❌ Это не голосовое сообщение')
            return

        await event.edit('📥 Скачивание...')

        voice_file = await reply.download_media('temp_voice.ogg')
        wav_file = 'temp_voice.wav'

        try:
            await event.edit('🔄 Конвертация...')

            process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-i', voice_file,
                '-ar', '16000',
                '-ac', '1',
                '-y', wav_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()

            if process.returncode != 0:
                await event.edit('❌ Ошибка конвертации. Установите ffmpeg')
                return

            await event.edit('🎤 Распознавание речи...')

            recognizer = sr.Recognizer()

            with sr.AudioFile(wav_file) as source:
                audio = recognizer.record(source)

            try:
                text = recognizer.recognize_google(audio, language='ru-RU')
                await event.edit(f'📝 **Распознанный текст:**\n\n{text}')
            except sr.UnknownValueError:
                await event.edit('❌ Не удалось распознать речь')
            except sr.RequestError:
                await event.edit('❌ Ошибка сервиса распознавания')

        except FileNotFoundError:
            await event.edit('❌ ffmpeg не установлен\n\nУстановите: apt install ffmpeg')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
        finally:
            if os.path.exists(voice_file):
                os.remove(voice_file)
            if os.path.exists(wav_file):
                os.remove(wav_file)
