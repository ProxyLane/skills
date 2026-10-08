#!/usr/bin/env python3
"""Check a proxy before a scraper or browser depends on it.

Reports, without printing credentials:
  - whether the proxy connects and authenticates;
  - the exit IP, country, city, timezone and network owner;
  - whether the exit stays the same across probes (sticky) or changes;
  - the browser timezone_id and locale that match the exit.

Usage:
    # Load PROXY_URL privately into the environment first.
    python3 proxy_doctor.py
    python3 proxy_doctor.py --probes 5 --interval 20 --sticky --expect-country US

Put {session} in the username to test a sticky session: the script replaces
it with --session, or one random id, shared by all probes. Test the same id
the browser will use; another id can exit in another city and timezone.

From Python, browser_settings(proxy_url) returns the timezone_id and locale
for that exact URL. Standard library only for HTTP
and HTTPS proxies; SOCKS needs `requests[socks]`.

Exit codes: 0 ok, 1 no probe succeeded, 2 an expectation failed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import unquote, urlsplit

GEO_ENDPOINTS = ["https://ipinfo.io/json", "https://ipwho.is/"]

# Primary browser locale for common exit countries. Unknown countries fall
# back to en-US, which is reported so the caller can override it.
COUNTRY_LOCALES = {
    "AE": "ar-AE", "AR": "es-AR", "AT": "de-AT", "AU": "en-AU", "BE": "nl-BE",
    "BR": "pt-BR", "CA": "en-CA", "CH": "de-CH", "CL": "es-CL", "CN": "zh-CN",
    "CO": "es-CO", "CZ": "cs-CZ", "DE": "de-DE", "DK": "da-DK", "EG": "ar-EG",
    "ES": "es-ES", "FI": "fi-FI", "FR": "fr-FR", "GB": "en-GB", "GR": "el-GR",
    "HK": "zh-HK", "HU": "hu-HU", "ID": "id-ID", "IE": "en-IE", "IL": "he-IL",
    "IN": "en-IN", "IT": "it-IT", "JP": "ja-JP", "KR": "ko-KR", "KZ": "ru-KZ",
    "MX": "es-MX", "MY": "ms-MY", "NG": "en-NG", "NL": "nl-NL", "NO": "nb-NO",
    "NZ": "en-NZ", "PE": "es-PE", "PH": "en-PH", "PK": "en-PK", "PL": "pl-PL",
    "PT": "pt-PT", "RO": "ro-RO", "RU": "ru-RU", "SA": "ar-SA", "SE": "sv-SE",
    "SG": "en-SG", "TH": "th-TH", "TR": "tr-TR", "TW": "zh-TW", "UA": "uk-UA",
    "US": "en-US", "VN": "vi-VN", "ZA": "en-ZA",
}


def redact(text: str, proxy_url: str) -> str:
    """Remove the proxy's username and password from any message."""
    parts = urlsplit(proxy_url)
    text = re.sub(r"//[^/\s]+@", "//***@", text)
    secrets_to_hide = {value for secret in (parts.password, parts.username) if secret
                       for value in (secret, unquote(secret))}
    for secret in sorted(secrets_to_hide, key=len, reverse=True):
        if len(secret) < 4:
            text = re.sub(r"(?<!\w)" + re.escape(secret) + r"(?!\w)", "***", text)
        else:
            text = text.replace(secret, "***")
    return text


class ProxyBypassError(RuntimeError):
    """A system bypass rule would send a proxy check directly."""


class RequiredProxyHandler(urllib.request.ProxyHandler):
    """Fail closed when urllib would bypass the explicit proxy, including redirects."""

    def proxy_open(self, request: urllib.request.Request, proxy: str, scheme: str) -> object:
        if request.host and urllib.request.proxy_bypass(request.host):
            raise ProxyBypassError("a system proxy bypass rule matches the destination")
        return super().proxy_open(request, proxy, scheme)


class RequiredProxyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects to protocols outside the configured HTTP(S) proxy."""

    def redirect_request(self, request, response, code, message, headers, new_url):
        if urlsplit(new_url).scheme not in {"http", "https"}:
            raise ProxyBypassError("redirect protocol is outside the configured proxy")
        return super().redirect_request(request, response, code, message, headers, new_url)


def with_session(proxy_url: str, session_id: str) -> str:
    return proxy_url.replace("{session}", session_id)


def locale_for(country: str | None) -> str:
    return COUNTRY_LOCALES.get((country or "").upper(), "en-US")


def normalize_geo(payload: dict) -> dict:
    """Map ipinfo.io and ipwho.is responses to one shape."""
    timezone = payload.get("timezone")
    if isinstance(timezone, dict):
        timezone = timezone.get("id")
    connection = payload.get("connection") if isinstance(payload.get("connection"), dict) else {}
    return {
        "ip": payload.get("ip"),
        "country": payload.get("country_code") or payload.get("country"),
        "region": payload.get("region"),
        "city": payload.get("city"),
        "timezone": timezone,
        "org": payload.get("org") or connection.get("org") or connection.get("isp"),
    }


def fetch_json(url: str, proxy_url: str, timeout: float) -> dict:
    scheme = urlsplit(proxy_url).scheme
    if scheme.startswith("socks"):
        try:
            import requests  # type: ignore
        except ImportError as error:
            raise RuntimeError("SOCKS proxies need: pip install 'requests[socks]'") from error
        with requests.Session() as client:
            client.trust_env = False
            response = client.get(url, proxies={"http": proxy_url, "https": proxy_url}, timeout=timeout)
            response.raise_for_status()
            return response.json()

    opener = urllib.request.build_opener(
        RequiredProxyHandler({"http": proxy_url, "https": proxy_url}), RequiredProxyRedirectHandler()
    )
    request = urllib.request.Request(url, headers={"User-Agent": "proxy-doctor/1.0", "Accept": "application/json"})
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def probe(proxy_url: str, timeout: float) -> dict:
    started = time.monotonic()
    last_error = "no geo endpoint answered"
    for endpoint in GEO_ENDPOINTS:
        try:
            geo = normalize_geo(fetch_json(endpoint, proxy_url, timeout))
            if geo["ip"]:
                geo["latency_ms"] = round((time.monotonic() - started) * 1000)
                geo["ok"] = True
                return geo
        except ProxyBypassError:
            last_error = "proxy bypass or unsupported redirect prevents a required proxy check"
        except urllib.error.HTTPError as error:
            last_error = f"HTTP {error.code} from {'proxy' if error.code == 407 else urlsplit(endpoint).hostname}"
            if error.code == 407:
                break
        except Exception as error:  # noqa: BLE001 - reported, never raised
            if "407" in str(error):
                last_error = "HTTP 407 from proxy"
                break
            last_error = f"{type(error).__name__}: proxy check failed"
    return {"ok": False, "error": last_error, "latency_ms": round((time.monotonic() - started) * 1000)}


def browser_settings(proxy_url: str, timeout: float = 20) -> dict:
    """Return the timezone_id and locale matching this exact proxy URL's exit.

    Call it with the same session id the browser will use; another session
    can exit in another city and timezone.
    """
    result = probe(proxy_url, timeout)
    if not result.get("ok"):
        raise RuntimeError(f"proxy check failed: {result.get('error')}")
    if not result.get("timezone"):
        raise RuntimeError("proxy connected but the geo lookup returned no timezone; pass timezone_id yourself")
    return {
        "ip": result["ip"],
        "country": result.get("country"),
        "timezone_id": result.get("timezone"),
        "locale": locale_for(result.get("country")),
    }


def summarize(probes: list[dict], expect_country: str | None, sticky: bool) -> dict:
    good = [p for p in probes if p.get("ok")]
    ips = [p["ip"] for p in good]
    changes = sum(1 for a, b in zip(ips, ips[1:]) if a != b)
    first = good[0] if good else {}
    problems = []
    notes = []
    if not good:
        problems.append("no probe succeeded")
    if expect_country and any((p.get("country") or "").upper() != expect_country.upper() for p in good):
        problems.append(f"exit country differs from {expect_country.upper()}")
    if sticky and changes:
        problems.append(f"sticky exit changed {changes} time(s) across {len(good)} probes")
    timezones = sorted({p["timezone"] for p in good if p.get("timezone")})
    if len(timezones) > 1:
        message = "exit timezone changed between probes: " + ", ".join(timezones)
        (problems if sticky else notes).append(message)
    if changes and not sticky:
        notes.append("rotating exit: give each browser context its own sticky session")
    return {
        "reachable": bool(good),
        "probes_ok": len(good),
        "probes_total": len(probes),
        "distinct_ips": len(set(ips)),
        "ip_changes": changes,
        "median_latency_ms": sorted(p["latency_ms"] for p in good)[len(good) // 2] if good else None,
        "browser": {"timezone_id": first.get("timezone"), "locale": locale_for(first.get("country"))} if good else None,
        "problems": problems,
        "notes": notes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a proxy before a scraper depends on it.")
    parser.add_argument("--proxy", help="proxy URL; defaults to $PROXY_URL. Avoid passing secrets as arguments.")
    parser.add_argument("--probes", type=int, default=3)
    parser.add_argument("--interval", type=float, default=0, help="seconds between probes")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--sticky", action="store_true", help="fail when the exit IP changes")
    parser.add_argument("--expect-country", help="ISO country code the exit must match")
    parser.add_argument("--session", help="session id to put in {session}; default is a random one")
    args = parser.parse_args(argv)

    template = args.proxy or os.environ.get("PROXY_URL")
    if not template:
        parser.error("set PROXY_URL or pass --proxy")
    try:
        parts = urlsplit(template)
        valid_proxy = (parts.scheme in {"http", "https", "socks5", "socks5h"}
                       and parts.hostname and parts.port and parts.path in {"", "/"}
                       and not parts.query and not parts.fragment)
    except ValueError:
        valid_proxy = False
    if not valid_proxy:
        parser.error("proxy must look like scheme://[user:pass@]host:port with scheme http, https, socks5 or socks5h")

    session_id = (args.session or secrets.token_hex(4)) if "{session}" in template else None
    proxy_url = with_session(template, session_id) if session_id else template

    probes = []
    for index in range(max(1, args.probes)):
        if index and args.interval:
            time.sleep(args.interval)
        probes.append(probe(proxy_url, args.timeout))

    report = {
        "proxy": redact(proxy_url, proxy_url),
        "session_id": session_id,
        "probes": probes,
        "summary": summarize(probes, args.expect_country, args.sticky or bool(session_id)),
    }
    print(json.dumps(report, indent=2))
    if not report["summary"]["reachable"]:
        return 1
    return 2 if report["summary"]["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
