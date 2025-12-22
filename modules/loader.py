import asyncio
import os
import re
import sys
import subprocess
import importlib.util
import aiohttp
import json
from telethon import events, Button

def register(kernel):
    client = kernel.client
    
    @kernel.register_command('im')
    async def install_module_handler(event):
        if not event.is_reply:
            await event.edit('❌ Ответьте на .py файл')
            return
        
        reply = await event.get_reply_message()
        if not reply.document or not reply.document.attributes[0].file_name.endswith('.py'):
            await event.edit('❌ Это не .py файл')
            return
        
        file_name = reply.document.attributes[0].file_name
        module_name = file_name[:-3]
        
        await event.edit(f'📥 Установка {module_name}...')
        
        file_path = os.path.join(kernel.MODULES_LOADED_DIR, file_name)
        await reply.download_media(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            if 'from .. import' in code or 'import loader' in code:
                await event.edit(f'❌ Модуль не совместим')
                os.remove(file_path)
                return
            
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            
            module.kernel = kernel
            module.client = client
            module.custom_prefix = kernel.custom_prefix
            
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            if hasattr(module, 'register'):
                try:
                    module.register(client)
                    kernel.loaded_modules[module_name] = module
                    await event.edit(f'✅ Модуль {module_name} установлен')
                except Exception as e:
                    await event.edit(f'❌ Ошибка регистрации: {str(e)}')
                    os.remove(file_path)
            else:
                await event.edit(f'❌ Модуль должен иметь функцию register(client)')
                os.remove(file_path)
                
        except ImportError as e:
            error_msg = str(e)
            match = re.search(r"No module named '([^']+)'", error_msg)
            if match:
                dep = match.group(1)
                await event.edit(f'📦 Установка зависимости: {dep}')
                
                try:
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', dep],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    if result.returncode == 0:
                        await event.edit(f'✅ Зависимость {dep} установлена\n🔄 Перезагрузка модуля...')
                        
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)
                        
                        module.kernel = kernel
                        module.client = client
                        module.custom_prefix = kernel.custom_prefix
                        
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        
                        if hasattr(module, 'register'):
                            module.register(client)
                            kernel.loaded_modules[module_name] = module
                            await event.edit(f'✅ Модуль {module_name} установлен с зависимостью {dep}')
                        else:
                            await event.edit(f'❌ Модуль должен иметь функцию register(client)')
                            os.remove(file_path)
                    else:
                        await event.edit(f'❌ Не удалось установить {dep}\n{result.stderr[:500]}')
                        os.remove(file_path)
                        
                except subprocess.CalledProcessError as pip_err:
                    await event.edit(f'❌ Ошибка установки {dep}\n{pip_err.stderr[:500]}')
                    os.remove(file_path)
                except Exception as e:
                    await event.edit(f'❌ Неожиданная ошибка: {str(e)}')
                    os.remove(file_path)
            else:
                await event.edit(f'❌ Ошибка импорта: {error_msg}')
                os.remove(file_path)
                
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
            if os.path.exists(file_path):
                os.remove(file_path)
    
    @kernel.register_command('dlm')
    async def download_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}dlm название_модуля')
            return
        
        module_name = args[1]
        is_update = module_name in kernel.loaded_modules
        msg = await event.edit(f'📥 {"Обновление" if is_update else "Загрузка"} {module_name}...')
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{kernel.MODULES_REPO}/{module_name}.py') as resp:
                    if resp.status == 200:
                        code = await resp.text()
                        
                        if not os.path.exists(kernel.MODULES_LOADED_DIR):
                            os.makedirs(kernel.MODULES_LOADED_DIR)
                        
                        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
                        
                        if is_update and module_name in sys.modules:
                            del sys.modules[module_name]
                        
                        await msg.edit(f'📥 Сохранение {module_name}.py...')
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(code)
                        
                        await msg.edit(f'📦 Установка зависимостей...')
                        if 'requires' in code:
                            reqs = re.findall(r'# requires: (.+)', code)
                            if reqs:
                                for req in reqs[0].split(','):
                                    try:
                                        subprocess.run(
                                            [sys.executable, '-m', 'pip', 'install', req.strip()],
                                            capture_output=True,
                                            check=True
                                        )
                                    except subprocess.CalledProcessError:
                                        await msg.edit(f'⚠️ Не удалось установить {req.strip()}')
                        
                        await msg.edit(f'⚙️ Загрузка модуля...')
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)
                        
                        module.kernel = kernel
                        module.client = client
                        module.custom_prefix = kernel.custom_prefix
                        
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        
                        if hasattr(module, 'register'):
                            module.register(client)
                            kernel.loaded_modules[module_name] = module
                            status = '🔄 обновлен' if is_update else '✅ установлен'
                            await msg.edit(f'{status} Модуль {module_name}')
                        else:
                            await event.edit(f'❌ Модуль не имеет register(client)')
                            os.remove(file_path)
                    else:
                        await event.edit(f'❌ Модуль {module_name} не найден')
        except ImportError as e:
            error_msg = str(e)
            match = re.search(r"No module named '([^']+)'", error_msg)
            if match:
                dep = match.group(1)
                await msg.edit(f'📦 Автоустановка зависимости: {dep}')
                
                try:
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', dep],
                        capture_output=True,
                        check=True
                    )
                    
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    
                    module.kernel = kernel
                    module.client = client
                    module.custom_prefix = kernel.custom_prefix
                    
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, 'register'):
                        module.register(client)
                        kernel.loaded_modules[module_name] = module
                        await msg.edit(f'✅ Модуль {module_name} установлен с авто-зависимостью')
                    else:
                        await event.edit(f'❌ Модуль не имеет register(client)')
                        os.remove(file_path)
                        
                except Exception as pip_err:
                    await event.edit(f'❌ Не удалось установить зависимость {dep}')
                    if os.path.exists(file_path):
                        os.remove(file_path)
            else:
                await event.edit(f'❌ Ошибка импорта: {error_msg}')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
    
    @kernel.register_command('lm')
    async def list_modules_handler(event):
        if not kernel.loaded_modules:
            await event.edit('📦 Модули не загружены')
            return
        
        msg = '📦 **Загруженные модули:**\n\n'
        for name, module in kernel.loaded_modules.items():
            msg += f'• **{name}**\n'
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{name}.py')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                    commands = re.findall(r"pattern=r['\"]\^?\\?\.([a-zA-Z0-9_]+)", code)
                    if commands:
                        msg += f'  Команды: {", ".join([f"{kernel.custom_prefix}{cmd}" for cmd in commands])}\n'
            msg += '\n'
        await event.edit(msg)
    
    @kernel.register_command('um')
    async def unload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}um название_модуля')
            return
        
        module_name = args[1]
        
        if module_name not in kernel.loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        del kernel.loaded_modules[module_name]
        await event.edit(f'🗑️ Модуль {module_name} удален\n\n⚠️ Перезагрузите юзербот для полного удаления')
    
    @kernel.register_command('dlml')
    async def catalog_handler(event):
        page = 1
        args = event.text.split()
        if len(args) > 1:
            try:
                page = int(args[1])
            except:
                page = 1
        
        bot_username = kernel.config.get('inline_bot_username')
        if not bot_username:
            await event.edit('❌ Inline-бот не настроен')
            return
        
        await event.delete()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{kernel.MODULES_REPO}/catalog.json') as resp:
                    if resp.status == 200:
                        text_data = await resp.text()
                        catalog = json.loads(text_data)
                        
                        kernel.catalog_cache = catalog
                        
                        query = f'catalog_{page}'
                        results = await client.inline_query(bot_username, query)
                        
                        if results:
                            await results[0].click(event.chat_id)
                        else:
                            await client.send_message(event.chat_id, '❌ Ошибка инлайн-бота')
                    else:
                        await client.send_message(event.chat_id, '❌ Каталог не найден')
        except Exception as e:
            await client.send_message(event.chat_id, f'❌ Ошибка: {str(e)}')
    
    @kernel.register_command('unlm')
    async def upload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}unlm название_модуля')
            return
        
        module_name = args[1]
        
        if module_name not in kernel.loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        if not os.path.exists(file_path):
            await event.edit(f'❌ Файл модуля {module_name}.py не найден')
            return
        
        await event.edit(f'📤 Отправка модуля {module_name}...')
        await client.send_file(event.chat_id, file_path, caption=f'📦 Модуль: {module_name}.py')
        await event.delete()
    
    @kernel.register_command('reload')
    async def reload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}reload название_модуля')
            return
        
        module_name = args[1]
        
        if module_name not in kernel.loaded_modules:
            await event.edit(f'❌ Модуль {module_name} не найден')
            return
        
        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f'{module_name}.py')
        if not os.path.exists(file_path):
            await event.edit(f'❌ Файл модуля {module_name}.py не найден')
            return
        
        await event.edit(f'🔄 Перезагрузка {module_name}...')
        
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            
            module.kernel = kernel
            module.client = client
            module.custom_prefix = kernel.custom_prefix
            
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            if hasattr(module, 'register'):
                module.register(client)
                kernel.loaded_modules[module_name] = module
                await event.edit(f'✅ Модуль {module_name} перезагружен')
            else:
                await event.edit(f'❌ Модуль должен иметь функцию register(client)')
        except ImportError as e:
            error_msg = str(e)
            match = re.search(r"No module named '([^']+)'", error_msg)
            if match:
                dep = match.group(1)
                await event.edit(f'📦 Установка зависимости: {dep}')
                
                try:
                    subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', dep],
                        capture_output=True,
                        check=True
                    )
                    
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    
                    module.kernel = kernel
                    module.client = client
                    module.custom_prefix = kernel.custom_prefix
                    
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, 'register'):
                        module.register(client)
                        kernel.loaded_modules[module_name] = module
                        await event.edit(f'✅ Модуль {module_name} перезагружен с зависимостью')
                    else:
                        await event.edit(f'❌ Модуль должен иметь функцию register(client)')
                        
                except Exception as pip_err:
                    await event.edit(f'❌ Не удалось установить зависимость {dep}')
            else:
                await event.edit(f'❌ Ошибка импорта: {error_msg}')
        except Exception as e:
            await event.edit(f'❌ Ошибка перезагрузки: {str(e)}')

