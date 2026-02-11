# author: @Hairpin00
# version: 1.0.0
# description: kernel restart

import sys
import os
import json
import time
from typing import Optional


async def restart_kernel(kernel, chat_id: Optional[int] = None, message_id: Optional[int] = None):
    """
    Выполняет перезагрузку процесса юзербота.
    Сохраняет данные для пост-рестарт уведомления и корректно закрывает ресурсы.

    Args:
        kernel: экземпляр класса Kernel
        chat_id: ID чата для отправки уведомления после перезагрузки
        message_id: ID сообщения, которое будет отредактировано после перезагрузки
    """
    kernel.logger.info("Restart...")

    # Сохраняем информацию о перезагрузке, если передан чат
    if chat_id:
        try:
            restart_data = {
                "chat_id": chat_id,
                "msg_id": message_id,
                "time": time.time(),
            }
            with open(kernel.RESTART_FILE, "w") as f:
                json.dump(restart_data, f)
            kernel.logger.debug(f"Данные рестарта сохранены в {kernel.RESTART_FILE}")
        except Exception as e:
            kernel.logger.error(f"Не удалось сохранить данные рестарта: {e}")

    # Закрываем ресурсы ядра
    try:
        if kernel.db_conn:
            await kernel.db_conn.close()
        if kernel.scheduler:
            kernel.scheduler.cancel_all_tasks()
    except Exception as e:
        kernel.logger.error(f"Ошибка при закрытии ресурсов: {e}")

    # Перезапуск процесса
    args = sys.argv[:]
    os.execl(sys.executable, sys.executable, *args)
