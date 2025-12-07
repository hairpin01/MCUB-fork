from telethon import events
from PIL import Image, ImageDraw, ImageFont
import io
import os
import json

CONFIG_FILE = 'msgsticker_config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

async def create_message_sticker(client, message):
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
    width, height = 512, 512
    img = Image.new('RGB', (width, height), '#0E1621')
    draw = ImageDraw.Draw(img)
    
    # Рисуем аватарку
    avatar_size = 80
    avatar_x, avatar_y = 20, 20
    
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes))
            avatar = avatar.resize((avatar_size, avatar_size))
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            img.paste(avatar, (avatar_x, avatar_y), mask)
        except:
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill='#2B5278')
    else:
        draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill='#2B5278')
    
    # Рисуем имя
    try:
        font_name = ImageFont.truetype("arial.ttf", 28)
        font_text = ImageFont.truetype("arial.ttf", 24)
    except:
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    name_x = avatar_x + avatar_size + 15
    name_y = avatar_y + 10
    draw.text((name_x, name_y), name, fill='white', font=font_name)
    
    # Рисуем текст сообщения
    text_x = 20
    text_y = avatar_y + avatar_size + 30
    max_width = width - 40
    
    lines = []
    words = text.split()
    current_line = ""
    
    for word in words:
        test_line = current_line + word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font_text)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
            current_line = word + " "
    if current_line:
        lines.append(current_line.strip())
    
    # Ограничиваем количество строк
    lines = lines[:12]
    
    for i, line in enumerate(lines):
        draw.text((text_x, text_y + i * 30), line, fill='#E8E8E8', font=font_text)
    
    # Сохраняем в байты
    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    
    return output

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.addsticker$'))
    async def add_sticker(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на сообщение')
            return
        
        config = load_config()
        user_id = str(event.sender_id)
        
        if user_id not in config or 'pack_name' not in config[user_id]:
            await event.edit('❌ Сначала установите стикерпак: .stickerpack <short_name>')
            return
        
        await event.edit('🎨 Создаю стикер...')
        
        reply = await event.get_reply_message()
        sticker_bytes = await create_message_sticker(client, reply)
        
        try:
            pack_name = config[user_id]['pack_name']
            
            # Отправляем стикер в @Stickers
            async with client.conversation('@Stickers') as conv:
                await conv.send_message('/addsticker')
                await conv.get_response()
                
                await conv.send_message(pack_name)
                response = await conv.get_response()
                
                if 'not found' in response.text.lower():
                    await event.edit(f'❌ Стикерпак {pack_name} не найден')
                    return
                
                await conv.send_file(sticker_bytes, force_document=False)
                await conv.get_response()
                
                await conv.send_message('😊')
                await conv.get_response()
                
                await conv.send_message('/done')
                await conv.get_response()
            
            await event.edit(f'✅ Стикер добавлен в пак: t.me/addstickers/{pack_name}')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.stickerpack (.+)$'))
    async def set_pack(event):
        pack_name = event.pattern_match.group(1).strip()
        
        # Извлекаем short_name из ссылки если нужно
        if 'addstickers/' in pack_name:
            pack_name = pack_name.split('addstickers/')[-1]
        
        config = load_config()
        user_id = str(event.sender_id)
        
        if user_id not in config:
            config[user_id] = {}
        
        config[user_id]['pack_name'] = pack_name
        save_config(config)
        
        await event.edit(f'✅ Стикерпак установлен: {pack_name}\n\nТеперь используйте .addsticker в ответ на сообщение')
