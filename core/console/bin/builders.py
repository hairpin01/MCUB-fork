# Shell command: builders
# Show Telethon event builders currently bound to the client.

DESCRIPTION = "Show current Telethon event builder bindings."


async def run(shell, args):
    kernel = shell.kernel
    if kernel is None:
        shell.output("Kernel is not available.")
        return

    builder_snapshot = []
    if hasattr(kernel, "_debug_event_builders_snapshot"):
        builder_snapshot = kernel._debug_event_builders_snapshot()
    elif getattr(kernel, "client", None) is not None:
        for event_obj, callback in getattr(kernel.client, "_event_builders", []) or []:
            builder_snapshot.append(
                f"{type(event_obj).__name__}:{getattr(callback, '__name__', repr(callback))}"
            )

    if not builder_snapshot:
        shell.output("No event builders registered.")
        return

    shell.output("\n".join(builder_snapshot))
