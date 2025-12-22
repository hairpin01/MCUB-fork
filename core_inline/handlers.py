from telethon import events, Button

class InlineHandlers:
    def __init__(self, kernel, bot_client):
        self.kernel = kernel
        self.bot_client = bot_client
    
    async def register_handlers(self):
        @self.bot_client.on(events.InlineQuery)
        async def inline_handler(event):
            query = event.text
            
            if query.startswith('2fa_'):
                parts = query.split('_', 3)
                if len(parts) >= 4:
                    confirm_key = f'{parts[1]}_{parts[2]}'
                    command = parts[3]
                    text = f'⚠️ **Требуется подтверждение**\n\nКоманда: `{command}`\n\nВы действительно хотите выполнить эту команду?'
                    buttons = [
                        [Button.inline('✅ Подтвердить', b'confirm_yes'),
                         Button.inline('❌ Отменить', b'confirm_no')]
                    ]
                    builder = event.builder.article('2FA', text=text, buttons=buttons)
                else:
                    builder = event.builder.article('Error', text='❌ Ошибка подтверждения')
            
            elif query.startswith('catalog_'):
                page = int(query.split('_')[1])
                
                if not self.kernel.catalog_cache:
                    builder = event.builder.article('Error', text='❌ Каталог не загружен')
                else:
                    catalog = self.kernel.catalog_cache
                    modules_list = list(catalog.items())
                    per_page = 5
                    total_pages = (len(modules_list) + per_page - 1) // per_page
                    
                    if page < 1:
                        page = 1
                    if page > total_pages:
                        page = total_pages
                    
                    start_idx = (page - 1) * per_page
                    end_idx = start_idx + per_page
                    page_modules = modules_list[start_idx:end_idx]
                    
                    msg = f'📚 <b>Каталог модулей</b> (Стр. {page}/{total_pages})\n\n'
                    for module_name, info in page_modules:
                        msg += f'• <b>{module_name}</b>\n'
                        msg += f'  {info.get("description", "Описание отсутствует")}\n'
                        if 'author' in info:
                            msg += f'  👤 Автор: @{info["author"]}\n'
                        if 'commands' in info:
                            msg += f'  Команды: {", ".join(info["commands"])}\n'
                        msg += '\n'
                    
                    msg += f'\nИспользуйте: <code>{self.kernel.custom_prefix}dlm название</code>'
                    
                    buttons = []
                    nav_buttons = []
                    if page > 1:
                        nav_buttons.append(Button.inline('⬅️ Назад', f'dlml_{page-1}'.encode()))
                    if page < total_pages:
                        nav_buttons.append(Button.inline('➡️ Вперёд', f'dlml_{page+1}'.encode()))
                    
                    if nav_buttons:
                        buttons.append(nav_buttons)
                    
                    builder = event.builder.article('Catalog', text=msg, buttons=buttons if buttons else None, parse_mode='html')
            
            elif '|' in query:
                parts = query.split('|')
                text = parts[0].strip()
                buttons = []
                
                for btn_data in parts[1:]:
                    btn_data = btn_data.strip()
                    if ':' in btn_data:
                        btn_parts = btn_data.split(':', 1)
                        btn_text = btn_parts[0].strip()
                        btn_url = btn_parts[1].strip()
                        
                        if btn_url.startswith(('http://', 'https://', 't.me/', 'tg://')):
                            buttons.append([Button.url(btn_text, btn_url)])
                        elif btn_url.startswith('page_'):
                            buttons.append([Button.inline(btn_text, btn_url.encode())])
                
                builder = event.builder.article('Message', text=text, buttons=buttons if buttons else None, parse_mode='html')
            
            else:
                builder = event.builder.article('Message', text=query, parse_mode='html')
            
            await event.answer([builder])
        
        @self.bot_client.on(events.CallbackQuery)
        async def bot_callback_handler(event):
            from .keyboards import InlineKeyboards
            keyboards = InlineKeyboards(self.kernel)
            
            if event.data == b'confirm_yes':
                await keyboards.handle_confirm_yes(event)
            elif event.data == b'confirm_no':
                await keyboards.handle_confirm_no(event)
            elif event.data.startswith(b'dlml_'):
                await keyboards.handle_catalog_page(event)
            elif event.data.startswith(b'page_'):
                await keyboards.handle_custom_page(event)
