"""
Tests for module loader
"""

import pytest
from unittest.mock import MagicMock


class TestModuleLoading:
    """Test module loading functionality"""

    def test_module_loader_init(self):
        """Test ModuleLoader can be instantiated"""
        from core.lib.loader.loader import ModuleLoader
        
        kernel = MagicMock()
        loader = ModuleLoader(kernel)
        
        assert loader is not None
