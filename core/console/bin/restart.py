# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

# Restart the shell.

DESCRIPTION = "Restart the shell."


async def run(shell, args):
    shell.output("\033[93mRestarting shell...\033[0m")
    shell.restart()
