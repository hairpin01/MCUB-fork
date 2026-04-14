# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

# Shell command: watchers
# Show watcher state tracked by the kernel.

DESCRIPTION = "Show watcher state, direction and binding status."


async def run(shell, args):
    kernel = shell.kernel
    if kernel is None or not hasattr(kernel, "register"):
        shell.output("Kernel is not available.")
        return

    filter_text = " ".join(args).strip().lower()
    watchers = kernel.register.get_watchers()
    builder_snapshot = []
    if hasattr(kernel, "_debug_event_builders_snapshot"):
        builder_snapshot = kernel._debug_event_builders_snapshot()

    lines = ["Watchers debug:"]
    matched = 0

    for watcher in watchers:
        module_name = watcher["module"]
        watcher_name = watcher["method"]
        full_name = f"{module_name}.{watcher_name}"
        if filter_text and filter_text not in full_name.lower():
            continue

        wrapper_name = getattr(watcher["wrapper"], "__name__", watcher_name)
        builder_marker = f"{type(watcher['event']).__name__}:{wrapper_name}"
        in_builders = builder_marker in builder_snapshot

        direction = []
        if watcher["tags"].get("incoming"):
            direction.append("incoming")
        if watcher["tags"].get("out"):
            direction.append("out")
        if not direction:
            direction.append("any")

        lines.append(
            f"{full_name} - enabled={watcher['enabled']} "
            f"bound={in_builders} dir={','.join(direction)}"
        )
        matched += 1

    if not matched:
        shell.output("No watchers matched.")
        return

    shell.output("\n".join(lines))
