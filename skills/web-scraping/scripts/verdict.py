#!/usr/bin/env python3
r"""Classify a fetched page as ok, captcha, block, empty or error.

A scraper that saves a challenge page as data, or reports "no results" for a
refusal, hides the one fact needed to choose the next step. This script reads
what came back and names it. Standard library only.

Library use:
    from verdict import classify
    result = classify(status=200, body=html, url=final_url, expect="Add to cart")
    result = classify(status=200, body=html, expect=r"\$\d+", expect_regex=True)

CLI use:
    python3 verdict.py page.html --status 200 --url https://example.com/p/1
    curl -s https://example.com | python3 verdict.py - --status 200

The CLI prints one JSON object and exits 0 for ok, 3 for captcha, 4 for block,
5 for empty and 6 for error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass

EXIT_CODES = {"ok": 0, "captcha": 3, "block": 4, "empty": 5, "error": 6}

# (vendor, pattern) pairs. Patterns match markup that only appears on the
# vendor's interstitial, not on ordinary pages that merely load its script.
CAPTCHA_SIGNATURES = [
    ("cloudflare", r"<title>\s*just a moment\.\.\.\s*</title>"),
    ("cloudflare", r"cf-chl-(?:bypass|widget|opt)|/cdn-cgi/challenge-platform/h/"),
    ("cloudflare-turnstile", r"cf-turnstile[^>]*data-sitekey"),
    ("datadome", r"geo\.captcha-delivery\.com|ct\.captcha-delivery\.com"),
    ("perimeterx", r"px-captcha|_pxCaptcha|Press &amp; Hold|Press & Hold"),
    ("aws-waf", r"awswaf\.com/.+captcha|AwsWafIntegration\.(?:checkForceRefresh|getToken)"),
    ("google", r"/sorry/index|Our systems have detected unusual traffic"),
    ("amazon", r"/errors/validateCaptcha|Type the characters you see in this image"),
    ("recaptcha", r"<div[^>]+class=\"g-recaptcha\"|www\.google\.com/recaptcha/api2/anchor"),
    ("hcaptcha", r"<div[^>]+class=\"h-captcha\"|hcaptcha\.com/captcha"),
    ("generic", r"verify (?:that )?you are (?:a )?human|are you a robot\??"),
]

BLOCK_SIGNATURES = [
    ("cloudflare", r"Attention Required! \| Cloudflare|cf-error-details|Error 1020"),
    ("akamai", r"<title>\s*Access Denied\s*</title>[\s\S]*Reference&#32;#|errors\.edgesuite\.net"),
    ("imperva", r"Incapsula incident ID|_Incapsula_Resource"),
    # Google serves HTTP 200 with a JavaScript-required wall to non-browser clients.
    ("google-js-wall", r"/httpservice/retry/enablejs"),
    ("datadome", r"\"blocked\"\s*:\s*true[\s\S]*datadome|dd\.datadome\.co"),
    ("generic", r"<title>\s*(?:403 Forbidden|Access denied|Request blocked|Forbidden)\s*</title>"),
    ("generic", r"your (?:ip|request) (?:address )?has been (?:blocked|banned)"),
]

BLOCK_STATUSES = {401, 403, 407, 429, 451}
MISSING_STATUSES = {404, 410}
MIN_TEXT_CHARS = 200


@dataclass
class Verdict:
    verdict: str
    reason: str
    vendor: str | None = None
    status: int | None = None
    text_chars: int = 0


def visible_text(html: str) -> str:
    """Return a rough visible-text approximation without parsing dependencies."""
    html = re.sub(r"(?is)<(script|style|noscript|template|svg)\b.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _match(signatures: list[tuple[str, str]], body: str) -> str | None:
    for vendor, pattern in signatures:
        if re.search(pattern, body, re.IGNORECASE):
            return vendor
    return None


def classify(
    status: int | None,
    body: str | bytes | None,
    url: str | None = None,
    expect: str | None = None,
    min_text_chars: int = MIN_TEXT_CHARS,
    error: str | None = None,
    expect_regex: bool = False,
) -> Verdict:
    """Classify one response.

    status: final HTTP status, or None when no response arrived.
    body: response body as text or bytes.
    url: final URL after redirects; some vendors redirect to a challenge path.
    expect: text the wanted page must contain (a regex when expect_regex is
        True); its absence on an otherwise normal page is "empty", not "ok".
    error: transport error message when the request itself failed.
    """
    if error or status is None:
        return Verdict("error", error or "no response", status=status)

    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    body = body or ""
    probe = f"{url or ''}\n{body[:400_000]}"
    text = visible_text(body)

    vendor = _match(CAPTCHA_SIGNATURES, probe)
    if vendor:
        return Verdict("captcha", "challenge markup", vendor, status, len(text))

    vendor = _match(BLOCK_SIGNATURES, probe)
    if vendor:
        return Verdict("block", "block page markup", vendor, status, len(text))

    if status in BLOCK_STATUSES:
        return Verdict("block", f"HTTP {status}", None, status, len(text))

    if status >= 500:
        return Verdict("error", f"HTTP {status}", None, status, len(text))

    if status in MISSING_STATUSES:
        return Verdict("empty", f"HTTP {status}", None, status, len(text))

    if status >= 400:
        return Verdict("block", f"HTTP {status}", None, status, len(text))

    found = re.search(expect, body, re.IGNORECASE) if expect and expect_regex else (
        expect.lower() in body.lower() if expect else True)
    if not found:
        return Verdict("empty", "expected content missing", None, status, len(text))

    if not expect and len(text) < min_text_chars:
        return Verdict("empty", f"under {min_text_chars} visible characters", None, status, len(text))

    return Verdict("ok", "content present", None, status, len(text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", help="HTML file, or - for stdin")
    parser.add_argument("--status", type=int, help="final HTTP status; omit when the request failed")
    parser.add_argument("--url", help="final URL after redirects")
    parser.add_argument("--expect", help="text the wanted page must contain")
    parser.add_argument("--expect-regex", help="regex the wanted page must match")
    parser.add_argument("--error", help="transport error message, if the request failed")
    parser.add_argument("--min-text-chars", type=int, default=MIN_TEXT_CHARS)
    args = parser.parse_args(argv)

    if args.file == "-":
        body = sys.stdin.buffer.read()
    else:
        with open(args.file, "rb") as handle:
            body = handle.read()

    expect = args.expect_regex or args.expect
    result = classify(args.status, body, args.url, expect, args.min_text_chars, args.error, bool(args.expect_regex))
    print(json.dumps(asdict(result)))
    return EXIT_CODES[result.verdict]


if __name__ == "__main__":
    sys.exit(main())
