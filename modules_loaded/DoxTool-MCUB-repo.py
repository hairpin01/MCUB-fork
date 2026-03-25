# github: https://github.com/hairpin01/repo-MCUB-fork
# Channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires: random
# author: @codrago_m
# version: 1.0.0
# description: Your Best doxing tool! (For entertainment purposes only) / Ваш лучший инструмент доксинга! (Только в развлекательных целях)
# ----------------------- End ------------------------------
import random
import asyncio

def register(kernel):
    strings = {
        "gb_1": "Searching for the victim's number...",
        "gb_2": "Searching for the victim's address and name...",
        "gb_3": "Searching for parents...",
        "gb_4": "Searching for a school...",
        "gb_5": "Finding parents' jobs...",
        "gb_r": "My owner behaved badly, so I decided to leak info about him!\n\n├ Phone: wrecked\n├ Country: normal\n├ Region: of liars\n├ Parents: soon will be gone\n├ Address: a ditch on Arbat\n├ Name: why were you born\n├ Middle name: missing\n├ Surname: missing\n├ How many times screwed: 32\n├ Gender: linoleum\n├ House: a ditch on Arbat\n├ Sucks per day: 20 (times) for 10 rub\n├ Hospital: not allowed in\n├ Poop color: none, doesn’t eat\n├ Prostate: massaged\n├ Mouth: ruined\n└ #####################\n\nMother: a prostitute\nMother’s workplace: the highway\nCountry: in the CIS\nCity: how should I know?\nBorn: somewhere under a fence\n\nFather: a homeless\nWorkplace: begging on the street\nCountry: in the CIS\nCity: how should I know?\nBorn: in the sewers\nSchool: of fools",
        "info": "This module is created solely for entertainment purposes, its functionality is solely for the sake of a joke"
    }

    deanon_messages = [
        "It's bad to do something like this...",
        "I’m tired of you!",
        "One more prank like this and I’ll delete your account.",
        "Didn’t you understand the first time?",
        "Why do you keep doing this??",
        "We both know that this doesn’t do us any good.",
        "what won't it lead to?"
    ]

    @kernel.register.command('gb')
    async def gb_handler(event):
        await event.edit(strings["gb_1"])
        await asyncio.sleep(1)
        await event.edit(strings["gb_2"])
        await asyncio.sleep(1)
        await event.edit(strings["gb_3"])
        await asyncio.sleep(1)
        await event.edit(strings["gb_4"])
        await asyncio.sleep(1)
        await event.edit(strings["gb_5"])
        await asyncio.sleep(1)
        await event.edit(strings["gb_r"])

    @kernel.register.command('deanon')
    async def deanon_handler(event):
        await event.edit(random.choice(deanon_messages))

    @kernel.register.command('dinfo')
    async def dinfo_handler(event):
        await event.edit(strings["info"])
