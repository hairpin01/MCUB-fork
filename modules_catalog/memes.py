# requires: Pillow
import io
from PIL import Image, ImageDraw, ImageFont
from telethon import events

def add_text_to_image(image_bytes, top_text, bottom_text):
    img = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(img)
    
    width, height = img.size
    font_size = int(height / 10)
    
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    def draw_text_with_outline(text, position):
        x, y = position
        for adj_x in range(-2, 3):
            for adj_y in range(-2, 3):
                draw.text((x + adj_x, y + adj_y), text, font=font, fill='black')
        draw.text(position, text, font=font, fill='white')
    
    if top_text:
        bbox = draw.textbbox((0, 0), top_text, font=font)
        text_width = bbox[2] - bbox[0]
        draw_text_with_outline(top_text, ((width - text_width) / 2, 10))
    
    if bottom_text:
        bbox = draw.textbbox((0, 0), bottom_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw_text_with_outline(bottom_text, ((width - text_width) / 2, height - text_height - 10))
    
    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.meme(?:\s+(.+))?'))
    async def meme_handler(event):
        args = event.pattern_match.group(1)
        
        if not event.is_reply:
            await event.edit('❌ Ответьте на изображение\n\nИспользование: .meme верхний текст | нижний текст')
            return
        
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.edit('❌ Сообщение должно содержать изображение')
            return
        
        if not args:
            await event.edit('❌ Укажите текст\n\nПример: .meme когда код работает | с первого раза')
            return
        
        parts = args.split('|')
        top_text = parts[0].strip().upper() if len(parts) > 0 else ''
        bottom_text = parts[1].strip().upper() if len(parts) > 1 else ''
        
        await event.edit('🎨 Создание мема...')
        
        try:
            image_bytes = await reply.download_media(bytes)
            meme_image = add_text_to_image(image_bytes, top_text, bottom_text)
            
            await event.delete()
            await client.send_file(event.chat_id, meme_image, reply_to=reply.id)
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
