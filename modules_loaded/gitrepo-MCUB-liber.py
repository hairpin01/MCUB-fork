#------------------------------------------------------------------
# github: https://github.com/hairpin01/repo-MCUB-fork/liber/
# Channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires:
# author: port: @Hairpin00, author: @qShad0_bio
# version: 1.0.0
# description: Клонирует git репозиторий и отправляет его в виде zip-архива
# ----------------------- End ------------------------------

import os
import tempfile
import zipfile
import aiohttp
import asyncio
from utils import answer, get_args_raw

async def run_subprocess(command):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()

async def clonerepo(url: str, dir: str):
    command = ['git', 'clone', url, dir]
    returncode, stdout, stderr = await run_subprocess(command)
    return returncode, stderr

def register(kernel):
    @kernel.register.command('git')
    # Клонирует git репозиторий и отправляет его в виде zip-архива
    async def git(event):
        if event.reply_to_msg_id:
            replied_message = await event.get_reply_message()
            url = replied_message.event.strip()
        else:
            args = get_args_raw(event)
            if not args:
                await answer(event, "<b>Укажите URL git репозитория.</b>", as_html=True)
                return
            url = args.strip()

        await answer(event, "<b>Начинаю загрузку....</b>", as_html=True)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = os.path.join(temp_dir, "repo")
                try:
                    repocode, stderr = await clonerepo(url, repo_dir)
                    if repocode != 0:
                        await answer(event, f"<b>Ошибка при клонировании репозитория: {str(stderr)}</b>", as_html=True)
                        return
                    repo_name = os.path.basename(url.split("/").pop().rstrip(".git"))
                except Exception as e:
                    await answer(event, f"<b>Ошибка при клонировании репозитория: {str(e)}</b>", as_html=True)
                    return

                zip_file = os.path.join(temp_dir, f"{repo_name}.zip")
                try:
                    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(repo_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, repo_dir)
                                zipf.write(file_path, arcname)
                except Exception as e:
                    await answer(event, f"<b>Ошибка при архивации репозитория: {str(e)}</b>", as_html=True)
                    return

                await event.edit( f"<b>Репозиторий {repo_name} в виде zip-архива.</b>", file=zip_file, parse_mode='html')

        except Exception as e:
            await answer(event, f"<b>Произошла ошибка: {str(e)}</b>", as_html=True)

    @kernel.register.command('wget')
    # Сохраняет файл из интернета
    async def wget(event):
        if event.reply_to_msg_id:
            replied_message = await event.get_reply_message()
            url = replied_message.event.strip()
        else:
            args = get_args_raw(event)
            if not args:
                await answer(event, "<b>Укажите URL с файлом</b>", as_html=True)
                return
            url = args.strip()

        await answer(event, "<b>Начинаю загрузку....</b>", as_html=True)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                downloaded_file_path = os.path.join(temp_dir, os.path.basename(url))
                
                # Скачивание файла
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                with open(downloaded_file_path, 'wb') as f:
                                    f.write(await resp.read())
                            else:
                                await answer(event, "<b>Ошибка при скачивании файла.</b>", as_html=True)
                                return
                except Exception as e:
                    await answer(event, f"<b>Ошибка сохранения: {str(e)}</b>", as_html=True)
                    return

                await event.edit(f"<b>Файл {url} успешно сохранен</b>", file=downloaded_file_path, parse_mode='html')

        except Exception as e:
            await answer(event, f"<b>Произошла ошибка: {str(e)}</b>", parse_mode='html')
