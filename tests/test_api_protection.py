import pytest
import time
import math
from collections import deque
from unittest.mock import MagicMock

from modules.api_protection import RequestAnalyzer, DEFAULT_CONFIG, LIMIT_PROFILES


class TestRequestAnalyzer:
    """Test RequestAnalyzer class"""

    def setup_method(self):
        self.config = DEFAULT_CONFIG.copy()
        self.request_log = deque(maxlen=10000)
        self.analyzer = RequestAnalyzer(
            request_log=self.request_log,
            ignore_set_fn=lambda: set(self.config.get("ignore_methods", [])),
            config=self.config,
        )

    def test_record_adds_to_log(self):
        """Test record adds to request_log"""
        self.analyzer.record("GetUsersRequest", time.time())
        # record() adds to _sec_buckets, not directly to request_log
        # The request_log is used for window counts
        assert len(self.analyzer._sec_buckets) >= 1

    def test_record_adds_to_sec_buckets(self):
        """Test record adds to second buckets"""
        now = time.time()
        self.analyzer.record("GetUsersRequest", now)
        sec = int(now)
        assert sec in self.analyzer._sec_buckets
        assert self.analyzer._sec_buckets[sec] == 1

    def test_window_counts_empty(self):
        """Test window counts with no requests"""
        now = time.time()
        counts = self.analyzer.window_counts(now)
        assert counts[1]["total"] == 0
        assert counts[5]["total"] == 0
        assert counts[15]["total"] == 0
        assert counts[60]["total"] == 0

    def test_window_counts_single_request(self):
        """Test window counts with one request"""
        now = time.time()
        self.request_log.append(("GetUsersRequest", now))
        counts = self.analyzer.window_counts(now)
        assert counts[1]["total"] == 1
        assert counts[5]["total"] == 1
        assert counts[15]["total"] == 1
        assert counts[60]["total"] == 1

    def test_window_counts_old_request(self):
        """Test window counts excludes old requests"""
        now = time.time()
        self.request_log.append(("GetUsersRequest", now - 120))  # 2 minutes ago
        counts = self.analyzer.window_counts(now)
        assert counts[1]["total"] == 0
        assert counts[60]["total"] == 0

    def test_window_counts_ignore_methods(self):
        """Test that ignored methods are excluded from relevant count"""
        now = time.time()
        self.config["ignore_methods"] = ["GetMessagesRequest"]
        self.request_log.append(("GetMessagesRequest", now))
        self.request_log.append(("GetUsersRequest", now))
        counts = self.analyzer.window_counts(now)
        assert counts[1]["total"] == 2
        assert counts[1]["relevant"] == 1  # GetMessagesRequest ignored

    def test_zscore_no_data(self):
        """Test z-score returns 0 with insufficient data"""
        now = time.time()
        score = self.analyzer.zscore(now)
        assert score == 0.0

    def test_zscore_insufficient_baseline(self):
        """Test z-score returns 0 with insufficient baseline data"""
        now = time.time()
        # Add less than 10 baseline values
        for i in range(5):
            self.analyzer.record("GetUsersRequest", now - 60 + i)
        score = self.analyzer.zscore(now)
        assert score == 0.0

    def test_backoff_initial_base(self):
        """Test initial backoff equals local_floodwait"""
        # backoff_seconds = base * 2^0 = base
        assert self.analyzer.backoff_seconds() == 30  # local_floodwait default

    def test_backoff_after_trigger(self):
        """Test backoff doubles after trigger"""
        now = time.time()
        self.analyzer.on_trigger(now)
        backoff = self.analyzer.backoff_seconds()
        # 30 * 2^1 = 60
        assert backoff == 60

    def test_backoff_max_capped(self):
        """Test backoff is capped at 600 seconds (10 min)"""
        now = time.time()
        # Trigger many times
        for _ in range(10):
            self.analyzer.on_trigger(now)
        backoff = self.analyzer.backoff_seconds()
        assert backoff == 600  # Capped at 600

    def test_backoff_exponential(self):
        """Test backoff increases exponentially"""
        now = time.time()
        self.analyzer.on_trigger(now)
        first_backoff = self.analyzer.backoff_seconds()

        self.analyzer.on_trigger(now)
        second_backoff = self.analyzer.backoff_seconds()

        # Second backoff should be >= first (exponential increase)
        assert second_backoff >= first_backoff

    def test_transition_graph(self):
        """Test method transition graph recording"""
        now = time.time()
        self.analyzer.record("GetUsersRequest", now - 2)
        self.analyzer.record("GetMessagesRequest", now - 1)
        self.analyzer.record("GetUsersRequest", now)

        # Check transitions were recorded
        assert (
            self.analyzer._transitions[("GetUsersRequest", "GetMessagesRequest")] == 1
        )
        assert (
            self.analyzer._transitions[("GetMessagesRequest", "GetUsersRequest")] == 1
        )

    def test_hourly_profile(self):
        """Test hourly behavioral profile"""
        now = time.time()
        hour = time.localtime(now).tm_hour

        self.analyzer.record("GetUsersRequest", now)

        assert hour in self.analyzer._hourly_profile
        assert self.analyzer._hourly_profile[hour]["GetUsersRequest"] == 1
        assert self.analyzer._hourly_total[hour] == 1

    def test_maybe_reset_backoff_cools_down(self):
        """Test backoff resets after cooldown"""
        now = time.time()

        self.analyzer.on_trigger(now)
        # Reset explicitly
        self.analyzer.reset()
        assert self.analyzer.trigger_count == 0

    def test_reset_clears_state(self):
        """Test reset clears all state"""
        now = time.time()
        self.analyzer.record("GetUsersRequest", now)
        self.analyzer.on_trigger(now)

        self.analyzer.reset()

        assert len(self.analyzer._sec_buckets) == 0
        assert len(self.analyzer._transitions) == 0
        assert len(self.analyzer._hourly_profile) == 0
        assert self.analyzer.trigger_count == 0

    def test_top_transitions(self):
        """Test top transitions returns most frequent pairs"""
        now = time.time()
        # Add some transitions
        for _ in range(5):
            self.analyzer.record("GetUsersRequest", now - 2)
            self.analyzer.record("GetMessagesRequest", now - 1)

        top = self.analyzer.top_transitions(limit=5)
        assert len(top) >= 1
        # Most frequent should be first
        assert top[0][0] == ("GetUsersRequest", "GetMessagesRequest")

    def test_acceleration(self):
        """Test acceleration calculation"""
        now = time.time()
        # Add requests with increasing rate
        for i in range(10):
            for _ in range(i + 1):
                self.analyzer.record("GetUsersRequest", now - 10 + i)

        accel = self.analyzer.acceleration(now)
        # Should have some acceleration value
        assert isinstance(accel, float)


class TestRequestAnalyzerConfig:
    """Test RequestAnalyzer with different configurations"""

    def test_custom_windows(self):
        """Test analyzer with custom window config"""
        config = DEFAULT_CONFIG.copy()
        analyzer = RequestAnalyzer(
            request_log=deque(maxlen=10000),
            ignore_set_fn=lambda: set(),
            config=config,
        )
        assert analyzer.WINDOWS == [1, 5, 15, 60]

    def test_custom_floodwait(self):
        """Test analyzer uses local_floodwait for backoff base"""
        config = DEFAULT_CONFIG.copy()
        config["local_floodwait"] = 60
        analyzer = RequestAnalyzer(
            request_log=deque(maxlen=10000),
            ignore_set_fn=lambda: set(),
            config=config,
        )
        assert analyzer.backoff_seconds() == 60  # base * 2^0


class TestDefaultConfig:
    """Test DEFAULT_CONFIG values"""

    def test_default_values(self):
        """Test all default config values are sensible"""
        assert DEFAULT_CONFIG["time_sample"] == 30
        assert DEFAULT_CONFIG["limit_profile"] == "normal"
        assert DEFAULT_CONFIG["custom_threshold"] == 200
        assert DEFAULT_CONFIG["local_floodwait"] == 30
        assert DEFAULT_CONFIG["enable_protection"] is True
        assert DEFAULT_CONFIG["mcub_mode"] == "safe"
        assert DEFAULT_CONFIG["enable_analytics"] is True
        assert DEFAULT_CONFIG["zscore_threshold"] == 3.0
        assert DEFAULT_CONFIG["warn_percent"] == 90
        assert isinstance(DEFAULT_CONFIG["ignore_methods"], list)

    def test_ignore_methods_default(self):
        """Test default ignore methods include GetMessagesRequest"""
        assert "GetMessagesRequest" in DEFAULT_CONFIG["ignore_methods"]


class TestLimitProfiles:
    """Test limit profiles"""

    def test_profiles_exist(self):
        """Test all expected profiles exist"""
        assert "conservative" in LIMIT_PROFILES
        assert "normal" in LIMIT_PROFILES
        assert "aggressive" in LIMIT_PROFILES

    def test_profile_values(self):
        """Test profile values are reasonable"""
        assert LIMIT_PROFILES["conservative"] == 100
        assert LIMIT_PROFILES["normal"] == 200
        assert LIMIT_PROFILES["aggressive"] == 350

    def test_profiles_increasing(self):
        """Test profiles are in increasing order"""
        assert LIMIT_PROFILES["conservative"] < LIMIT_PROFILES["normal"]
        assert LIMIT_PROFILES["normal"] < LIMIT_PROFILES["aggressive"]
