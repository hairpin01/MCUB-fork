import shutil
from typing import List, Tuple

from core.version import VersionManager


class ModuleCompatChecker:
    """
    Checks whether a module's '# scop:' directives are satisfied
    by the current kernel environment.
    """

    def __init__(self, kernel):
        self.kernel = kernel
        self.version_manager: VersionManager = kernel.version_manager

    @staticmethod
    def _parse_scop_directives(code: str) -> List[Tuple[str, str]]:
        """
        Scans module source code and returns all '# scop:' directives
        as a list of (scope, params) tuples.

        Example:
            '# scop: kernel min v1.0.2'  →  ('kernel', 'min v1.0.2')
            '# scop: inline'             →  ('inline', '')
        """
        directives: List[Tuple[str, str]] = []

        for line in code.split("\n"):
            stripped = line.strip()
            if not stripped.startswith("# scop:"):
                continue

            rest = stripped[len("# scop:") :].strip()
            space_index = rest.find(" ")

            if space_index == -1:
                directives.append((rest, ""))
            else:
                directives.append((rest[:space_index], rest[space_index + 1 :].strip()))

        return directives

    async def _check_kernel_scope(
        self,
        params: str,
        current_version: str,
        latest_version_cache: List,  # mutable 1-element list used as a lazy cache
    ) -> Tuple[bool, str]:
        """
        Handles '# scop: kernel ...' directives.

        Supported forms:
            kernel min v{version}       — require current >= version
            kernel max v{version}       — require current <= version
            kernel v{version}           — require current == version
            kernel v[__lastest__]       — require current == latest in repo
        """
        parts = params.split()
        if not parts:
            return True, ""

        compare = self.version_manager.compare_versions

        if parts[0] == "min":
            if len(parts) >= 2 and parts[1].startswith("v"):
                required = parts[1][1:]
                if compare(current_version, required) < 0:
                    return False, (
                        f"Module requires kernel version ≥ {required}, "
                        f"current is {current_version}"
                    )

        elif parts[0] == "max":
            if len(parts) >= 2 and parts[1].startswith("v"):
                required = parts[1][1:]
                if compare(current_version, required) > 0:
                    return False, (
                        f"Module requires kernel version ≤ {required}, "
                        f"current is {current_version}"
                    )

        else:
            if not parts[0].startswith("v"):
                return True, ""

            spec = parts[0][1:]

            if spec == "[__lastest__]":
                if latest_version_cache[0] is None:
                    latest_version_cache[0] = (
                        await self.version_manager.get_latest_kernel_version()
                    )
                latest = latest_version_cache[0]
                if compare(current_version, latest) != 0:
                    return False, (
                        f"Module requires the latest kernel version ({latest}), "
                        f"but current is {current_version}"
                    )
            else:
                if compare(current_version, spec) != 0:
                    return False, (
                        f"Module requires kernel version exactly {spec}, "
                        f"but current is {current_version}"
                    )

        return True, ""

    def _check_inline_scope(self) -> Tuple[bool, str]:
        """
        Handles '# scop: inline'.
        Verifies that bot_client exists and is connected.
        """
        if not hasattr(self.kernel, "bot_client") or self.kernel.bot_client is None:
            return (
                False,
                "Module requires inline bot to be enabled, but bot_client is not available",
            )
        if not self.kernel.bot_client.is_connected():
            return (
                False,
                "Module requires inline bot to be connected, but bot_client is disconnected",
            )
        return True, ""

    @staticmethod
    def _check_ffmpeg_scope() -> Tuple[bool, str]:
        """
        Handles '# scop: ffmpeg'.
        Verifies that ffmpeg is present on the system PATH.
        """
        if shutil.which("ffmpeg") is None:
            return False, "Module requires ffmpeg to be installed on the system"
        return True, ""

    async def check_module_compatibility(self, code: str) -> Tuple[bool, str]:
        """
        Parses all '# scop:' directives in the module source code
        and verifies each one against the current environment.

        Returns (True, "") if all checks pass,
        or (False, reason) on the first failing check.
        """
        directives = self._parse_scop_directives(code)
        if not directives:
            return True, ""

        current_version = self.kernel.VERSION
        latest_version_cache = [None]  # lazy-fetched once if needed

        for scope, params in directives:
            if scope == "kernel":
                ok, reason = await self._check_kernel_scope(
                    params, current_version, latest_version_cache
                )
            elif scope == "inline":
                ok, reason = self._check_inline_scope()
            elif scope == "ffmpeg":
                ok, reason = self._check_ffmpeg_scope()
            else:
                continue

            if not ok:
                return False, reason

        return True, ""
