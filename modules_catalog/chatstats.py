import sqlite3
from telethon import events
from datetime import datetime, timedelta

DB_FILE = 'chatstats.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (chat_id INTEGER, user_id INTEGER, username TEXT, 
                  first_name TEXT, timestamp INTEGER)''')
    conn.commit()
    conn.close()

def register(bot):
    init_db()
    
    @bot.on(events.NewMessage)
    async def track_message(event):
        if event.is_private:
            return
        
        sender = await event.get_sender()
        if not sender:
            return
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO messages VALUES (?, ?, ?, ?, ?)',
                  (event.chat_id, sender.id, sender.username or '', 
                   sender.first_name or '', int(datetime.now().timestamp())))
        conn.commit()
        conn.close()
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.chatstats$'))
    async def chatstats(event):
        await event.edit('📊 Собираю статистику...')
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Общая статистика
        c.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (event.chat_id,))
        total = c.fetchone()[0]
        
        # За последние 24 часа
        day_ago = int((datetime.now() - timedelta(days=1)).timestamp())
        c.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND timestamp > ?', 
                  (event.chat_id, day_ago))
        day_count = c.fetchone()[0]
        
        # Топ 10 пользователей
        c.execute('''SELECT user_id, first_name, username, COUNT(*) as cnt 
                     FROM messages WHERE chat_id = ? 
                     GROUP BY user_id ORDER BY cnt DESC LIMIT 10''', (event.chat_id,))
        top_users = c.fetchall()
        
        conn.close()
        
        msg = f'📊 **Статистика чата**\n\n'
        msg += f'📝 Всего сообщений: **{total}**\n'
        msg += f'📅 За 24 часа: **{day_count}**\n\n'
        msg += '👥 **Топ пользователей:**\n'
        
        for i, (uid, fname, uname, cnt) in enumerate(top_users, 1):
            name = fname or uname or f'User {uid}'
            msg += f'{i}. {name}: **{cnt}** сообщений\n'
        
        await event.edit(msg)
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.chatstats clear$'))
    async def clear_stats(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE chat_id = ?', (event.chat_id,))
        conn.commit()
        conn.close()
        await event.edit('🗑️ Статистика чата очищена')
