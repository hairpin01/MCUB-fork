# System information display.

import asyncio
import platform
import shutil

DESCRIPTION = "Display system information."


def _bar(percent, width=10):
    filled = int(percent / 100 * width)
    return "\033[92m" + "█" * filled + "\033[90m" + "░" * (width - filled) + "\033[0m"


async def run(shell, args):
    uname = platform.uname()
    cpu = platform.processor() or platform.machine()

    shell.output("\n\033[96m\033[1mSystem Information\033[0m\n")

    shell.output(f"  \033[93mOS:\033[0m   {uname.system} {uname.release}")
    shell.output(f"  \033[93mHost:\033[0m {uname.node}")
    shell.output(f"  \033[93mArch:\033[0m {uname.machine}")
    shell.output(f"  \033[93mCPU:\033[0m  {cpu}")

    try:
        import psutil
        mem = psutil.virtual_memory()
        shell.output("\n  \033[93mMemory:\033[0m")
        shell.output(f"    Total: {mem.total // (1024**3)} GB")
        shell.output(f"    Used:  {mem.used // (1024**3)} GB  {_bar(mem.percent)} {mem.percent}%")
        shell.output(f"    Free:  {mem.available // (1024**3)} GB")

        disk = psutil.disk_usage("/")
        shell.output("\n  \033[93mDisk (/):\033[0m")
        shell.output(f"    Total: {disk.total // (1024**3)} GB")
        shell.output(f"    Used:  {disk.used // (1024**3)} GB  {_bar(disk.percent)} {disk.percent}%")
        shell.output(f"    Free:  {disk.free // (1024**3)} GB")

        boot_time = psutil.boot_time()
        import time
        uptime_h = (time.time() - boot_time) / 3600
        shell.output(f"\n  \033[93mUptime:\033[0m {uptime_h:.1f} hours")

    except ImportError:
        shell.output("\n\033[90m  (install psutil for memory/disk info)\033[0m")

    if shutil.which("uptime"):
        proc = await asyncio.create_subprocess_exec(
            "uptime",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        shell.output(f"\n  \033[93mUptime:\033[0m {stdout.decode().strip()}")
