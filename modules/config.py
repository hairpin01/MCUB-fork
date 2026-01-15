# requires: json, telethon>=1.24, hashlib
# author: @Hairpin00
# version: 1.1.2
# description: config Kernel fixed

import json
import html
import hashlib
from telethon import Button

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
    '✅': '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    '❌': '<tg-emoji emoji-id="5370843963559254781">❌</tg-emoji>',
    '🔄': '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
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

    async def save_config():
        try:
            with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            await kernel.handle_error(e, source="save_config")

    def parse_value(value_str, expected_type=None):
        value_str = value_str.strip()
        if value_str.lower() == 'null': return None

        if expected_type:
            if expected_type == 'bool':
                if value_str.lower() == 'true': return True
                elif value_str.lower() == 'false': return False
                else: raise ValueError("Must be true or false")
            elif expected_type == 'int': return int(value_str)
            elif expected_type == 'float': return float(value_str)
            elif expected_type == 'dict': return json.loads(value_str)
            elif expected_type == 'list': return json.loads(value_str)
            elif expected_type == 'str': return value_str

        if value_str.lower() == 'true': return True
        elif value_str.lower() == 'false': return False
        elif value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
            return int(value_str)
        elif value_str.replace('.', '', 1).isdigit() and value_str.count('.') == 1:
            return float(value_str)
        elif value_str.startswith('{') and value_str.endswith('}'):
            try: return json.loads(value_str)
            except: return value_str
        elif value_str.startswith('[') and value_str.endswith(']'):
            try: return json.loads(value_str)
            except: return value_str
        else: return value_str

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
            kernel.cache.set(f"cfg_view_{key_id}", (key, page), ttl=86400)
            row.append(Button.inline(display_key, data=f"cfg_view_{key_id}".encode()))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️", data=f"config_page_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("➡️", data=f"config_page_{page + 1}".encode()))
        if nav_buttons: buttons.append(nav_buttons)
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
            except: page = 0
        
        total_pages = (total_keys + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_keys > 0 else 1
        if page < 0: page = 0
        if page >= total_pages: page = total_pages - 1
        
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_keys = visible_keys[start_idx:end_idx]
        
        text = f"{CUSTOM_EMOJI['📋']} <b>Config Kernel</b>\n"
        text += f"{CUSTOM_EMOJI['📰']} Page <b>{page + 1}/{total_pages}</b> ({total_keys} keys)"
        
        buttons = create_buttons_grid(page_keys, page, total_pages)
        builder = event.builder.article(title=f"Config - {page + 1}", text=text, buttons=buttons, parse_mode='html')
        await event.answer([builder])

    kernel.register_inline_handler('config_keys', config_keys_inline_handler)

    async def show_key_view(event, key_id):
        cached = kernel.cache.get(f"cfg_view_{key_id}")
        if not cached:
            key_id_parts = key_id.split('_')
            if len(key_id_parts) >= 2:
                try:
                    key = '_'.join(key_id_parts[:-1])
                    page = int(key_id_parts[-1])
                    if key in kernel.config:
                        kernel.cache.set(f"cfg_view_{key_id}", (key, page), ttl=86400)
                        cached = (key, page)
                except: pass
        
        if not cached:
            await event.answer("❌ Expired", alert=True)
            return None, None, None, None
        
        key, page = cached
        if key not in kernel.config:
            await event.answer("❌ Not found", alert=True)
            return None, None, None, None
        
        value = kernel.config[key]
        value_type = type(value).__name__
        type_emoji = get_type_emoji(value_type)
        
        if isinstance(value, (dict, list)):
            formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
            display_value = f"<pre>{html.escape(formatted_value)}</pre>"
        elif value is None:
            display_value = "<code>null</code>"
        elif isinstance(value, bool):
            display_value = "✔️ <code>true</code>" if value else "✖️ <code>false</code>"
        else:
            display_value = f"<code>{html.escape(str(value))}</code>"
        
        text = f"{CUSTOM_EMOJI['📝']} <b>{key}</b> ({type_emoji} {value_type})\n{display_value}"
        return text, key, page, value_type

    async def config_callback_handler(event):
        data = event.data.decode()
        
        if data.startswith('config_page_'):
            try: page = int(data.split('_')[2])
            except: page = 0
            
            visible_keys = get_visible_keys()
            total_keys = len(visible_keys)
            total_pages = (total_keys + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_keys > 0 else 1
            if page < 0: page = 0
            if page >= total_pages: page = total_pages - 1
            
            start_idx = page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            page_keys = visible_keys[start_idx:end_idx]
            
            text = f"{CUSTOM_EMOJI['📋']} <b>Config Kernel</b>\n"
            text += f"{CUSTOM_EMOJI['📰']} Page <b>{page + 1}/{total_pages}</b> ({total_keys} keys)"
            buttons = create_buttons_grid(page_keys, page, total_pages)
            try: await event.edit(text, buttons=buttons, parse_mode='html')
            except Exception as e: await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('cfg_view_'):
            try:
                key_id = data[9:]
                result = await show_key_view(event, key_id)
                if result[0] is None: return
                text, key, page, value_type = result
                
                buttons = []
                if value_type == 'bool':
                    value = kernel.config[key]
                    toggle_text = f"❌ Set false" if value else f"✅ Set true"
                    buttons.append([Button.inline(toggle_text, data=f"cfg_bool_toggle_{key_id}".encode())])
                
                buttons.append([Button.inline("🔙 Back", data=f"config_page_{page}".encode())])
                await event.edit(text, buttons=buttons, parse_mode='html')
            except Exception as e: await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('cfg_bool_toggle_'):
            try:
                # FIX: Length of "cfg_bool_toggle_" is 16, not 17
                key_id = data[16:] 
                cached = kernel.cache.get(f"cfg_view_{key_id}")
                if not cached:
                    key_id_parts = key_id.split('_')
                    if len(key_id_parts) >= 2:
                        try:
                            key = '_'.join(key_id_parts[:-1])
                            page = int(key_id_parts[-1])
                            if key in kernel.config:
                                kernel.cache.set(f"cfg_view_{key_id}", (key, page), ttl=86400)
                                cached = (key, page)
                        except: pass
                
                if not cached:
                    await event.answer("❌ Expired", alert=True)
                    return
                
                key, page = cached
                if key not in kernel.config:
                    await event.answer("❌ Not found", alert=True)
                    return
                
                value = kernel.config[key]
                if not isinstance(value, bool):
                    await event.answer("❌ Not boolean", alert=True)
                    return
                
                kernel.config[key] = not value
                await save_config()
                
                result = await show_key_view(event, key_id)
                if result[0] is None: return
                text, key, page, value_type = result
                
                new_value = kernel.config[key]
                toggle_text = f"❌ Set false" if new_value else f"✅ Set true"
                buttons = [
                    [Button.inline(toggle_text, data=f"cfg_bool_toggle_{key_id}".encode())],
                    [Button.inline(f"🔙 Back", data=f"config_page_{page}".encode())]
                ]
                
                await event.edit(text, buttons=buttons, parse_mode='html')
                await event.answer(f"✅ Changed to {new_value}", alert=False)
            except Exception as e: await event.answer(str(e)[:50], alert=True)

    kernel.register_callback_handler('config_page_', config_callback_handler)
    kernel.register_callback_handler('cfg_view_', config_callback_handler)
    kernel.register_callback_handler('cfg_bool_toggle_', config_callback_handler)

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
                    except: pass
                await event.edit(f"{CUSTOM_EMOJI['⚙️']} <b>Config</b>: Use inline or <code>.cfg [now/hide/unhide]</code>", parse_mode='html')

            elif len(args) >= 3:
                subcommand = args[1].lower()
                key = args[2].strip()

                if subcommand == 'now':
                    if is_key_hidden(key):
                        await event.edit(f"{CUSTOM_EMOJI['💼']} <b>Hidden</b>: <code>{key}</code>", parse_mode='html')
                        return
                    if key not in kernel.config:
                        await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Not found</b>: <code>{key}</code>", parse_mode='html')
                        return
                    
                    value = kernel.config[key]
                    value_type = type(value).__name__
                    if isinstance(value, (dict, list)):
                        display_value = f"<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre>"
                    else:
                        display_value = f"<code>{html.escape(str(value))}</code>"
                    
                    await event.edit(f"{CUSTOM_EMOJI['📝']} <b>{key}</b> ({value_type})\n{display_value}", parse_mode='html')

                elif subcommand == 'hide':
                    if key in SENSITIVE_KEYS:
                        await event.edit(f"{CUSTOM_EMOJI['📎']} <b>System key</b>", parse_mode='html')
                        return
                    hidden = kernel.config.get('hidden_keys', [])
                    if key not in hidden:
                        hidden.append(key)
                        kernel.config['hidden_keys'] = hidden
                        await save_config()
                    await event.edit(f"{CUSTOM_EMOJI['💼']} <b>Hidden</b>: <code>{key}</code>", parse_mode='html')

                elif subcommand == 'unhide':
                    hidden = kernel.config.get('hidden_keys', [])
                    if key in hidden:
                        hidden.remove(key)
                        kernel.config['hidden_keys'] = hidden
                        await save_config()
                    await event.edit(f"{CUSTOM_EMOJI['📖']} <b>Visible</b>: <code>{key}</code>", parse_mode='html')
        except Exception as e:
            await kernel.handle_error(e, source="cfg", event=event)

    @kernel.register_command('fcfg')
    async def fcfg_handler(event):
        try:
            args = event.text.split()
            if len(args) < 2:
                await event.edit(f"{CUSTOM_EMOJI['⚙️']} <code>.fcfg [set/del/add/dict/list]</code>", parse_mode='html')
                return

            action = args[1].lower()

            if action == 'set':
                if len(args) < 4: return
                key = args[2].strip()
                if key in SENSITIVE_KEYS:
                    await event.edit(f"{CUSTOM_EMOJI['❌']} <b>Protected</b>", parse_mode='html')
                    return
                value_str = ' '.join(args[3:]).strip()
                try:
                    current_type = type(kernel.config.get(key)).__name__ if key in kernel.config else None
                    value = parse_value(value_str, current_type)
                    kernel.config[key] = value
                    await save_config()
                    await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Set</b> <code>{key}</code> = <code>{value}</code>", parse_mode='html')
                except Exception as e: await event.edit(f"{CUSTOM_EMOJI['❌']} {e}", parse_mode='html')

            elif action == 'del':
                if len(args) < 3: return
                key = args[2].strip()
                if key in SENSITIVE_KEYS: return
                if key in kernel.config:
                    kernel.config.pop(key)
                    if key in kernel.config.get('hidden_keys', []):
                        kernel.config['hidden_keys'].remove(key)
                    await save_config()
                    await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Deleted</b> <code>{key}</code>", parse_mode='html')
                else:
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Not found", parse_mode='html')

            elif action == 'add':
                if len(args) < 4: return
                key = args[2].strip()
                if key in kernel.config:
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Exists", parse_mode='html')
                    return
                value_str = ' '.join(args[3:]).strip()
                try:
                    value = parse_value(value_str)
                    kernel.config[key] = value
                    await save_config()
                    await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Added</b> <code>{key}</code>", parse_mode='html')
                except Exception as e: await event.edit(f"{CUSTOM_EMOJI['❌']} {e}", parse_mode='html')

            elif action == 'dict':
                if len(args) < 5: return
                key, subkey = args[2].strip(), args[3].strip()
                value_str = ' '.join(args[4:]).strip()
                try:
                    if key not in kernel.config: kernel.config[key] = {}
                    if not isinstance(kernel.config[key], dict): return
                    kernel.config[key][subkey] = parse_value(value_str)
                    await save_config()
                    await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Dict</b> <code>{key}[{subkey}]</code> updated", parse_mode='html')
                except Exception as e: await event.edit(f"{CUSTOM_EMOJI['❌']} {e}", parse_mode='html')

            elif action == 'list':
                if len(args) < 4: return
                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()
                try:
                    if key not in kernel.config: kernel.config[key] = []
                    if not isinstance(kernel.config[key], list): return
                    kernel.config[key].append(parse_value(value_str))
                    await save_config()
                    await event.edit(f"{CUSTOM_EMOJI['✅']} <b>List</b> <code>{key}</code> appended", parse_mode='html')
                except Exception as e: await event.edit(f"{CUSTOM_EMOJI['❌']} {e}", parse_mode='html')

        except Exception as e:
            await kernel.handle_error(e, source="fcfg", event=event)
