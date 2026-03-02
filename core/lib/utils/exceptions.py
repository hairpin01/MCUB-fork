# author: @Hairpin00
# version: 1.0.1
# description: Custom exceptions for kernel

class CommandConflictError(Exception):
    """Исключение для конфликта команд"""

    def __init__(self, message, conflict_type=None, command=None):
        super().__init__(message)
        self.conflict_type = conflict_type
        self.command = command

class McubTelethonError(Exception):
        pass
