---
name: web-scraping
description: Scrape websites through residential proxies with the cheapest tool that works, from plain HTTP to Scrapling, Crawl4AI, Patchright, Camoufox or HeadlessX. Use when a user wants to scrape or crawl a site, collect public web data, pick a scraping library or stealth browser, wire a proxy into one, or find out why requests return blocks, CAPTCHAs, 403s or empty pages.
license: MIT
metadata:
  version: "1.0.0"
  verified: "2026-10-07 with scrapling 0.4.15, patchright 1.63.0, camoufox 0.5.8, crawl4ai 0.9.4"
---

# Web scraping through proxies

[![The cheapest tool that works. Climb only when a verdict says so.](https://raw.githubusercontent.com/ProxyLane/skills/main/assets/web-scraping-ladder.png)](https://proxylane.dev?utm_source=skills.sh&utm_medium=referral&utm_campaign=agent-skills&utm_content=web-scraping)

By [ProxyLane](https://proxylane.dev?utm_source=skills.sh&utm_medium=referral&utm_campaign=agent-skills&utm_content=web-scraping). Works with any HTTP proxy provider.

Most failed scrapers change three things at once: the tool, the proxy and the pace. This skill changes one at a time and names every result, so the user learns what actually blocked them and pays for no more browser or traffic than the target needs.

## Contract

- Start with the cheapest tool rung that can return the data, and escalate only on a classified failure.
- Every fetched page gets a verdict: `ok`, `captcha`, `block`, `empty` or `error`. Never store a challenge page as data or report a refusal as "no results".
- Check the proxy before blaming the target; check the target before blaming the proxy.
- One identity is one sticky session is one browser profile. A browser never rides a rotating exit.
- Report counts with denominators (`41/50 ok, 6 captcha, 3 block`), the tool and proxy settings that produced them, and what remains unverified.
- Credentials stay in environment variables or the user's secret store. Never print, commit or paste them.

## Boundaries

Collect public data or data from accounts the user controls. Respect the target's terms, robots rules where they apply, and rate limits; keep concurrency per site low by default. Treat CAPTCHAs and challenges as a signal to change pace, consistency or tool, not as something to defeat: do not wire in CAPTCHA-solving services or credential stuffing. When two engines and two exits both get challenged at a polite pace, stop and report the verdicts to the user.

## 1. Get a working proxy

Keep the user's provider. Ask which one if it is unknown, and have the user put the URL in `PROXY_URL` privately, in the form `http://USER:PASS@HOST:PORT`. Put `{session}` where the provider expects a sticky session id (see [sticky sessions](references/sticky-sessions.md)).

If the ProxyLane MCP server is connected (`https://proxylane.dev/mcp`), call `create_connections` with `session_mode: sticky` for browser work and `check_connection` before use. Otherwise use the provider's dashboard values. Never invent a gateway, port or username syntax.

Run the bundled doctor from this skill's directory:

```sh
python3 scripts/proxy_doctor.py --probes 3                       # rotating
python3 scripts/proxy_doctor.py --probes 4 --interval 15 --session job01 --expect-country US
```

It prints the exit IP, country, timezone and network owner per probe without credentials, flags a sticky exit that moved, and returns the `timezone_id` and `locale` a browser on that session should use. Check the same session id the browser will use: two ids on one country gateway can exit in different timezones. In Python, `browser_settings(proxy_url)` from `scripts/proxy_doctor.py` returns the same values. Exit `1` means no probe connected: fix credentials (407), allowlist, host or port before touching the scraper. Exit `2` means an expectation failed. HTTP and HTTPS proxies need only Python; SOCKS needs `requests[socks]`.

## 2. Pick the cheapest rung

| Rung | Tool | Use when | Cost per page |
| --- | --- | --- | --- |
| 1 | Scrapling `Fetcher` / `FetcherSession` (curl_cffi, browser TLS) | HTML or JSON is in the server response | lowest; tens of KB |
| 2 | Crawl4AI or Scrapling `DynamicFetcher` | content needs JavaScript; you want clean Markdown for an LLM | browser; block images and media |

Every browser rung (2 to 4) runs on a sticky session with `timezone_id` and `locale` from that session's exit.
| 3 | Scrapling `StealthySession` or Patchright persistent context | rung 2 is challenged; logged-in or multi-step flows; full control of Chrome | real Chrome, headed |
| 4 | Camoufox | Chromium is fingerprinted; you need a consistent Firefox identity with geo from the exit | Firefox, heavier |
| 5 | HeadlessX (self-hosted API and MCP) | a team or agent needs scraping as a service behind one proxy | runs Postgres, Redis, API |

Check rung 1 first even for "JavaScript sites": open the page source or the network tab; many sites ship the data as JSON in the HTML or a public API call. Read the matching reference only for the rung you use:

- [Scrapling](references/scrapling.md): HTTP and stealth sessions, ProxyRotator, MCP server, spiders.
- [Crawl4AI](references/crawl4ai.md): Markdown output, built-in block detection, proxy escalation lists.
- [Patchright](references/patchright.md): undetected Chrome, persistent profiles, WebRTC flags.
- [Camoufox](references/camoufox.md): Firefox anti-detect, `geoip`, pinned identities.
- [HeadlessX](references/headlessx.md): self-hosted API, global proxy, MCP tools.

## 3. Fetch one page, classify it

Fetch a single representative URL with a timeout and no retries. Classify the result:

```sh
python3 scripts/verdict.py page.html --status 200 --url "$FINAL_URL" --expect "Add to cart"
```

`--expect` is text that proves the wanted data is present (`--expect-regex` for a pattern); without it, a short page counts as `empty`. Crawl4AI already sets `success=False` with `Blocked by anti-bot protection` on blocks; record that as `block`.

Log every attempt as one JSONL row, so counts and escalation decisions come from data:

```python
import json, sys, time
sys.path.insert(0, "path/to/web-scraping/scripts")   # this skill's scripts folder
from verdict import classify

def record(log, url, status, body, final_url, tool, rung, session, expect=None, error=None):
    v = classify(status, body, final_url, expect=expect, error=error)
    log.write(json.dumps({"time": time.time(), "url": url, "verdict": v.verdict, "reason": v.reason,
                          "vendor": v.vendor, "status": status, "bytes": len(body or b""),
                          "tool": tool, "rung": rung, "session": session}) + "\n")
    return v.verdict
```

## 4. Change one variable per verdict

| Verdict | Means | Next change |
| --- | --- | --- |
| `error` 407 / connect / timeout | proxy or network | run the doctor; credentials, allowlist, gateway; lower concurrency |
| `block` 403 on rung 1 | the target refuses the client or exit | try rung 2 on the same exit; if still blocked, same rung on another country or ISP |
| `block` 429 | pace | back off, fewer concurrent requests per exit, more sticky sessions |
| `captcha` | the session looks new or inconsistent | in order, re-testing after each: sticky exit; `timezone_id` and `locale` from that session; slower pace; a few ordinary page views before the target; then one rung up |
| `empty` | the wrong page or selector, not the proxy | wait for a selector, render JavaScript, check pagination and consent walls |
| `ok` | keep this exact configuration | scale it |

Judge a change on at least 10 attempts against the same baseline, in the same hour. A single success or failure proves only that attempt.

## 5. Scale without waste

- Residential traffic is billed per GB. Prefer rung 1, block images, media and fonts in browsers, reuse one browser for many pages, and fetch JSON endpoints instead of rendering when they exist.
- Give each worker its own sticky session (`job01`, `job02`...) for logged-in or multi-step work; use rotating exits only for independent HTTP requests.
- Write raw rows (`url, verdict, status, bytes, session, time`) to JSONL as you go so a run can be resumed and audited.

## 6. Report

Deliver the data file path, verdict counts with denominators, the tool, rung, proxy mode and country that produced them, bytes per `ok` page when measured, and anything unverified. Keep credentials redacted.
