from telethon import events, Button
import re
import difflib

def register(kernel):
    client = kernel.client
    
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
        
        title = f"🌩️ {user_count} модулей. системных модулей: {system_count}"
        
        system_mods = [name for name, typ in page_modules if typ == 'system']
        user_mods = [name for name, typ in page_modules if typ == 'user']
        
        system_block = ""
        user_block = ""
        
        if system_mods:
            system_block = "<blockquote expandable>\n"
            for name in system_mods:
                commands = get_module_commands(name, kernel)
                cmd_text = f": {', '.join([f'{kernel.custom_prefix}{cmd}' for cmd in commands])}" if commands else ""
                system_block += f"<b>{name}</b>{cmd_text}\n"
            system_block += "</blockquote>"
        
        if user_mods:
            user_block = "<blockquote expandable>\n"
            for name in user_mods:
                commands = get_module_commands(name, kernel)
                cmd_text = f": {', '.join([f'{kernel.custom_prefix}{cmd}' for cmd in commands])}" if commands else ""
                user_block += f"<b>{name}</b>{cmd_text}\n"
            user_block += "</blockquote>"
        
        msg = f"**{title}**\n\n"
        
        if system_block:
            msg += system_block + "\n"
        if user_block:
            msg += user_block
        
        if module_filter:
            msg = f"🔍 **Результаты поиска: '{module_filter}'**\n\n" + msg
        
        if total_pages > 1:
            msg += f"\n📄 Страница {page}/{total_pages}"
            msg += f"\nИспользуйте: `{kernel.custom_prefix}man [страница]`"
        
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
                    pattern = r"pattern\s*=\s*r['\"]\^?\\?\.([a-zA-Z0-9_]+)"
                    found = re.findall(pattern, code)
                    commands.extend(found)
                    
                    pattern2 = r"register_command\s*\('([^']+)'"
                    found2 = re.findall(pattern2, code)
                    commands.extend(found2)
                    
                    pattern3 = r"@kernel\.register_command\('([^']+)'\)"
                    found3 = re.findall(pattern3, code)
                    commands.extend(found3)
            except:
                pass
        
        return list(set(commands))
    
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
    
    # Регистрируем обработчик callback-кнопок для навигации
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
    
    # Регистрируем инлайн-обработчик для модуля man
    async def man_inline_handler(event):
        query = event.text
        if query.startswith('man_page_'):
            try:
                page = int(query.split('_')[2])
            except:
                page = 1
            
            msg, total_pages, current_page = await generate_man_page(page)
            
            buttons = []
            nav_buttons = []
            if current_page > 1:
                nav_buttons.append(Button.inline('⬅️ Назад', f'man_page_{current_page-1}'.encode()))
            if current_page < total_pages:
                nav_buttons.append(Button.inline('➡️ Вперёд', f'man_page_{current_page+1}'.encode()))
            
            if nav_buttons:
                buttons.append(nav_buttons)
            
            builder = event.builder.article('Modules', text=msg, buttons=buttons if buttons else None, parse_mode='html')
            await event.answer([builder])
        else:
            # Общий поиск
            search_query = query
            msg, total_pages, current_page = await generate_man_page(module_filter=search_query)
            builder = event.builder.article('Modules Search', text=msg, parse_mode='html')
            await event.answer([builder])
    
    kernel.register_inline_handler('man', man_inline_handler)
    
    @kernel.register_command('modules')
    async def modules_info_handler(event):
        total = len(kernel.loaded_modules) + len(kernel.system_modules)
        
        msg = f"📊 **Статистика модулей**\n\n"
        msg += f"• Всего модулей: {total}\n"
        msg += f"• Системных: {len(kernel.system_modules)}\n"
        msg += f"• Пользовательских: {len(kernel.loaded_modules)}\n\n"
        
        if kernel.system_modules:
            msg += "**🛠️ Системные модули:**\n"
            msg += "<blockquote expandable>\n"
            for name in sorted(kernel.system_modules.keys()):
                commands = get_module_commands(name, kernel)
                cmd_text = f" ({', '.join([f'`{kernel.custom_prefix}{c}`' for c in commands[:3]])})" if commands else ""
                msg += f"<b>{name}</b>{cmd_text}\n"
            msg += "</blockquote>\n"
        
        if kernel.loaded_modules:
            msg += "\n**📦 Пользовательские модули:**\n"
            msg += "<blockquote expandable>\n"
            for name in sorted(kernel.loaded_modules.keys()):
                commands = get_module_commands(name, kernel)
                cmd_text = f" ({', '.join([f'`{kernel.custom_prefix}{c}`' for c in commands[:3]])})" if commands else ""
                msg += f"<b>{name}</b>{cmd_text}\n"
            msg += "</blockquote>\n"
        
        await event.edit(msg, parse_mode='html')