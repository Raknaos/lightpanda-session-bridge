# Table of Contents
1. [What is Lightpanda Session Bridge?](#what-is-lightpanda-session-bridge)
2. [Why Not Share Passwords With LLM Agents?](#why-not-share-passwords-with-llm-agents)
3. [How Does Session Synchronization Work?](#how-does-session-synchronization-work)
4. [SSRF Security and Threat Model](#ssrf-security-and-threat-model)
5. [Integrating With Custom Agent Code](#integrating-with-custom-agent-code)
6. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

### What is Lightpanda Session Bridge?
Lightpanda Session Bridge is an open-source bridge allowing developers to authenticate in their standard desktop browser and securely copy that active session (cookies, local storage) to a headless [Lightpanda](https://lightpanda.io) browser over the Chrome DevTools Protocol (CDP).

### Why Not Share Passwords With LLM Agents?
Sharing credentials with AI models exposes accounts to prompt injection, transcript exfiltration, and permanent account takeover. Cookies, by contrast, are scoped, ephemeral, and instantly revokable.

### How Does Session Synchronization Work?
1. The human user logs in via biometric passkeys, OAuth, or 2FA.
2. The user clicks "Sync Session" in the Manifest V3 extension.
3. The extension posts the scoped cookies to the loopback relay (`127.0.0.1:8765`).
4. The relay injects the cookies via CDP into Lightpanda (`127.0.0.1:9222`).

### SSRF Security and Threat Model
The relay enforces:
- Loopback-only binding (`127.0.0.1`).
- Mandatory DNS resolution + 60s pin caching.
- Categorical rejection of IdP root domains (Google, Microsoft, GitHub, Auth0).
- Rejection of private IP ranges and wildcard DNS (`nip.io`).

### Integrating With Custom Agent Code
Use `lightpanda_client.py`:
```python
from lightpanda_client import LightpandaClient
client = LightpandaClient(cdp_ws="ws://127.0.0.1:9222/")
client.connect()
client.attach_or_create("https://example.com/dashboard")
data = client.evaluate("document.title")
print(data)
```

### Troubleshooting Common Issues
- **Popup says "Relay Offline":** Ensure `./scripts/start-relay.ps1` is running.
- **WebSocket connection failed:** Check if Lightpanda is running in WSL2 on port 9222.
