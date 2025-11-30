# mcdeleter.py

__version__ = (1, 0, 0)

import asyncio
from .. import loader, utils

@loader.tds
class MCDeleterPlugin(loader.Module):
    """Модуль для быстрого удаления сообщений"""

    strings = {
        "name": "MCDeleter",
        "deleting": "🗑️ Удаляю сообщения...",
        "deleted_single": "✅ Удалено 1 сообщение",
        "deleted_multiple": "✅ Удалено {} сообщений",
        "deleted_user": "✅ Удалено {} сообщений пользователя {}",
        "no_messages": "❌ Не найдено сообщений для удаления",
        "no_reply": "❌ Ответьте на сообщение для удаления",
        "error": "❌ Ошибка удаления: {}",
        "help_text": """🗑️ <b>MCDeleter - Удаление сообщений:</b>

<code>.mcdel</code> - удалить сообщение (ответьте на сообщение)
<code>.mcdel [число]</code> - удалить несколько сообщений
<code>.mcdel user</code> - удалить сообщения пользователя (ответьте на сообщение)
<code>.mcdel user [число]</code> - удалить несколько сообщений пользователя
<code>.mcdel me [число]</code> - удалить свои сообщения
<code>.mcdel from [ID]</code> - удалить сообщения от пользователя с ID
<code>.mcdel all</code> - удалить все сообщения в чате (админы)
<code>.mcdelhelp</code> - эта справка

💡 <b>Особенности:</b>
• Быстрое удаление без подтверждения
• Поддержка разных режимов удаления
• Безопасное удаление с проверкой прав"""
    }

    strings_ru = {
        "name": "MCDeleter",
        "help_text": """🗑️ <b>MCDeleter - Удаление сообщений:</b>

<code>.mcdel</code> - удалить сообщение (ответьте на сообщение)
<code>.mcdel [число]</code> - удалить несколько сообщений
<code>.mcdel user</code> - удалить сообщения пользователя (ответьте на сообщение)
<code>.mcdel user [число]</code> - удалить несколько сообщений пользователя
<code>.mcdel me [число]</code> - удалить свои сообщения
<code>.mcdel from [ID]</code> - удалить сообщения от пользователя с ID
<code>.mcdel all</code> - удалить все сообщения в чате (админы)
<code>.mcdelhelp</code> - эта справка"""
    }

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    async def _get_user_info(self, user_id):
        """Получение информации о пользователе"""
        try:
            user = await self.client.get_entity(user_id)
            if hasattr(user, 'username') and user.username:
                return f"@{user.username}"
            elif hasattr(user, 'first_name'):
                name = user.first_name
                if hasattr(user, 'last_name') and user.last_name:
                    name += f" {user.last_name}"
                return name
            else:
                return f"User_{user_id}"
        except:
            return f"User_{user_id}"

    async def _delete_messages(self, message, messages):
        """Удаление сообщений с обработкой ошибок"""
        if not messages:
            return 0
        
        deleted_count = 0
        for msg in messages:
            try:
                await msg.delete()
                deleted_count += 1
                await asyncio.sleep(0.1)  # Небольшая задержка чтобы не спамить API
            except Exception as e:
                continue
        
        return deleted_count

    async def mcdelcmd(self, message):
        """Удаление сообщений"""
        args = utils.get_args_raw(message)
        chat_id = utils.get_chat_id(message)
        
        # Обработка разных режимов
        if args and args.lower() == 'all':
            await self._delete_all_messages(message)
            return
        
        if args and args.lower() == 'me':
            count = 10  # по умолчанию 10 сообщений
            if ' ' in args:
                parts = args.split()
                if len(parts) > 1 and parts[1].isdigit():
                    count = min(int(parts[1]), 100)
            await self._delete_my_messages(message, count)
            return
        
        if args and args.lower().startswith('from '):
            parts = args.split()
            if len(parts) >= 2:
                user_id = parts[1]
                count = 10
                if len(parts) >= 3 and parts[2].isdigit():
                    count = min(int(parts[2]), 50)
                await self._delete_from_user(message, user_id, count)
            return
        
        if args and args.lower() == 'user':
            # Удаление сообщений пользователя
            reply = await message.get_reply_message()
            if not reply:
                await utils.answer(message, self.strings("no_reply"))
                return
            
            user_id = reply.sender_id
            count = 10  # по умолчанию 10 сообщений
            await self._delete_user_messages(message, user_id, count)
            return
        
        if args and args.lower().startswith('user '):
            # Удаление N сообщений пользователя
            parts = args.split()
            if len(parts) >= 2 and parts[1].isdigit():
                reply = await message.get_reply_message()
                if not reply:
                    await utils.answer(message, self.strings("no_reply"))
                    return
                
                user_id = reply.sender_id
                count = min(int(parts[1]), 50)
                await self._delete_user_messages(message, user_id, count)
                return
        
        # Удаление одиночного сообщения (реплай)
        reply = await message.get_reply_message()
        if reply:
            await self._delete_single_message(message, reply)
            return
        
        # Удаление нескольких сообщений
        count = 1
        if args and args.isdigit():
            count = min(int(args), 100)
        
        if count > 1:
            await self._delete_multiple_messages(message, count)
        else:
            await utils.answer(message, "❌ Ответьте на сообщение для удаления или укажите количество")

    async def _delete_single_message(self, message, target_message):
        """Удаление одного сообщения"""
        m = await utils.answer(message, self.strings("deleting"))
        msg = m[0] if isinstance(m, list) else m
        
        try:
            await target_message.delete()
            await msg.edit(self.strings("deleted_single"))
            
            # Удаляем сообщение с результатом через 2 секунды
            await asyncio.sleep(2)
            await msg.delete()
            
        except Exception as e:
            await msg.edit(self.strings("error").format(str(e)))

    async def _delete_multiple_messages(self, message, count):
        """Удаление нескольких сообщений"""
        m = await utils.answer(message, self.strings("deleting"))
        msg = m[0] if isinstance(m, list) else m
        
        try:
            chat_id = utils.get_chat_id(message)
            messages_to_delete = []
            
            async for msg_obj in self.client.iter_messages(chat_id, limit=count):
                messages_to_delete.append(msg_obj)
            
            if not messages_to_delete:
                await utils.answer(message, self.strings("no_messages"))
                return
            
            deleted_count = await self._delete_messages(message, messages_to_delete)
            
            await msg.edit(self.strings("deleted_multiple").format(deleted_count))
            
            # Удаляем сообщение с результатом через 2 секунды
            await asyncio.sleep(2)
            await msg.delete()
            
        except Exception as e:
            await msg.edit(self.strings("error").format(str(e)))

    async def _delete_user_messages(self, message, user_id, count):
        """Удаление сообщений конкретного пользователя"""
        m = await utils.answer(message, self.strings("deleting"))
        msg = m[0] if isinstance(m, list) else m
        
        try:
            chat_id = utils.get_chat_id(message)
            user_info = await self._get_user_info(user_id)
            
            messages_to_delete = []
            async for msg_obj in self.client.iter_messages(chat_id, limit=count * 2):
                if msg_obj.sender_id == user_id:
                    messages_to_delete.append(msg_obj)
                if len(messages_to_delete) >= count:
                    break
            
            if not messages_to_delete:
                await utils.answer(message, f"❌ Не найдено сообщений от {user_info}")
                return
            
            deleted_count = await self._delete_messages(message, messages_to_delete)
            
            await msg.edit(self.strings("deleted_user").format(deleted_count, user_info))
            
            # Удаляем сообщение с результатом через 2 секунды
            await asyncio.sleep(2)
            await msg.delete()
            
        except Exception as e:
            await msg.edit(self.strings("error").format(str(e)))

    async def _delete_my_messages(self, message, count):
        """Удаление своих сообщений"""
        m = await utils.answer(message, self.strings("deleting"))
        msg = m[0] if isinstance(m, list) else m
        
        try:
            chat_id = utils.get_chat_id(message)
            my_id = (await self.client.get_me()).id
            
            messages_to_delete = []
            async for msg_obj in self.client.iter_messages(chat_id, limit=count * 2):
                if msg_obj.sender_id == my_id:
                    messages_to_delete.append(msg_obj)
                if len(messages_to_delete) >= count:
                    break
            
            if not messages_to_delete:
                await utils.answer(message, "❌ Не найдено ваших сообщений")
                return
            
            deleted_count = await self._delete_messages(message, messages_to_delete)
            
            await msg.edit(self.strings("deleted_multiple").format(deleted_count))
            
            # Удаляем сообщение с результатом через 2 секунды
            await asyncio.sleep(2)
            await msg.delete()
            
        except Exception as e:
            await msg.edit(self.strings("error").format(str(e)))

    async def _delete_from_user(self, message, user_id_str, count):
        """Удаление сообщений от пользователя по ID"""
        m = await utils.answer(message, self.strings("deleting"))
        msg = m[0] if isinstance(m, list) else m
        
        try:
            chat_id = utils.get_chat_id(message)
            
            # Пробуем преобразовать ID
            try:
                user_id = int(user_id_str)
            except ValueError:
                await utils.answer(message, "❌ Неверный ID пользователя")
                return
            
            user_info = await self._get_user_info(user_id)
            
            messages_to_delete = []
            async for msg_obj in self.client.iter_messages(chat_id, limit=count * 2):
                if msg_obj.sender_id == user_id:
                    messages_to_delete.append(msg_obj)
                if len(messages_to_delete) >= count:
                    break
            
            if not messages_to_delete:
                await utils.answer(message, f"❌ Не найдено сообщений от пользователя {user_info}")
                return
            
            deleted_count = await self._delete_messages(message, messages_to_delete)
            
            await msg.edit(self.strings("deleted_user").format(deleted_count, user_info))
            
            # Удаляем сообщение с результатом через 2 секунды
            await asyncio.sleep(2)
            await msg.delete()
            
        except Exception as e:
            await msg.edit(self.strings("error").format(str(e)))

    async def _delete_all_messages(self, message):
        """Удаление всех сообщений в чате (только для админов)"""
        m = await utils.answer(message, "🗑️ Удаляю все сообщения...")
        msg = m[0] if isinstance(m, list) else m
        
        try:
            chat_id = utils.get_chat_id(message)
            
            # Проверяем права администратора
            chat = await self.client.get_entity(chat_id)
            if not hasattr(chat, 'admin_rights') or not chat.admin_rights:
                await utils.answer(message, "❌ Эта команда доступна только администраторам чата")
                return
            
            deleted_count = 0
            batch_size = 100
            
            while True:
                messages_to_delete = []
                async for msg_obj in self.client.iter_messages(chat_id, limit=batch_size):
                    messages_to_delete.append(msg_obj)
                
                if not messages_to_delete:
                    break
                
                deleted_count += await self._delete_messages(message, messages_to_delete)
                
                # Обновляем статус
                await msg.edit(f"🗑️ Удалено {deleted_count} сообщений...")
            
            await msg.edit(f"✅ Удалено всех сообщений: {deleted_count}")
            
            # Удаляем сообщение с результатом через 3 секунды
            await asyncio.sleep(3)
            await msg.delete()
            
        except Exception as e:
            await msg.edit(self.strings("error").format(str(e)))

    async def mcdelhelpcmd(self, message):
        """Справка по командам удаления"""
        await utils.answer(message, self.strings("help_text"))