# Scrapling (0.4.15)

Rungs 1 to 3 in one library: `Fetcher` (curl_cffi with browser TLS), `DynamicFetcher` (Playwright Chromium) and `StealthyFetcher` (Patchright). For the full API, the maintainer publishes the `scrapling-official` skill (`npx skills add D4Vinci/Scrapling --skill scrapling-official`); this page covers proxies and verdicts.

```sh
pip install "scrapling[fetchers]>=0.4.15"   # add [ai] for the MCP server
scrapling install                            # downloads the browsers
```

Requires Python 3.10+. Use 0.4.9 or newer: older `FetcherSession` silently ignored a session-level `proxy`, which sent requests from the real IP.

## Rung 1: HTTP with browser TLS

```python
import os
from scrapling.fetchers import FetcherSession

with FetcherSession(proxy=os.environ["PROXY_URL"], impersonate="chrome", timeout=30, retries=1) as session:
    page = session.get("https://example.com/products?page=1")
    print(page.status, len(page.body), page.css("h2::text").getall()[:3])
```

- `proxy=` takes a URL string here. `proxy_rotator=ProxyRotator([...])` rotates per request and cannot be combined with `proxy`.
- `page.body` is bytes; `page.json()` is a method; `css_first` was removed in 0.4, use `.css(...).first` or `.get()`.

## Rung 3: stealth browser on one sticky exit

```python
import os, sys
from scrapling.fetchers import StealthySession

sys.path.insert(0, "path/to/web-scraping/scripts")   # this skill's scripts folder
from proxy_doctor import browser_settings

proxy = os.environ["PROXY_URL"].replace("{session}", "job01")
geo = browser_settings(proxy)         # timezone and locale of this session's exit
with StealthySession(
    proxy=proxy,                      # str or {"server", "username", "password"}
    timezone_id=geo["timezone_id"],
    locale=geo["locale"],
    block_webrtc=True,
    disable_resources=True,           # skips images, fonts, media: less traffic
    timeout=60000,                    # milliseconds
) as session:
    page = session.fetch("https://example.com/", wait_selector="h1")
    print(page.status, page.css("title::text").get())
```

- Leave `solve_cloudflare` off. A challenge is a verdict to act on (pace, consistency, rung), not something to defeat.
- A session-level `proxy` keeps one browser context, so cookies and the exit persist across `fetch` calls. A per-call `proxy=` or a `proxy_rotator` opens a fresh context each time.
- `humanize` and `geoip` no longer exist in Scrapling (removed in 0.3.13 with the move from Camoufox to Patchright). Set `timezone_id` and `locale` yourself.
- `response.meta["proxy"]` records the proxy a response used.

## MCP server

`pip install "scrapling[ai]"`, then register the absolute path of the binary:

```sh
claude mcp add ScraplingServer "$(which scrapling-mcp)"
```

Tools: `make_request`, `bulk_get`, `fetch`, `bulk_fetch`, `stealthy_fetch`, `bulk_stealthy_fetch`, `open_session`, `open_request_session`, `session_fetch`, `session_make_request`, `close_session`, `list_sessions`, `screenshot`. One-shot tools and `open_session` accept `proxy`; session tools reuse the proxy chosen at open. Since 0.4.15 the HTTP transport (`scrapling-mcp --http`) requires `--auth-token` or an explicit `--no-auth`.

## Spiders

`from scrapling.spiders import Spider` crawls with `concurrent_requests`, `download_delay`, pause and resume via `crawldir`, and retries blocked statuses (401, 403, 407, 429, 444, 5xx) with a fresh proxy from the session's rotator. Add sessions in `configure_sessions(self, manager)`.

CLI: `scrapling extract get|fetch|stealthy-fetch URL out.md --proxy "$PROXY_URL"`.
