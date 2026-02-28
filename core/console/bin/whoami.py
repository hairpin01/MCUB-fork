# Display current user info.

DESCRIPTION = "Display current Telegram user info."


async def run(shell, args):
    client = shell.kernel.client
    me = await client.get_me()
    
    shell.output(f"\n\033[96m\033[1mTelegram User Info\033[0m\n")
    shell.output(f"  \033[93mID:\033[0m      {me.id}")
    shell.output(f"  \033[93mFirst:\033[0m  {me.first_name}")
    if me.last_name:
        shell.output(f"  \033[93mLast:\033[0m   {me.last_name}")
    if me.username:
        shell.output(f"  \033[93mUsername:\033[0m @{me.username}")
    shell.output(f"  \033[93mPhone:\033[0m  {me.phone or 'hidden'}")
    if me.lang_code:
        shell.output(f"  \033[93mLang:\033[0m   {me.lang_code}")
