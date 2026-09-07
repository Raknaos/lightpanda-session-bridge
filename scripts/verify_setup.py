#!/usr/bin/env python3
"""
Quickstart verification script for Lightpanda Session Bridge.
Tests local connectivity, dependencies, and reports environment readiness.
"""
import sys
import json
import urllib.request

RELAY_HEALTH = "http://127.0.0.1:8765/health"
LIGHTPANDA_VERSION = "http://127.0.0.1:9222/json/version"

def check():
    print("🐼 Verifying Lightpanda Session Bridge Environment...\n")
    
    # 1. Python check
    print(f"[*] Python Runtime: {sys.version.split()[0]} (OK)")
    
    # 2. Dependencies
    try:
        import websocket
        print("[*] Dependency 'websocket-client': INSTALLED (OK)")
    except ImportError:
        print("[-] Dependency 'websocket-client': MISSING (Run: pip install -r requirements.txt)")
        return
        
    # 3. Lightpanda CDP
    try:
        with urllib.request.urlopen(LIGHTPANDA_VERSION, timeout=2) as r:
            lp_info = json.loads(r.read())
            print(f"[*] Lightpanda CDP Engine (127.0.0.1:9222): ONLINE ({lp_info.get('Browser', 'Lightpanda')})")
    except Exception:
        print("[-] Lightpanda CDP Engine (127.0.0.1:9222): OFFLINE (Run: ./scripts/start-lightpanda.ps1)")

    # 4. Bridge Relay
    try:
        with urllib.request.urlopen(RELAY_HEALTH, timeout=2) as r:
            relay_info = json.loads(r.read())
            print(f"[*] Bridge Relay (127.0.0.1:8765): ONLINE ({relay_info.get('service', 'active')})")
    except Exception:
        print("[-] Bridge Relay (127.0.0.1:8765): OFFLINE (Run: ./scripts/start-relay.ps1)")

    print("\n[+] Verification complete! Check https://github.com/Raknaos/lightpanda-session-bridge for docs.")

if __name__ == "__main__":
    check()
