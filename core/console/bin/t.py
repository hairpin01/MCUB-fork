# Run a shell command.

import asyncio
from typing import List

DESCRIPTION = "Execute a shell command."


async def run(shell, args: List[str]):
    """
    Запускает внешнюю команду в подоболочке и выводит её stdout/stderr.
    Использование: t <команда> [аргументы...]
    """
    if not args:
        shell.output("Usage: t <command> [arguments...]")
        return

    cmd = " ".join(args)
    shell.output(f"\033[90m$ {cmd}\033[0m")  # серым цветом

    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # читаем построчно, чтобы вывод появлялся по мере выполнения
    async for line in process.stdout:
        shell.output(line.decode().rstrip())
    async for line in process.stderr:
        shell.output(f"\033[91m{line.decode().rstrip()}\033[0m")  # красным цветом

    await process.wait()
    if process.returncode != 0:
        shell.output(f"\033[91mCommand exited with code {process.returncode}\033[0m")
