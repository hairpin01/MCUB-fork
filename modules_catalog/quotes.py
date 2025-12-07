from telethon import events
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap

async def create_quote(client, message):
    sender = await message.get_sender()
    name = sender.first_name or "User"
    text = message.text or "[Медиа]"
    
    # Скачиваем аватарку
    avatar_bytes = None
    try:
        photos = await client.get_profile_photos(sender, limit=1)
        if photos:
            avatar_bytes = await client.download_media(photos[0], bytes)
    except:
        pass
    
    # Создаем изображение
    width = 800
    padding = 40
    avatar_size = 80
    
    # Подготовка текста
    try:
        font_name = ImageFont.truetype("arial.ttf", 32)
        font_text = ImageFont.truetype("arial.ttf", 28)
    except:
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    # Разбиваем текст на строки
    temp_img = Image.new('RGB', (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    
    wrapped_lines = []
    for line in text.split('\n'):
        wrapped = textwrap.wrap(line, width=35)
        wrapped_lines.extend(wrapped if wrapped else [''])
    
    # Вычисляем высоту
    text_height = len(wrapped_lines) * 40
    height = padding * 2 + avatar_size + 30 + text_height + 40
    
    # Создаем финальное изображение
    img = Image.new('RGB', (width, height), '#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Рисуем декоративную линию сверху
    draw.rectangle([0, 0, width, 8], fill='#16213e')
    
    # Рисуем аватарку
    avatar_x = padding
    avatar_y = padding + 20
    
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes))
            avatar = avatar.resize((avatar_size, avatar_size))
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            img.paste(avatar, (avatar_x, avatar_y), mask)
        except:
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill='#0f3460')
    else:
        draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill='#0f3460')
    
    # Рисуем имя
    name_x = avatar_x + avatar_size + 20
    name_y = avatar_y + 25
    draw.text((name_x, name_y), name, fill='#e94560', font=font_name)
    
    # Рисуем кавычки
    quote_y = avatar_y + avatar_size + 30
    draw.text((padding, quote_y), '"', fill='#e94560', font=ImageFont.truetype("arial.ttf", 60) if font_name != ImageFont.load_default() else font_name)
    
    # Рисуем текст цитаты
    text_y = quote_y + 50
    for i, line in enumerate(wrapped_lines):
        draw.text((padding + 30, text_y + i * 40), line, fill='#ffffff', font=font_text)
    
    # Закрывающая кавычка
    last_line_y = text_y + len(wrapped_lines) * 40
    draw.text((width - padding - 40, last_line_y), '"', fill='#e94560', font=ImageFont.truetype("arial.ttf", 60) if font_name != ImageFont.load_default() else font_name)
    
    # Сохраняем
    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    
    return output

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.quote$'))
    async def quote_handler(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на сообщение')
            return
        
        await event.edit('🎨 Создаю цитату...')
        
        reply = await event.get_reply_message()
        quote_img = await create_quote(client, reply)
        
        await client.send_file(event.chat_id, quote_img, force_document=False)
        await event.delete()
