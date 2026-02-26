# console/bin/py.py
# Execute Python code asynchronously with kernel access.

import textwrap
import traceback
from typing import List

DESCRIPTION = "Execute Python code (asynchronous context available, can use 'await')"

async def run(shell, args: List[str]):
    """
    Выполняет переданный код Python в асинхронном контексте.
    В пространстве имён доступны:
      - kernel  – объект ядра MCUB
      - shell   – сам объект Shell (для вывода и работы с конфигом)
      - любые стандартные встроенные функции
    Можно использовать `await` прямо в коде.
    Использование: py <код>
    Пример: py print(kernel.VERSION)
    Пример с await: py await kernel.client.send_message('me', 'Hello')
    """
    if not args:
        shell.output("Usage: py <python code>")
        return

    code = " ".join(args)
    # Нормализуем отступы, чтобы убрать случайный общий префикс
    code = textwrap.dedent(code)
    # Оборачиваем в асинхронную функцию для поддержки await на верхнем уровне
    indented = textwrap.indent(code, '    ')
    wrapped = f"async def __code():\n{indented}"

    namespace = {
        "kernel": shell.kernel,
        "shell": shell,
        "__name__": "__console__"
    }

    try:
        exec(wrapped, namespace)
        await namespace["__code"]()
    except Exception:
        shell.output(traceback.format_exc())
