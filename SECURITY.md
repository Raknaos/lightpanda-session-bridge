# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3.0 | :x:                |

## Reporting a Vulnerability

Security is the foundational design goal of the Lightpanda Session Bridge. Since the local relay mediates session cookies, protecting against Server-Side Request Forgery (SSRF) and credential exfiltration is paramount.

If you discover a potential vulnerability:
1. **Do not open a public GitHub issue.**
2. Report the vulnerability via GitHub Private Vulnerability Reporting on this repository.
3. Include detailed steps to reproduce, affected endpoints (e.g. `/v1/session/import`, `/v1/bootstrap`), and impact analysis.

We will review reports within 48 hours and coordinate a patch and CVE disclosure if applicable.
