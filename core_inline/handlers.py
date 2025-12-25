# author: @Hairpin00
# version: 1.0.1
# description: handler
from telethon import events, Button
import aiohttp

class InlineHandlers:
    def __init__(self, kernel, bot_client):
        self.kernel = kernel
        self.bot_client = bot_client
    
    async def register_handlers(self):
        @self.bot_client.on(events.InlineQuery)
        async def inline_handler(event):
            query = event.text
            
            
            for pattern, handler in self.kernel.inline_handlers.items():
                if query.startswith(pattern):
                    await handler(event)
                    return
            
            # Стандартные обработчики
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
                parts = query.split('_')
                if len(parts) >= 3:
                    repo_index = int(parts[1])
                    page = int(parts[2])

                    repos = [self.kernel.default_repo] + self.kernel.repositories

                    if repo_index < 0 or repo_index >= len(repos):
                        repo_index = 0

                    repo_url = repos[repo_index]

                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(f'{repo_url}/modules.ini') as resp:
                                if resp.status == 200:
                                    modules_text = await resp.text()
                                    modules = [line.strip() for line in modules_text.split('\n') if line.strip()]
                                else:
                                    modules = []

                            async with session.get(f'{repo_url}/name.ini') as resp:
                                if resp.status == 200:
                                    repo_name = await resp.text()
                                    repo_name = repo_name.strip()
                                else:
                                    repo_name = repo_url.split('/')[-2] if '/' in repo_url else repo_url
                    except:
                        modules = []
                        repo_name = repo_url.split('/')[-2] if '/' in repo_url else repo_url

                    per_page = 8
                    total_pages = (len(modules) + per_page - 1) // per_page

                    if page < 1:
                        page = 1
                    if page > total_pages:
                        page = total_pages

                    start_idx = (page - 1) * per_page
                    end_idx = start_idx + per_page
                    page_modules = modules[start_idx:end_idx]

                    if repo_index == 0:
                        msg = f'<b>🌩️ Официальный репозиторий MCUB</b> <code>{repo_url}</code>\n\n'
                    else:
                        msg = f'<i>{repo_name}</i> <code>{repo_url}</code>\n\n'

                    if page_modules:
                        modules_text = " | ".join([f"<code>{m}</code>" for m in page_modules])
                        msg += modules_text

                    msg += f'\n\n📄 Страница {page}/{total_pages}'

                    buttons = []
                    nav_buttons = []

                    if page > 1:
                        nav_buttons.append(Button.inline('⬅️ Назад', f'catalog_{repo_index}_{page-1}'.encode()))

                    if page < total_pages:
                        nav_buttons.append(Button.inline('➡️ Вперёд', f'catalog_{repo_index}_{page+1}'.encode()))

                    if nav_buttons:
                        buttons.append(nav_buttons)

                    if len(repos) > 1:
                        repo_buttons = []
                        for i in range(len(repos)):
                            repo_buttons.append(Button.inline(f'{i+1}', f'catalog_{i}_1'.encode()))
                        buttons.append(repo_buttons)

                    builder = event.builder.article('Catalog', text=msg, buttons=buttons if buttons else None, parse_mode='html')
                    await event.answer([builder])
                    return
            
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
            
            if event.data:
                data_str = event.data.decode()
                for pattern, handler in self.kernel.callback_handlers.items():
                    if data_str.startswith(pattern):
                        await handler(event)
                        return
            
            
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
