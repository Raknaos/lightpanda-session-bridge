# How to Bypass Headless Login Walls with Lightpanda

> **Problem:** You are building an AI agent or a browser automation script with **Lightpanda**, **Playwright**, or **Puppeteer**, and your target website requires:
> - Google 2-Step Verification
> - Microsoft SSO / Okta / Duo
> - Hardware Passkeys (WebAuthn / FIDO2 / TouchID / FaceID)
> - Cloudflare Turnstile / reCAPTCHA v3

Because headless browsers run without an interactive human user interface, passing biometric prompts or 2FA codes directly inside automated scripts is notoriously brittle or technically impossible.

---

## The Solution: Scoped Session Bridging

Instead of giving your automated agent passwords or long-lived master tokens, use [**Lightpanda Session Bridge**](https://github.com/Raknaos/lightpanda-session-bridge).

### Step 1: Perform the Login in Your Regular Browser
Log into the target service (e.g. AWS console, your internal SaaS, or any web service) on your desktop Chrome, Comet, or Edge browser. Your physical presence completes the 2FA or Passkey challenge.

### Step 2: Sync to Lightpanda via CDP
With the [Lightpanda Session Bridge extension](https://github.com/Raknaos/lightpanda-session-bridge/releases/latest), click **"Sync Session"**. 

The local loopback relay (`127.0.0.1:8765`) securely extracts only the session cookies for that exact origin, normalizes them, and injects them over Chrome DevTools Protocol (CDP) into your running Lightpanda instance (`127.0.0.1:9222`).

### Step 3: Run Your Headless Automation
Your automation script connects directly to Lightpanda and navigates to the authenticated URL. The session is already live:

```python
from lightpanda_client import LightpandaClient

client = LightpandaClient(cdp_ws="ws://127.0.0.1:9222/")
client.connect()
client.attach_or_create("https://your-service.com/dashboard")

# Evaluate directly on the authenticated page
data = client.evaluate("document.querySelector('.dashboard-stats').innerText")
print(data)
```

---

## Why This Architecture Wins
- **Zero Credential Exposure:** Passwords and passkeys never enter prompt contexts, `.env` files, or agent logs.
- **SSRF Hardened:** The local relay blocks private subnets (`127.0.0.0/8`, `192.168.0.0/16`), enforces DNS resolution caching, and rejects root IdP domains.
- **Works with Playwright & Puppeteer:** Connect with `connect_over_cdp("http://127.0.0.1:9222")` and execute end-to-end tests seamlessly.

Learn more on the [Official Repository](https://github.com/Raknaos/lightpanda-session-bridge).
