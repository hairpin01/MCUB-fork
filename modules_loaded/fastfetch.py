from telethon import events
import subprocess

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.fastfetch$'))
    async def handler(event):
        try:
            result = subprocess.run(
                "fastfetch | sed 's/\\x1B\\[[0-9;?]*[a-zA-Z]//g'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            output = result.stdout.strip()

            if not output:
                await event.edit('❌ **fastfetch не найден!**\n\n'
                               'Установите его:\n'
                               '• Termux: `pkg install fastfetch`\n'
                               '• Ubuntu/Debian: `sudo apt install fastfetch`\n'
                               '• Arch: `sudo pacman -S fastfetch`\n'
                               '• macOS: `brew install fastfetch`')
                return

            if len(output) > 4000:
                output = output[:4000] + "\n... (вывод обрезан)"

            await event.edit(f'```\n{output}\n```')

        except subprocess.TimeoutExpired:
            await event.edit('❌ **Таймаут выполнения команды!**')
        except Exception as e:
            await event.edit(f'❌ **Ошибка:**\n```\n{str(e)}\n```')
