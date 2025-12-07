# requires: qrcode, pyzbar, Pillow
import io
import qrcode
from PIL import Image
from pyzbar.pyzbar import decode
from telethon import events

def generate_qr(text):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output

def read_qr(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    decoded = decode(img)
    if decoded:
        return decoded[0].data.decode('utf-8')
    return None

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.qr\s+(.+)'))
    async def qr_generate(event):
        text = event.pattern_match.group(1)
        await event.edit('📱 Генерация QR-кода...')
        
        try:
            qr_image = generate_qr(text)
            await event.delete()
            await client.send_file(event.chat_id, qr_image, caption=f'QR-код для: `{text}`')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.readqr$'))
    async def qr_read(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на изображение с QR-кодом')
            return
        
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.edit('❌ Сообщение должно содержать изображение')
            return
        
        await event.edit('🔍 Чтение QR-кода...')
        
        try:
            image_bytes = await reply.download_media(bytes)
            result = read_qr(image_bytes)
            
            if result:
                await event.edit(f'✅ **QR-код распознан:**\n\n`{result}`')
            else:
                await event.edit('❌ QR-код не найден на изображении')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
