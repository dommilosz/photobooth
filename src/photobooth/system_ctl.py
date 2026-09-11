"""Host system helpers for Settings → System (IP, Wi-Fi, power)."""

from __future__ import annotations

import logging
import platform
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    signal: int
    security: str
    active: bool


@dataclass(frozen=True)
class NetworkStatus:
    hostname: str
    ipv4: list[str]
    wifi_ssid: str | None
    wifi_device: str | None
    wifi_available: bool
    detail: str = ""


def _run(cmd: list[str], timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _has_nmcli() -> bool:
    return shutil.which("nmcli") is not None


def hostname() -> str:
    try:
        return socket.gethostname() or "—"
    except OSError:
        return "—"


def ipv4_addresses() -> list[str]:
    addrs: list[str] = []
    try:
        proc = _run(["hostname", "-I"], timeout=3)
        if proc.returncode == 0 and proc.stdout.strip():
            for part in proc.stdout.split():
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", part) and not part.startswith("127."):
                    if part not in addrs:
                        addrs.append(part)
    except (OSError, subprocess.TimeoutExpired):
        pass

    if addrs:
        return addrs

    try:
        proc = _run(["ip", "-4", "-o", "addr", "show", "scope", "global"], timeout=3)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m and m.group(1) not in addrs:
                    addrs.append(m.group(1))
    except (OSError, subprocess.TimeoutExpired):
        pass

    if addrs:
        return addrs

    # Fallback: UDP trick (no packets sent) — may fail offline.
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return [ip]
    except OSError:
        pass
    return []


def wifi_status() -> tuple[str | None, str | None]:
    """Return (ssid, device) if connected."""
    if not _has_nmcli():
        return None, None
    try:
        proc = _run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
            timeout=5,
        )
        if proc.returncode != 0:
            return None, None
        for line in proc.stdout.splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            device, dtype, state, connection = parts[0], parts[1], parts[2], parts[3]
            if dtype == "wifi" and state == "connected" and connection and connection != "--":
                return connection, device
    except (OSError, subprocess.TimeoutExpired):
        log.exception("wifi_status failed")
    return None, None


def network_status() -> NetworkStatus:
    ssid, device = wifi_status()
    available = _has_nmcli()
    detail = ""
    if not available:
        if platform.system() == "Windows":
            detail = "Wi-Fi control needs nmcli (Raspberry Pi / NetworkManager)."
        else:
            detail = "NetworkManager (nmcli) not found."
    return NetworkStatus(
        hostname=hostname(),
        ipv4=ipv4_addresses(),
        wifi_ssid=ssid,
        wifi_device=device,
        wifi_available=available,
        detail=detail,
    )


def scan_wifi() -> list[WifiNetwork]:
    if not _has_nmcli():
        raise RuntimeError("nmcli not available")
    proc = _run(
        ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
        timeout=30,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "scan failed").strip()
        raise RuntimeError(err)
    seen: dict[str, WifiNetwork] = {}
    for line in proc.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        active_raw, ssid, signal_raw, security = parts[0], parts[1], parts[2], parts[3]
        ssid = ssid.strip()
        if not ssid:
            continue
        try:
            signal = int(signal_raw)
        except ValueError:
            signal = 0
        net = WifiNetwork(
            ssid=ssid,
            signal=signal,
            security=security or "—",
            active=active_raw in ("yes", "y", "true", "1"),
        )
        prev = seen.get(ssid)
        if prev is None or net.signal > prev.signal or (net.active and not prev.active):
            seen[ssid] = net
    return sorted(seen.values(), key=lambda n: (not n.active, -n.signal, n.ssid.lower()))


def connect_wifi(ssid: str, password: str = "") -> None:
    if not _has_nmcli():
        raise RuntimeError("nmcli not available")
    ssid = ssid.strip()
    if not ssid:
        raise RuntimeError("SSID is empty")
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd.extend(["password", password])
    proc = _run(cmd, timeout=60)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "connect failed").strip()
        raise RuntimeError(err)


def _power_cmd(action: str) -> None:
    """action: reboot | poweroff"""
    if platform.system() == "Windows":
        raise RuntimeError(f"{action} is only available on Raspberry Pi / Linux")
    candidates = [
        ["systemctl", action],
        ["sudo", "-n", "systemctl", action],
        ["sudo", "-n", action if action != "poweroff" else "poweroff"],
        ["sudo", action if action != "poweroff" else "poweroff"],
    ]
    if action == "reboot":
        candidates.insert(2, ["sudo", "-n", "reboot"])
    else:
        candidates.insert(2, ["sudo", "-n", "shutdown", "-h", "now"])

    last_err = "no command succeeded"
    for cmd in candidates:
        try:
            proc = _run(cmd, timeout=8)
            if proc.returncode == 0:
                log.info("Power command OK: %s", " ".join(cmd))
                return
            last_err = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_err = str(exc)
    raise RuntimeError(last_err)


def reboot() -> None:
    _power_cmd("reboot")


def shutdown() -> None:
    _power_cmd("poweroff")
