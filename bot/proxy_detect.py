"""Proxy detection and configuration utilities for Windows."""

import os
import socket
import subprocess
import sys
import winreg
from typing import Optional, List, Tuple

from bot.config import get_settings


COMMON_PROXY_PORTS = [
    10809,  # clash-verge, mihomo
    10808,  # clash-verge
    7890,   # clash (HTTP)
    7891,   # clash (SOCKS5)
    2080,   # v2ray
    2081,   # v2ray
    1080,   # generic SOCKS
    8080,   # generic HTTP
    12334,  # Windows system proxy
    59654,  # EonVPN
]


def get_system_proxy() -> Tuple[Optional[str], bool]:
    """Get Windows system proxy settings from registry."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_READ,
        )
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        enabled = bool(proxy_enable)
        if enabled and proxy_server:
            # proxy_server format: "http=127.0.0.1:8080;https=127.0.0.1:8080"
            # or just "127.0.0.1:8080"
            if "=" in proxy_server:
                # Parse protocol-specific proxies
                parts = proxy_server.split(";")
                for part in parts:
                    if part.startswith("http=") or part.startswith("https="):
                        return part.split("=", 1)[1], True
            else:
                return proxy_server, True
        return None, enabled
    except Exception:
        return None, False


def get_env_proxy() -> Optional[str]:
    """Get proxy from environment variables."""
    return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


def get_listening_ports() -> List[int]:
    """Get locally listening TCP ports using netstat."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ports = set()
        for line in result.stdout.splitlines():
            if "LISTENING" in line and ("127.0.0.1" in line or "0.0.0.0" in line):
                parts = line.split()
                if len(parts) >= 2:
                    addr = parts[1]
                    if ":" in addr:
                        port_str = addr.rsplit(":", 1)[-1]
                        try:
                            ports.add(int(port_str))
                        except ValueError:
                            pass
        return sorted(ports)
    except Exception:
        return []


def test_proxy_http(host: str, port: int, timeout: int = 10) -> bool:
    """Test HTTP proxy with curl."""
    try:
        result = subprocess.run(
            [
                "curl.exe",
                "-x",
                f"http://{host}:{port}",
                "-I",
                "https://api.telegram.org",
                "--max-time",
                str(timeout),
                "-s",
                "-o",
                "nul",
                "-w",
                "%{http_code}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        return result.returncode == 0 and result.stdout.strip().startswith("2")
    except Exception:
        return False


def test_proxy_socks5(host: str, port: int, timeout: int = 10) -> bool:
    """Test SOCKS5 proxy with curl."""
    try:
        result = subprocess.run(
            [
                "curl.exe",
                "--socks5-hostname",
                f"{host}:{port}",
                "-I",
                "https://api.telegram.org",
                "--max-time",
                str(timeout),
                "-s",
                "-o",
                "nul",
                "-w",
                "%{http_code}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        return result.returncode == 0 and result.stdout.strip().startswith("2")
    except Exception:
        return False


def test_direct_connection(timeout: int = 10) -> bool:
    """Test direct connection to Telegram."""
    try:
        result = subprocess.run(
            [
                "curl.exe",
                "-I",
                "https://api.telegram.org",
                "--max-time",
                str(timeout),
                "-s",
                "-o",
                "nul",
                "-w",
                "%{http_code}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        return result.returncode == 0 and result.stdout.strip().startswith("2")
    except Exception:
        return False


def find_working_proxy() -> Optional[str]:
    """
    Find a working proxy by testing candidates.
    Returns proxy URL string (e.g., "http://127.0.0.1:7890") or None.
    """
    # 1. Check environment variable
    env_proxy = get_env_proxy()
    if env_proxy:
        print(f"[proxy] Checking env proxy: {env_proxy}")
        # Parse to get host:port
        # This is a simple check; full parsing would be more complex
        return env_proxy

    # 2. Check Windows system proxy
    sys_proxy, enabled = get_system_proxy()
    if sys_proxy and enabled:
        print(f"[proxy] Checking system proxy: {sys_proxy}")
        if test_proxy_http("127.0.0.1", 12334):
            return f"http://{sys_proxy}"

    # 3. Check listening ports for known proxy ports
    listening = get_listening_ports()
    candidate_ports = [p for p in listening if p in COMMON_PROXY_PORTS]
    candidate_ports += [p for p in COMMON_PROXY_PORTS if p not in candidate_ports]

    print(f"[proxy] Testing candidate ports: {candidate_ports}")

    for port in candidate_ports:
        # Test HTTP proxy
        if test_proxy_http("127.0.0.1", port):
            print(f"[proxy] HTTP proxy works on port {port}")
            return f"http://127.0.0.1:{port}"
        # Test SOCKS5 proxy
        if test_proxy_socks5("127.0.0.1", port):
            print(f"[proxy] SOCKS5 proxy works on port {port}")
            return f"socks5://127.0.0.1:{port}"

    # 4. Test direct connection
    if test_direct_connection():
        print("[proxy] Direct connection works")
        return ""

    print("[proxy] No working proxy found")
    return None


def apply_proxy_to_env(proxy_url: Optional[str]) -> None:
    """Apply detected proxy to environment variables for subprocesses."""
    if proxy_url:
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
        print(f"[proxy] Applied proxy to env: {proxy_url}")
    else:
        # Clear proxy env vars
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        print("[proxy] No proxy applied")


# Run detection when imported (for backward compatibility)
if __name__ != "__main__":
    detected = find_working_proxy()
    if detected is not None:
        apply_proxy_to_env(detected)