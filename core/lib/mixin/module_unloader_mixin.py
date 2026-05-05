# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kernel import Kernel


class ModuleUnloaderMixin:
    """Mixin for unloading and unregistering modules."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def unregister_module_commands(self, module_name: str) -> None:
        """Stop loops, remove event handlers, and unregister all commands for a module.

        Args:
            module_name: Name of the module to unregister.
        """
        k = self.k

        module = k.loaded_modules.get(module_name) or k.system_modules.get(module_name)

        k.logger.debug(
            "[loader.unregister] start module=%r loaded=%s system=%s commands=%r aliases=%r",
            module_name,
            module_name in k.loaded_modules,
            module_name in k.system_modules,
            [cmd for cmd, owner in k.command_owners.items() if owner == module_name],
            {
                alias: target
                for alias, target in k.aliases.items()
                if k.command_owners.get(target) == module_name
            },
        )

        reg = getattr(module, "register", None) if module is not None else None

        instance = getattr(module, "_class_instance", None)
        if instance is not None:
            if instance._loaded:
                instance._loaded = False
                try:
                    if inspect.iscoroutinefunction(instance.on_unload):
                        await instance.on_unload()
                    else:
                        result = instance.on_unload()
                        if asyncio.iscoroutine(result):
                            await result
                    k.logger.debug(f"on_unload called for class module: {module_name}")
                except Exception as e:
                    k.logger.error(f"on_unload error in {module_name}: {e}")

                cleanup_callback_tokens = getattr(
                    instance, "_cleanup_callback_tokens", None
                )
                if callable(cleanup_callback_tokens):
                    try:
                        cleanup_callback_tokens()
                    except Exception as e:
                        k.logger.error(f"callback cleanup error in {module_name}: {e}")

            if hasattr(k, "_class_module_instances"):
                k._class_module_instances.pop(module_name, None)

            k.logger.debug(
                "[loader.unregister] class module instance removed module=%r",
                module_name,
            )

        if module is not None:
            if reg is None:
                k.logger.debug(
                    "[loader.unregister] no-register module=%r type=%r",
                    module_name,
                    type(module).__name__,
                )

            for loop in getattr(reg, "__loops__", []):
                try:
                    k.logger.debug(
                        "[loader.unregister] stopping loop module=%r loop=%r",
                        module_name,
                        getattr(getattr(loop, "func", None), "__name__", repr(loop)),
                    )
                    loop.stop()
                except Exception as e:
                    k.logger.error(f"Error stopping loop in {module_name}: {e}")

            for entry in getattr(reg, "__watchers__", []):
                wrapper, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else k.client
                try:
                    k.logger.debug(
                        "[loader.unregister] removing watcher module=%r wrapper=%r event=%r client=%r",
                        module_name,
                        getattr(wrapper, "__name__", repr(wrapper)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    client.remove_event_handler(wrapper, event_obj)
                except Exception as e:
                    k.logger.error(f"Error removing watcher in {module_name}: {e}")

            await asyncio.sleep(0)

            for entry in getattr(reg, "__event_handlers__", []):
                handler, event_obj = entry[0], entry[1]
                client = entry[2] if len(entry) > 2 else k.client
                try:
                    k.logger.debug(
                        "[loader.unregister] removing event module=%r handler=%r event=%r client=%r",
                        module_name,
                        getattr(handler, "__name__", repr(handler)),
                        type(event_obj).__name__,
                        type(client).__name__,
                    )
                    client.remove_event_handler(handler, event_obj)
                except Exception as e:
                    k.logger.error(
                        f"Error removing event handler in {module_name}: {e}"
                    )

        # Remove raw client.on() handlers (Telethon-MCUB automatic tracking)
        try:
            if hasattr(k.client, "remove_module_handlers"):
                k.client.remove_module_handlers(module_name)
            elif hasattr(k.client, "_event_builders") and k.client._event_builders:
                # Fallback for standard Telethon: remove by scanning _event_builders
                module = k.loaded_modules.get(module_name) or k.system_modules.get(
                    module_name
                )
                if module:
                    reg = getattr(module, "register", None)
                    if reg and hasattr(reg, "__event_handlers__"):
                        for entry in reg.__event_handlers__:
                            handler = entry[0]
                            event_obj = entry[1] if len(entry) > 1 else None
                            try:
                                k.client.remove_event_handler(handler, event_obj)
                            except Exception:
                                pass

            if hasattr(k, "bot_client") and k.bot_client:
                if hasattr(k.bot_client, "remove_module_handlers"):
                    k.bot_client.remove_module_handlers(module_name)
                elif (
                    hasattr(k.bot_client, "_event_builders")
                    and k.bot_client._event_builders
                ):
                    # Fallback for standard Telethon bot_client
                    module = k.loaded_modules.get(module_name) or k.system_modules.get(
                        module_name
                    )
                    if module:
                        reg = getattr(module, "register", None)
                        if reg and hasattr(reg, "__event_handlers__"):
                            for entry in reg.__event_handlers__:
                                handler = entry[0]
                                event_obj = entry[1] if len(entry) > 1 else None
                                try:
                                    k.bot_client.remove_event_handler(
                                        handler, event_obj
                                    )
                                except Exception:
                                    pass
        except Exception as e:
            k.logger.error(f"Error removing module raw handlers in {module_name}: {e}")

        uninstall = getattr(reg, "__uninstall__", None)
        if uninstall is not None:
            try:
                result = uninstall(k)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.ensure_future(result)
                    except RuntimeError:
                        k.logger.debug(
                            "[loader.unregister] uninstall-asyncio-run module=%r",
                            module_name,
                        )
                        asyncio.run(result)
            except Exception as e:
                k.logger.error(f"Error in uninstall callback of {module_name}: {e}")
        else:
            if module is None:
                k.logger.debug(
                    "[loader.unregister] missing-module module=%r", module_name
                )
            else:
                k.logger.debug(
                    "[loader.unregister] no-uninstall module=%r",
                    module_name,
                )

        to_remove = [
            cmd for cmd, owner in k.command_owners.items() if owner == module_name
        ]
        k.logger.debug(
            "[loader.unregister] command-removal module=%r to_remove=%r",
            module_name,
            to_remove,
        )
        for cmd in to_remove:
            if cmd in k.command_handlers:
                del k.command_handlers[cmd]
            if cmd in k.command_owners:
                del k.command_owners[cmd]
            k.logger.debug(f"Unregistered command: {cmd}")

        # Unregister bot commands
        if hasattr(k, "bot_command_handlers"):
            bot_to_remove = [
                cmd
                for cmd, owner in k.bot_command_owners.items()
                if owner == module_name
            ]
            for cmd in bot_to_remove:
                if cmd in k.bot_command_handlers:
                    del k.bot_command_handlers[cmd]
                if cmd in k.bot_command_owners:
                    del k.bot_command_owners[cmd]
                k.logger.debug(f"Unregistered bot command: {cmd}")

        # Don't remove aliases on unregister - they persist across reloads
        # aliases_to_remove = [
        #     alias
        #     for alias, target_cmd in k.aliases.items()
        #     if k.command_owners.get(target_cmd) == module_name
        #     or target_cmd in to_remove
        # ]
        # for alias in aliases_to_remove:
        #     del k.aliases[alias]
        #     k.logger.debug(f"Unregistered alias: {alias}")

        if not to_remove:
            k.logger.debug(
                "[loader.unregister] nothing-to-remove module=%r",
                module_name,
            )

        k.unregister_module_inline_handlers(module_name)
        k.logger.debug(
            "[loader.unregister] done module=%r remaining_commands=%r remaining_aliases=%r",
            module_name,
            list(k.command_handlers.keys()),
            dict(k.aliases),
        )

    def remove_module_aliases(
        self, module_name: str, commands_removed: list[str] | None = None
    ) -> None:
        """Remove all aliases pointing to commands owned by a module.

        This is called when a module is permanently uninstalled (um command),
        not when it's just reloaded.

        Args:
            module_name: Name of the module whose aliases should be removed.
            commands_removed: Optional list of commands that were already removed
                from command_owners. If provided, aliases for these commands
                will also be removed.
        """
        k = self.k
        aliases_to_remove = [
            alias
            for alias, target_cmd in k.aliases.items()
            if k.command_owners.get(target_cmd) == module_name
        ]
        if commands_removed:
            for alias, target_cmd in list(k.aliases.items()):
                if target_cmd in commands_removed:
                    aliases_to_remove.append(alias)
        for alias in aliases_to_remove:
            if alias in k.aliases:
                del k.aliases[alias]
                k.logger.debug(f"Removed alias: {alias} (module={module_name})")
