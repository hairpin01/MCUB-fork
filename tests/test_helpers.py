"""
Tests for utils helpers
"""

import pytest
import datetime
from utils.helpers import (
    format_time,
    format_date,
    format_relative_time,
    escape_html,
    escape_quotes,
    make_button,
    make_buttons,
)


class TestFormatTime:
    """Test format_time function"""

    def test_seconds_only(self):
        assert format_time(30) == "30s"
        assert format_time(59) == "59s"

    def test_minutes(self):
        assert format_time(60) == "1m"
        assert format_time(90) == "1m 30s"
        assert format_time(120) == "2m"

    def test_hours(self):
        assert format_time(3600) == "1h"
        assert format_time(3660) == "1h 1m"
        assert format_time(7200) == "2h"
        assert format_time(7320) == "2h 2m"

    def test_detailed(self):
        assert format_time(30, detailed=True) == "30s"
        assert format_time(3661, detailed=True) == "1h 1m 1s"
        assert format_time(604800, detailed=True) == "1w"


class TestFormatDate:
    """Test format_date function"""

    def test_timestamp(self):
        ts = 1704067200  # 2024-01-01 00:00:00
        result = format_date(ts)
        assert "2024" in result
        assert "01" in result

    def test_datetime_object(self):
        dt = datetime.datetime(2024, 6, 15, 12, 30, 0)
        result = format_date(dt)
        assert "2024" in result
        assert "15" in result

    def test_custom_format(self):
        ts = 1704067200
        result = format_date(ts, "%d.%m.%Y")
        assert result == "01.01.2024"


class TestFormatRelativeTime:
    """Test format_relative_time function"""

    def test_just_now(self):
        import time
        result = format_relative_time(time.time())
        assert result == "just now"

    def test_minutes_ago(self):
        import time
        ts = time.time() - 300  # 5 minutes ago
        result = format_relative_time(ts)
        assert "minute" in result
        assert "ago" in result


class TestEscapeHtml:
    """Test escape_html function"""

    def test_basic(self):
        assert escape_html("<b>test</b>") == "&lt;b&gt;test&lt;/b&gt;"
        assert escape_html("a & b") == "a &amp; b"
        assert escape_html('a < b > c') == "a &lt; b &gt; c"


class TestEscapeQuotes:
    """Test escape_quotes function"""

    def test_quotes(self):
        assert escape_quotes('say "hello"') == "say &quot;hello&quot;"
        assert escape_quotes("<a href=\"url\">") == "&lt;a href=&quot;url&quot;&gt;"


class TestMakeButton:
    """Test make_button function"""

    def test_callback_button(self):
        btn = make_button("Click", data="test")
        assert btn is not None
        assert "Click" in str(btn)

    def test_url_button(self):
        btn = make_button("Link", url="https://example.com")
        assert btn is not None

    def test_switch_button(self):
        btn = make_button("Search", switch="query")
        assert btn is not None


class TestMakeButtons:
    """Test make_buttons function"""

    def test_flat_list_default_cols(self):
        buttons = [
            {"text": "A", "data": "a"},
            {"text": "B", "data": "b"},
            {"text": "C", "data": "c"},
        ]
        result = make_buttons(buttons)
        assert len(result) == 2  # 3 items / 2 = 2 rows
        assert len(result[0]) == 2
        assert len(result[1]) == 1

    def test_flat_list_custom_cols(self):
        buttons = [
            {"text": "A", "data": "a"},
            {"text": "B", "data": "b"},
            {"text": "C", "data": "c"},
        ]
        result = make_buttons(buttons, cols=3)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_grouped_list(self):
        buttons = [
            [{"text": "A", "data": "a"}],
            [{"text": "B", "data": "b"}, {"text": "C", "data": "c"}],
        ]
        result = make_buttons(buttons)
        assert len(result) == 2
        assert len(result[0]) == 1
        assert len(result[1]) == 2

    def test_empty_list(self):
        assert make_buttons([]) == []


class TestGetArgs:
    """Test get_args and related functions"""

    def test_get_args_basic(self):
        from utils.helpers import get_args
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.text = ".test arg1 arg2"
        msg.raw_text = ".test arg1 arg2"

        result = get_args(msg)
        assert result == ["arg1", "arg2"]

    def test_get_args_raw(self):
        from utils.helpers import get_args_raw
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.text = ".test some random text"
        msg.raw_text = ".test some random text"

        result = get_args_raw(msg)
        assert result == "some random text"


class TestGetChatId:
    """Test get_chat_id"""

    def test_positive_chat_id(self):
        from utils.helpers import get_chat_id
        from unittest.mock import MagicMock

        event = MagicMock()
        event.chat_id = 123456789

        assert get_chat_id(event) == 123456789

    def test_negative_channel_id(self):
        from utils.helpers import get_chat_id
        from unittest.mock import MagicMock

        event = MagicMock()
        event.chat_id = -1001234567890

        assert get_chat_id(event) == -1001234567890
