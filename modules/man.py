from telethon import events, Button
import re
import difflib

def register(kernel):
    client = kernel.client
    
    async def generate_man_page(page=1, module_filter=None):
        total_modules = len(kernel.loaded_modules) + len(kernel.system_modules)
        system_count = len(kernel.system_modules)
        user_count = len(kernel.loaded_modules)
        
        title = f"🌒 {user_count} модуль загружен. системных модулей: {system_count}"
        
        all_modules = {}
        all_modules.update(kernel.system_modules)
        all_modules.update(kernel.loaded_modules)
        
        if module_filter:
            matches = []
            for name in all_modules.keys():
                if module_filter.lower() in name.lower():
                    matches.append((name, 1))
                else:
                    for cmd in get_module_commands(name, kernel):
                        if module_filter.lower() == cmd.lower():
                            matches.append((name, 2))
                            break
                        elif module_filter.lower() in cmd.lower():
                            matches.append((name, 3))
            
            matches.sort(key=lambda x: (-x[1], x[0]))
            filtered_modules = {name: all_modules[name] for name, _ in matches[:10]}
            page = 1
            per_page = 10
            is_search = True
        else:
            filtered_modules = all_modules
            per_page = 8
            is_search = False
        
        modules_list = list(filtered_modules.items())
        total_pages = (len(modules_list) + per_page - 1) // per_page
        
        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_modules = modules_list[start_idx:end_idx]
        
        msg = f"**{title}**\n\n"
        
        if is_search:
            msg += f"🔍 Результаты поиска: '{module_filter}'\n\n"
        
        for module_name, module in page_modules:
            module_type = "🛠️" if module_name in kernel.system_modules else "📦"
            msg += f"**{module_type} {module_name}**\n"
            
            commands = get_module_commands(module_name, kernel)
            if commands:
                msg += f"   Команды: {', '.join([f'`{kernel.custom_prefix}{cmd}`' for cmd in commands])}\n"
            
            file_path = None
            if module_name in kernel.system_modules:
                file_path = f"modules/{module_name}.py"
            elif module_name in kernel.loaded_modules:
                file_path = f"modules_loaded/{module_name}.py"
            
            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                        desc_match = re.search(r'"""([^"]+)"""', code, re.DOTALL)
                        if desc_match:
                            description = desc_match.group(1).strip()
                            msg += f"   Описание: {description[:100]}...\n"
                except:
                    pass
            
            msg += "\n"
        
        if total_pages > 1:
            msg += f"📄 Страница {page}/{total_pages}\n"
        
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
                
                await event.edit(msg, buttons=buttons if buttons else None)
            else:
                await event.edit(msg)
        
        elif len(args) >= 2:
            search_query = ' '.join(args[1:])
            msg, total_pages, current_page = await generate_man_page(module_filter=search_query)
            
            bot_username = kernel.config.get('inline_bot_username')
            
            if total_pages > 3:
                if bot_username:
                    await event.delete()
                    
                    query = f"📚 **Результаты поиска: '{search_query}'**\n\n"
                    query += f"Используйте кнопки для навигации | "
                    query += f"◀️:page_man_prev_{current_page} | ▶️:page_man_next_{current_page}"
                    
                    try:
                        results = await client.inline_query(bot_username, query)
                        if results:
                            await results[0].click(event.chat_id)
                    except:
                        await event.edit(msg)
                else:
                    await event.edit(f"{msg}\n\n⚠️ Для навигации по страницам настройте инлайн-бота")
            else:
                await event.edit(msg)
    
    @client.on(events.CallbackQuery(pattern=b'man_page_'))
    async def man_page_handler(event):
        try:
            page = int(event.data.decode().split('_')[2])
            msg, total_pages, current_page = await generate_man_page(page)
            
            buttons = []
            if current_page > 1:
                buttons.append(Button.inline('⬅️ Назад', f'man_page_{current_page-1}'.encode()))
            if current_page < total_pages:
                buttons.append(Button.inline('➡️ Вперёд', f'man_page_{current_page+1}'.encode()))
            
            await event.edit(msg, buttons=buttons if buttons else None)
        except:
            await event.answer('❌ Ошибка навигации')
    
    @kernel.register_command('modules')
    async def modules_info_handler(event):
        total = len(kernel.loaded_modules) + len(kernel.system_modules)
        
        msg = f"📊 **Статистика модулей**\n\n"
        msg += f"• Всего модулей: {total}\n"
        msg += f"• Системных: {len(kernel.system_modules)}\n"
        msg += f"• Пользовательских: {len(kernel.loaded_modules)}\n\n"
        
        if kernel.system_modules:
            msg += "**🛠️ Системные модули:**\n"
            for name in sorted(kernel.system_modules.keys()):
                commands = get_module_commands(name, kernel)
                cmd_text = f" ({', '.join([f'`{kernel.custom_prefix}{c}`' for c in commands[:3]])})" if commands else ""
                msg += f"  ◦ {name}{cmd_text}\n"
        
        if kernel.loaded_modules:
            msg += "\n**📦 Пользовательские модули:**\n"
            for name in sorted(kernel.loaded_modules.keys()):
                commands = get_module_commands(name, kernel)
                cmd_text = f" ({', '.join([f'`{kernel.custom_prefix}{c}`' for c in commands[:3]])})" if commands else ""
                msg += f"  ◦ {name}{cmd_text}\n"
        
        await event.edit(msg)
