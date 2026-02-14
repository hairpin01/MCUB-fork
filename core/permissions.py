# author: @Hairpin00
# version: 1.0.1
# description: Permission manager for callback operations

import time
from collections import defaultdict
from typing import Dict, Optional, Pattern, Union


class CallbackPermissionManager:
    """
    A manager for granting temporary permissions for callback operations.

    This class provides time-based permission grants with pattern matching.
    It's useful for implementing secure callback systems where users need
    temporary access to specific operations or data patterns.

    Attributes:
        permissions: Nested dictionary storing user permissions
                    Structure: {user_id: {pattern: expiry_time}}
    """

    def __init__(self) -> None:
        """
        Initialize the permission manager with empty permissions.
        """
        # {user_id: {pattern: expiry_time}}
        self.permissions: Dict[int, Dict[str, float]] = defaultdict(dict)

    def _to_str(self, val: Union[str, bytes, Pattern]) -> str:
        """
        Convert various input types to a normalized string pattern.

        Args:
            val: Value to convert. Can be:
                - str: Returned as-is
                - bytes: Decoded from UTF-8
                - Pattern (re.Pattern): Pattern string is extracted
                - Any other type: Converted to string with str()

        Returns:
            Normalized string pattern

        Raises:
            UnicodeDecodeError: If bytes cannot be decoded from UTF-8
        """
        if isinstance(val, bytes):
            return val.decode("utf-8")
        elif isinstance(val, Pattern):
            # Extract pattern string from compiled regex
            return val.pattern
        return str(val)

    def allow(self,
              user_id: int,
              pattern: Union[str, bytes, Pattern],
              duration_seconds: float = 60) -> None:
        """
        Grant temporary permission to a user for a specific pattern.

        The permission will automatically expire after the specified duration.
        Multiple patterns can be granted to the same user.

        Args:
            user_id: User identifier (typically Telegram user ID)
            pattern: Permission pattern (supports prefix matching)
            duration_seconds: How long the permission lasts in seconds (default: 60)

        Example:
            >>> manager.allow(123456, "settings_edit_", duration_seconds=300)
            # User 123456 can access any callback starting with "settings_edit_"
            # for 5 minutes
        """
        pattern_str = self._to_str(pattern)
        expiry_time = time.time() + duration_seconds

        self.permissions[user_id][pattern_str] = expiry_time

    def is_allowed(self,
                   user_id: int,
                   pattern: Union[str, bytes, Pattern]) -> bool:
        """
        Check if a user has permission for a specific pattern.

        The check uses prefix matching: if the requested pattern starts with
        any allowed pattern that hasn't expired, permission is granted.
        Expired permissions are automatically skipped.

        Args:
            user_id: User identifier to check
            pattern: Pattern to check permission for

        Returns:
            True if user has valid permission for the pattern, False otherwise

        Example:
            >>> manager.allow(123456, "menu_", duration_seconds=60)
            >>> manager.is_allowed(123456, "menu_main")  # True
            >>> manager.is_allowed(123456, "settings")   # False
        """
        pattern_str = self._to_str(pattern)
        current_time = time.time()

        # Quick check: user has no permissions
        if user_id not in self.permissions:
            return False

        # Check each allowed pattern for this user
        for allowed_pattern, expiry_time in self.permissions[user_id].items():
            # Skip expired permissions
            if expiry_time <= current_time:
                continue

            # Prefix matching: if requested pattern starts with allowed pattern
            if pattern_str.startswith(allowed_pattern):
                return True

        return False

    def prohibit(self,
                 user_id: int,
                 pattern: Optional[Union[str, bytes, Pattern]] = None) -> None:
        """
        Revoke permission(s) for a user.

        Args:
            user_id: User identifier
            pattern: Specific pattern to revoke. If None, revoke all permissions
                     for this user

        Example:
            >>> manager.allow(123456, "menu_")
            >>> manager.allow(123456, "settings_")
            >>> manager.prohibit(123456, "menu_")  # Revoke only menu permissions
            >>> manager.prohibit(123456)           # Revoke all permissions
        """
        if user_id not in self.permissions:
            return

        if pattern is not None:
            pattern_str = self._to_str(pattern)
            # Remove specific pattern
            if pattern_str in self.permissions[user_id]:
                del self.permissions[user_id][pattern_str]

            # Clean up empty user entry
            if not self.permissions[user_id]:
                del self.permissions[user_id]
        else:
            # Remove all permissions for this user
            del self.permissions[user_id]

    def cleanup(self) -> int:
        """
        Remove all expired permissions across all users.

        This method should be called periodically to free up memory.

        Returns:
            Number of expired permissions removed

        Example:
            >>> expired_count = manager.cleanup()
            >>> print(f"Cleaned up {expired_count} expired permissions")
        """
        current_time = time.time()
        removed_count = 0

        # Iterate over copy of keys to avoid modification during iteration
        for user_id in list(self.permissions.keys()):
            user_patterns = self.permissions[user_id]

            # Find expired patterns for this user
            expired_patterns = [
                pattern for pattern, expiry_time in user_patterns.items()
                if expiry_time <= current_time
            ]

            # Remove expired patterns
            for pattern in expired_patterns:
                del user_patterns[pattern]
                removed_count += 1

            # Remove user entry if no patterns remain
            if not user_patterns:
                del self.permissions[user_id]

        return removed_count

    def get_user_permissions(self, user_id: int) -> Dict[str, float]:
        """
        Get all active permissions for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of pattern -> expiry_time for active permissions
            Empty dict if user has no active permissions
        """
        if user_id not in self.permissions:
            return {}

        current_time = time.time()
        # Return only non-expired permissions
        return {
            pattern: expiry_time
            for pattern, expiry_time in self.permissions[user_id].items()
            if expiry_time > current_time
        }

    def get_expiry_time(self,
                       user_id: int,
                       pattern: Union[str, bytes, Pattern]) -> Optional[float]:
        """
        Get the expiry time for a specific user-pattern permission.

        Args:
            user_id: User identifier
            pattern: Permission pattern

        Returns:
            Expiry timestamp in seconds since epoch, or None if permission
            doesn't exist or has expired
        """
        pattern_str = self._to_str(pattern)

        if user_id not in self.permissions:
            return None

        expiry_time = self.permissions[user_id].get(pattern_str)
        if expiry_time is None or expiry_time <= time.time():
            return None

        return expiry_time

    def remaining_time(self,
                      user_id: int,
                      pattern: Union[str, bytes, Pattern]) -> Optional[float]:
        """
        Get remaining time (in seconds) for a specific permission.

        Args:
            user_id: User identifier
            pattern: Permission pattern

        Returns:
            Remaining time in seconds, or None if permission doesn't exist
            or has expired
        """
        expiry_time = self.get_expiry_time(user_id, pattern)
        if expiry_time is None:
            return None

        return max(0.0, expiry_time - time.time())

    def clear_all(self) -> None:
        """
        Clear all permissions for all users.

        This is useful for testing or complete reset of the permission system.
        """
        self.permissions.clear()

    def get_all_permissions(self) -> Dict[int, Dict[str, float]]:
        """
        Get all permissions (including expired ones).

        Returns:
            Complete permissions dictionary
        """
        # Return a deep copy to prevent external modification
        return {
            user_id: patterns.copy()
            for user_id, patterns in self.permissions.items()
        }
