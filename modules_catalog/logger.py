import sqlite3
from telethon import events
from datetime import datetime

DB_FILE = 'logger.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS deleted
                 (chat_id INTEGER, user_id INTEGER, username TEXT, 
                  first_name TEXT, message TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS edited
                 (chat_id INTEGER, user_id INTEGER, username TEXT, 
                  first_name TEXT, old_text TEXT, new_text TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logging
                 (chat_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def register(bot):
    init_db()
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.log on$'))
    async def log_on(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO logging VALUES (?)', (event.chat_id,))
        conn.commit()
        conn.close()
        await event.edit('✅ Логирование включено для этого чата')
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.log off$'))
    async def log_off(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM logging WHERE chat_id = ?', (event.chat_id,))
        conn.commit()
        conn.close()
        await event.edit('🔕 Логирование отключено для этого чата')
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.deleted$'))
    async def show_deleted(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT * FROM deleted WHERE chat_id = ? 
                     ORDER BY timestamp DESC LIMIT 10''', (event.chat_id,))
        msgs = c.fetchall()
        conn.close()
        
        if not msgs:
            await event.edit('📋 Нет удаленных сообщений')
            return
        
        msg = '🗑️ **Последние удаленные сообщения:**\n\n'
        for chat_id, uid, uname, fname, text, ts in msgs:
            dt = datetime.fromtimestamp(ts).strftime('%d.%m %H:%M')
            name = fname or uname or f'User {uid}'
            msg += f'**{dt}** - {name}:\n{text[:100]}...\n\n' if len(text) > 100 else f'**{dt}** - {name}:\n{text}\n\n'
        
        await event.edit(msg)
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.edited$'))
    async def show_edited(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT * FROM edited WHERE chat_id = ? 
                     ORDER BY timestamp DESC LIMIT 10''', (event.chat_id,))
        msgs = c.fetchall()
        conn.close()
        
        if not msgs:
            await event.edit('📋 Нет отредактированных сообщений')
            return
        
        msg = '✏️ **Последние отредактированные сообщения:**\n\n'
        for chat_id, uid, uname, fname, old, new, ts in msgs:
            dt = datetime.fromtimestamp(ts).strftime('%d.%m %H:%M')
            name = fname or uname or f'User {uid}'
            msg += f'**{dt}** - {name}:\n'
            msg += f'Было: {old[:50]}...\n' if len(old) > 50 else f'Было: {old}\n'
            msg += f'Стало: {new[:50]}...\n\n' if len(new) > 50 else f'Стало: {new}\n\n'
        
        await event.edit(msg)
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.log clear$'))
    async def clear_logs(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM deleted WHERE chat_id = ?', (event.chat_id,))
        c.execute('DELETE FROM edited WHERE chat_id = ?', (event.chat_id,))
        conn.commit()
        conn.close()
        await event.edit('🗑️ Логи чата очищены')
    
    message_cache = {}
    
    @bot.on(events.NewMessage)
    async def cache_message(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT chat_id FROM logging WHERE chat_id = ?', (event.chat_id,))
        if not c.fetchone():
            conn.close()
            return
        conn.close()
        
        if event.text:
            message_cache[event.id] = event.text
    
    @bot.on(events.MessageDeleted)
    async def log_deleted(event):
        for msg_id in event.deleted_ids:
            if msg_id in message_cache:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute('SELECT chat_id FROM logging WHERE chat_id = ?', (event.chat_id,))
                if c.fetchone():
                    c.execute('INSERT INTO deleted VALUES (?, ?, ?, ?, ?, ?)',
                              (event.chat_id, 0, '', 'Unknown', 
                               message_cache[msg_id], int(datetime.now().timestamp())))
                    conn.commit()
                conn.close()
                del message_cache[msg_id]
    
    @bot.on(events.MessageEdited)
    async def log_edited(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT chat_id FROM logging WHERE chat_id = ?', (event.chat_id,))
        if not c.fetchone():
            conn.close()
            return
        
        old_text = message_cache.get(event.id, '')
        new_text = event.text or ''
        
        if old_text and old_text != new_text:
            sender = await event.get_sender()
            c.execute('INSERT INTO edited VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (event.chat_id, sender.id if sender else 0, 
                       sender.username if sender else '', 
                       sender.first_name if sender else 'Unknown',
                       old_text, new_text, int(datetime.now().timestamp())))
            conn.commit()
            message_cache[event.id] = new_text
        
        conn.close()
