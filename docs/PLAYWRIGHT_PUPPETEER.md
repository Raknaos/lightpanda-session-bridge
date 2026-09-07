# Lightpanda Playwright & Puppeteer Integration

How to seamlessly connect **Playwright** and **Puppeteer** to a **Lightpanda** instance already authenticated via **Lightpanda Session Bridge**.

---

## 1. Playwright (Python)

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Connect Playwright directly to Lightpanda's CDP endpoint (WSL2 / Local)
        # Port 9222 already contains your authenticated session transferred via Lightpanda Bridge!
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        
        # Access the existing context carrying the synced cookies
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Navigate to the authenticated app (e.g. AWS, A6API, private dashboard)
        await page.goto("https://a6api.com/console/log")
        
        # Extract dashboard information without logging in
        title = await page.title()
        print(f"Logged in page title: {title}")
        
        await browser.close()

asyncio.run(main())
```

---

## 2. Playwright (Node.js / TypeScript)

```typescript
import { chromium } from 'playwright';

async function run() {
  // Connect to Lightpanda CDP
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const defaultContext = browser.contexts()[0];
  const page = defaultContext.pages()[0] || await defaultContext.newPage();

  await page.goto('https://app.example.com/dashboard');
  console.log('Authenticated view reached:', await page.title());

  await browser.close();
}

run();
```

---

## 3. Puppeteer (Node.js)

```javascript
const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.connect({
    browserURL: 'http://127.0.0.1:9222'
  });

  const pages = await browser.pages();
  const page = pages.length > 0 ? pages[0] : await browser.newPage();

  await page.goto('https://app.example.com/dashboard');
  const content = await page.content();
  console.log('Page content length:', content.length);

  await browser.disconnect();
})();
```

---

## Why this solves the headless login dilemma

Headless browsers cannot handle:
- Google 2-Step Verification
- Microsoft Authenticator number matching
- Biometric WebAuthn (Passkeys / TouchID / FaceID)
- CAPTCHA challenges (Cloudflare Turnstile, reCAPTCHA v3)

By synchronizing session cookies from your desktop browser with **Lightpanda Session Bridge**, your Playwright and Puppeteer scripts run instantly against the authenticated DOM with zero password handling.
