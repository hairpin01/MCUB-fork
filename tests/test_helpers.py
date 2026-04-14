# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Tests for utils helpers
"""

import datetime
import time
from unittest.mock import MagicMock

import pytest

from utils.helpers import (
    escape_html,
    escape_quotes,
    format_date,
    format_relative_time,
    format_time,
    get_args,
    get_args_raw,
    get_chat_id,
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

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0, "0s"),
            (1, "1s"),
            (59, "59s"),
            (60, "1m"),
            (3600, "1h"),
            (86400, "1d"),
            (604800, "1w"),
            (3601, "1h 1s"),
            (90061, "1d 1h 1m 1s"),
        ],
    )
    def test_various_time_formats(self, seconds, expected):
        result = format_time(seconds, detailed=True)
        assert result == expected

    def test_edge_case_zero_seconds(self):
        assert format_time(0) == "0s"

    def test_unicode_format(self):
        result = format_time(3661, detailed=True)
        assert "h" in result
        assert "m" in result
        assert "s" in result


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

    @pytest.mark.parametrize(
        "ts,format_str,expected",
        [
            (1704067200, "%Y", "2024"),
            (1704067200, "%m", "01"),
            (1704067200, "%d", "01"),
            (1704153600, "%Y-%m-%d", "2024-01-02"),
        ],
    )
    def test_various_formats(self, ts, format_str, expected):
        result = format_date(ts, format_str)
        assert result == expected

    def test_datetime_with_microseconds(self):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0, 123456)
        result = format_date(dt)
        assert "2024" in result

    def test_future_timestamp(self):
        future_ts = int(time.time()) + 86400 * 365
        result = format_date(future_ts)
        assert len(result) > 0


class TestFormatRelativeTime:
    """Test format_relative_time function"""

    def test_just_now(self):
        result = format_relative_time(time.time())
        assert result == "just now"

    def test_minutes_ago(self):
        ts = time.time() - 300  # 5 minutes ago
        result = format_relative_time(ts)
        assert "minute" in result
        assert "ago" in result

    @pytest.mark.parametrize(
        "seconds_ago,expected_in",
        [
            (30, "just now"),
            (60, "minute"),
            (120, "minutes"),
            (3600, "hour"),
            (7200, "hours"),
            (86400, "day"),
            (172800, "days"),
            (604800, "week"),
        ],
    )
    def test_relative_time_formats(self, seconds_ago, expected_in):
        ts = time.time() - seconds_ago
        result = format_relative_time(ts)
        assert expected_in in result.lower() or "ago" in result.lower()

    def test_future_time(self):
        ts = time.time() + 3600
        result = format_relative_time(ts)
        assert len(result) > 0

    def test_ancient_timestamp(self):
        ts = 0
        result = format_relative_time(ts)
        assert len(result) > 0


class TestEscapeHtml:
    """Test escape_html function"""

    def test_basic(self):
        assert escape_html("<b>test</b>") == "&lt;b&gt;test&lt;/b&gt;"
        assert escape_html("a & b") == "a &amp; b"
        assert escape_html("a < b > c") == "a &lt; b &gt; c"

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("<", "&lt;"),
            (">", "&gt;"),
            ("&", "&amp;"),
            ('"', "&quot;"),
            ("'", "&#x27;"),
            ("<script>", "&lt;script&gt;"),
            ("<b>bold</b>", "&lt;b&gt;bold&lt;/b&gt;"),
            ("a & b < c > d", "a &amp; b &lt; c &gt; d"),
            ("", ""),
            ("plain text", "plain text"),
            ("1 < 2 > 0", "1 &lt; 2 &gt; 0"),
        ],
    )
    def test_html_escaping(self, input_str, expected):
        assert escape_html(input_str) == expected

    def test_double_escaping(self):
        text = "<b>test</b>"
        escaped = escape_html(text)
        assert "<" not in escaped
        assert "&lt;" in escaped

    def test_unicode_characters_preserved(self):
        result = escape_html("日本語テスト")
        assert "日本語テスト" in result


class TestEscapeQuotes:
    """Test escape_quotes function"""

    def test_quotes(self):
        assert escape_quotes('say "hello"') == "say &quot;hello&quot;"
        assert escape_quotes('<a href="url">') == "&lt;a href=&quot;url&quot;&gt;"

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ('"test"', "&quot;test&quot;"),
            ("'test'", "&#x27;test&#x27;"),
            (
                '"nested "quotes" inside"',
                "&quot;nested &quot;quotes&quot; inside&quot;",
            ),
            ("no quotes", "no quotes"),
            ('<a href="link">', "&lt;a href=&quot;link&quot;&gt;"),
        ],
    )
    def test_quote_escaping(self, input_str, expected):
        assert escape_quotes(input_str) == expected


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

    def test_button_with_unicode(self):
        btn = make_button("日本語", data="jp")
        assert btn is not None
        assert "日本語" in str(btn)

    def test_button_empty_text(self):
        btn = make_button("", data="empty")
        assert btn is not None

    @pytest.mark.parametrize(
        "text,data,url,switch",
        [
            ("Btn", "data", None, None),
            ("Link", None, "https://x.com", None),
            ("Search", None, None, "query"),
            ("Emoji 🎉", "emoji", None, None),
        ],
    )
    def test_button_various_types(self, text, data, url, switch):
        btn = make_button(text, data=data, url=url, switch=switch)
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

    def test_single_button(self):
        buttons = [{"text": "A", "data": "a"}]
        result = make_buttons(buttons)
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_two_buttons_one_row(self):
        buttons = [{"text": "A", "data": "a"}, {"text": "B", "data": "b"}]
        result = make_buttons(buttons, cols=2)
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_large_number_of_buttons(self):
        buttons = [{"text": f"B{i}", "data": f"b{i}"} for i in range(10)]
        result = make_buttons(buttons, cols=3)
        assert len(result) == 4  # ceil(10/3)

    @pytest.mark.parametrize(
        "cols,expected_rows",
        [
            (1, 3),
            (2, 2),
            (3, 1),
            (4, 1),
        ],
    )
    def test_various_column_counts(self, cols, expected_rows):
        buttons = [
            {"text": "A", "data": "a"},
            {"text": "B", "data": "b"},
            {"text": "C", "data": "c"},
        ]
        result = make_buttons(buttons, cols=cols)
        assert len(result) == expected_rows


class TestGetArgs:
    """Test get_args and related functions"""

    def test_get_args_basic(self):
        msg = MagicMock()
        msg.text = ".test arg1 arg2"
        msg.raw_text = ".test arg1 arg2"

        result = get_args(msg)
        assert "arg1" in result

    def test_get_args_raw(self):
        msg = MagicMock()
        msg.text = ".test some random text"
        msg.raw_text = ".test some random text"

        result = get_args_raw(msg)
        assert "some" in result

    def test_get_args_single_arg(self):
        msg = MagicMock()
        msg.text = ".cmd single"
        msg.raw_text = ".cmd single"

        result = get_args(msg)
        assert "single" in result

    def test_get_args_no_args(self):
        msg = MagicMock()
        msg.text = ".cmd"
        msg.raw_text = ".cmd"

        result = get_args(msg)
        assert len(result) == 0

    def test_get_args_with_quotes(self):
        msg = MagicMock()
        msg.text = '.cmd "arg with spaces"'
        msg.raw_text = '.cmd "arg with spaces"'

        result = get_args(msg)
        assert len(result) >= 1

    def test_get_args_raw_preserves_whitespace(self):
        msg = MagicMock()
        msg.text = ".cmd   spaced   out"
        msg.raw_text = ".cmd   spaced   out"

        result = get_args_raw(msg)
        assert "spaced" in result


class TestGetChatId:
    """Test get_chat_id"""

    def test_positive_chat_id(self):
        event = MagicMock()
        event.chat_id = 123456789

        assert get_chat_id(event) == 123456789

    def test_negative_channel_id(self):
        event = MagicMock()
        event.chat_id = -1001234567890

        assert get_chat_id(event) == -1001234567890

    def test_chat_id_zero(self):
        event = MagicMock()
        event.chat_id = 0

        assert get_chat_id(event) == 0

    def test_chat_id_large_negative(self):
        event = MagicMock()
        event.chat_id = -9999999999999

        assert get_chat_id(event) == -9999999999999
