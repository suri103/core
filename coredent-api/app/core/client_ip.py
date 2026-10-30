"""Trusted-proxy-aware client IP resolution.

Audit finding M-23: the custom per-user limiter took the *first* entry of
``X-Forwarded-For`` unconditionally:

    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip()

``X-Forwarded-For`` is a request header, so a client sets it freely. Taking the
leftmost value means a caller can rotate that header per request and land in a
different bucket every time, evading the limiter completely. The same value
also reached audit-log IP columns, so the recorded source address of a PHI
access was attacker-controlled.

Uvicorn already solves this for ``request.client.host`` via
``proxy_headers=True`` + ``forwarded_allow_ips`` (see ``start.py`` and the
``TRUSTED_PROXIES`` env var). The bug was application code reading the raw
header *again* and overriding that work.

This module is the one place that answers "who is the client". It only honours
``X-Forwarded-For`` when the immediate peer is a configured trusted proxy, and
then walks the chain from the right, skipping trusted hops, so an attacker
prepending values cannot control the result.
"""

from __future__ import annotations

import ipaddress
import logging
from functools import lru_cache

from fastapi import Request

from app.core.config_simple import settings

logger = logging.getLogger(__name__)

UNKNOWN_IP = "unknown"


@lru_cache(maxsize=1)
def _trusted_networks() -> tuple[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...], bool]:
    """Parse ``TRUSTED_PROXIES`` into networks.

    Returns ``(networks, trust_all)``. ``trust_all`` is True only when the
    configuration is literally ``*``, which is the development default; it is
    rejected for production by boot validation.
    """
    raw = (getattr(settings, "TRUSTED_PROXIES", "") or "").strip()
    if not raw:
        # No configuration: trust loopback only. Behind a real proxy the
        # operator must set TRUSTED_PROXIES.
        raw = "127.0.0.1,::1"
    if raw == "*":
        return (), True

    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.error(
                "Ignoring invalid TRUSTED_PROXIES entry %r; it is neither an IP "
                "nor a CIDR range",
                entry,
            )
    return tuple(networks), False


def _is_trusted_proxy(address: str) -> bool:
    networks, trust_all = _trusted_networks()
    if trust_all:
        return True
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in networks)


def _parse_forwarded_chain(header: str) -> list[str]:
    return [part.strip() for part in header.split(",") if part.strip()]


def get_client_ip(request: Request) -> str:
    """Return the best-known client IP for *request*.

    ``X-Forwarded-For`` is consulted only when the direct peer is a trusted
    proxy. The chain is then walked right-to-left, discarding trusted hops, and
    the first untrusted address is the client. Values a client prepended sit to
    the *left* of the proxy's own appended entry, so they are never selected.
    """
    peer = request.client.host if request.client else None
    if not peer:
        return UNKNOWN_IP

    if not _is_trusted_proxy(peer):
        # Direct connection (or an untrusted hop): the socket address is the
        # only trustworthy answer. Any X-Forwarded-For here is client-supplied
        # and deliberately ignored.
        return peer

    forwarded = request.headers.get("X-Forwarded-For")
    if not forwarded:
        return peer

    chain = _parse_forwarded_chain(forwarded)
    for candidate in reversed(chain):
        # Strip an optional port (IPv4 "1.2.3.4:5678"); bracketed IPv6 keeps
        # its form for ip_address parsing below.
        host = candidate
        if host.count(":") == 1 and "." in host:
            host = host.split(":", 1)[0]
        host = host.strip("[]")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            continue
        if _is_trusted_proxy(host):
            continue
        return host

    # Every hop in the chain is a trusted proxy: the peer is the closest thing
    # to a client we have.
    return peer


def rate_limit_key(request: Request) -> str:
    """slowapi-compatible key function using the trusted client IP."""
    return get_client_ip(request)


def reset_trusted_proxy_cache() -> None:
    """Clear the parsed-configuration cache (tests / config reload)."""
    _trusted_networks.cache_clear()
