# author: @Hairpin00
# version: 1.0.3
# description: handler fixed UnboundLocalError
from telethon import events, Button
import aiohttp
import traceback

class InlineHandlers:
    def __init__(self, kernel, bot_client):
        self.kernel = kernel
        self.bot_client = bot_client

    def check_admin(self, event):
        try:
            if not hasattr(self.kernel, 'ADMIN_ID'):
                return False

            sender_id = event.sender_id
            is_admin = sender_id == self.kernel.ADMIN_ID
            return is_admin
        except Exception as e:
            print(f"[DEBUG] Ошибка в check_admin: {e}")
            return False

    async def register_handlers(self):
        # Обработчик InlineQuery (поиск через @bot)
        @self.bot_client.on(events.InlineQuery)
        async def inline_query_handler(event):
            query = event.text
            builder = None  # Инициализируем переменную заранее, чтобы избежать UnboundLocalError

            # 0. Если запрос пустой (просто открыли бота)
            if not query:
                builder = event.builder.article(
                    'MCUB Info',
                    text=f'🤖 <b>MCUB Bot</b>\n\nЯ работаю! Введите запрос или используйте команды.',
                    parse_mode='html'
                )
                await event.answer([builder])
                return

            # 1. Проверка кастомных обработчиков ядра
            for pattern, handler in self.kernel.inline_handlers.items():
                if query.startswith(pattern):
                    await handler(event)
                    return

            # 2. Логика 2FA
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

            # 3. Логика каталога
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

            # 4. Логика сообщений с кнопками через разделитель |
            elif '|' in query:
                parts = query.split('|')
                text = parts[0].strip()
                if not text: text = "Message" # Защита от пустого текста
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

            # 5. Просто эхо (если не попали ни в одно условие)
            else:
                if query:
                    builder = event.builder.article('Message', text=query, parse_mode='html')
                else:
                    # На случай если query пустой, но мы прошли мимо первой проверки
                    builder = event.builder.article('Empty', text='...', parse_mode='html')

            # Финальная отправка только если builder создан
            if builder:
                await event.answer([builder])

        # Обработчик нажатий на кнопки (CallbackQuery)
        @self.bot_client.on(events.CallbackQuery)
        async def callback_query_handler(event):
            try:
                if not event.data:
                    return

                if isinstance(event.data, bytes):
                    data_str = event.data.decode('utf-8')
                else:
                    data_str = str(event.data)

                # Проверка кастомных обработчиков ядра
                for pattern, handler in self.kernel.callback_handlers.items():
                    if data_str.startswith(pattern):
                        if not self.check_admin(event):
                            await event.answer('❌ Эта кнопка не ваша', alert=True)
                            return
                        try:
                            await handler(event)
                        except Exception as e:
                            print(f"Ошибка в кастомном обработчике: {e}")
                            traceback.print_exc()
                        return

                from .keyboards import InlineKeyboards
                keyboards = InlineKeyboards(self.kernel)

                if not keyboards.check_admin(event):
                    await event.answer('❌ Эта кнопка не ваша', alert=True)
                    return

                if data_str == 'confirm_yes':
                    await keyboards.handle_confirm_yes(event)
                elif data_str == 'confirm_no':
                    await keyboards.handle_confirm_no(event)
                elif data_str.startswith('dlml_'):
                    await keyboards.handle_catalog_page(event)
                elif data_str.startswith('page_'):
                    await keyboards.handle_custom_page(event)
                elif data_str.startswith('catalog_'):
                    parts = data_str.split('_')
                    if len(parts) >= 3:
                        repo_index = int(parts[1])
                        page = int(parts[2])

                        try:
                            repos = [self.kernel.default_repo] + self.kernel.repositories

                            if repo_index < 0 or repo_index >= len(repos):
                                repo_index = 0

                            repo_url = repos[repo_index]

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

                            await event.edit(msg, buttons=buttons if buttons else None, parse_mode='html')

                        except Exception as e:
                            await event.answer(f'Ошибка: {str(e)[:50]}', alert=True)
                else:
                    # print(f"Неизвестный callback: {data_str}")
                    await event.answer('❌ Неизвестная команда', alert=True)

            except Exception as e:
                print(f"Критическая ошибка в bot_callback_handler: {e}")
                traceback.print_exc()
