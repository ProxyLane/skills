# Crawl4AI (0.9.4)

Rung 2 when the output is Markdown for an LLM or a RAG index. It detects anti-bot pages itself and can walk a list of proxies.

```sh
pip install -U crawl4ai
crawl4ai-setup && crawl4ai-doctor
```

Requires Python 3.10+.

```python
import asyncio, os, sys
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, ProxyConfig, CacheMode

sys.path.insert(0, "path/to/web-scraping/scripts")   # this skill's scripts folder
from proxy_doctor import browser_settings
from verdict import classify

proxy_url = os.environ["PROXY_URL"].replace("{session}", "job01")
geo = browser_settings(proxy_url)        # timezone and locale of this session's exit
run = CrawlerRunConfig(proxy_config=ProxyConfig.from_string(proxy_url), cache_mode=CacheMode.BYPASS,
                       max_retries=1, timezone_id=geo["timezone_id"], locale=geo["locale"])

async def main():
    async with AsyncWebCrawler(config=BrowserConfig(headless=True, enable_stealth=True)) as crawler:
        result = await crawler.arun("https://example.com/", config=run)
        if not result.success and "anti-bot" in (result.error_message or ""):
            verdict = "block"
        else:
            verdict = classify(result.status_code, result.html or "", result.redirected_url,
                               expect="Example Domain", error=None if result.success else result.error_message).verdict
        print(verdict, result.status_code, len(str(result.markdown)))

asyncio.run(main())
```

- Set the proxy on `CrawlerRunConfig(proxy_config=...)`. `BrowserConfig(proxy=...)` is deprecated.
- `ProxyConfig.from_string` accepts `http://user:pass@host:port`, `ip:port:user:pass` and `ip:port`.
- Each distinct proxy username gets its own browser context, so one session id per context keeps one exit.
- `proxy_config=[ProxyConfig.DIRECT, p1, p2]` with `max_retries=N` escalates through the list, which changes the exit automatically. Use it after the baseline diagnosis, not while testing one variable or holding a browser identity; `result.crawl_stats["proxies_used"]` records each attempt's status and block reason.
- `str(result.markdown)` is the raw Markdown. `result.markdown.fit_markdown` needs a content filter. `result.fit_markdown` and `markdown_v2` were removed.
- Stealth: `BrowserConfig(enable_stealth=True)`, or `UndetectedAdapter` with `AsyncPlaywrightCrawlerStrategy` for a stronger patch set.

Docker server: since 0.9.0 the REST API rejects `proxy` and `proxy_config` in request bodies (HTTP 400), and auth is mandatory. Use the Python SDK for residential proxies.
