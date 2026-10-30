# Security Policy

We take the security of CoreDent seriously. This document describes how to report a vulnerability, what to expect, and the scope of the program.

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| `< 1.0` | :x:                |

## Reporting a vulnerability

**Please do not file a public issue.** Email `security@coredent.com` with:

- A description of the vulnerability and its impact
- A minimal proof-of-concept (curl command, screenshot, or short script)
- The endpoint(s) / file(s) affected
- Your name and how you'd like to be credited (or "anonymous")

We acknowledge receipt within **2 business days** and aim to provide a triage within **5 business days**. Critical vulnerabilities are fixed within **7 days**; non-critical within **30 days**. We follow a 90-day disclosure window (after which the issue may be publicly disclosed even if unpatched) — this is a guideline, not a deadline, and we work with the reporter to extend it if a fix needs more time.

## Scope

In scope:
- Any code under `coredent-api/`, `coredent-style-main/`, or infrastructure in the `infra/` directory
- The production API at `api.coredent.com` and the patient portal at `portal.coredent.com`
- The Stripe webhook endpoint
- Any PHI handling, tenant isolation, or encryption logic

Out of scope:
- Denial-of-service attacks
- Social engineering of CoreDent staff
- Physical security
- Third-party services we use (Stripe, SendGrid, Sentry, etc.) — report to them directly
- The `DEV_MODE` development bypass (it is intentionally non-production)
- Findings that require an attacker to already have privileged access (e.g. DBA → DB read)

## Safe harbor

We will not pursue legal action against researchers who:
- Make a good-faith effort to avoid privacy violations, data destruction, or service disruption
- Only interact with accounts they own or have explicit permission to access
- Stop testing immediately if they encounter real PHI and report it to us without retaining copies
- Do not exploit a vulnerability beyond what is necessary to demonstrate it

## Hall of fame

We acknowledge security researchers who have reported valid vulnerabilities. With your permission, your name will be listed here.

_(To be populated as reports come in.)_

## Acknowledgements

This policy is inspired by `disclose.io` and the GitHub security policy template.
