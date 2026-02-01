import asyncio
import sys
import os
from core.kernel import Kernel

sys.path.insert(
        0, 
        os.path.dirname(
            os.path.abspath(
                __file__
            )
        )
)

async def main():
    kernel = Kernel()
    await kernel.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nStop Kernel...')
        kernel.client.disconnect()
        sys.exit(0)
        

    except Exception as e:
        print(f'\nError: "{e}" [X]')
        sys.exit(1)

