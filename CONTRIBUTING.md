# Contributing to Lightpanda Session Bridge

Thank you for your interest in improving the Lightpanda Session Bridge!

## Development & Testing

Before submitting a Pull Request, ensure that all security unit tests pass cleanly:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the security self-test
python relay/server.py --self-test

# 3. Run the unit test suite
python -m unittest discover -s tests -v
```

## Security Principles to Maintain

1. **Zero Plaintext Logging:** Never print, log, or persist cookie names or values.
2. **Strict Origin Scoping:** Identity provider root domains (`accounts.google.com`, etc.) and private/local network ranges must remain unconditionally blocked.
3. **CORS Enforcement:** The relay must only accept cross-origin requests bearing valid `chrome-extension://` headers.
