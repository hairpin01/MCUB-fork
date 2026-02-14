# author: @Hairpin00
# version: 1.0.1
# description: Entry point for running MCUB as a module

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.kernel import Kernel
# from .kernel import Kernel
import asyncio

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
