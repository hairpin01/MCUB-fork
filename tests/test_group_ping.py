import pytest

from core.lib.loader.security import SecurityChats
from core.modules.security_module import SecurityModule


@pytest.mark.parametrize('spelling', ['ping', 'userbot:ping', 'command:userbot:ping'])
def test_group_grant_spelling(spelling):
    assert SecurityModule._grant_rule([spelling], legacy=True) == {
        'type': 'command', 'target': 'userbot:ping', 'allow': 'all',
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('stored', ['ping', 'userbot:ping'])
async def test_group_ping_access(stored):
    security = SecurityChats()
    await security._ensure_cache_loaded()
    rule = {'type': 'command', 'target': stored, 'allow': 'all'}
    security._groups_cache = {'ping': {'users': [42], 'permissions': [rule]}}
    assert await security.is_allow('command', 'userbot:ping', 42)
    assert not await security.is_allow('command', 'userbot:ping', 43)
    for target in ('inline:ping', 'bot:ping', 'guest:ping', 'userbot:other'):
        assert not await security.is_allow('command', target, 42)
    rule['allow'] = 'chat'
    assert await security.is_allow('command', 'userbot:ping', 42, 'group')
    assert not await security.is_allow('command', 'userbot:ping', 42, 'private')
    rule['temp'] = 1
    assert not await security.is_allow('command', 'userbot:ping', 42, 'group')
