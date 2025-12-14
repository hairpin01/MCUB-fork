# MCpy.py - Выполнение Python кода

import io
import sys
import traceback
import contextlib
from datetime import datetime
from telethon import events

def register(client):

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.pymc'))
    async def pymc_handler(event):
        code = event.text[6:].strip()

        if not code:
            await event.edit("❌ Пожалуйста, укажите код для выполнения после команды `.pymc`")
            return

        await event.edit("🔧 Выполнение кода...")
        start_time = datetime.now()

        try:
            output_buffer = io.StringIO()

            with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
                exec_globals = {
                    'event': event,
                    'client': client,
                }
                exec_globals.update(__builtins__)
                exec(code, exec_globals)

            output = output_buffer.getvalue().strip()
            if not output:
                output = "✅ Код выполнен без вывода"

            execution_time = (datetime.now() - start_time).total_seconds()
            timestamp = datetime.now().strftime("%H:%M:%S")

            result = f"""✅ **Python Code Executor**

⏰ **Время:** `{timestamp}`
⏱️ **Выполнено за:** `{execution_time:.2f}с`

📥 **Ввод:**
```python
{code}
```

📤 **Вывод:**
```python
{output}
```"""

            await event.edit(result)

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            timestamp = datetime.now().strftime("%H:%M:%S")

            exc_type = type(e).__name__
            exc_message = str(e)
            tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
            formatted_traceback = "".join(tb_lines[-3:]).strip()

            error_output = f"{exc_type}: {exc_message}\n\n{formatted_traceback}"

            result = f"""❌ **Python Code Executor**

⏰ **Время:** `{timestamp}`
⏱️ **Выполнено за:** `{execution_time:.2f}с`

📥 **Ввод:**
```python
{code}
```

📤 **Вывод:**
```python
{error_output}
```"""

            await event.edit(result)
