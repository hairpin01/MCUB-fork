# Backward compatibility shim - re-exports from core/kernel/
from core.kernel.standard import Kernel

# Re-export exceptions etc. if needed
try:
    from core.kernel.standard import CommandConflictError
except ImportError:
    pass

__all__ = ["Kernel"]
