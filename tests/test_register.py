"""
Tests for Register class
"""

import pytest
from unittest.mock import MagicMock


class TestRegisterClass:
    """Test Register functionality"""

    def test_register_initialization(self):
        """Test Register initialization"""
        kernel = MagicMock()
        from core.lib.loader.register import Register
        
        register = Register(kernel)
        assert register is not None
        assert register.kernel is kernel
