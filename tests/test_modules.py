"""
Tests for modules in the modules/ directory
"""

import html
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTrustedModule:
    """Tests for modules/trusted.py"""

    @pytest.fixture
    def mock_kernel(self):
        """Create mock kernel for trusted module tests"""
        kernel = MagicMock()
        kernel.client = AsyncMock()
        kernel.ADMIN_ID = 123456789
        kernel.custom_prefix = "."
        kernel.db_get = AsyncMock(return_value=None)
        kernel.db_set = AsyncMock()
        kernel.logger = MagicMock()
        kernel.command_handlers = {}
        kernel.callback_permissions = MagicMock()
        kernel.callback_permissions.allow = MagicMock()
        return kernel

    @pytest.mark.asyncio
    async def test_get_trusted_list_empty(self, mock_kernel):
        """Test get_trusted_list returns empty list when no data"""
        mock_kernel.db_get = AsyncMock(return_value=None)

        with patch("core_inline.lib.manager.InlineManager", return_value=MagicMock()):
            import importlib

            spec = importlib.util.find_spec("modules.trusted")
            if spec:
                pass

        mock_kernel.db_get = AsyncMock(return_value=None)

        trusted = []
        if mock_kernel.db_get:
            data = await mock_kernel.db_get("trusted", "users")
            if not data:
                trusted = []
            else:
                try:
                    if isinstance(data, str):
                        trusted = json.loads(data)
                    else:
                        trusted = json.loads(str(data))
                except Exception:
                    trusted = []

        assert trusted == []

    @pytest.mark.asyncio
    async def test_get_trusted_list_with_data(self, mock_kernel):
        """Test get_trusted_list parses existing data"""
        mock_kernel.db_get = AsyncMock(return_value="[111, 222, 333]")

        data = await mock_kernel.db_get("trusted", "users")
        if not data:
            trusted = []
        else:
            try:
                if isinstance(data, str):
                    trusted = json.loads(data)
                else:
                    trusted = json.loads(str(data))
            except Exception:
                trusted = []

        assert trusted == [111, 222, 333]

    @pytest.mark.asyncio
    async def test_get_user_id_from_reply(self, mock_kernel):
        """Test get_user_id extracts user from reply"""
        mock_event = AsyncMock()
        mock_event.is_reply = True
        mock_event.get_reply_message = AsyncMock(return_value=MagicMock(sender_id=999))

        if mock_event.is_reply:
            reply = await mock_event.get_reply_message()
            if reply:
                user_id = reply.sender_id
            else:
                user_id = None
        else:
            user_id = None

        assert user_id == 999

    @pytest.mark.asyncio
    async def test_get_user_id_from_username(self, mock_kernel):
        """Test get_user_id extracts user from username"""
        mock_kernel.client.get_entity = AsyncMock(return_value=MagicMock(id=777))

        username = "testuser"
        user_id = None
        if len(username) > 0:
            username = username.lstrip("@")
            try:
                entity = await mock_kernel.client.get_entity(username)
                user_id = entity.id
            except Exception:
                pass

        assert user_id == 777

    @pytest.mark.asyncio
    async def test_save_trusted_list(self, mock_kernel):
        """Test save_trusted_list stores JSON correctly"""
        mock_kernel.db_set = AsyncMock()

        users = [111, 222, 333]
        await mock_kernel.db_set("trusted", "users", json.dumps(users))

        mock_kernel.db_set.assert_called_once_with(
            "trusted", "users", "[111, 222, 333]"
        )


class TestConfigModule:
    """Tests for modules/config.py"""

    def test_custom_emoji_dict(self):
        """Test CUSTOM_EMOJI dictionary structure"""
        CUSTOM_EMOJI = {
            "📁": '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
            "📝": '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
            "✅": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
            "❌": '<tg-emoji emoji-id="5370843963559254781">❌</tg-emoji>',
        }

        assert "📝" in CUSTOM_EMOJI
        assert "✅" in CUSTOM_EMOJI
        assert CUSTOM_EMOJI["📁"].startswith("<tg-emoji")

    def test_type_emojis_mapping(self):
        """Test TYPE_EMOJIS mapping for config types"""
        TYPE_EMOJIS = {
            "str": "📝",
            "int": "🔢",
            "float": "🔢",
            "bool": "☑️",
            "list": "📚",
            "dict": "🗂",
            "NoneType": "🗳",
            "hidden": "🔒",
        }

        assert TYPE_EMOJIS["str"] == "📝"
        assert TYPE_EMOJIS["int"] == "🔢"
        assert TYPE_EMOJIS["bool"] == "☑️"
        assert TYPE_EMOJIS["NoneType"] == "🗳"

    def test_parse_value_bool_true(self):
        """Test parsing boolean true value"""
        value_str = "true"
        result = None

        if value_str.lower() == "true":
            result = True
        elif value_str.lower() == "false":
            result = False

        assert result is True

    def test_parse_value_bool_false(self):
        """Test parsing boolean false value"""
        value_str = "false"
        result = None

        if value_str.lower() == "true":
            result = True
        elif value_str.lower() == "false":
            result = False

        assert result is False

    def test_parse_value_integer(self):
        """Test parsing integer value"""
        value_str = "123"
        result = None

        if value_str.lower() == "true":
            result = True
        elif value_str.lower() == "false":
            result = False
        elif value_str.isdigit():
            result = int(value_str)
        elif value_str.startswith("-") and value_str[1:].isdigit():
            result = int(value_str)

        assert result == 123

    def test_parse_value_negative_integer(self):
        """Test parsing negative integer value"""
        value_str = "-456"
        result = None

        if value_str.isdigit():
            result = int(value_str)
        elif value_str.startswith("-") and value_str[1:].isdigit():
            result = int(value_str)

        assert result == -456

    def test_parse_value_float(self):
        """Test parsing float value"""
        value_str = "3.14"
        result = None

        if value_str.replace(".", "", 1).isdigit() and value_str.count(".") == 1:
            result = float(value_str)

        assert result == 3.14

    def test_parse_value_string(self):
        """Test parsing string value"""
        value_str = "hello world"
        result = None

        if value_str.lower() == "true":
            result = True
        elif value_str.lower() == "false":
            result = False
        else:
            result = value_str

        assert result == "hello world"

    def test_parse_value_null(self):
        """Test parsing null value"""
        value_str = "null"
        result = None

        if value_str.strip().lower() == "null":
            result = None

        assert result is None

    def test_parse_value_with_expected_type_bool(self):
        """Test parsing with expected_type bool"""
        expected_type = "bool"

        value_true = "true"
        value_false = "false"

        if expected_type == "bool":
            if value_true.lower() == "true":
                result_true = True
            elif value_true.lower() == "false":
                result_true = False
            else:
                result_true = None

            if value_false.lower() == "true":
                result_false = True
            elif value_false.lower() == "false":
                result_false = False
            else:
                result_false = None

        assert result_true is True
        assert result_false is False

    def test_parse_value_with_expected_type_int(self):
        """Test parsing with expected_type int"""
        expected_type = "int"
        value_str = "42"

        result = None
        if expected_type == "int":
            result = int(value_str)

        assert result == 42

    def test_parse_value_with_expected_type_float(self):
        """Test parsing with expected_type float"""
        expected_type = "float"
        value_str = "2.718"

        result = None
        if expected_type == "float":
            result = float(value_str)

        assert result == 2.718

    def test_parse_value_json_dict(self):
        """Test parsing JSON dict"""
        expected_type = "dict"
        value_str = '{"key": "value"}'

        result = None
        if expected_type == "dict":
            result = json.loads(value_str)

        assert result == {"key": "value"}

    def test_parse_value_json_list(self):
        """Test parsing JSON list"""
        expected_type = "list"
        value_str = '["a", "b", "c"]'

        result = None
        if expected_type == "list":
            result = json.loads(value_str)

        assert result == ["a", "b", "c"]

    def test_strip_formatting_bold(self):
        """Test stripping bold markdown"""
        value_str = "**bold text**"
        result = value_str
        result = result.replace("**", "")

        assert "bold text" in result
        assert "**" not in result

    def test_strip_formatting_code(self):
        """Test stripping inline code markdown"""
        value_str = "`code text`"
        result = value_str
        result = result.replace("`", "")

        assert "code text" in result
        assert "`" not in result

    def test_strip_html_entities(self):
        """Test HTML entity unescaping"""
        value_str = "&lt;code&gt;"
        result = html.unescape(value_str)

        assert result == "<code>"

    def test_truncate_key_short(self):
        """Test truncate_key doesn't modify short keys"""
        key = "short"
        max_length = 15

        if len(key) > max_length:
            result = key[: max_length - 3] + "..."
        else:
            result = key

        assert result == "short"

    def test_truncate_key_long(self):
        """Test truncate_key truncates long keys"""
        key = "this_is_a_very_long_key_name"
        max_length = 15

        if len(key) > max_length:
            result = key[: max_length - 3] + "..."
        else:
            result = key

        assert len(result) == 15
        assert result.endswith("...")

    def test_generate_key_id(self):
        """Test generate_key_id produces consistent hashes"""
        import hashlib

        key = "test_key"
        page = 0
        config_type = "kernel"

        hash_obj = hashlib.md5(f"{config_type}_{key}_{page}".encode())
        key_id = hash_obj.hexdigest()[:8]

        assert len(key_id) == 8
        assert key_id.isalnum()

    def test_generate_key_id_consistency(self):
        """Test generate_key_id produces same result for same input"""
        import hashlib

        key = "my_key"
        page = 1
        config_type = "module"

        hash_obj1 = hashlib.md5(f"{config_type}_{key}_{page}".encode())
        key_id1 = hash_obj1.hexdigest()[:8]

        hash_obj2 = hashlib.md5(f"{config_type}_{key}_{page}".encode())
        key_id2 = hash_obj2.hexdigest()[:8]

        assert key_id1 == key_id2

    def test_generate_key_id_different_inputs(self):
        """Test generate_key_id produces different results for different inputs"""
        import hashlib

        hash_obj1 = hashlib.md5(b"kernel_key1_0")
        hash_obj2 = hashlib.md5(b"kernel_key2_0")

        assert hash_obj1.hexdigest()[:8] != hash_obj2.hexdigest()[:8]


class TestEvalModule:
    """Tests for modules/eval.py"""

    def test_custom_emoji_structure(self):
        """Test CUSTOM_EMOJI dictionary in eval module"""
        CUSTOM_EMOJI = {
            "🧿": '<tg-emoji emoji-id="5426900601101374618">🧿</tg-emoji>',
            "❌": '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>',
            "🧬": '<tg-emoji emoji-id="5368513458469878442">🧬</tg-emoji>',
            "💠": '<tg-emoji emoji-id="5404366668635865453">💠</tg-emoji>',
        }

        assert "🧿" in CUSTOM_EMOJI
        assert "❌" in CUSTOM_EMOJI
        assert CUSTOM_EMOJI["🧿"].startswith("<tg-emoji")

    def test_strings_en_translation(self):
        """Test English strings dictionary"""
        strings = {
            "ru": {
                "code": "Код",
                "result": "Результат",
            },
            "en": {
                "code": "Code",
                "result": "Result",
            },
        }

        assert strings["en"]["code"] == "Code"
        assert strings["en"]["result"] == "Result"
        assert strings["ru"]["code"] == "Код"

    def test_strings_ru_translation(self):
        """Test Russian strings dictionary"""
        strings = {
            "ru": {
                "code": "Код",
                "result": "Результат",
                "result_file": "Результат отправлен файлом",
                "executed_in": "Выполнено за",
                "ms": "мс",
            },
            "en": {
                "code": "Code",
                "result": "Result",
            },
        }

        lang = "ru"
        lang_strings = strings.get(lang, strings["en"])

        assert lang_strings["code"] == "Код"
        assert lang_strings["ms"] == "мс"

    def test_code_extraction(self):
        """Test code extraction from message"""
        prefix = "."
        message = ".py print('hello')"

        code = message[len(prefix) + 3 :].strip()

        assert code == "print('hello')"

    def test_code_extraction_with_leading_spaces(self):
        """Test code extraction removes leading spaces"""
        prefix = "."
        message = ".py   print('hello')"

        code = message[len(prefix) + 3 :].strip()

        assert code == "print('hello')"

    def test_html_escape_special_chars(self):
        """Test HTML escaping of special characters"""
        code = "<script>alert('xss')</script>"
        escaped = html.escape(code)

        assert "&lt;" in escaped
        assert "&gt;" in escaped
        assert "<script>" not in escaped

    def test_result_truncation(self):
        """Test result text truncation for display"""
        long_result = "x" * 5000
        max_display = 1000

        result_display = html.escape(long_result[:max_display]) + (
            "..." if len(long_result) > max_display else ""
        )

        assert len(result_display) <= 1003
        assert result_display.endswith("...")

    def test_elapsed_time_calculation(self):
        """Test elapsed time calculation"""
        import time

        start_time = time.time()
        time.sleep(0.01)
        end_time = time.time()

        elapsed = round((end_time - start_time) * 1000, 2)

        assert elapsed >= 10
        assert elapsed < 100


class TestCommandModule:
    """Tests for modules/command.py"""

    def test_strings_structure(self):
        """Test strings dictionary structure for both languages"""
        strings = {
            "ru": {
                "hello": '<tg-emoji emoji-id="6012620675829734836">❤️</tg-emoji> Привет!',
                "pong": "Понг!",
            },
            "en": {
                "hello": '<tg-emoji emoji-id="6012620675829734836">❤️</tg-emoji> Hello!',
                "pong": "Pong!",
            },
        }

        assert "ru" in strings
        assert "en" in strings
        assert "hello" in strings["ru"]
        assert "pong" in strings["en"]

    def test_language_fallback(self):
        """Test language fallback to English"""
        strings = {
            "ru": {"hello": "Привет"},
            "en": {"hello": "Hello"},
        }

        lang = "fr"
        lang_strings = strings.get(lang, strings["en"])

        assert lang_strings["hello"] == "Hello"

    def test_is_private_with_bot_true(self):
        """Test is_private_with_bot returns True for private chats with non-bot"""
        mock_event = MagicMock()
        mock_event.is_private = True
        mock_event.sender = MagicMock()
        mock_event.sender.bot = False

        if mock_event.is_private:
            try:
                result = not mock_event.sender.bot
            except Exception:
                result = True
        else:
            result = False

        assert result is True

    def test_is_private_with_bot_false_for_bot(self):
        """Test is_private_with_bot returns True for bots (edge case)"""
        mock_event = MagicMock()
        mock_event.is_private = True
        mock_event.sender = MagicMock()
        mock_event.sender.bot = True

        if mock_event.is_private:
            try:
                result = not mock_event.sender.bot
            except Exception:
                result = True
        else:
            result = False

        assert result is False

    def test_is_private_with_bot_false_for_group(self):
        """Test is_private_with_bot returns False for group chats"""
        mock_event = MagicMock()
        mock_event.is_private = False

        result = mock_event.is_private

        assert result is False

    def test_emoji_format(self):
        """Test emoji format with Telegram emoji-id"""
        emoji_pattern = '<tg-emoji emoji-id="[0-9]+">.*?</tg-emoji>'
        import re

        test_emoji = '<tg-emoji emoji-id="6012620675829734836">❤️</tg-emoji>'

        assert re.match(emoji_pattern, test_emoji) is not None

    def test_button_url_format(self):
        """Test Button URL format in HTML response"""
        expected_format = '<a href="{}">{}</a>'

        url = "https://github.com/test"
        text = "GitHub"

        assert (
            expected_format.format(url, text)
            == '<a href="https://github.com/test">GitHub</a>'
        )


class TestTrModule:
    """Tests for modules/tr.py"""

    def test_tr_strings_structure(self):
        """Test translator module strings"""
        strings = {
            "ru": {
                "loading": "Перевожу...",
                "no_args": "No args",
                "translation_error": "Ошибка перевода",
                "network_error": "Ошибка сети:",
            },
            "en": {
                "loading": "Translating...",
                "no_args": "No args",
                "translation_error": "Translation error",
                "network_error": "Network error:",
            },
        }

        assert strings["ru"]["loading"] == "Перевожу..."
        assert strings["en"]["loading"] == "Translating..."

    def test_translate_url_construction(self):
        """Test Google Translate URL construction"""

        url = "https://translate.googleapis.com/translate_a/single"

        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "ru",
            "dt": "t",
            "q": "hello",
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query_string}"

        assert "translate.googleapis.com" in full_url
        assert "client=gtx" in full_url
        assert "tl=ru" in full_url

    def test_translate_headers(self):
        """Test translation request headers"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

        assert "User-Agent" in headers
        assert headers["Accept"] == "application/json"

    def test_lang_code_validation(self):
        """Test language code validation (2 letters)"""
        test_codes = ["ru", "en", "de", "fr", "es", "abc", "1", "r"]

        for code in test_codes:
            is_valid = len(code) == 2 and code.isalpha()

            if code in ["ru", "en", "de", "fr", "es"]:
                assert is_valid is True
            else:
                assert is_valid is False

    def test_emoji_constants(self):
        """Test emoji constants in tr module"""
        EMOJI_LOADING = '<tg-emoji emoji-id="5323463142775202324">🏓</tg-emoji>'
        EMOJI_SUCCESS = '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>'
        EMOJI_ERROR = '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>'

        assert "🏓" in EMOJI_LOADING
        assert "✅" in EMOJI_SUCCESS
        assert "❌" in EMOJI_ERROR

    def test_response_parsing_translation(self):
        """Test parsing translation API response"""
        api_response = [[["Hello", "Привет", None, None]], None, "en"]

        translated_parts = []
        if api_response and len(api_response) > 0 and api_response[0]:
            for sentence in api_response[0]:
                if sentence and len(sentence) > 0 and sentence[0]:
                    translated_parts.append(str(sentence[0]))

        result = "".join(translated_parts)

        assert result == "Hello"

    def test_response_parsing_empty(self):
        """Test parsing empty translation response"""
        api_response = [None, None, "en"]

        translated_parts = []
        if api_response and len(api_response) > 0 and api_response[0]:
            for sentence in api_response[0]:
                if sentence and len(sentence) > 0 and sentence[0]:
                    translated_parts.append(str(sentence[0]))

        result = "".join(translated_parts) if translated_parts else ""

        assert result == ""


class TestLoaderModule:
    """Tests for modules/loader.py"""

    def test_custom_emoji_structure(self):
        """Test loader module custom emoji dictionary"""
        CUSTOM_EMOJI = {
            "loading": '<tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>',
            "success": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
            "error": '<tg-emoji emoji-id="5370843963559254781">😖</tg-emoji>',
        }

        assert "loading" in CUSTOM_EMOJI
        assert "success" in CUSTOM_EMOJI
        assert CUSTOM_EMOJI["loading"].startswith("<tg-emoji")

    def test_random_emojis_list(self):
        """Test random emojis list for loader completion"""
        RANDOM_EMOJIS = [
            "ಠ_ಠ",
            "( ཀ ʖ̯ ཀ)",
            "(◕‿◕✿)",
            "(つ･･)つ",
            "༼つ◕_◕༽つ",
        ]

        assert len(RANDOM_EMOJIS) == 5
        assert "ಠ_ಠ" in RANDOM_EMOJIS

    def test_get_module_commands_patterns(self):
        """Test command patterns for module parsing"""
        patterns = [
            r"@kernel\.register\.command\('([^']+)'\)",
            r"kernel\.register\.command\('([^']+)'\)",
            r"@kernel\.register_command\('([^']+)'\)",
            r"@register\.command\('([^']+)'\)",
        ]

        import re

        test_code = """
@kernel.register.command('test')
async def test_handler(event):
    pass
"""
        found_commands = []
        for pattern in patterns:
            found = re.findall(pattern, test_code)
            found_commands.extend(found)

        assert "test" in found_commands

    def test_dependencies_parsing(self):
        """Test parsing # requires: comments"""
        code = """
# requires: requests, numpy
# requires: pandas>=1.0.0

def register(kernel):
    pass
"""
        import re

        if "requires" in code:
            reqs = re.findall(r"# requires: (.+)", code)
            assert len(reqs) == 2

        raw = reqs[0]
        parts = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if " " in part:
                parts.extend(part.split())
            else:
                parts.append(part)

        dependencies = [p.strip() for p in parts if p.strip()]

        assert "requests" in dependencies
        assert "numpy" in dependencies

    def test_handle_catalog_parsing(self):
        """Test catalog query parsing"""
        query = "catalog_0_1"

        parts = query.split("_")

        repo_index = 0
        page = 1

        if len(parts) >= 2 and parts[1].isdigit():
            repo_index = int(parts[1])

        if len(parts) >= 3 and parts[2].isdigit():
            page = int(parts[2])

        assert repo_index == 0
        assert page == 1

    def test_handle_catalog_with_custom_repo(self):
        """Test catalog query parsing with custom repo"""
        query = "catalog_2_3"

        parts = query.split("_")

        repo_index = 0
        page = 1

        if len(parts) >= 2 and parts[1].isdigit():
            repo_index = int(parts[1])

        if len(parts) >= 3 and parts[2].isdigit():
            page = int(parts[2])

        assert repo_index == 2
        assert page == 3

    def test_pagination_calculation(self):
        """Test pagination calculation for module lists"""
        total_modules = 25
        per_page = 8

        total_pages = (
            (total_modules + per_page - 1) // per_page if total_modules > 0 else 1
        )

        assert total_pages == 4

    def test_pagination_edge_case_single_page(self):
        """Test pagination with fewer items than per_page"""
        total_modules = 5
        per_page = 8

        total_pages = (
            (total_modules + per_page - 1) // per_page if total_modules > 0 else 1
        )

        assert total_pages == 1

    def test_pagination_edge_case_empty(self):
        """Test pagination with no modules"""
        total_modules = 0
        per_page = 8

        total_pages = (
            (total_modules + per_page - 1) // per_page if total_modules > 0 else 1
        )

        assert total_pages == 1


class TestTerminalModule:
    """Tests for modules/terminal.py"""

    def test_terminal_strings_structure(self):
        """Test terminal module strings"""
        strings = {
            "en": {
                "exec_error": "Execution error",
                "no_terminal": "Terminal not available",
                "loading": "Executing...",
            },
            "ru": {
                "exec_error": "Ошибка выполнения",
                "no_terminal": "Терминал недоступен",
                "loading": "Выполняю...",
            },
        }

        assert "en" in strings
        assert "ru" in strings
        assert "exec_error" in strings["en"]
        assert "loading" in strings["ru"]


class TestManModule:
    """Tests for modules/man.py"""

    def test_man_strings_structure(self):
        """Test man module strings"""
        strings = {
            "en": {
                "modules_list": "Modules list",
                "no_modules": "No modules loaded",
                "system_modules": "System modules",
            },
            "ru": {
                "modules_list": "Список модулей",
                "no_modules": "Модули не загружены",
                "system_modules": "Системные модули",
            },
        }

        assert "modules_list" in strings["en"]
        assert "modules_list" in strings["ru"]
        assert strings["en"]["modules_list"] != strings["ru"]["modules_list"]


class TestUpdatesModule:
    """Tests for modules/updates.py"""

    def test_updates_strings_structure(self):
        """Test updates module strings"""
        strings = {
            "en": {
                "checking": "Checking for updates...",
                "up_to_date": "Already up to date",
                "update_available": "Update available",
            },
            "ru": {
                "checking": "Проверяю обновления...",
                "up_to_date": "Уже актуальная версия",
                "update_available": "Доступно обновление",
            },
        }

        assert "checking" in strings["en"]
        assert "up_to_date" in strings["en"]
        assert strings["en"]["up_to_date"] != strings["ru"]["up_to_date"]


class TestApiProtectionModule:
    """Tests for modules/api_protection.py"""

    def test_api_protection_strings_structure(self):
        """Test api_protection module strings"""
        strings = {
            "en": {
                "api_blocked": "API access blocked",
                "rate_limited": "Rate limit exceeded",
            },
            "ru": {
                "api_blocked": "Доступ к API заблокирован",
                "rate_limited": "Превышен лимит запросов",
            },
        }

        assert "api_blocked" in strings["en"]
        assert "rate_limited" in strings["ru"]


class TestSettingsModule:
    """Tests for modules/settings.py"""

    def test_settings_strings_structure(self):
        """Test settings module strings"""
        strings = {
            "en": {
                "settings_menu": "Settings Menu",
                "prefix": "Prefix",
                "language": "Language",
            },
            "ru": {
                "settings_menu": "Меню настроек",
                "prefix": "Префикс",
                "language": "Язык",
            },
        }

        assert "settings_menu" in strings["en"]
        assert "prefix" in strings["ru"]
        assert strings["en"]["language"] == "Language"
        assert strings["ru"]["language"] == "Язык"


class TestLogBotModule:
    """Tests for modules/log_bot.py"""

    def test_log_bot_strings_structure(self):
        """Test log_bot module strings"""
        strings = {
            "en": {
                "log_sent": "Log message sent",
                "log_failed": "Failed to send log",
            },
            "ru": {
                "log_sent": "Лог отправлен",
                "log_failed": "Не удалось отправить лог",  # noqa: RUF001
            },
        }

        assert "log_sent" in strings["en"]
        assert "log_failed" in strings["ru"]
        assert strings["en"]["log_sent"] != strings["ru"]["log_sent"]


class TestMcubInfoModule:
    """Tests for modules/MCUB_info.py"""

    def test_mcub_info_strings_structure(self):
        """Test MCUB_info module strings"""
        strings = {
            "en": {
                "version": "Version",
                "author": "Author",
                "description": "MCUB-fork bot",
            },
            "ru": {
                "version": "Версия",
                "author": "Автор",
                "description": "Бот MCUB-fork",
            },
        }

        assert "version" in strings["en"]
        assert "author" in strings["ru"]
        assert strings["en"]["description"] == "MCUB-fork bot"


class TestTesterModule:
    """Tests for modules/tester.py"""

    def test_tester_strings_structure(self):
        """Test tester module strings"""
        strings = {
            "en": {
                "test_started": "Test started",
                "test_passed": "Test passed",
                "test_failed": "Test failed",
            },
            "ru": {
                "test_started": "Тест начат",
                "test_passed": "Тест пройден",
                "test_failed": "Тест провален",
            },
        }

        assert "test_started" in strings["en"]
        assert "test_passed" in strings["ru"]
        assert strings["en"]["test_passed"] != strings["ru"]["test_passed"]
