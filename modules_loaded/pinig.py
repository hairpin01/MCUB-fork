# description: return ping
# version: 1.0
# author: @Hairpin00


import time

def register (kernel):

    @kernel.register.command('return')
    # ping?
    async def return_command (m):
        time_start = time.time()
        await m.edit("🍭")
        time_end = time.time()

        await m.edit("return in {} ms".format(int((time_end - time_start) * 1000)))
