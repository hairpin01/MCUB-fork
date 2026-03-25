# Generate QR codes in terminal.

import asyncio
import shutil

DESCRIPTION = "Generate a QR code from text."


async def run(shell, args):
    if not args:
        shell.output("Usage: qr <text>")
        shell.output("       qr -f <file>  (read from file)")
        return

    if args[0] == "-f":
        if len(args) < 2:
            shell.output("Usage: qr -f <file>")
            return
        try:
            with open(args[1], "r") as f:
                text = f.read().strip()
        except FileNotFoundError:
            shell.output(f"\033[91mFile not found: {args[1]}\033[0m")
            return
    else:
        text = " ".join(args)

    try:
        import qrcode
        qr = qrcode.QRCode(box_size=2, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image()
        
        width = img.width
        height = img.height
        pixels = img.load()
        
        out_lines = []
        for y in range(height):
            line = ""
            for x in range(width):
                px = pixels[x, y]
                if isinstance(px, tuple):
                    val = px[0]
                else:
                    val = px
                line += "\033[92m  \033[0m" if val < 128 else "  "
            out_lines.append(line)
        
        shell.output("\n" + "\n".join(out_lines))
    except ImportError:
        if shutil.which("qrencode"):
            proc = await asyncio.create_subprocess_exec(
                "qrencode", "-t", "utf8", text,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                shell.output(stdout.decode())
            else:
                shell.output(f"\033[91mError: {stderr.decode()}\033[0m")
        else:
            shell.output("\033[91mError: Install 'qrcode' pip package or 'qrencode' binary.\033[0m")
