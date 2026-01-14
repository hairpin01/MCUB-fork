# requires: json, telethon>=1.24, hashlib
# author: @Hairpin00
# version: 1.0.9
# description: config kernel

import json
import html
import hashlib
from telethon import Button

# premium emoji dictionary 
CUSTOM_EMOJI = {
    '📁': '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
    '📝': '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    '📚': '<tg-emoji emoji-id="5373098009640836781">📚</tg-emoji>',
    '📖': '<tg-emoji emoji-id="5226512880362332956">📖</tg-emoji>',
    '💼': '<tg-emoji emoji-id="5359785904535774578">💼</tg-emoji>',
    '🖨': '<tg-emoji emoji-id="5386494631112353009">🖨</tg-emoji>',
    '☑️': '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
    '➕': '<tg-emoji emoji-id="5226945370684140473">➕</tg-emoji>',
    '➖': '<tg-emoji emoji-id="5229113891081956317">➖</tg-emoji>',
    '💬': '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    '🗯': '<tg-emoji emoji-id="5465132703458270101">🗯</tg-emoji>',
    '✏️': '<tg-emoji emoji-id="5334673106202010226">✏️</tg-emoji>',
    '🧊': '<tg-emoji emoji-id="5404728536810398694">🧊</tg-emoji>',
    '❄️': '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    '📎': '<tg-emoji emoji-id="5377844313575150051">📎</tg-emoji>',
    '🗳': '<tg-emoji emoji-id="5359741159566484212">🗳</tg-emoji>',
    '🗂': '<tg-emoji emoji-id="5431736674147114227">🗂</tg-emoji>',
    '📰': '<tg-emoji emoji-id="5433982607035474385">📰</tg-emoji>',
    '🔍': '<tg-emoji emoji-id="5429283852684124412">🔍</tg-emoji>',
    '📋': '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji>',
    '⚙️': '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji>',
    '🔢': '<tg-emoji emoji-id="5465154440287757794">🔢</tg-emoji>',
    '🔙': '<tg-emoji emoji-id="5332600281970517875">🔙</tg-emoji>',
}

ITEMS_PER_PAGE = 16

TYPE_EMOJIS = {
    'str': '📝',
    'int': '🔢',
    'float': '🔢',
    'bool': '☑️',
    'list': '📚',
    'dict': '🗂',
    'NoneType': '🗳'
}

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

    def get_visible_keys():
        visible_keys = []
        for key, value in kernel.config.items():
            if not is_key_hidden(key):
                visible_keys.append((key, value))
        return sorted(visible_keys, key=lambda x: x[0])

    def get_type_emoji(value_type):
        return TYPE_EMOJIS.get(value_type, '📎')

    def truncate_key(key, max_length=15):
        if len(key) > max_length:
            return key[:max_length-3] + "..."
        return key

    def generate_key_id(key, page):
        hash_obj = hashlib.md5(f"{key}_{page}".encode())
        return hash_obj.hexdigest()[:8]

    def create_buttons_grid(page_keys, page, total_pages):
        buttons = []
        row = []
        
        for i, (key, value) in enumerate(page_keys):
            display_key = truncate_key(key)
            key_id = generate_key_id(key, page)
            
            # Сохраняем соответствие ID -> (key, page) в кэше
            kernel.cache.set(f"cfg_view_{key_id}", (key, page), ttl=3600)
            
            row.append(
                Button.inline(
                    display_key,
                    data=f"cfg_view_{key_id}".encode()
                )
            )
            
            if len(row) == 4:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                Button.inline(
                    "⬅️ Назад",
                    data=f"config_page_{page - 1}".encode()
                )
            )
        
        if page < total_pages - 1:
            nav_buttons.append(
                Button.inline(
                    "Вперед ➡️",
                    data=f"config_page_{page + 1}".encode()
                )
            )
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        return buttons

    async def config_keys_inline_handler(event):
        query = event.text.strip()
        
        visible_keys = get_visible_keys()
        total_keys = len(visible_keys)
        
        page = 0
        if query.startswith('config_keys_'):
            try:
                page_str = query.split('_')[2] if len(query.split('_')) > 2 else '0'
                page = int(page_str)
            except:
                page = 0
        
        total_pages = (total_keys + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_keys > 0 else 1
        
        if page < 0:
            page = 0
        if page >= total_pages:
            page = total_pages - 1
        
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_keys = visible_keys[start_idx:end_idx]
        
        text = f"{CUSTOM_EMOJI['📋']} <b>Kernel Config</b>\n"
        text += f"{CUSTOM_EMOJI['📰']} Страница <b>{page + 1}/{total_pages}</b>\n"
        text += f"{CUSTOM_EMOJI['🔢']} Всего <b>{total_keys}</b> ключей"
        
        
        buttons = create_buttons_grid(page_keys, page, total_pages)
        
        builder = event.builder.article(
            title=f"Конфигурация - Страница {page + 1}",
            text=text,
            buttons=buttons,
            parse_mode='html'
        )
        await event.answer([builder])

    kernel.register_inline_handler('config_keys', config_keys_inline_handler)

    async def config_callback_handler(event):
        data = event.data.decode()
        
        if data.startswith('config_page_'):
            try:
                page = int(data.split('_')[2])
            except:
                page = 0
            
            visible_keys = get_visible_keys()
            total_keys = len(visible_keys)
            total_pages = (total_keys + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_keys > 0 else 1
            
            if page < 0:
                page = 0
            if page >= total_pages:
                page = total_pages - 1
            
            start_idx = page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            page_keys = visible_keys[start_idx:end_idx]
            
            text = f"{CUSTOM_EMOJI['📋']} <b>Kernel Config</b>\n"
            text += f"{CUSTOM_EMOJI['📰']} Страница <b>{page + 1}/{total_pages}</b>\n"
            text += f"{CUSTOM_EMOJI['🔢']} Всего <b>{total_keys}</b> ключей"
            
            buttons = create_buttons_grid(page_keys, page, total_pages)
            
            try:
                await event.edit(text, buttons=buttons, parse_mode='html')
            except Exception as e:
                await event.answer(f"Ошибка: {str(e)[:50]}", alert=True)
        
        elif data.startswith('cfg_view_'):
            try:
                key_id = data[9:]  # Убираем 'cfg_view_'
                
                # Получаем ключ и страницу из кэша
                cached = kernel.cache.get(f"cfg_view_{key_id}")
                if not cached:
                    await event.answer("❌ Данные устарели, обновите страницу", alert=True)
                    return
                
                key, page = cached
                
                if key not in kernel.config:
                    await event.answer("❌ Ключ не найден", alert=True)
                    return
                
                value = kernel.config[key]
                value_type = type(value).__name__
                type_emoji = get_type_emoji(value_type)
                
                # Форматируем значение для отображения
                if isinstance(value, dict):
                    formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                    display_value = f"<pre>{html.escape(formatted_value)}</pre>"
                elif isinstance(value, list):
                    formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                    display_value = f"<pre>{html.escape(formatted_value)}</pre>"
                elif value is None:
                    display_value = "<code>null</code>"
                elif isinstance(value, bool):
                    display_value = f"<code>{'true' if value else 'false'}</code>"
                elif isinstance(value, (int, float)):
                    display_value = f"<code>{value}</code>"
                else:
                    display_value = f"{html.escape(str(value))}"
                
                text = f"{CUSTOM_EMOJI['📝']} <b>Ключ:</b> <code>{key}</code>\n"
                text += f"{CUSTOM_EMOJI['📰']} <b>Тип:</b> {type_emoji} <code>{value_type}</code>\n"
                text += f"{CUSTOM_EMOJI['💬']} <b>Значение:</b> <code>{display_value}</code>"
                
                # Кнопка "назад" для возврата к той же странице
                buttons = [[Button.inline(f"🔙 Назад", data=f"config_page_{page}".encode())]]
                
                await event.edit(text, buttons=buttons, parse_mode='html')
                
            except Exception as e:
                await event.answer(f"Ошибка: {str(e)[:50]}", alert=True)

    kernel.register_callback_handler('config_page_', config_callback_handler)
    kernel.register_callback_handler('cfg_view_', config_callback_handler)

    @kernel.register_command('cfg')
    async def cfg_handler(event):
        try:
            args = event.text.split()

            if len(args) == 1:
                if hasattr(kernel, 'bot_client') and kernel.config.get('inline_bot_username'):
                    try:
                        bot_username = kernel.config.get('inline_bot_username')
                        results = await kernel.client.inline_query(bot_username, 'config_keys')
                        if results:
                            await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id)
                            await event.delete()
                            return
                    except Exception as e:
                        pass

                await event.edit(f"{CUSTOM_EMOJI['💬']} <b>Используйте:</b>\n<blockquote><code>.cfg</code> - список ключей (инлайн)\n<code>.cfg now ключ</code> - значение ключа\n<code>.cfg hide ключ</code> - скрыть ключ\n<code>.cfg unhide ключ</code> - показать ключ</blockquote>", parse_mode='html')

            elif len(args) >= 3:
                subcommand = args[1].lower()
                key = args[2].strip()

                if subcommand == 'now':
                    if is_key_hidden(key):
                        if key in SENSITIVE_KEYS:
                            await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Доступ запрещен</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>Ключ <code>{key}</code> является системным</i></blockquote>", parse_mode='html')
                        else:
                            await event.edit(f"{CUSTOM_EMOJI['💼']} <b>Ключ скрыт</b>\n<blockquote>{CUSTOM_EMOJI['💼']} <i>Ключ <code>{key}</code> скрыт пользователем</i></blockquote>", parse_mode='html')
                        return

                    if key not in kernel.config:
                        await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Ключ не найден</b>\n<blockquote>{CUSTOM_EMOJI['🗳']} <i><code>{key}</code> не существует в конфигурации</i></blockquote>", parse_mode='html')
                        return

                    value = kernel.config[key]
                    value_type = type(value).__name__
                    type_emoji = get_type_emoji(value_type)

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

                    response = f"""{CUSTOM_EMOJI['✏️']} <b>Ключ:</b> <code>{key}</code>
{type_emoji} <b>Тип:</b> <code>{value_type}</code>
{CUSTOM_EMOJI['💬']} <b>Значение:</b>

{display_value}"""
                    await event.edit(response, parse_mode='html')

                elif subcommand == 'hide':
                    if key in SENSITIVE_KEYS:
                        await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Запрещено</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>Ключ <code>{key}</code> является системным</i></blockquote>", parse_mode='html')
                        return

                    if key not in kernel.config:
                        await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Ключ не найден</b>\n<blockquote>{CUSTOM_EMOJI['🗳']} <i><code>{key}</code> не существует в конфигурации</i></blockquote>", parse_mode='html')
                        return

                    hidden_keys = kernel.config.get('hidden_keys', [])
                    if key in hidden_keys:
                        await event.edit(f"{CUSTOM_EMOJI['💼']} <b>Ключ уже скрыт</b>\n<blockquote>{CUSTOM_EMOJI['💼']} <i>Ключ <code>{key}</code> уже в списке скрытых</i></blockquote>", parse_mode='html')
                        return

                    hidden_keys.append(key)
                    kernel.config['hidden_keys'] = hidden_keys
                    await save_config()

                    await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Ключ скрыт</b>\n<blockquote>{CUSTOM_EMOJI['💼']} <i>Ключ <code>{key}</code> добавлен в список скрытых</i>\n{CUSTOM_EMOJI['📰']} <b>Всего скрыто:</b> <code>{len(hidden_keys)}</code></blockquote>", parse_mode='html')

                elif subcommand == 'unhide':
                    if key in SENSITIVE_KEYS:
                        await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Запрещено</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>Ключ <code>{key}</code> является системным</i></blockquote>", parse_mode='html')
                        return

                    hidden_keys = kernel.config.get('hidden_keys', [])
                    if key not in hidden_keys:
                        await event.edit(f"{CUSTOM_EMOJI['💼']} <b>Ключ не скрыт</b>\n<blockquote>{CUSTOM_EMOJI['💼']} <i>Ключ <code>{key}</code> не найден в списке скрытых</i></blockquote>", parse_mode='html')
                        return

                    hidden_keys.remove(key)
                    kernel.config['hidden_keys'] = hidden_keys
                    await save_config()

                    await event.edit(f"{CUSTOM_EMOJI['📖']} <b>Ключ показан</b>\n<blockquote>{CUSTOM_EMOJI['💼']} <i>Ключ <code>{key}</code> удален из списка скрытых</i>\n{CUSTOM_EMOJI['📰']} <b>Осталось скрыто:</b> <code>{len(hidden_keys)}</code></blockquote>", parse_mode='html')

                else:
                    await event.edit(f"{CUSTOM_EMOJI['🖨']} <b>Неизвестная подкоманда</b>\n<blockquote>{CUSTOM_EMOJI['💬']} <i>Доступные подкоманды:</i>\n<code>now</code> - значение ключа\n<code>hide</code> - скрыть ключ\n<code>unhide</code> - показать ключ</blockquote>", parse_mode='html')

            else:
                await event.edit(f"{CUSTOM_EMOJI['🖨']} <b>Использование</b>\n<blockquote>{CUSTOM_EMOJI['📖']} <code>.cfg</code> - список ключей (инлайн)\n{CUSTOM_EMOJI['📖']} <code>.cfg now ключ</code> - значение ключа\n{CUSTOM_EMOJI['📖']} <code>.cfg hide ключ</code> - скрыть ключ\n{CUSTOM_EMOJI['📖']} <code>.cfg unhide ключ</code> - показать ключ</blockquote>", parse_mode='html')

        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="cfg", event=event)

    @kernel.register_command('fcfg')
    async def fcfg_handler(event):
        try:
            args = event.text.split()

            if len(args) < 2:
                await event.edit(f"{CUSTOM_EMOJI['💼']} <b>Использование</b>\n<blockquote>{CUSTOM_EMOJI['☑️']} <code>.fcfg set ключ значение</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg del ключ</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg add ключ значение</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg dict ключ подключа значение</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg list ключ значение</code></blockquote>", parse_mode='html')
                return

            action = args[1].lower()

            if action == 'set':
                if len(args) < 4:
                    await event.edit(f"{CUSTOM_EMOJI['📰']} <b>Недостаточно аргументов</b>\n<blockquote>{CUSTOM_EMOJI['📝']} <code>.fcfg set ключ значение</code></blockquote>", parse_mode='html')
                    return

                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()

                if key in SENSITIVE_KEYS:
                    await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Запрещено</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>Ключ <code>{key}</code> нельзя изменять через команды</i></blockquote>", parse_mode='html')
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
                        await event.edit(f"{CUSTOM_EMOJI['🖨']} <b>Ключ добавлен</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <code>{key}</code> → <code>{value}</code></blockquote>", parse_mode='html')
                    else:
                        await event.edit(f"{CUSTOM_EMOJI['📁']} <b>Ключ обновлен</b>\n<blockquote>{CUSTOM_EMOJI['📁']} <code>{key}</code>\n<tg-spoiler>{CUSTOM_EMOJI['➕']} <i>было:</i> <code>{old_value}</code>\n{CUSTOM_EMOJI['➖']} <i>стало:</i> <code>{value}</code></tg-spoiler></blockquote>", parse_mode='html')

                except Exception as e:
                    await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Некорректное значение</b>\n<blockquote>{CUSTOM_EMOJI['🧊']} <i>{str(e)}</i></blockquote>", parse_mode='html')

            elif action == 'del':
                if len(args) < 3:
                    await event.edit(f"{CUSTOM_EMOJI['📰']} <b>Недостаточно аргументов</b>\n<blockquote>{CUSTOM_EMOJI['📝']} <code>.fcfg del ключ</code></blockquote>", parse_mode='html')
                    return

                key = args[2].strip()

                if key in SENSITIVE_KEYS:
                    await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Запрещено</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>Ключ <code>{key}</code> нельзя удалять</i></blockquote>", parse_mode='html')
                    return

                if key not in kernel.config:
                    await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Ключ не найден</b>\n<blockquote>{CUSTOM_EMOJI['🗳']} <i><code>{key}</code> не существует в конфигурации</i></blockquote>", parse_mode='html')
                    return

                old_value = kernel.config.pop(key)

                hidden_keys = kernel.config.get('hidden_keys', [])
                if key in hidden_keys:
                    hidden_keys.remove(key)
                    kernel.config['hidden_keys'] = hidden_keys

                await save_config()

                default_value = DEFAULT_VALUES.get(key, 'не определено')
                await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Ключ удален</b>\n<blockquote>{CUSTOM_EMOJI['🗳']} <code>{key}</code>\n<tg-spoiler>{CUSTOM_EMOJI['➕']} <i>было:</i> <code>{old_value}</code>\n{CUSTOM_EMOJI['🗳']} <i>умолчание:</i> <code>{default_value}</code></tg-spoiler></blockquote>", parse_mode='html')

            elif action == 'add':
                if len(args) < 4:
                    await event.edit(f"{CUSTOM_EMOJI['📰']} <b>Недостаточно аргументов</b>\n<blockquote>{CUSTOM_EMOJI['📝']} <code>.fcfg add ключ значение</code></blockquote>", parse_mode='html')
                    return

                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()

                if key in kernel.config:
                    await event.edit(f"{CUSTOM_EMOJI['🧊']} <b>Ключ уже существует</b>\n<blockquote>{CUSTOM_EMOJI['📝']} <i>Используйте <code>.fcfg set {key} значение</code> для изменения</i></blockquote>", parse_mode='html')
                    return

                try:
                    value = parse_value(value_str)

                    kernel.config[key] = value
                    await save_config()

                    value_type = type(value).__name__
                    await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Новый ключ добавлен</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <code>{key}</code> → <code>{value}</code>\n{CUSTOM_EMOJI['📰']} <i>тип:</i> <code>{value_type}</code></blockquote>", parse_mode='html')

                except Exception as e:
                    await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Некорректное значение</b>\n<blockquote>{CUSTOM_EMOJI['🧊']} <i>{str(e)}</i></blockquote>", parse_mode='html')

            elif action == 'dict':
                if len(args) < 5:
                    await event.edit(f"{CUSTOM_EMOJI['📰']} <b>Недостаточно аргументов</b>\n<blockquote>{CUSTOM_EMOJI['📝']} <code>.fcfg dict ключ подключа значение</code></blockquote>", parse_mode='html')
                    return

                key = args[2].strip()
                subkey = args[3].strip()
                value_str = ' '.join(args[4:]).strip()

                if key in SENSITIVE_KEYS:
                    await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Запрещено</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>Ключ <code>{key}</code> нельзя изменять через команды</i></blockquote>", parse_mode='html')
                    return

                try:
                    if key not in kernel.config:
                        kernel.config[key] = {}

                    if not isinstance(kernel.config[key], dict):
                        await event.edit(f"{CUSTOM_EMOJI['🧊']} <b>Неправильный тип</b>\n<blockquote>{CUSTOM_EMOJI['📰']} <i>Ключ <code>{key}</code> имеет тип <code>{type(kernel.config[key]).__name__}</code>, а не dict</i></blockquote>", parse_mode='html')
                        return

                    value = parse_value(value_str)

                    old_value = kernel.config[key].get(subkey)
                    kernel.config[key][subkey] = value
                    await save_config()

                    if old_value is None:
                        await event.edit(f"{CUSTOM_EMOJI['🗂']} <b>Элемент добавлен в словарь</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <code>{key}.{subkey}</code> → <code>{value}</code></blockquote>", parse_mode='html')
                    else:
                        await event.edit(f"{CUSTOM_EMOJI['📁']} <b>Элемент обновлен в словаре</b>\n<blockquote>{CUSTOM_EMOJI['🗂']} <code>{key}.{subkey}</code>\n<tg-spoiler>{CUSTOM_EMOJI['➕']} <i>было:</i> <code>{old_value}</code>\n{CUSTOM_EMOJI['➖']} <i>стало:</i> <code>{value}</code></tg-spoiler></blockquote>", parse_mode='html')

                except Exception as e:
                    await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Некорректное значение</b>\n<blockquote>{CUSTOM_EMOJI['🧊']} <i>{str(e)}</i></blockquote>", parse_mode='html')

            elif action == 'list':
                if len(args) < 4:
                    await event.edit(f"{CUSTOM_EMOJI['📰']} <b>Недостаточно аргументов</b>\n<blockquote>{CUSTOM_EMOJI['📝']} <code>.fcfg list ключ значение</code></blockquote>", parse_mode='html')
                    return

                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()

                if key in SENSITIVE_KEYS:
                    await event.edit(f"{CUSTOM_EMOJI['📎']} <b>Запрещено</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>Ключ <code>{key}</code> нельзя изменять через команды</i></blockquote>", parse_mode='html')
                    return

                try:
                    if key not in kernel.config:
                        kernel.config[key] = []

                    if not isinstance(kernel.config[key], list):
                        await event.edit(f"{CUSTOM_EMOJI['🧊']} <b>Неправильный тип</b>\n<blockquote>{CUSTOM_EMOJI['📰']} <i>Ключ <code>{key}</code> имеет тип <code>{type(kernel.config[key]).__name__}</code>, а не list</i></blockquote>", parse_mode='html')
                        return

                    value = parse_value(value_str)

                    kernel.config[key].append(value)
                    await save_config()

                    await event.edit(f"{CUSTOM_EMOJI['📚']} <b>Элемент добавлен в список</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <code>{key}</code> → <code>{value}</code>\n{CUSTOM_EMOJI['📰']} <b>Размер списка:</b> <code>{len(kernel.config[key])}</code></blockquote>", parse_mode='html')

                except Exception as e:
                    await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Некорректное значение</b>\n<blockquote>{CUSTOM_EMOJI['📎']} <i>{str(e)}</i></blockquote>", parse_mode='html')

            else:
                await event.edit(f"{CUSTOM_EMOJI['🖨']} <b>Неизвестное действие</b>\n<blockquote>{CUSTOM_EMOJI['☑️']} <code>.fcfg set ключ значение</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg del ключ</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg add ключ значение</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg dict ключ подключа значение</code>\n{CUSTOM_EMOJI['☑️']} <code>.fcfg list ключ значение</code></blockquote>", parse_mode='html')

        except Exception as e:
            await event.edit(f"{CUSTOM_EMOJI['❄️']} <b>Ошибка, смотри логи</b>", parse_mode='html')
            await kernel.handle_error(e, source="fcfg", event=event)