# 📦 CoreDent PMS - Dependency Security Report

**Date:** March 15, 2026

## 1. Backend Dependencies (requirements.txt)

| Package | Current | Latest | Status | recommendation |
|:---|:---|:---|:---|:---|
| `fastapi` | 0.109.0 | 0.115.8 | 🔴 Outdated | Upgrade for Pydantic v2 performance and security fixes. |
| `sqlalchemy` | 2.0.25 | 2.0.38 | 🟡 Outdated | Upgrade to latest 2.0.x for refined async support. |
| `pydantic` | 2.5.3 | 2.10.6 | 🔴 Outdated | Upgrade to latest 2.x. |
| `cryptography` | 42.0.0 | 44.0.1 | 🟡 Outdated | Regular security update recommended. |
| `python-jose` | 3.3.0 | 3.3.0 | ✅ OK | Consider `PyJWT` if `python-jose` becomes unmaintained. |

## 2. Frontend Dependencies (package.json)

| Package | Current | Latest | Status | Recommendation |
|:---|:---|:---|:---|:---|
| `@sentry/browser` | 7.120.4 | 8.54.0 | 🔴 Outdated | Major version update available with better tracing. |
| `react-router-dom` | 6.30.1 | 7.2.0 | 🟡 Outdated | Version 7 introduces many performance improvements. |
| `zod` | 3.25.76 | 3.24.2 | 🟡 Outdated | Minor updates available. |
| `vite` | 6.4.1 | 6.1.1 | 🟡 Outdated | Check for stable 6.x releases. |

## 3. Unnecessary / Problematic Dependencies
- **`python-cors`**: Found in root analysis, but verified it is NOT in `requirements.txt`.
- **`lovable-tagger`**: Identified as a dev dependency, ensure it is excluded from production builds.

---

## 4. Upgrade Commands

### Backend Upgrade
```bash
pip install --upgrade fastapi sqlalchemy pydantic cryptography pydantic-settings
pip freeze > requirements.txt
```

### Frontend Upgrade
```bash
npm update
npm install @sentry/browser@latest react-router-dom@latest
```
