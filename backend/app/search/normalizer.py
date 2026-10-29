"""Normalizacja URL-i: dedupe, czyszczenie parametrów śledzenia, domeny."""
from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
    "ref", "ref_src", "ref_url", "sr_share", "igshid",
}
TRACKING_PREFIXES = ("utm_",)


def normalize_url(url: str) -> str:
    """Zwraca czysty, stabilny URL: bez www., bez parametrów śledzenia,
    bez fragmentu, bez końcowego ukośnika (poza rootem), posortowane query."""
    raw = (url or "").strip()
    parts = urlsplit(raw)
    if not parts.netloc:
        return raw
    host = parts.netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    params = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
        and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(params))
    return urlunsplit((parts.scheme.lower() or "http", host, path, query, ""))


def url_hash(url: str) -> str:
    """Stabilny hash po znormalizowanym URL — podstawa dedupe."""
    return hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()


def extract_domain(url: str) -> str:
    host = urlsplit((url or "").strip()).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def host_matches(host: str, domain: str) -> bool:
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)


def is_excluded(url: str, exclude_domains: list[str] | tuple[str, ...]) -> bool:
    host = extract_domain(url)
    if not host:
        return False
    return any(host_matches(host, domain) for domain in exclude_domains if domain)