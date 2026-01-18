# requires: json, telethon>=1.24, hashlib
# author: @Hairpin00
# version: 1.2.2
# description: config Kernel with fixed callback parsing

import json
import html
import hashlib
import re
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
    '🧩': '<tg-emoji emoji-id="5359785904535774578">🧩</tg-emoji>',
    '🔧': '<tg-emoji emoji-id="5332654441508119011">🔧</tg-emoji>',
}

ITEMS_PER_PAGE = 16
MODULES_PER_PAGE = 12

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

    class CustomJSONEncoder(json.JSONEncoder):
        def encode(self, o):
            result = super().encode(o)
            # Исправляем двойные escape-последовательности
            result = re.sub(r'(?<!\\)\\\\(n|t|r|f|b|")', r'\\\1', result)
            return result

    async def save_config():
        try:
            with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(kernel.config, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
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
            elif expected_type == 'str': 
                # Правильная обработка escape-последовательностей
                value_str = re.sub(r'(?<!\\)\\n', '\n', value_str)
                value_str = re.sub(r'(?<!\\)\\t', '\t', value_str)
                value_str = re.sub(r'(?<!\\)\\r', '\r', value_str)
                value_str = re.sub(r'\\\\n', '\\n', value_str)  # Сохраняем \\n как \n
                value_str = re.sub(r'\\\\t', '\\t', value_str)  # Сохраняем \\t как \t
                return value_str

        if value_str.lower() == 'true': return True
        elif value_str.lower() == 'false': return False
        elif value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
            return int(value_str)
        elif value_str.replace('.', '', 1).isdigit() and value_str.count('.') == 1:
            return float(value_str)
        elif value_str.startswith('{') and value_str.endswith('}'):
            try: return json.loads(value_str)
            except: 
                return value_str
        elif value_str.startswith('[') and value_str.endswith(']'):
            try: return json.loads(value_str)
            except: 
                return value_str
        else: 
            # Правильная обработка escape-последовательностей для строк
            value_str = re.sub(r'(?<!\\)\\n', '\n', value_str)
            value_str = re.sub(r'(?<!\\)\\t', '\t', value_str)
            value_str = re.sub(r'(?<!\\)\\r', '\r', value_str)
            value_str = re.sub(r'\\\\n', '\\n', value_str)
            value_str = re.sub(r'\\\\t', '\\t', value_str)
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

    def truncate_module_name(name, max_length=12):
        if len(name) > max_length:
            return name[:max_length-3] + "..."
        return name

    def generate_key_id(key, page, config_type='kernel'):
        hash_obj = hashlib.md5(f"{config_type}_{key}_{page}".encode())
        return hash_obj.hexdigest()[:8]

    def create_kernel_buttons_grid(page_keys, page, total_pages):
        buttons = []
        row = []
        for i, (key, value) in enumerate(page_keys):
            display_key = truncate_key(key)
            key_id = generate_key_id(key, page, 'kernel')
            kernel.cache.set(f"cfg_view_{key_id}", (key, page, 'kernel'), ttl=86400)
            row.append(Button.inline(display_key, data=f"cfg_view_{key_id}".encode()))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️", data=f"config_kernel_page_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("➡️", data=f"config_kernel_page_{page + 1}".encode()))
        nav_buttons.append(Button.inline("🔙 Menu", data=f"config_menu".encode()))
        if nav_buttons: buttons.append(nav_buttons)
        return buttons

    def create_modules_buttons_grid(modules, page, total_pages):
        buttons = []
        row = []
        for i, module_name in enumerate(modules):
            display_name = truncate_module_name(module_name)
            key_id = generate_key_id(module_name, page, 'module')
            kernel.cache.set(f"module_select_{key_id}", (module_name, page), ttl=86400)
            row.append(Button.inline(display_name, data=f"module_select_{key_id}".encode()))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️", data=f"config_modules_page_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("➡️", data=f"config_modules_page_{page + 1}".encode()))
        nav_buttons.append(Button.inline("🔙 Menu", data=f"config_menu".encode()))
        if nav_buttons: buttons.append(nav_buttons)
        return buttons

    def create_module_config_buttons(module_name, page_keys, page, total_pages):
        buttons = []
        row = []
        for i, (key, value) in enumerate(page_keys):
            display_key = truncate_key(key)
            # Используем новый формат для callback data с разделителем __
            key_id = generate_key_id(f"{module_name}__{key}", page, 'module_cfg')
            kernel.cache.set(f"module_cfg_view_{key_id}", (module_name, key, page), ttl=86400)
            row.append(Button.inline(display_key, data=f"module_cfg_view_{key_id}".encode()))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️", data=f"module_cfg_page_{module_name}__{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("➡️", data=f"module_cfg_page_{module_name}__{page + 1}".encode()))
        nav_buttons.append(Button.inline("🔙 Modules", data=f"config_modules_page_0".encode()))
        if nav_buttons: buttons.append(nav_buttons)
        return buttons

    async def config_menu_handler(event):
        query = event.text.strip()
        text = f"{CUSTOM_EMOJI['📋']} <b>Config Menu</b>\nВыберите раздел конфигурации:"
        
        buttons = [
            [Button.inline("🪄 Kernel Config", data=b'config_kernel_page_0')],
            [Button.inline("🚂 Modules Config", data=b'config_modules_page_0')]
        ]
        
        builder = event.builder.article(title="Config Menu", text=text, buttons=buttons, parse_mode='html')
        await event.answer([builder])

    async def config_kernel_handler(event):
        query = event.text.strip()
        visible_keys = get_visible_keys()
        total_keys = len(visible_keys)
        page = 0
        
        if query.startswith('config_kernel_'):
            try:
                parts = query.split('_')
                if len(parts) >= 4:
                    page_str = parts[3]
                    page = int(page_str)
            except: 
                page = 0
        
        total_pages = (total_keys + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_keys > 0 else 1
        if page < 0: page = 0
        if page >= total_pages: page = total_pages - 1
        
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_keys = visible_keys[start_idx:end_idx]
        
        text = "🪡 <b>Kernel Config</b>\n"
        text += f"{CUSTOM_EMOJI['📰']} Page <b>{page + 1}/{total_pages}</b> ({total_keys} keys)"
        
        buttons = create_kernel_buttons_grid(page_keys, page, total_pages)
        builder = event.builder.article(title=f"Kernel Config - {page + 1}", text=text, buttons=buttons, parse_mode='html')
        await event.answer([builder])

    async def config_modules_handler(event):
        query = event.text.strip()
        all_modules = list(kernel.system_modules.keys()) + list(kernel.loaded_modules.keys())
        all_modules = sorted(list(set(all_modules)))
        
        page = 0
        if query.startswith('config_modules_'):
            try:
                parts = query.split('_')
                if len(parts) >= 4:
                    page_str = parts[3]
                    page = int(page_str)
            except: 
                page = 0
        
        total_modules = len(all_modules)
        total_pages = (total_modules + MODULES_PER_PAGE - 1) // MODULES_PER_PAGE if total_modules > 0 else 1
        if page < 0: page = 0
        if page >= total_pages: page = total_pages - 1
        
        start_idx = page * MODULES_PER_PAGE
        end_idx = start_idx + MODULES_PER_PAGE
        page_modules = all_modules[start_idx:end_idx]
        
        text = f"{CUSTOM_EMOJI['🧩']} <b>Modules Config</b>\n"
        text += f"{CUSTOM_EMOJI['📰']} Page <b>{page + 1}/{total_pages}</b> ({total_modules} modules)"
        
        buttons = create_modules_buttons_grid(page_modules, page, total_pages)
        builder = event.builder.article(title=f"Modules Config - {page + 1}", text=text, buttons=buttons, parse_mode='html')
        await event.answer([builder])

    async def show_key_view(event, key_id):
        cached = kernel.cache.get(f"cfg_view_{key_id}")
        if not cached:
            await event.answer("❌ Expired", alert=True)
            return None, None, None, None, None
        
        key, page, config_type = cached
        if config_type != 'kernel':
            await event.answer("❌ Invalid config type", alert=True)
            return None, None, None, None, None
        
        if key not in kernel.config:
            await event.answer("❌ Not found", alert=True)
            return None, None, None, None, None
        
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
        elif isinstance(value, str):
            escaped_value = html.escape(value)
            escaped_value = escaped_value.replace('\n', '<br>')
            display_value = f"<code>{escaped_value}</code>"
        else:
            display_value = f"<code>{html.escape(str(value))}</code>"
        
        text = f"{CUSTOM_EMOJI['📝']} <b>{key}</b> ({type_emoji} {value_type})\n{display_value}"
        return text, key, page, value_type, 'kernel'

    async def show_module_config_view(event, module_name, page=0):
        try:
            module_config = await kernel.get_module_config(module_name, {})
            if not module_config:
                await event.answer("❌ Module has no config", alert=True)
                return
            
            items = list(module_config.items())
            total_items = len(items)
            total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_items > 0 else 1
            
            if page < 0: page = 0
            if page >= total_pages: page = total_pages - 1
            
            start_idx = page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            page_keys = items[start_idx:end_idx]
            
            text = f"{CUSTOM_EMOJI['🧩']} <b>Module:</b> <code>{module_name}</code>\n"
            text += f"{CUSTOM_EMOJI['📰']} Page <b>{page + 1}/{total_pages}</b> ({total_items} keys)"
            
            buttons = create_module_config_buttons(module_name, page_keys, page, total_pages)
            await event.edit(text, buttons=buttons, parse_mode='html')
            
        except Exception as e:
            await event.answer(f"❌ Error: {str(e)[:50]}", alert=True)

    async def show_module_key_view(event, module_name, key, page):
        try:
            module_config = await kernel.get_module_config(module_name, {})
            if key not in module_config:
                await event.answer("❌ Key not found", alert=True)
                return
            
            value = module_config[key]
            value_type = type(value).__name__
            type_emoji = get_type_emoji(value_type)
            
            if isinstance(value, (dict, list)):
                formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                display_value = f"<pre>{html.escape(formatted_value)}</pre>"
            elif value is None:
                display_value = "<code>null</code>"
            elif isinstance(value, bool):
                display_value = "✔️ <code>true</code>" if value else "✖️ <code>false</code>"
            elif isinstance(value, str):
                escaped_value = html.escape(value)
                escaped_value = escaped_value.replace('\n', '<br>')
                display_value = f"<code>{escaped_value}</code>"
            else:
                display_value = f"<code>{html.escape(str(value))}</code>"
            
            text = f"{CUSTOM_EMOJI['📝']} <b>{key}</b> ({type_emoji} {value_type})\n{display_value}"
            
            buttons = []
            if value_type == 'bool':
                toggle_text = f"❌ Set false" if value else f"✅ Set true"
                # Используем новый формат с __
                buttons.append([Button.inline(toggle_text, data=f"cfg_modules_bool_{module_name}__{key}__{page}".encode())])
            
            buttons.append([Button.inline("🔙 Back", data=f"module_cfg_page_{module_name}__{page}".encode())])
            await event.edit(text, buttons=buttons, parse_mode='html')
            
        except Exception as e:
            await event.answer(f"❌ Error: {str(e)[:50]}", alert=True)

    async def toggle_module_bool_key(event, module_name, key, page):
        try:
            module_config = await kernel.get_module_config(module_name, {})
            if key not in module_config:
                await event.answer("❌ Key not found", alert=True)
                return
            
            value = module_config[key]
            if not isinstance(value, bool):
                await event.answer("❌ Not boolean", alert=True)
                return
            
            module_config[key] = not value
            await kernel.save_module_config(module_name, module_config)
            
            await show_module_key_view(event, module_name, key, page)
            await event.answer(f"✅ Changed to {module_config[key]}", alert=False)
            
        except Exception as e:
            await event.answer(f"❌ Error: {str(e)[:50]}", alert=True)

    async def config_callback_handler(event):
        data = event.data.decode()
        
        if data == 'config_menu':
            text = "🪡 <b>Config Menu</b>\nВыберите раздел конфигурации:"
            buttons = [
                [Button.inline("🪄 Kernel Config", data=b'config_kernel_page_0')],
                [Button.inline("🚂 Modules Config", data=b'config_modules_page_0')]
            ]
            try: await event.edit(text, buttons=buttons, parse_mode='html')
            except Exception as e: await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('config_kernel_page_'):
            try: 
                page = int(data.split('_')[3])
                visible_keys = get_visible_keys()
                total_keys = len(visible_keys)
                total_pages = (total_keys + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_keys > 0 else 1
                if page < 0: page = 0
                if page >= total_pages: page = total_pages - 1
                
                start_idx = page * ITEMS_PER_PAGE
                end_idx = start_idx + ITEMS_PER_PAGE
                page_keys = visible_keys[start_idx:end_idx]
                
                text = "🪡 <b>Kernel Config</b>\n"
                text += f"{CUSTOM_EMOJI['📰']} Page <b>{page + 1}/{total_pages}</b> ({total_keys} keys)"
                buttons = create_kernel_buttons_grid(page_keys, page, total_pages)
                await event.edit(text, buttons=buttons, parse_mode='html')
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('config_modules_page_'):
            try:
                page = int(data.split('_')[3])
                all_modules = list(kernel.system_modules.keys()) + list(kernel.loaded_modules.keys())
                all_modules = sorted(list(set(all_modules)))
                
                total_modules = len(all_modules)
                total_pages = (total_modules + MODULES_PER_PAGE - 1) // MODULES_PER_PAGE if total_modules > 0 else 1
                if page < 0: page = 0
                if page >= total_pages: page = total_pages - 1
                
                start_idx = page * MODULES_PER_PAGE
                end_idx = start_idx + MODULES_PER_PAGE
                page_modules = all_modules[start_idx:end_idx]
                
                text = f"{CUSTOM_EMOJI['🧩']} <b>Modules Config</b>\n"
                text += f"{CUSTOM_EMOJI['📰']} Page <b>{page + 1}/{total_pages}</b> ({total_modules} modules)"
                buttons = create_modules_buttons_grid(page_modules, page, total_pages)
                await event.edit(text, buttons=buttons, parse_mode='html')
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('module_select_'):
            try:
                key_id = data[14:]
                cached = kernel.cache.get(f"module_select_{key_id}")
                if not cached:
                    await event.answer("❌ Expired", alert=True)
                    return
                
                module_name, page = cached
                await show_module_config_view(event, module_name, 0)
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('module_cfg_page_'):
            try:
                # Новый формат: module_cfg_page_{module_name}__{page}
                if '__' in data:
                    parts = data.split('__')
                    module_name = parts[0].replace('module_cfg_page_', '')
                    page = int(parts[1])
                else:
                    # Старый формат для совместимости: module_cfg_page_{module_name}_{page}
                    parts = data.split('_')
                    # Находим индекс, где начинается номер страницы (последний элемент)
                    page_part = parts[-1]
                    if page_part.isdigit():
                        page = int(page_part)
                        module_name = '_'.join(parts[3:-1])  # module_cfg_page_ имеет 3 части
                    else:
                        await event.answer("❌ Invalid format", alert=True)
                        return
                
                await show_module_config_view(event, module_name, page)
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('module_cfg_view_'):
            try:
                key_id = data[16:]
                cached = kernel.cache.get(f"module_cfg_view_{key_id}")
                if not cached:
                    await event.answer("❌ Expired", alert=True)
                    return
                
                module_name, key, page = cached
                await show_module_key_view(event, module_name, key, page)
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('cfg_modules_bool_'):
            try:
                # Новый формат: cfg_modules_bool_{module_name}__{key}__{page}
                if '__' in data:
                    rest = data.replace('cfg_modules_bool_', '')
                    parts = rest.split('__')
                    if len(parts) >= 3:
                        module_name = parts[0]
                        key = parts[1]
                        page = int(parts[2])
                    else:
                        await event.answer("❌ Invalid format", alert=True)
                        return
                else:
                    # Старый формат для совместимости: module_cfg_bool_{module_name}_{key}_{page}
                    rest = data.replace('module_cfg_bool_', '')
                    parts = rest.split('_')
                    # Последний элемент - страница
                    if parts[-1].isdigit():
                        page = int(parts[-1])
                        # Первая часть - имя модуля (может содержать дефисы)
                        module_name = parts[0]
                        # Остальное - ключ
                        key = '_'.join(parts[1:-1])
                    else:
                        await event.answer("❌ Invalid format", alert=True)
                        return
                
                await toggle_module_bool_key(event, module_name, key, page)
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('cfg_view_'):
            try:
                key_id = data[9:]
                result = await show_key_view(event, key_id)
                if result[0] is None: return
                text, key, page, value_type, config_type = result
                
                buttons = []
                if value_type == 'bool':
                    value = kernel.config[key]
                    toggle_text = f"❌ Set false" if value else f"✅ Set true"
                    buttons.append([Button.inline(toggle_text, data=f"cfg_bool_toggle_{key_id}".encode())])
                
                buttons.append([Button.inline("🔙 Back", data=f"config_kernel_page_{page}".encode())])
                await event.edit(text, buttons=buttons, parse_mode='html')
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)
        
        elif data.startswith('cfg_bool_toggle_'):
            try:
                key_id = data[16:] 
                cached = kernel.cache.get(f"cfg_view_{key_id}")
                if not cached:
                    await event.answer("❌ Expired", alert=True)
                    return
                
                key, page, config_type = cached
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
                text, key, page, value_type, config_type = result
                
                new_value = kernel.config[key]
                toggle_text = f"❌ Set false" if new_value else f"✅ Set true"
                buttons = [
                    [Button.inline(toggle_text, data=f"cfg_bool_toggle_{key_id}".encode())],
                    [Button.inline(f"🔙 Back", data=f"config_kernel_page_{page}".encode())]
                ]
                
                await event.edit(text, buttons=buttons, parse_mode='html')
                await event.answer(f"✅ Changed to {new_value}", alert=False)
            except Exception as e: 
                await event.answer(str(e)[:50], alert=True)

    kernel.register_callback_handler('config_menu', config_callback_handler)
    kernel.register_callback_handler('config_kernel_page_', config_callback_handler)
    kernel.register_callback_handler('config_modules_page_', config_callback_handler)
    kernel.register_callback_handler('module_select_', config_callback_handler)
    kernel.register_callback_handler('module_cfg_page_', config_callback_handler)
    kernel.register_callback_handler('module_cfg_view_', config_callback_handler)
    kernel.register_callback_handler('cfg_modules_bool_', config_callback_handler)
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
                        results = await kernel.client.inline_query(bot_username, 'config_menu')
                        if results:
                            await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id)
                            await event.delete()
                            return
                    except: 
                        pass
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
                    elif isinstance(value, str):
                        escaped_value = html.escape(value)
                        escaped_value = escaped_value.replace('\n', '<br>')
                        display_value = f"<code>{escaped_value}</code>"
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
                await event.edit(f"{CUSTOM_EMOJI['⚙️']} <code>.fcfg [set/del/add/dict/list] -m [modules]</code>", parse_mode='html')
                return

            action = args[1].lower()
            
            # Проверяем наличие флага -m
            module_mode = False
            module_name = None
            
            if '-m' in args:
                module_mode = True
                m_index = args.index('-m')
                if len(args) <= m_index + 1:
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Specify module name after -m", parse_mode='html')
                    return
                module_name = args[m_index + 1]
                # Удаляем флаг -m и имя модуля из аргументов
                args = args[:m_index] + args[m_index+2:]

            if action == 'set':
                if len(args) < 4: 
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Not enough arguments", parse_mode='html')
                    return
                
                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()
                
                if module_mode:
                    # Режим модуля
                    try:
                        module_config = await kernel.get_module_config(module_name, {})
                        current_type = type(module_config.get(key)).__name__ if key in module_config else None
                        value = parse_value(value_str, current_type)
                        module_config[key] = value
                        await kernel.save_module_config(module_name, module_config)
                        # Показываем значение с переносами строк
                        display_value = value
                        if isinstance(value, str):
                            display_value = value.replace('\n', '\\n')
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Set</b> module <code>{module_name}</code> key <code>{key}</code> = <code>{html.escape(str(display_value))}</code>", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')
                else:
                    # Режим ядра
                    if key in SENSITIVE_KEYS:
                        await event.edit(f"{CUSTOM_EMOJI['❌']} <b>Protected</b>", parse_mode='html')
                        return
                    try:
                        current_type = type(kernel.config.get(key)).__name__ if key in kernel.config else None
                        value = parse_value(value_str, current_type)
                        kernel.config[key] = value
                        await save_config()
                        # Показываем значение с переносами строк
                        display_value = value
                        if isinstance(value, str):
                            display_value = value.replace('\n', '\\n')
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Set</b> <code>{key}</code> = <code>{html.escape(str(display_value))}</code>", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')

            elif action == 'del':
                if len(args) < 3: 
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Not enough arguments", parse_mode='html')
                    return
                
                key = args[2].strip()
                
                if module_mode:
                    # Режим модуля
                    module_config = await kernel.get_module_config(module_name, {})
                    if key in module_config:
                        module_config.pop(key)
                        await kernel.save_module_config(module_name, module_config)
                        await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Deleted</b> module <code>{module_name}</code> key <code>{key}</code>", parse_mode='html')
                    else:
                        await event.edit(f"{CUSTOM_EMOJI['❌']} Not found in module config", parse_mode='html')
                else:
                    # Режим ядра
                    if key in SENSITIVE_KEYS: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} <b>Protected</b>", parse_mode='html')
                        return
                    if key in kernel.config:
                        kernel.config.pop(key)
                        if key in kernel.config.get('hidden_keys', []):
                            kernel.config['hidden_keys'].remove(key)
                        await save_config()
                        await event.edit(f"{CUSTOM_EMOJI['🗳']} <b>Deleted</b> <code>{key}</code>", parse_mode='html')
                    else:
                        await event.edit(f"{CUSTOM_EMOJI['❌']} Not found", parse_mode='html')

            elif action == 'add':
                if len(args) < 4: 
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Not enough arguments", parse_mode='html')
                    return
                
                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()
                
                if module_mode:
                    # Режим модуля
                    module_config = await kernel.get_module_config(module_name, {})
                    if key in module_config:
                        await event.edit(f"{CUSTOM_EMOJI['❌']} Key already exists in module config", parse_mode='html')
                        return
                    try:
                        value = parse_value(value_str)
                        module_config[key] = value
                        await kernel.save_module_config(module_name, module_config)
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Added</b> module <code>{module_name}</code> key <code>{key}</code>", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')
                else:
                    # Режим ядра
                    if key in kernel.config:
                        await event.edit(f"{CUSTOM_EMOJI['❌']} Exists", parse_mode='html')
                        return
                    try:
                        value = parse_value(value_str)
                        kernel.config[key] = value
                        await save_config()
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Added</b> <code>{key}</code>", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')

            elif action == 'dict':
                if len(args) < 5: 
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Not enough arguments", parse_mode='html')
                    return
                
                key, subkey = args[2].strip(), args[3].strip()
                value_str = ' '.join(args[4:]).strip()
                
                if module_mode:
                    # Режим модуля
                    try:
                        module_config = await kernel.get_module_config(module_name, {})
                        if key not in module_config: 
                            module_config[key] = {}
                        if not isinstance(module_config[key], dict):
                            await event.edit(f"{CUSTOM_EMOJI['❌']} Key is not a dict", parse_mode='html')
                            return
                        module_config[key][subkey] = parse_value(value_str)
                        await kernel.save_module_config(module_name, module_config)
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Dict</b> module <code>{module_name}</code> key <code>{key}[{subkey}]</code> updated", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')
                else:
                    # Режим ядра
                    try:
                        if key not in kernel.config: 
                            kernel.config[key] = {}
                        if not isinstance(kernel.config[key], dict): 
                            await event.edit(f"{CUSTOM_EMOJI['❌']} Key is not a dict", parse_mode='html')
                            return
                        kernel.config[key][subkey] = parse_value(value_str)
                        await save_config()
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>Dict</b> <code>{key}[{subkey}]</code> updated", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')

            elif action == 'list':
                if len(args) < 4: 
                    await event.edit(f"{CUSTOM_EMOJI['❌']} Not enough arguments", parse_mode='html')
                    return
                
                key = args[2].strip()
                value_str = ' '.join(args[3:]).strip()
                
                if module_mode:
                    # Режим модуля
                    try:
                        module_config = await kernel.get_module_config(module_name, {})
                        if key not in module_config: 
                            module_config[key] = []
                        if not isinstance(module_config[key], list):
                            await event.edit(f"{CUSTOM_EMOJI['❌']} Key is not a list", parse_mode='html')
                            return
                        module_config[key].append(parse_value(value_str))
                        await kernel.save_module_config(module_name, module_config)
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>List</b> module <code>{module_name}</code> key <code>{key}</code> appended", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')
                else:
                    # Режим ядра
                    try:
                        if key not in kernel.config: 
                            kernel.config[key] = []
                        if not isinstance(kernel.config[key], list):
                            await event.edit(f"{CUSTOM_EMOJI['❌']} Key is not a list", parse_mode='html')
                            return
                        kernel.config[key].append(parse_value(value_str))
                        await save_config()
                        await event.edit(f"{CUSTOM_EMOJI['✅']} <b>List</b> <code>{key}</code> appended", parse_mode='html')
                    except Exception as e: 
                        await event.edit(f"{CUSTOM_EMOJI['❌']} {html.escape(str(e))}", parse_mode='html')

        except Exception as e:
            await kernel.handle_error(e, source="fcfg", event=event)

    # Register inline handlers
    kernel.register_inline_handler('config_menu', config_menu_handler)
    kernel.register_inline_handler('config_kernel', config_kernel_handler)
    kernel.register_inline_handler('config_modules', config_modules_handler)

