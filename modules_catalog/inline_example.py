from telethon import events
import time
import random

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.card$'))
    async def send_card(event):
        """Визитная карточка с HTML форматированием"""
        await event.delete()
        
        me = await client.get_me()
        card_text = f"""<b>📇 Визитная карточка</b>

👤 <b>Имя:</b> {me.first_name}
🆔 <b>ID:</b> <code>{me.id}</code>
📱 <b>Username:</b> @{me.username if me.username else 'Не установлен'}

💬 <i>Отправлено через UserBot</i>"""
        
        await client.send_inline(client, event.chat_id, card_text)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.links$'))
    async def send_links(event):
        """Меню с несколькими кнопками-ссылками"""
        await event.delete()
        
        menu_text = """<b>🔗 Полезные ссылки</b>

Выберите раздел:"""
        
        query = f"{menu_text} | 📚 GitHub:https://github.com | 🌐 Google:https://google.com | 💬 Telegram:https://t.me | 🎬 YouTube:https://youtube.com"
        
        await client.send_inline(client, event.chat_id, query)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.time$'))
    async def send_time(event):
        """Текущее время с форматированием"""
        await event.delete()
        
        current_time = time.strftime('%H:%M:%S')
        current_date = time.strftime('%d.%m.%Y')
        day_name = time.strftime('%A')
        
        time_text = f"""<b>🕐 Текущее время</b>

⏰ <b>Время:</b> <code>{current_time}</code>
📅 <b>Дата:</b> <code>{current_date}</code>
📆 <b>День:</b> {day_name}

<i>Обновлено автоматически</i>"""
        
        await client.send_inline(client, event.chat_id, time_text)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.announce (.+)'))
    async def send_announce(event):
        """Объявление с кнопкой"""
        await event.delete()
        
        text = event.pattern_match.group(1)
        
        announce_text = f"""<b>📢 ОБЪЯВЛЕНИЕ</b>

{text}

<i>— Администрация</i>"""
        
        query = f"{announce_text} | ✅ Понятно:https://t.me"
        
        await client.send_inline(client, event.chat_id, query)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.quote$'))
    async def send_quote(event):
        """Случайная цитата"""
        await event.delete()
        
        quotes = [
            "Код работает - не трогай!",
            "99 багов в коде, исправил один - стало 117",
            r"Работает на моей машине ¯\_(ツ)_/¯",
            "Это не баг, это фича!",
            "Комментарии в коде? Код и есть комментарий!"
        ]
        
        quote = random.choice(quotes)
        
        quote_text = f"""<b>💭 Цитата дня</b>

<i>"{quote}"</i>

— Мудрость программиста"""
        
        await client.send_inline(client, event.chat_id, quote_text)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.social$'))
    async def send_social(event):
        """Социальные сети с кнопками"""
        await event.delete()
        
        social_text = """<b>🌐 Мои социальные сети</b>

Подписывайтесь и следите за обновлениями!"""
        
        query = f"{social_text} | 📱 VK:https://vk.com | 📷 Instagram:https://instagram.com | 🐦 Twitter:https://twitter.com"
        
        await client.send_inline(client, event.chat_id, query)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.rules$'))
    async def send_rules(event):
        """Правила чата"""
        await event.delete()
        
        rules_text = """<b>📋 Правила чата</b>

1️⃣ Уважайте других участников
2️⃣ Не спамьте сообщениями
3️⃣ Запрещена реклама без разрешения
4️⃣ Будьте вежливы и культурны
5️⃣ Помогайте новичкам

<i>Нарушение правил = бан</i>"""
        
        query = f"{rules_text} | ✅ Согласен:https://t.me | ❌ Покинуть:https://t.me"
        
        await client.send_inline(client, event.chat_id, query)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.inlinehelp$'))
    async def inline_help(event):
        """Справка по инлайн-командам"""
        help_text = """<b>📖 Инлайн модуль - Справка</b>

<b>Команды:</b>
• <code>.card</code> - визитная карточка
• <code>.links</code> - полезные ссылки
• <code>.time</code> - текущее время
• <code>.announce [текст]</code> - объявление
• <code>.quote</code> - случайная цитата
• <code>.social</code> - социальные сети
• <code>.rules</code> - правила чата
• <code>.inlinehelp</code> - эта справка

<b>HTML теги:</b>
• <code>&lt;b&gt;жирный&lt;/b&gt;</code>
• <code>&lt;i&gt;курсив&lt;/i&gt;</code>
• <code>&lt;code&gt;код&lt;/code&gt;</code>

<b>Кнопки:</b>
Формат: <code>текст | Кнопка:url</code>
Пример: <code>.ibot Привет | GitHub:https://github.com</code>"""
        
        await event.edit(help_text)
