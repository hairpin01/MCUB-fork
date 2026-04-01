"""
Tests for utils.platform.
"""

import utils.platform as platform_utils


class TestPlatformDetector:
    def test_detect_priority_termux_before_other_virtual_platforms(self, monkeypatch):
        detector = platform_utils.PlatformDetector()
        monkeypatch.setattr(detector, "_is_termux", lambda: True)
        monkeypatch.setattr(detector, "_is_wsl", lambda: True)
        monkeypatch.setattr(detector, "_is_wsl2", lambda: True)
        monkeypatch.setattr(detector, "_is_docker", lambda: True)
        monkeypatch.setattr(detector, "_is_vds", lambda: True)
        assert detector.detect() == "termux"

    def test_get_friendly_name_mapping(self, monkeypatch):
        detector = platform_utils.PlatformDetector()
        monkeypatch.setattr(detector, "detect", lambda: "docker")
        assert detector.get_friendly_name() == "🐳 Docker Container"

    def test_is_desktop_and_virtualized(self, monkeypatch):
        detector = platform_utils.PlatformDetector()
        monkeypatch.setattr(detector, "detect", lambda: "linux")
        assert detector.is_desktop() is True
        assert detector.is_virtualized() is False


class TestPlatformShortcuts:
    def test_shortcuts_use_global_detector(self, monkeypatch):
        monkeypatch.setattr(platform_utils.detector, "detect", lambda: "docker")

        assert platform_utils.get_platform() == "docker"
        assert platform_utils.is_docker() is True
        assert platform_utils.is_wsl() is False
        assert platform_utils.is_vds() is False
        assert platform_utils.is_mobile() is False
        assert platform_utils.is_virtualized() is True

    def test_get_platform_name_from_global_detector(self, monkeypatch):
        monkeypatch.setattr(
            platform_utils.detector, "get_friendly_name", lambda: "Custom"
        )
        assert platform_utils.get_platform_name() == "Custom"
