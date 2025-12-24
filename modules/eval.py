import html
import traceback
import sys
import io
import time

def register(kernel):
    client = kernel.client
    
    @kernel.register_command('py')
    async def python_exec_handler(event):
        code = event.text[len(kernel.custom_prefix)+2:].strip()
        
        if not code:
            await event.edit(f"❌ Использование: `{kernel.custom_prefix}py код_на_python`")
            return
        
        start_time = time.time()
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = sys.stderr = output = io.StringIO()
        
        local_vars = {
            'kernel': kernel,
            'client': client,
            'event': event,
            'asyncio': __import__('asyncio'),
            'telethon': __import__('telethon'),
            'Button': __import__('telethon').Button,
            'events': __import__('telethon').events
        }
        
        try:
            exec(f"async def __exec():\n    " + "\n    ".join(code.split('\n')), local_vars)
            result = await local_vars['__exec']()
            complete = output.getvalue()
            if result is not None:
                complete += str(result)
        except Exception as e:
            complete = traceback.format_exc()
        
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        end_time = time.time()
        elapsed = round((end_time - start_time) * 1000, 2)
        
        code_display = html.escape(code[:1000]) + ("..." if len(code) > 1000 else "")
        complete_display = html.escape(complete[:2000]) + ("..." if len(complete) > 2000 else "")
        
        response = f"""🧿 <b>Код</b>
<code>{code_display}</code>

🧬 <b>Результат</b>
<code>{complete_display}</code>

<blockquote>💠 <i>Выполнено за</i> <code>{elapsed}ms</code></blockquote>"""
        
        await event.edit(response, parse_mode='html')