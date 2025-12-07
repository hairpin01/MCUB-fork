import sqlite3
from telethon import events
from datetime import datetime

DB_FILE = 'tracker.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS profiles
                 (user_id INTEGER, username TEXT, first_name TEXT, 
                  last_name TEXT, bio TEXT, photo_id TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tracking
                 (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def register(bot):
    init_db()
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.track$'))
    async def track_user(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на сообщение пользователя')
            return
        
        reply = await event.get_reply_message()
        user = await reply.get_sender()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO tracking VALUES (?)', (user.id,))
        
        photos = await bot.get_profile_photos(user, limit=1)
        photo_id = str(photos[0].id) if photos else ''
        
        full_user = await bot.get_entity(user.id)
        bio = full_user.about if hasattr(full_user, 'about') else ''
        
        c.execute('INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (user.id, user.username or '', user.first_name or '', 
                   user.last_name or '', bio, photo_id, int(datetime.now().timestamp())))
        conn.commit()
        conn.close()
        
        name = user.first_name or user.username or f'User {user.id}'
        await event.edit(f'✅ Отслеживание профиля **{name}** включено')
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.untrack$'))
    async def untrack_user(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на сообщение пользователя')
            return
        
        reply = await event.get_reply_message()
        user = await reply.get_sender()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM tracking WHERE user_id = ?', (user.id,))
        conn.commit()
        conn.close()
        
        name = user.first_name or user.username or f'User {user.id}'
        await event.edit(f'🔕 Отслеживание профиля **{name}** отключено')
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.tracked$'))
    async def list_tracked(event):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT user_id FROM tracking')
        users = c.fetchall()
        conn.close()
        
        if not users:
            await event.edit('📋 Нет отслеживаемых пользователей')
            return
        
        msg = '📋 **Отслеживаемые пользователи:**\n\n'
        for (uid,) in users:
            try:
                user = await bot.get_entity(uid)
                name = user.first_name or user.username or f'User {uid}'
                msg += f'• {name} (ID: {uid})\n'
            except:
                msg += f'• User {uid}\n'
        
        await event.edit(msg)
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.changes$'))
    async def show_changes(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на сообщение пользователя')
            return
        
        reply = await event.get_reply_message()
        user = await reply.get_sender()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT * FROM profiles WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10', 
                  (user.id,))
        history = c.fetchall()
        conn.close()
        
        if not history:
            await event.edit('❌ История изменений не найдена')
            return
        
        msg = f'📝 **История изменений профиля:**\n\n'
        for i, (uid, uname, fname, lname, bio, photo, ts) in enumerate(history):
            dt = datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M')
            msg += f'**{dt}**\n'
            msg += f'Имя: {fname} {lname}\n'
            if uname:
                msg += f'Username: @{uname}\n'
            if bio:
                msg += f'Био: {bio[:50]}...\n' if len(bio) > 50 else f'Био: {bio}\n'
            msg += '\n'
        
        await event.edit(msg)
    
    @bot.on(events.UserUpdate)
    async def check_updates(event):
        if not hasattr(event, 'user_id'):
            return
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT user_id FROM tracking WHERE user_id = ?', (event.user_id,))
        if not c.fetchone():
            conn.close()
            return
        
        try:
            user = await bot.get_entity(event.user_id)
            full_user = await bot.get_entity(event.user_id)
            
            c.execute('SELECT * FROM profiles WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1', 
                      (event.user_id,))
            last = c.fetchone()
            
            photos = await bot.get_profile_photos(user, limit=1)
            photo_id = str(photos[0].id) if photos else ''
            bio = full_user.about if hasattr(full_user, 'about') else ''
            
            changed = False
            changes = []
            
            if last:
                if last[1] != (user.username or ''):
                    changes.append(f'Username: @{last[1]} → @{user.username}')
                    changed = True
                if last[2] != (user.first_name or ''):
                    changes.append(f'Имя: {last[2]} → {user.first_name}')
                    changed = True
                if last[5] != photo_id and photo_id:
                    changes.append('Аватар изменен')
                    changed = True
                if last[4] != bio:
                    changes.append('Био изменено')
                    changed = True
            
            if changed:
                c.execute('INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?)',
                          (user.id, user.username or '', user.first_name or '', 
                           user.last_name or '', bio, photo_id, int(datetime.now().timestamp())))
                conn.commit()
                
                me = await bot.get_me()
                name = user.first_name or user.username or f'User {user.id}'
                msg = f'🔔 **Изменения в профиле {name}:**\n\n'
                msg += '\n'.join(changes)
                await bot.send_message(me.id, msg)
        except:
            pass
        
        conn.close()
