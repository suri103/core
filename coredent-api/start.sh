#!/bin/sh
# Delegate to start.py which handles:
# 1. Alembic migrations (with proper async→sync URL conversion)
# 2. Uvicorn proxy_headers / forwarded_allow_ips for correct client IP
#    behind reverse proxies (Railway, nginx, Cloudflare)
exec python start.py
