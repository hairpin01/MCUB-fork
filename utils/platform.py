# author: @Hairpin00
# description: Platform detection utility
# version: 1.0.0

import os
import sys
import platform
import subprocess
from pathlib import Path

class PlatformDetector:
    """Detects the platform where the userbot is running"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.machine = platform.machine().lower()
        self.platform = platform.platform().lower()
        
    def detect(self):
        """
        Detects the current platform
        
        Returns:
            str: Platform name (termux, wsl, vds, macos, windows, linux, unknown)
        """
        # Check for Termux
        if self._is_termux():
            return "termux"
        
        # Check for WSL (Windows Subsystem for Linux)
        if self._is_wsl():
            return "wsl"
        
        # Check for WSL2
        if self._is_wsl2():
            return "wsl2"
        
        # Check for Docker
        if self._is_docker():
            return "docker"
        
        # Check for VDS/VPS (usually Linux without GUI)
        if self._is_vds():
            return "vds"
        
        # Check for macOS
        if self.system == "darwin":
            return "macos"
        
        # Check for Windows
        if self.system == "windows":
            return "windows"
        
        # Check for regular Linux
        if self.system == "linux":
            return "linux"
        
        return "unknown"
    
    def _is_termux(self):
        """Checks if running in Termux"""
        # Method 1: Check Termux environment variables
        if "TERMUX_VERSION" in os.environ:
            return True
        
        # Method 2: Check Termux paths
        termux_paths = [
            "/data/data/com.termux/files/usr",
            "/data/data/com.termux",
            "/usr/bin/termux-info"
        ]
        
        for path in termux_paths:
            if os.path.exists(path):
                return True
        
        # Method 3: Check via which termux-info
        try:
            result = subprocess.run(
                ["which", "termux-info"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return True
        except:
            pass
        
        return False
    
    def _is_wsl(self):
        """Checks if running in WSL (Windows Subsystem for Linux)"""
        # Method 1: Check kernel version
        try:
            with open("/proc/version", "r") as f:
                version_info = f.read().lower()
                if "microsoft" in version_info or "wsl" in version_info:
                    return True
        except:
            pass
        
        # Method 2: Check release info
        try:
            with open("/proc/sys/kernel/osrelease", "r") as f:
                osrelease = f.read().lower()
                if "microsoft" in osrelease or "wsl" in osrelease:
                    return True
        except:
            pass
        
        # Method 3: Check environment variables
        if "WSL_DISTRO_NAME" in os.environ or "WSL_INTEROP" in os.environ:
            return True
        
        return False
    
    def _is_wsl2(self):
        """Checks if running in WSL2"""
        if not self._is_wsl():
            return False
        
        # WSL2 has /dev/pts directory with specific features
        try:
            # Check WSL version
            with open("/proc/version", "r") as f:
                version_info = f.read().lower()
                if "wsl2" in version_info:
                    return True
                
            # Check for WSL2 specific files
            wsl2_files = [
                "/dev/lxss",
                "/mnt/wsl"
            ]
            
            for file in wsl2_files:
                if os.path.exists(file):
                    return True
        except:
            pass
        
        return False
    
    def _is_docker(self):
        """Checks if running in Docker container"""
        # Method 1: Check /.dockerenv
        if os.path.exists("/.dockerenv"):
            return True
        
        # Method 2: Check cgroup
        try:
            with open("/proc/1/cgroup", "r") as f:
                cgroup_info = f.read().lower()
                if "docker" in cgroup_info or "lxc" in cgroup_info:
                    return True
        except:
            pass
        
        # Method 3: Check process name
        try:
            with open("/proc/self/cgroup", "r") as f:
                content = f.read().lower()
                if "docker" in content:
                    return True
        except:
            pass
        
        return False
    
    def _is_vds(self):
        """
        Checks if running on VDS/VPS server
        
        VDS indicators:
        1. Linux system
        2. No GUI environment
        3. No terminal applications
        4. Usually accessible only via SSH
        """
        if self.system != "linux":
            return False
        
        # Check for DISPLAY (graphical environment)
        if "DISPLAY" in os.environ:
            return False
        
        # Check for X11
        x11_paths = [
            "/usr/bin/X11",
            "/usr/bin/X",
            "/usr/lib/xorg"
        ]
        
        for path in x11_paths:
            if os.path.exists(path):
                return False
        
        # Check for sshd process (server usually accessible via SSH)
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if "sshd" in result.stdout.lower():
                return True
        except:
            pass
        
        # Additional VDS indicators
        vds_indicators = [
            # No user home directory like on desktop
            not os.path.exists("/home/user"),
            # Common VPS provider indicators
            any(keyword in self.platform for keyword in ["cloud", "vps", "vds", "aws", "digitalocean", "linode"]),
            # Check hostname (often contains provider names)
            any(provider in platform.node().lower() for provider in ["vps", "cloud", "server", "node"])
        ]
        
        return any(vds_indicators)
    
    def get_detailed_info(self):
        """
        Returns detailed platform information
        
        Returns:
            dict: Detailed system information
        """
        info = {
            "platform": self.detect(),
            "system": self.system,
            "machine": self.machine,
            "platform_string": self.platform,
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "processor": platform.processor(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.architecture()[0],
            "is_64bit": sys.maxsize > 2**32,
            "env_vars": {
                "termux": "TERMUX_VERSION" in os.environ,
                "wsl": "WSL_DISTRO_NAME" in os.environ,
                "docker": self._is_docker(),
                "display": "DISPLAY" in os.environ,
                "wayland": "WAYLAND_DISPLAY" in os.environ
            }
        }
        
        return info
    
    def get_friendly_name(self):
        """
        Returns human-readable platform name
        
        Returns:
            str: Human-readable platform name
        """
        platform_name = self.detect()
        
        names = {
            "termux": "📱 Termux (Android)",
            "wsl": "🪟 Windows Subsystem for Linux",
            "wsl2": "🪟 Windows Subsystem for Linux 2",
            "docker": "🐳 Docker Container",
            "vds": "🖥️ VDS/VPS Server",
            "macos": "🍎 macOS",
            "windows": "🪟 Windows",
            "linux": "🐧 Linux Desktop",
            "unknown": "❓ Unknown Platform"
        }
        
        return names.get(platform_name, "❓ Unknown Platform")
    
    def is_mobile(self):
        """Checks if platform is mobile"""
        return self.detect() == "termux"
    
    def is_virtualized(self):
        """Checks if platform is virtualized"""
        virtual_platforms = ["termux", "wsl", "wsl2", "docker", "vds"]
        return self.detect() in virtual_platforms
    
    def is_desktop(self):
        """Checks if platform is desktop"""
        desktop_platforms = ["macos", "windows", "linux"]
        return self.detect() in desktop_platforms


# Create global instance for easy import
detector = PlatformDetector()

# Short functions for quick access
def get_platform():
    """Returns platform name"""
    return detector.detect()

def get_platform_info():
    """Returns detailed platform information"""
    return detector.get_detailed_info()

def get_platform_name():
    """Returns human-readable platform name"""
    return detector.get_friendly_name()

def is_termux():
    """Checks if running in Termux"""
    return get_platform() == "termux"

def is_wsl():
    """Checks if running in WSL"""
    platform = get_platform()
    return platform in ["wsl", "wsl2"]

def is_vds():
    """Checks if running on VDS"""
    return get_platform() == "vds"

def is_docker():
    """Checks if running in Docker"""
    return get_platform() == "docker"

def is_mobile():
    """Checks if platform is mobile"""
    return detector.is_mobile()

def is_desktop():
    """Checks if platform is desktop"""
    return detector.is_desktop()

def is_virtualized():
    """Checks if platform is virtualized"""
    return detector.is_virtualized()


# Example usage (if running file directly)
if __name__ == "__main__":
    print(f"Platform: {get_platform()}")
    print(f"Friendly Name: {get_platform_name()}")
    print(f"Detailed Info:")
    for key, value in get_platform_info().items():
        print(f"  {key}: {value}")
