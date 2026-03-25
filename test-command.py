def register(kernel):
    @kernel.register.command('test_command')
    async def command_handler(event):
        await kernel.client.send_message(event.chat_id, str(event.message))
