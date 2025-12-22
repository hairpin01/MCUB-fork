import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.kernel import Kernel

async def main():
    kernel = Kernel()
    await kernel.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n⛔ Остановка ядра...')
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
        sys.exit(1)
