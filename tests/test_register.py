"""
Tests for Register class and command/event registration
"""
import pytest
from unittest.mock import Mock, patch
from telethon import events

class TestRegisterClass:
    """Test Register functionality"""
    
    def test_register_initialization(self, kernel_instance):
        """Test Register instance creation"""
        from kernel import Register
        register = Register(kernel_instance)
        assert register.kernel == kernel_instance
        
    def test_method_decorator(self):
        """Test @Register.method decorator"""
        from kernel import Register
        kernel_mock = Mock()
        register = Register(kernel_mock)
        
        @register.method
        def test_function():
            return "test"
            
        # Check that module gets register attribute
        import sys
        module = sys.modules[__name__]
        assert hasattr(module, 'register')
        assert callable(getattr(module.register, 'method', None))
        
    def test_command_registration(self, kernel_instance):
        """Test command registration via decorator"""
        from kernel import Register
        register = Register(kernel_instance)
        
        # Setup current loading module
        kernel_instance.current_loading_module = 'test_module'
        
        @register.command('testcmd')
        async def test_handler(event):
            await event.edit("Test")
            
        assert 'testcmd' in kernel_instance.command_handlers
        assert kernel_instance.command_owners['testcmd'] == 'test_module'
        
    def test_command_with_alias(self, kernel_instance):
        """Test command with aliases"""
        from kernel import Register
        register = Register(kernel_instance)
        kernel_instance.current_loading_module = 'test_module'
        
        @register.command('command', alias=['cmd', 'c'])
        async def test_handler(event):
            await event.edit("Alias test")
            
        assert 'command' in kernel_instance.command_handlers
        assert kernel_instance.aliases['cmd'] == 'command'
        assert kernel_instance.aliases['c'] == 'command'
        
    def test_bot_command_registration(self, kernel_instance):
        """Test bot command registration"""
        from kernel import Register
        register = Register(kernel_instance)
        kernel_instance.current_loading_module = 'test_module'
        
        @register.bot_command('start')
        async def start_handler(event):
            await event.respond("Started!")
            
        assert 'start' in kernel_instance.bot_command_handlers
        assert kernel_instance.bot_command_owners['start'] == 'test_module'
        
    def test_event_registration(self, kernel_instance):
        """Test event handler registration"""
        from kernel import Register
        register = Register(kernel_instance)
        
        event_called = []
        
        @register.event('newmessage', pattern='hello')
        async def message_handler(event):
            event_called.append(event)
            
        # Check that event was registered on client
        assert kernel_instance.client.add_event_handler.called
        
    def test_callback_permission_manager(self):
        """Test callback permission system"""
        from kernel import CallbackPermissionManager
        
        perm_mgr = CallbackPermissionManager()
        
        # Grant permission
        perm_mgr.allow(123456, 'menu_', duration_seconds=60)
        
        # Check permission
        assert perm_mgr.is_allowed(123456, 'menu_page_1') is True
        assert perm_mgr.is_allowed(123456, 'menu_page_2') is True
        assert perm_mgr.is_allowed(999999, 'menu_page_1') is False
        
        # Revoke permission
        perm_mgr.prohibit(123456, 'menu_')
        assert perm_mgr.is_allowed(123456, 'menu_page_1') is False

class TestCommandConflict:
    """Test command conflict handling"""
    
    def test_command_conflict_error(self, kernel_instance):
        """Test conflict detection"""
        from kernel import Register, CommandConflictError
        register = Register(kernel_instance)
        
        kernel_instance.current_loading_module = 'module1'
        
        @register.command('conflict')
        async def handler1(event):
            pass
            
        # Try to register same command from different module
        kernel_instance.current_loading_module = 'module2'
        
        with pytest.raises(CommandConflictError) as exc_info:
            @register.command('conflict')
            async def handler2(event):
                pass
                
        assert 'conflict' in str(exc_info.value)
        assert exc_info.value.conflict_type in ['user', 'system']
