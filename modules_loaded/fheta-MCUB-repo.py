# github MCUB repo: https://github.com/hairpin01/repo-MCUB-fork
# github fheta https://github.com/Fixyres/FHeta/
# Fheta Updates Channel: https://t.me/FHeta_Updates
# Bot fheta: @FHeta_Robot
# My channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires: 
# author: @Fixyres && @Hairpin00
# version: 1.4.0
# description: Fheta for MCUB! / Фхета в MCUB! @FHeta_Updates
# scop: kernel min v1.0.2.1
# banner_url: https://github.com/Fixyres/FModules/blob/main/assets/FHeta/logo.png?raw=true
# ----------------------- End ------------------------------
import asyncio
import aiohttp
import ssl
import json
import html
from telethon import Button

def register(kernel):
    class FHeta:
        def __init__(self):
            self.token = None
            self.uid = None
            self.sync_task = None
            self.ssl = ssl.create_default_context()
            self.ssl.check_hostname = False
            self.ssl.verify_mode = ssl.CERT_NONE
            self.THEMES = {
                "default": {
                    "search": "🔎", "error": "❌", "warn": "❌", "result": "🔎",
                    "install": "💾", "description": "📁", "command": "👨‍💻", "inline": "🤖",
                    "like": "👍", "dislike": "👎", "prev": "◀️", "next": "▶️"
                }
            }

        async def client_ready(self):
            me = await kernel.client.get_me()
            self.uid = me.id

            config = await kernel.get_module_config(__name__, {
                'tracking': True,
                'only_official_developers': False,
                'theme': 'default'
            })
            self.config = config

            
            self.strings = {
                'ru': {
                    'enter_query': 'Введите запрос для поиска.',
                    'query_too_long': 'Ваш запрос слишком большой, пожалуйста, сократите его до 168 символов.',
                    'inline_bot_not_available': 'Инлайн-бот не доступен.',
                    'inline_bot_not_configured': 'Инлайн-бот не настроен.',
                    'searching_module': 'Ищу модуль 🔎',
                    'search_failed': 'Не удалось выполнить поиск.',
                    'command_error': 'Ошибка при выполнении команды.',
                    'enter_query_title': 'Введите запрос для поиска',
                    'enter_query_text': 'Введите запрос для поиска модулей.',
                    'enter_query_description': 'Название, команда, описание, автор.',
                    'query_too_long_title': 'Запрос слишком большой',
                    'query_too_long_text': 'Ваш запрос слишком большой, пожалуйста, сократите его до 168 символов.',
                    'query_too_long_description': 'Сократите запрос',
                    'modules_not_found': 'Модули не найдены',
                    'try_another_query': 'Попробуйте другой запрос.',
                    'rating_added': 'Оценка отправлена!',
                    'rating_changed': 'Оценка изменена!',
                    'rating_removed': 'Оценка удалена!',
                    'result_by_query': 'Результат по запросу:',
                    'result': 'Результат {idx}/{total} по запросу:',
                    'from_author': 'от',
                    'install_command': 'Команда для установки:',
                    'description_label': 'Описание:',
                    'commands_label': 'Команды:'
                },
                'en': {
                    'enter_query': 'Enter a search query.',
                    'query_too_long': 'Your query is too long, please shorten it to 168 characters.',
                    'inline_bot_not_available': 'Inline bot not available.',
                    'inline_bot_not_configured': 'Inline bot not configured.',
                    'searching_module': 'Searching module 🔎',
                    'search_failed': 'Search failed.',
                    'command_error': 'Error executing command.',
                    'enter_query_title': 'Enter search query',
                    'enter_query_text': 'Enter a query to search for modules.',
                    'enter_query_description': 'Name, command, description, author.',
                    'query_too_long_title': 'Query too long',
                    'query_too_long_text': 'Your query is too long, please shorten it to 168 characters.',
                    'query_too_long_description': 'Shorten query',
                    'modules_not_found': 'Modules not found',
                    'try_another_query': 'Try another query.',
                    'rating_added': 'Rating sent!',
                    'rating_changed': 'Rating changed!',
                    'rating_removed': 'Rating removed!',
                    'result_by_query': 'Result for query:',
                    'result': 'Result {idx}/{total} for query:',
                    'from_author': 'by',
                    'install_command': 'Install command:',
                    'description_label': 'Description:',
                    'commands_label': 'Commands:'
                }
            }

            if not self.token:
                self.token = await kernel.db_get('FHeta', 'token')
                if not self.token:
                    try:
                        async with kernel.client.conversation("@FHeta_robot") as conv:
                            await conv.send_message('/token')
                            resp = await conv.get_response(timeout=5)
                            self.token = resp.text.strip()
                            await kernel.db_set('FHeta', 'token', self.token)
                    except Exception as e:
                        kernel.log_error(f"Failed to get FHeta token: {e}")

            if self.token and (self.sync_task is None or self.sync_task.done()):
                self.sync_task = asyncio.create_task(self._sync_loop())

        def _(self, key, **kwargs):
            """Helper function to get localized string"""
            language = kernel.config.get('language', 'ru')
            strings = self.strings.get(language, self.strings['ru'])
            text = strings.get(key, key)
            return text.format(**kwargs) if kwargs else text

        async def _sync_loop(self):
            tracked = True
            timeout = aiohttp.ClientTimeout(total=5)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                while True:
                    try:
                        if not self.token:
                            await asyncio.sleep(10)
                            continue
                        if self.config.get('tracking', True):
                            async with session.post(
                                "https://api.fixyres.com/dataset",
                                params={
                                    "user_id": self.uid,
                                    "lang": kernel.config.get('language', 'ru')
                                },
                                headers={"Authorization": self.token},
                                ssl=self.ssl
                            ) as response:
                                tracked = True
                                await response.release()
                        elif tracked:
                            async with session.post(
                                "https://api.fixyres.com/rmd",
                                params={"user_id": self.uid},
                                headers={"Authorization": self.token},
                                ssl=self.ssl
                            ) as response:
                                tracked = False
                                await response.release()
                    except:
                        pass

                    await asyncio.sleep(10)

        def _get_emoji(self, key):
            theme = self.config.get('theme', 'default')
            return self.THEMES.get(theme, self.THEMES['default']).get(key, '')

        def _escape_html(self, text):
            return html.escape(str(text))

        async def _api_get(self, endpoint, **params):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://api.fixyres.com/{endpoint}",
                        params=params,
                        headers={"Authorization": self.token},
                        ssl=self.ssl,
                        timeout=aiohttp.ClientTimeout(total=180)
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                        return {}
            except Exception as e:
                kernel.log_error(f"API GET error: {e}")
                return {}

        async def _api_post(self, endpoint, json_data=None, **params):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"https://api.fixyres.com/{endpoint}",
                        json=json_data,
                        params=params,
                        headers={"Authorization": self.token},
                        ssl=self.ssl,
                        timeout=aiohttp.ClientTimeout(total=180)
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                        return {}
            except Exception as e:
                kernel.log_error(f"API POST error: {e}")
                return {}

        def _fmt_mod(self, mod, query="", idx=1, total=1, inline=False):
            info = f"<code>{self._escape_html(mod.get('name', ''))}</code> <b>{self._('from_author')}</b> <code>{self._escape_html(mod.get('author', '???'))}</code> <code>{self._escape_html(mod.get('version', '?.?.?'))}</code>\n{self._get_emoji('install')} <b>{self._('install_command')}</b> <code>{kernel.custom_prefix}{self._escape_html(mod.get('install', ''))}</code>"

            if total > 1:
                info = f"{self._get_emoji('result')} <b>{self._('result', idx=idx, total=total)}</b> <code>{self._escape_html(query)}</code>\n" + info
            elif query and not inline:
                info = f"{self._get_emoji('result')} <b>{self._('result_by_query')}</b> <code>{self._escape_html(query)}</code>\n" + info

            desc = mod.get("description")
            if desc:
                if isinstance(desc, dict):
                    text = desc.get(kernel.config.get('language', 'ru')) or desc.get("doc") or next(iter(desc.values()), "")
                else:
                    text = desc

                info += f"\n{self._get_emoji('description')} <b>{self._('description_label')}</b> {self._escape_html(text[:800])}"

            cmds = mod.get("commands", [])
            if cmds:
                regular_cmds = []
                for cmd in cmds:
                    if not cmd.get("inline"):
                        desc_dict = cmd.get("description", {})
                        desc_text = desc_dict.get(kernel.config.get('language', 'ru')) or desc_dict.get("doc") or ""
                        cmd_name = self._escape_html(cmd.get("name", ""))
                        cmd_desc = self._escape_html(desc_text) if desc_text else ""
                        regular_cmds.append(f"<code>.{cmd_name}</code> {cmd_desc}")

                if regular_cmds:
                    info += f"\n{self._get_emoji('command')} <b>{self._('commands_label')}</b>\n" + "\n".join(regular_cmds)

            return info

        def _mk_btns(self, install, stats, idx, mods=None, query=""):
            like_emoji = self._get_emoji("like")
            dislike_emoji = self._get_emoji("dislike")
            prev_emoji = self._get_emoji("prev")
            next_emoji = self._get_emoji("next")

            buttons = []
            like_row = []

            like_data = f"fheta_rate:{install}:like:{idx}:{query}"[:64]
            dislike_data = f"fheta_rate:{install}:dislike:{idx}:{query}"[:64]

            like_row.append(Button.inline(f"{like_emoji} {stats.get('likes', 0)}", data=like_data.encode()))
            like_row.append(Button.inline(f"{dislike_emoji} {stats.get('dislikes', 0)}", data=dislike_data.encode()))
            buttons.append(like_row)

            if mods and len(mods) > 1:
                nav_buttons = []
                if idx > 0:
                    nav_data = f"fheta_nav:{idx-1}:{query}"[:64]
                    nav_buttons.append(Button.inline(prev_emoji, data=nav_data.encode()))
                if idx < len(mods) - 1:
                    nav_data = f"fheta_nav:{idx+1}:{query}"[:64]
                    nav_buttons.append(Button.inline(next_emoji, data=nav_data.encode()))
                if nav_buttons:
                    buttons.append(nav_buttons)

            return buttons

        async def _rate_cb(self, event, install, action, idx, query=""):
            result = await self._api_post(f"rate/{self.uid}/{install}/{action}")

            stats_response = await self._api_post("get", json=[install])
            stats = stats_response.get(install, {"likes": 0, "dislikes": 0})

            try:
                if result and result.get("status"):
                    status = result.get("status")
                    if status == "added":
                        await event.answer(self._('rating_added'), alert=True)
                    elif status == "changed":
                        await event.answer(self._('rating_changed'), alert=True)
                    elif status == "removed":
                        await event.answer(self._('rating_removed'), alert=True)
            except:
                pass

            try:
                mods = kernel.cache.get(f"fheta_search_{query}")
                await event.edit(buttons=self._mk_btns(install, stats, idx, mods, query))
            except:
                pass

        async def _nav_cb(self, event, idx, query=""):
            try:
                await event.answer()
            except:
                pass

            mods = kernel.cache.get(f"fheta_search_{query}")
            if not mods or not (0 <= idx < len(mods)):
                return

            mod = mods[idx]
            install = mod.get('install', '')
            stats = {"likes": mod.get('likes', 0), "dislikes": mod.get('dislikes', 0)}

            try:
                await event.edit(
                    self._fmt_mod(mod, query, idx + 1, len(mods)),
                    parse_mode='html',
                    buttons=self._mk_btns(install, stats, idx, mods, query)
                )
            except:
                pass

    fheta = FHeta()

    async def fheta_init():
        await fheta.client_ready()

    asyncio.create_task(fheta_init())

    @kernel.register.command('fheta')
    # <запрос> найти модуль для heroku/hikka
    async def fheta_handler(event):
        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.edit(f"{fheta._get_emoji('error')} <b>{fheta._('enter_query')}</b>", parse_mode='html')
            return

        query = args[1]

        if len(query) > 168:
            await event.edit(f"{fheta._get_emoji('warn')} <b>{fheta._('query_too_long')}</b>", parse_mode='html')
            return

        if not kernel.is_bot_available():
            await event.edit(f"{fheta._get_emoji('error')} <b>{fheta._('inline_bot_not_available')}</b>", parse_mode='html')
            return

        try:
            bot_username = kernel.config.get('inline_bot_username')
            if not bot_username:
                await event.edit(f"{fheta._get_emoji('error')} <b>{fheta._('inline_bot_not_configured')}</b>", parse_mode='html')
                return
            await event.edit(
            f"<b>{fheta._('searching_module')}</b>",
            parse_mode='html'
            )
            success, message = await kernel.inline_query_and_click(
                chat_id=event.chat_id,
                query=f'fheta {query}',
                bot_username=bot_username,
                result_index=0,
                silent=False,
                reply_to=event.message.id
            )

            if success:
                try:
                    await event.delete()
                except:
                    pass
            else:
                await event.edit(f"{fheta._get_emoji('error')} <b>{fheta._('search_failed')}</b>", parse_mode='html')

        except Exception as e:
            await kernel.handle_error(e, source="fheta_handler", event=event)
            await event.edit(f"{fheta._get_emoji('error')} <b>{fheta._('command_error')}</b>", parse_mode='html')

    async def fheta_inline(event):
        query = event.text.strip()

        if query.lower().startswith('fheta '):
            query = query[6:].strip()
        elif query.lower() == 'fheta':
            query = ''

        if not query:
            builder = event.builder.article(
                title=fheta._('enter_query_title'),
                text=fheta._('enter_query_text'),
                description=fheta._('enter_query_description')
            )
            await event.answer([builder])
            return

        if len(query) > 168:
            builder = event.builder.article(
                title=fheta._('query_too_long_title'),
                text=fheta._('query_too_long_text'),
                description=fheta._('query_too_long_description')
            )
            await event.answer([builder])
            return

        mods = await fheta._api_get("search", query=query, inline="true", token=fheta.token,
                                   user_id=fheta.uid, ood=str(fheta.config.get('only_official_developers', False)).lower())

        if not mods or not isinstance(mods, list):
            builder = event.builder.article(
                title=fheta._('modules_not_found'),
                text=fheta._('try_another_query'),
                description=fheta._('try_another_query')
            )
            await event.answer([builder])
            return

        kernel.cache.set(f"fheta_search_{query}", mods, ttl=300)

        results = []
        for idx, mod in enumerate(mods[:50]):
            stats = {"likes": mod.get('likes', 0), "dislikes": mod.get('dislikes', 0)}
            desc = mod.get("description", "")
            if isinstance(desc, dict):
                desc = desc.get(kernel.config.get('language', 'ru')) or desc.get("doc") or next(iter(desc.values()), "")

            text = fheta._fmt_mod(mod, query, idx + 1, len(mods), inline=False)
            buttons = fheta._mk_btns(mod.get("install", ""), stats, idx, mods, query)

            results.append(event.builder.article(
                title=fheta._escape_html(mod.get("name", "")),
                text=text,
                parse_mode='html',
                buttons=buttons,
                description=fheta._escape_html(str(desc))[:100]
            ))

        await event.answer(results)

    kernel.register_inline_handler('fheta', fheta_inline)

    async def callback_handler(event):
        data = event.data.decode()

        if data.startswith('fheta_rate:'):
            parts = data.split(':')
            if len(parts) >= 5:
                install = parts[1]
                action = parts[2]
                idx = int(parts[3])
                query = ':'.join(parts[4:]) if len(parts) > 4 else ""
                await fheta._rate_cb(event, install, action, idx, query)

        elif data.startswith('fheta_nav:'):
            parts = data.split(':')
            if len(parts) >= 3:
                idx = int(parts[1])
                query = ':'.join(parts[2:]) if len(parts) > 2 else ""
                await fheta._nav_cb(event, idx, query)

    kernel.register_callback_handler('fheta_rate:', callback_handler)
    kernel.register_callback_handler('fheta_nav:', callback_handler)
