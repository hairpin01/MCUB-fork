from telethon import events, Button
import re

def register(kernel):
    client = kernel.client
    
    def plural_modules(n):
        if n % 10 == 1 and n % 100 != 11:
            return 'модуль'
        elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
            return 'модуля'
        else:
            return 'модулей'
    
    async def generate_man_page(page=1, module_filter=None):
        total_modules = len(kernel.loaded_modules) + len(kernel.system_modules)
        system_count = len(kernel.system_modules)
        user_count = len(kernel.loaded_modules)
        
        all_modules = []
        for name in kernel.system_modules:
            all_modules.append((name, 'system'))
        for name in kernel.loaded_modules:
            all_modules.append((name, 'user'))
        
        if module_filter:
            filtered_modules = []
            for name, typ in all_modules:
                if module_filter.lower() in name.lower():
                    filtered_modules.append((name, typ, 1))
                else:
                    commands = get_module_commands(name, kernel)
                    for cmd in commands:
                        if module_filter.lower() == cmd.lower():
                            filtered_modules.append((name, typ, 2))
                            break
                        elif module_filter.lower() in cmd.lower():
                            filtered_modules.append((name, typ, 3))
                            break
            
            filtered_modules.sort(key=lambda x: (-x[2], x[0]))
            all_modules = [(name, typ) for name, typ, _ in filtered_modules[:10]]
        
        all_modules.sort(key=lambda x: (0 if x[1] == 'system' else 1, x[0]))
        
        per_page = 8
        total_pages = (len(all_modules) + per_page - 1) // per_page
        
        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_modules = all_modules[start_idx:end_idx]
        
        title = f"<b>🌩️ {total_modules} {plural_modules(total_modules)}. системных модулей: {system_count}</b>"
        
        system_mods = [(name, get_module_commands(name, kernel)) for name, typ in page_modules if typ == 'system']
        user_mods = [(name, get_module_commands(name, kernel)) for name, typ in page_modules if typ == 'user']
        
        msg = f"{title}\n\n"
        
        if system_mods:
            msg += "<b>🛠️ Системные модули:</b>\n<blockquote expandable>\n"
            for name, commands in system_mods:
                if commands:
                    cmd_text = f": {', '.join([f'<code>{kernel.custom_prefix}{cmd}</code>' for cmd in commands])}"
                else:
                    cmd_text = ""
                msg += f"<b>{name}</b>{cmd_text}\n"
            msg += "</blockquote>\n"
        
        if user_mods:
            if system_mods:
                msg += "\n"
            msg += "<b>📦 Пользовательские модули:</b>\n<blockquote expandable>\n"
            for name, commands in user_mods:
                if commands:
                    cmd_text = f": {', '.join([f'<code>{kernel.custom_prefix}{cmd}</code>' for cmd in commands])}"
                else:
                    cmd_text = ""
                msg += f"<b>{name}</b>{cmd_text}\n"
            msg += "</blockquote>\n"
        
        if module_filter:
            msg = f"<b>🔍 Результаты поиска: '{module_filter}'</b>\n\n" + msg
        
        if total_pages > 1:
            msg += f"\n📄 Страница {page}/{total_pages}"
        
        return msg, total_pages, page
    
    def get_module_commands(module_name, kernel):
        commands = []
        file_path = None
        
        if module_name in kernel.system_modules:
            file_path = f"modules/{module_name}.py"
        elif module_name in kernel.loaded_modules:
            file_path = f"modules_loaded/{module_name}.py"
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                    
                    patterns = [
                        r"pattern\s*=\s*r['\"]\^?\\?\.([a-zA-Z0-9_]+)",
                        r"register_command\s*\('([^']+)'",
                        r"@kernel\.register_command\('([^']+)'\)",
                        r"kernel\.register_command\('([^']+)'",
                        r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'\\\\.([^']+)'\)\)"
                    ]
                    
                    for pattern in patterns:
                        found = re.findall(pattern, code)
                        commands.extend(found)
                        
            except Exception as e:
                pass
        
        return list(set([cmd for cmd in commands if cmd]))
    
    @kernel.register_command('man')
    async def man_handler(event):
        args = event.text.split()
        
        if len(args) == 1:
            msg, total_pages, current_page = await generate_man_page()
            
            if total_pages > 1:
                buttons = []
                if current_page > 1:
                    buttons.append(Button.inline('⬅️ Назад', f'man_page_{current_page-1}'.encode()))
                if current_page < total_pages:
                    buttons.append(Button.inline('➡️ Вперёд', f'man_page_{current_page+1}'.encode()))
                
                await event.edit(msg, buttons=buttons if buttons else None, parse_mode='html')
            else:
                await event.edit(msg, parse_mode='html')
        
        elif len(args) >= 2:
            if args[1].isdigit():
                page = int(args[1])
                msg, total_pages, current_page = await generate_man_page(page)
                
                if total_pages > 1:
                    buttons = []
                    if current_page > 1:
                        buttons.append(Button.inline('⬅️ Назад', f'man_page_{current_page-1}'.encode()))
                    if current_page < total_pages:
                        buttons.append(Button.inline('➡️ Вперёд', f'man_page_{current_page+1}'.encode()))
                    
                    await event.edit(msg, buttons=buttons if buttons else None, parse_mode='html')
                else:
                    await event.edit(msg, parse_mode='html')
            else:
                search_query = ' '.join(args[1:])
                msg, total_pages, current_page = await generate_man_page(module_filter=search_query)
                await event.edit(msg, parse_mode='html')
    
    async def man_callback_handler(event):
        try:
            page = int(event.data.decode().split('_')[2])
            msg, total_pages, current_page = await generate_man_page(page)
            
            buttons = []
            if current_page > 1:
                buttons.append(Button.inline('⬅️ Назад', f'man_page_{current_page-1}'.encode()))
            if current_page < total_pages:
                buttons.append(Button.inline('➡️ Вперёд', f'man_page_{current_page+1}'.encode()))
            
            await event.edit(msg, buttons=buttons if buttons else None, parse_mode='html')
        except:
            await event.answer('❌ Ошибка навигации')
    
    kernel.register_callback_handler('man_page_', man_callback_handler)
    
    async def man_inline_handler(event):
        try:
            query = event.text
            
            if query.startswith('man_page_'):
                try:
                    page = int(query.split('_')[2])
                except:
                    page = 1
                
                msg, total_pages, current_page = await generate_man_page(page)
                
                buttons = []
                if total_pages > 1:
                    if current_page > 1:
                        buttons.append([Button.inline('⬅️ Назад', f'man_page_{current_page-1}'.encode())])
                    if current_page < total_pages:
                        if buttons:
                            buttons[0].append(Button.inline('➡️ Вперёд', f'man_page_{current_page+1}'.encode()))
                        else:
                            buttons.append([Button.inline('➡️ Вперёд', f'man_page_{current_page+1}'.encode())])
                
                builder = event.builder.article(
                    '📚 Модули',
                    text=msg,
                    buttons=buttons if buttons else None,
                    parse_mode='html'
                )
                await event.answer([builder])
                
            else:
                builder = event.builder.article(
                    '📚 Модули',
                    text='Используйте: man_page_1 для навигации',
                    parse_mode='html'
                )
                await event.answer([builder])
                
        except Exception as e:
            builder = event.builder.article(
                '❌ Ошибка',
                text=f'Ошибка обработки запроса: {str(e)}',
                parse_mode='html'
            )
            await event.answer([builder])
    
    kernel.register_inline_handler('man', man_inline_handler)
