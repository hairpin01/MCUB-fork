# Download files from URL.

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

DESCRIPTION = "Download a file from URL."


async def run(shell, args):
    if not args:
        shell.output("Usage: fetch <url> [output_filename]")
        return

    url = args[0]
    filename = args[1] if len(args) > 1 else None

    if not filename:
        parsed = urlparse(url)
        filename = Path(parsed.path).name
        if not filename:
            filename = "index.html"

    shell.output(f"\033[96mDownloading\033[0m {url}")
    shell.output(f"\033[90m  -> {filename}\033[0m")

    try:
        async with shell.spinner(f"Fetching {filename}..."):
            proc = await asyncio.create_subprocess_exec(
                "curl", "-L", "-o", filename, url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            size = os.path.getsize(filename)
            shell.output(f"\033[92mSaved to {filename} ({size} bytes)\033[0m")
        else:
            shell.output(f"\033[91mError: {stderr.decode()}\033[0m")
    except FileNotFoundError:
        shell.output("\033[91mError: curl not found. Install curl first.\033[0m")
    except Exception as e:
        shell.output(f"\033[91mError: {e}\033[0m")
