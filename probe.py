"""
Sprint 1 — Connectivity Probe
Verifies: stem auth → Tor version → SOCKS5 fetch → .onion fetch
"""
import sys
import httpx
from stem.control import Controller

TOR_CONTROL_PORT = 9051
TOR_SOCKS_PORT = 9050
COOKIE_PATH = "/opt/homebrew/var/lib/tor/control_auth_cookie"

SOCKS_PROXY = f"socks5://127.0.0.1:{TOR_SOCKS_PORT}"

# Stable test targets
CLEARNET_CHECK = "https://check.torproject.org/api/ip"
ONION_TARGET = "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion"


def check_stem():
    print("[1] Connecting to Tor control port via stem...")
    with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
        ctrl.authenticate()
        version = ctrl.get_version()
        print(f"    Tor version : {version}")
        print(f"    Is alive    : {ctrl.is_alive()}")
    print("    stem OK\n")


def check_clearnet():
    print("[2] Fetching clearnet IP check through Tor SOCKS5...")
    with httpx.Client(proxy=SOCKS_PROXY, timeout=30) as client:
        r = client.get(CLEARNET_CHECK)
        data = r.json()
        print(f"    Exit IP     : {data.get('IP', 'unknown')}")
        print(f"    IsTor       : {data.get('IsTor', 'unknown')}")
    print("    clearnet OK\n")


def check_onion():
    print(f"[3] Fetching .onion target: {ONION_TARGET}")
    with httpx.Client(proxy=SOCKS_PROXY, timeout=60) as client:
        r = client.get(ONION_TARGET)
        print(f"    Status      : {r.status_code}")
        print(f"    Content len : {len(r.text)} chars")
        print(f"    Preview     : {r.text[:120].strip()!r}")
    print("    .onion OK\n")


if __name__ == "__main__":
    try:
        check_stem()
        check_clearnet()
        check_onion()
        print("All probes passed. ShadowFire Sprint 1 complete.")
    except Exception as e:
        print(f"\nFAIL: {e}", file=sys.stderr)
        sys.exit(1)
