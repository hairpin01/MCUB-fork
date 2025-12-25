# requires: json

import json
import html

def register(kernel):
    client = kernel.client
    
    SENSITIVE_KEYS = ['inline_bot_token', 'api_id', 'api_hash', 'phone']
    DEFAULT_VALUES = {
        'command_prefix': '.',
        'aliases': {},
        'power_save_mode': False,
        '2fa_enabled': False,
        'healthcheck_interval': 30,
        'developer_chat_id': None,
        'language': 'ru',
        'theme': 'default',
        'proxy': None,
        'inline_bot_username': None,
        'db_version': 2,
        'hidden_keys': []
    }

    async def save_config():
        try:
            with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            await kernel.handle_error(e, source="save_config")

    def parse_value(value_str, expected_type=None):
        value_str = value_str.strip()
        
        if value_str.lower() == 'null':
            return None
            
        if expected_type:
            if expected_type == 'bool':
                if value_str.lower() == 'true':
                    return True
                elif value_str.lower() == 'false':
                    return False
                else:
                    raise ValueError("Значение должно быть true или false")
            elif expected_type == 'int':
                if value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
                    return int(value_str)
                else:
                    raise ValueError("Значение должно быть целым числом")
            elif expected_type == 'float':
                try:
                    return float(value_str)
                except ValueError:
                    raise ValueError("Значение должно быть числом")
            elif expected_type == 'dict':
                try:
                    return json.loads(value_str)
                except json.JSONDecodeError:
                    raise ValueError("Значение должно быть валидным JSON объектом")
            elif expected_type == 'list':
                try:
                    return json.loads(value_str)
                except json.JSONDecodeError:
                    raise ValueError("Значение должно быть валидным JSON массивом")
            elif expected_type == 'str':
                return value_str
        
        if value_str.lower() == 'true':
            return True
        elif value_str.lower() == 'false':
            return False
        elif value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
            return int(value_str)
        elif value_str.replace('.', '', 1).isdigit() and value_str.count('.') == 1:
            return float(value_str)
        elif value_str.startswith('{') and value_str.endswith('}'):
            try:
                return json.loads(value_str)
            except:
                return value_str
        elif value_str.startswith('[') and value_str.endswith(']'):
            try:
                return json.loads(value_str)
            except:
                return value_str
        else:
            return value_str

    def is_key_hidden(key):
        hidden_keys = kernel.config.get('hidden_keys', [])
        return key in SENSITIVE_KEYS or key in hidden_keys

    def format_key(key, value_type):
        hidden = is_key_hidden(key)
        
        emojis = {
            'str': '📝',
            'int': '🔢', 
            'float': '🔢',
            'bool': '⚡',
            'list': '📋',
            'dict': '📚',
            'NoneType': '⚫'
        }
        emoji = emojis.get(value_type, '🔘')
        
        if hidden:
            return f"🔒 {emoji} <tg-spoiler><b>{key}</b></tg-spoiler>"
        else:
            return f"{emoji} <code>{key}</code>"

    @kernel.register_command('cfg')
    async def cfg_handler(event):
        try:
            args = event.text.split()
            
            if len(args) == 1:
                visible_keys = []
                hidden_keys = kernel.config.get('hidden_keys', [])
                all_keys = len(kernel.config)
                system_hidden = len([k for k in kernel.config if k in SENSITIVE_KEYS])
                user_hidden = len(hidden_keys)
                visible_count = all_keys - system_hidden - user_hidden
                
                for key, value in kernel.config.items():
                    if not is_key_hidden(key):
                        value_type = type(value).__name__
                        visible_keys.append(format_key(key, value_type))
                
                response = f"""🔮 <b>Конфигурация ядра</b>
<blockquote>📊 <b>Всего ключей:</b> <code>{all_keys}</code>
👁️ <b>Видимых:</b> <code>{visible_count}</code>
🔐 <b>Скрыто системой:</b> <code>{system_hidden}</code>
🎭 <b>Скрыто пользователем:</b> <code>{user_hidden}</code></blockquote>"""
                
                if visible_keys:
                    response += f"\n\n📋 <b>Доступные ключи:</b>\n{chr(10).join(visible_keys)}"
                
                response += """\n\n💠 <i>Используйте:</i>
<blockquote><code>.cfg</code> - этот список
<code>.cfg now ключ</code> - значение ключа
<code>.cfg hide ключ</code> - скрыть ключ
<code>.cfg unhide ключ</code> - показать ключ</blockquote>"""
                
                await event.edit(response, parse_mode='html')
                
            elif len(args) >= 3:
                subcommand = args[1].lower()
                key = args[2].strip()
                
                if subcommand == 'now':
                    if is_key_hidden(key):
                        if key in SENSITIVE_KEYS:
                            await event.edit(f"🔒 <b>Доступ запрещен</b>\n<blockquote>🎩 <i>Ключ <code>{key}</code> является системным</i></blockquote>", parse_mode='html')
                        else:
                            await event.edit(f"🎭 <b>Ключ скрыт</b>\n<blockquote>🃏 <i>Ключ <code>{key}</code> скрыт пользователем</i></blockquote>", parse_mode='html')
                        return
                    
                    if key not in kernel.config:
                        await event.edit(f"🃏 <b>Ключ не найден</b>\n<blockquote>🔍 <i><code>{key}</code> не существует в конфигурации</i></blockquote>", parse_mode='html')
                        return
                    
                    value = kernel.config[key]
                    value_type = type(value).__name__
                    
                    if isinstance(value, dict):
                        formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                        formatted_lines = formatted_value.split('\n')
                        formatted_lines = formatted_lines[1:-1] if len(formatted_lines) > 2 else []
                        formatted_value = '\n'.join(formatted_lines)
                        display_value = f"<blockquote><pre>{html.escape(formatted_value)}</pre></blockquote>"
                    elif isinstance(value, list):
                        formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                        formatted_lines = formatted_value.split('\n')
                        formatted_lines = formatted_lines[1:-1] if len(formatted_lines) > 2 else []
                        formatted_value = '\n'.join(formatted_lines)
                        display_value = f"<blockquote><pre>{html.escape(formatted_value)}</pre></blockquote>"
                    elif value is None:
                        display_value = "<code>null</code>"
                    elif isinstance(value, bool):
                        display_value = f"<code>{'true' if value else 'false'}</code>"
                    elif isinstance(value, (int, float)):
                        display_value = f"<code>{value}</code>"
                    else:
                        display_value = f"<blockquote>{html.escape(str(value))}</blockquote>"
                    
                    response = f"""⚗️ <b>Ключ:</b> <code>{key}</code>
📊 <b>Тип:</b> <code>{value_type}</code>
💠 <b>Значение:</b>

{display_value}"""
                    await event.edit(response, parse_mode='html')
                    
                elif subcommand == 'hide':
                    if key in SENSITIVE_KEYS:
                        await event.edit(f"🔒 <b>Запрещено</b>\n<blockquote>🖋️ <i>Ключ <code>{key}</code> является системным</i></blockquote>", parse_mode='html')
                        return
                    
                    if key not in kernel.config:
                        await event.edit(f"🃏 <b>Ключ не найден</b>\n<blockquote>🔍 <i><code>{key}</code> не существует в конфигурации</i></blockquote>", parse_mode='html')
                        return
                    
                    hidden_keys = kernel.config.get('hidden_keys', [])
                    if key in hidden_keys:
                        await event.edit(f"🎭 <b>Ключ уже скрыт</b>\n<blockquote>🃏 <i>Ключ <code>{key}</code> уже в списке скрытых</i></blockquote>", parse_mode='html')
                        return
                    
                    hidden_keys.append(key)
                    kernel.config['hidden_keys'] = hidden_keys
                    await save_config()
                    
                    await event.edit(f"🔒 <b>Ключ скрыт</b>\n<blockquote>🎭 <i>Ключ <code>{key}</code> добавлен в список скрытых</i>\n📊 <b>Всего скрыто:</b> <code>{len(hidden_keys)}</code></blockquote>", parse_mode='html')
                    
                elif subcommand == 'unhide':
                    if key in SENSITIVE_KEYS:
                        await event.edit(f"🔒 <b>Запрещено</b>\n<blockquote>🖋️ <i>Ключ <code>{key}</code> является системным</i></blockquote>", parse_mode='html')
                        return
                    
                    hidden_keys = kernel.config.get('hidden_keys', [])
                    if key not in hidden_keys:
                        await event.edit(f"🎭 <b>Ключ не скрыт</b>\n<blockquote>🃏 <i>Ключ <code>{key}</code> не найден в списке скрытых</i></blockquote>", parse_mode='html')
                        return
                    
                    hidden_keys.remove(key)
                    kernel.config['hidden_keys'] = hidden_keys
                    await save_config()
                    
                    await event.edit(f"👁️ <b>Ключ показан</b>\n<blockquote>🎭 <i>Ключ <code>{key}</code> удален из списка скрытых</i>\n📊 <b>Осталось скрыто:</b> <code>{len(hidden_keys)}</code></blockquote>", parse_mode='html')
                    
                elif subcommand == 'added' and len(args) >= 4:
                    if is_key_hidden(key):
                        await event.edit(f"🎭 <b>Ключ скрыт</b>\n<blockquote>🃏 <i>Ключ <code>{key}</code> скрыт пользователем</i></blockquote>", parse_mode='html')
                        return
                    
                    if key not in kernel.config:
                        await event.edit(f"🃏 <b>Ключ не найден</b>\n<blockquote>🔍 <i><code>{key}</code> не существует в конфигурации</i></blockquote>", parse_mode='html')
                        return
                    
                    current_value = kernel.config[key]
                    value_type = type(current_value).__name__
                    
                    if value_type == 'dict':
                        if len(args) < 5:
                            await event.edit("🔶 <b>Недостаточно аргументов</b>\n<blockquote>📝 <code>.cfg added ключ подключа значение</code></blockquote>", parse_mode='html')
                            return
                        
                        subkey = args[3].strip()
                        value_str = ' '.join(args[4:]).strip()
                        
                        try:
                            value = parse_value(value_str)
                            current_value[subkey] = value
                            kernel.config[key] = current_value
                            await save_config()
                            
                            await event.edit(f"📚 <b>Элемент добавлен в словарь</b>\n<blockquote>🧩 <code>{key}.{subkey}</code> → <code>{value}</code></blockquote>", parse_mode='html')
                        except Exception as e:
                            await event.edit(f"❄️ <b>Ошибка значения</b>\n<blockquote>🐍 <i>{str(e)}</i></blockquote>", parse_mode='html')
                            
                    elif value_type == 'list':
                        if len(args) < 4:
                            await event.edit("🔶 <b>Недостаточно аргументов</b>\n<blockquote>📝 <code>.cfg added ключ значение</code></blockquote>", parse_mode='html')
                            return
                        
                        value_str = ' '.join(args[3:]).strip()
                        
                        try:
                            value = parse_value(value_str)
                            current_value.append(value)
                            kernel.config[key] = current_value
                            await save_config()
                            
                            await event.edit(f"📋 <b>Элемент добавлен в список</b>\n<blockquote>🧩 <code>{key}</code> → <code>{value}</code>\n📊 <b>Размер списка:</b> <code>{len(current_value)}</code></blockquote>", parse_mode='html')
                        except Exception as e:
                            await event.edit(f"❄️ <b>Ошибка значения</b>\n<blockquote>🐍 <i>{str(e)}</i></blockquote>", parse_mode='html')
                    else:
                        await event.edit(f"💔 <b>Неподходящий тип</b>\n<blockquote>📊 <i>Ключ <code>{key}</code> имеет тип <code>{value_type}</code>, а не dict/list</i></blockquote>", parse_mode='html')
                    
                else:
                    await event.edit("🔭 <b>Неизвестная подкоманда</b>\n<blockquote>💠 <i>Доступные подкоманды:</i>\n<code>now</code> - значение ключа\n<code>hide</code> - скрыть ключ\n<code>unhide</code> - показать ключ\n<code>added</code> - добавить в dict/list</blockquote>", parse_mode='html')
                    
            else:
                await event.edit("🔭 <b>Использование</b>\n<blockquote>📖 <code>.cfg</code> - список ключей\n📖 <code>.cfg now ключ</code> - значение ключа\n📖 <code>.cfg hide ключ</code> - скрыть ключ\n📖 <code>.cfg unhide ключ</code> - показать ключ\n📖 <code>.cfg added ключ ...</code> - добавить в dict/list</blockquote>", parse_mode='html')
                
        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="cfg", event=event)

    @kernel.register_command('fcfg')
    async def fcfg_handler(event):
        try:
            args = event.text.split()
            
            if len(args) < 2:
                await event.edit("🎩 <b>Использование</b>\n<blockquote>⚡ <code>.fcfg set ключ значение</code>\n⚡ <code>.fcfg del ключ</code>\n⚡ <code>.fcfg add ключ значение</code>\n⚡ <code>.fcfg dict ключ подключа значение</code>\n⚡ <code>.fcfg list ключ значение</code></blockquote>", parse_mode='html')
                return
            
            action = args[1].lower()
            
            if action == 'set':
                if len(args) < 4:
                    await event.edit("🔶 <b>Недостаточно аргументов</b>\n<blockquote>📝 <code>.fcfg set ключ значение</code></blockquote>", parse_mode='html')
                    return
                
                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()
                
                if key in SENSITIVE_KEYS:
                    await event.edit(f"🔒 <b>Запрещено</b>\n<blockquote>🖋️ <i>Ключ <code>{key}</code> нельзя изменять через команды</i></blockquote>", parse_mode='html')
                    return
                
                try:
                    if key in kernel.config:
                        current_type = type(kernel.config[key]).__name__
                        value = parse_value(value_str, current_type)
                    else:
                        value = parse_value(value_str)
                    
                    old_value = kernel.config.get(key)
                    kernel.config[key] = value
                    await save_config()
                    
                    if old_value is None:
                        await event.edit(f"📡 <b>Ключ добавлен</b>\n<blockquote>🧬 <code>{key}</code> → <code>{value}</code></blockquote>", parse_mode='html')
                    else:
                        await event.edit(f"🔷 <b>Ключ обновлен</b>\n<blockquote>🔄 <code>{key}</code>\n<tg-spoiler>📤 <i>было:</i> <code>{old_value}</code>\n📥 <i>стало:</i> <code>{value}</code></tg-spoiler></blockquote>", parse_mode='html')
                        
                except Exception as e:
                    await event.edit(f"❄️ <b>Некорректное значение</b>\n<blockquote>🐍 <i>{str(e)}</i></blockquote>", parse_mode='html')
                    
            elif action == 'del':
                if len(args) < 3:
                    await event.edit("🔶 <b>Недостаточно аргументов</b>\n<blockquote>📝 <code>.fcfg del ключ</code></blockquote>", parse_mode='html')
                    return
                
                key = args[2].strip()
                
                if key in SENSITIVE_KEYS:
                    await event.edit(f"🔒 <b>Запрещено</b>\n<blockquote>🖋️ <i>Ключ <code>{key}</code> нельзя удалять</i></blockquote>", parse_mode='html')
                    return
                
                if key not in kernel.config:
                    await event.edit(f"🃏 <b>Ключ не найден</b>\n<blockquote>🔍 <i><code>{key}</code> не существует в конфигурации</i></blockquote>", parse_mode='html')
                    return
                
                old_value = kernel.config.pop(key)
                
                hidden_keys = kernel.config.get('hidden_keys', [])
                if key in hidden_keys:
                    hidden_keys.remove(key)
                    kernel.config['hidden_keys'] = hidden_keys
                
                await save_config()
                
                default_value = DEFAULT_VALUES.get(key, 'не определено')
                await event.edit(f"🧹 <b>Ключ удален</b>\n<blockquote>🗑️ <code>{key}</code>\n<tg-spoiler>📤 <i>было:</i> <code>{old_value}</code>\n⚫ <i>умолчание:</i> <code>{default_value}</code></tg-spoiler></blockquote>", parse_mode='html')
                
            elif action == 'add':
                if len(args) < 4:
                    await event.edit("🔶 <b>Недостаточно аргументов</b>\n<blockquote>📝 <code>.fcfg add ключ значение</code></blockquote>", parse_mode='html')
                    return
                
                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()
                
                if key in kernel.config:
                    await event.edit(f"💔 <b>Ключ уже существует</b>\n<blockquote>📝 <i>Используйте <code>.fcfg set {key} значение</code> для изменения</i></blockquote>", parse_mode='html')
                    return
                
                try:
                    value = parse_value(value_str)
                    
                    kernel.config[key] = value
                    await save_config()
                    
                    value_type = type(value).__name__
                    await event.edit(f"🍀 <b>Новый ключ добавлен</b>\n<blockquote>🧩 <code>{key}</code> → <code>{value}</code>\n📊 <i>тип:</i> <code>{value_type}</code></blockquote>", parse_mode='html')
                    
                except Exception as e:
                    await event.edit(f"❄️ <b>Некорректное значение</b>\n<blockquote>🐍 <i>{str(e)}</i></blockquote>", parse_mode='html')
            
            elif action == 'dict':
                if len(args) < 5:
                    await event.edit("🔶 <b>Недостаточно аргументов</b>\n<blockquote>📝 <code>.fcfg dict ключ подключа значение</code></blockquote>", parse_mode='html')
                    return
                
                key = args[2].strip()
                subkey = args[3].strip()
                value_str = ' '.join(args[4:]).strip()
                
                if key in SENSITIVE_KEYS:
                    await event.edit(f"🔒 <b>Запрещено</b>\n<blockquote>🖋️ <i>Ключ <code>{key}</code> нельзя изменять через команды</i></blockquote>", parse_mode='html')
                    return
                
                try:
                    if key not in kernel.config:
                        kernel.config[key] = {}
                    
                    if not isinstance(kernel.config[key], dict):
                        await event.edit(f"💔 <b>Неправильный тип</b>\n<blockquote>📊 <i>Ключ <code>{key}</code> имеет тип <code>{type(kernel.config[key]).__name__}</code>, а не dict</i></blockquote>", parse_mode='html')
                        return
                    
                    value = parse_value(value_str)
                    
                    old_value = kernel.config[key].get(subkey)
                    kernel.config[key][subkey] = value
                    await save_config()
                    
                    if old_value is None:
                        await event.edit(f"📚 <b>Элемент добавлен в словарь</b>\n<blockquote>🧩 <code>{key}.{subkey}</code> → <code>{value}</code></blockquote>", parse_mode='html')
                    else:
                        await event.edit(f"🔄 <b>Элемент обновлен в словаре</b>\n<blockquote>📚 <code>{key}.{subkey}</code>\n<tg-spoiler>📤 <i>было:</i> <code>{old_value}</code>\n📥 <i>стало:</i> <code>{value}</code></tg-spoiler></blockquote>", parse_mode='html')
                        
                except Exception as e:
                    await event.edit(f"❄️ <b>Некорректное значение</b>\n<blockquote>🐍 <i>{str(e)}</i></blockquote>", parse_mode='html')
            
            elif action == 'list':
                if len(args) < 4:
                    await event.edit("🔶 <b>Недостаточно аргументов</b>\n<blockquote>📝 <code>.fcfg list ключ значение</code></blockquote>", parse_mode='html')
                    return
                
                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()
                
                if key in SENSITIVE_KEYS:
                    await event.edit(f"🔒 <b>Запрещено</b>\n<blockquote>🖋️ <i>Ключ <code>{key}</code> нельзя изменять через команды</i></blockquote>", parse_mode='html')
                    return
                
                try:
                    if key not in kernel.config:
                        kernel.config[key] = []
                    
                    if not isinstance(kernel.config[key], list):
                        await event.edit(f"💔 <b>Неправильный тип</b>\n<blockquote>📊 <i>Ключ <code>{key}</code> имеет тип <code>{type(kernel.config[key]).__name__}</code>, а не list</i></blockquote>", parse_mode='html')
                        return
                    
                    value = parse_value(value_str)
                    
                    kernel.config[key].append(value)
                    await save_config()
                    
                    await event.edit(f"📋 <b>Элемент добавлен в список</b>\n<blockquote>🧩 <code>{key}</code> → <code>{value}</code>\n📊 <b>Размер списка:</b> <code>{len(kernel.config[key])}</code></blockquote>", parse_mode='html')
                        
                except Exception as e:
                    await event.edit(f"❄️ <b>Некорректное значение</b>\n<blockquote>🐍 <i>{str(e)}</i></blockquote>", parse_mode='html')
                    
            else:
                await event.edit("🔭 <b>Неизвестное действие</b>\n<blockquote>⚡ <code>.fcfg set ключ значение</code>\n⚡ <code>.fcfg del ключ</code>\n⚡ <code>.fcfg add ключ значение</code>\n⚡ <code>.fcfg dict ключ подключа значение</code>\n⚡ <code>.fcfg list ключ значение</code></blockquote>", parse_mode='html')
                
        except Exception as e:
            await event.edit("🌩️ <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="fcfg", event=event)