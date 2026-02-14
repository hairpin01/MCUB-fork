# author: @Hairpin00
# version: 1.0.1
# description: Entry point for running MCUB as a module

import asyncio
import sys

from .kernel import Kernel


async def main():
    """Main entry point for MCUB kernel."""
    kernel = Kernel()
    await kernel.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("-> exit kernel...")
        sys.exit(0)
    except Exception as e:
        print(f'\nError: "{e}" [X]')
        sys.exit(1)
