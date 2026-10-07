# ProxyLane Skills

[![skills.sh](https://skills.sh/b/ProxyLane/skills)](https://skills.sh/ProxyLane/skills)
[![tests](https://github.com/ProxyLane/skills/actions/workflows/tests.yml/badge.svg)](https://github.com/ProxyLane/skills/actions/workflows/tests.yml)

Practical agent skills from [ProxyLane](https://proxylane.dev?utm_source=github&utm_medium=referral&utm_campaign=agent-skills&utm_content=readme) for proxies, scraping and browser automation. They work with any proxy provider: you supply the endpoint and credentials privately, and nothing requires a ProxyLane account or SDK.

| Skill | Ask your agent | What it does |
| --- | --- | --- |
| [`web-scraping`](skills/web-scraping/SKILL.md) | “Scrape these product pages through my proxy.” “Why does this site return 403?” | Picks the cheapest tool that works (Scrapling, Crawl4AI, Patchright, Camoufox, HeadlessX), wires the proxy, classifies every page and escalates one change at a time |
| [`proxy-setup`](skills/proxy-setup/SKILL.md) | “Set up my residential proxy in Python and verify the exit IP.” | Configures HTTP or SOCKS5 for curl and Requests, verifies the exit and diagnoses 407s, timeouts and TLS errors |

## Install

```sh
npx skills add ProxyLane/skills --skill web-scraping
npx skills add ProxyLane/skills --skill proxy-setup
```

For Codex, globally: add `--agent codex -g -y`.

## web-scraping

[![The cheapest tool that works. Climb only when a verdict says so.](assets/web-scraping-ladder.png)](skills/web-scraping/SKILL.md)

The skill keeps a scraper on the cheapest rung that returns the data, because a browser costs more traffic than a request and residential traffic is billed per GB. Two bundled scripts, standard library only:

- [`proxy_doctor.py`](skills/web-scraping/scripts/proxy_doctor.py) checks a proxy before anything depends on it: exit IP, country, timezone, network owner, and whether a sticky session holds. It prints the `timezone_id` and `locale` a browser on that session should use, and never prints credentials.
- [`verdict.py`](skills/web-scraping/scripts/verdict.py) names every fetched page `ok`, `captcha`, `block`, `empty` or `error`, with the vendor when it recognizes one (Cloudflare, DataDome, PerimeterX, Akamai, Imperva, AWS WAF, Google). A challenge page is never saved as data.

```sh
PROXY_URL='http://USER_s_{session}:PASS@HOST:PORT' python3 skills/web-scraping/scripts/proxy_doctor.py --session job01 --probes 4 --interval 15
python3 skills/web-scraping/scripts/verdict.py page.html --status 200 --expect "Add to cart"
```

Per-tool references cover current releases: [Scrapling 0.4.15](skills/web-scraping/references/scrapling.md), [Crawl4AI 0.9.4](skills/web-scraping/references/crawl4ai.md), [Patchright 1.63.0](skills/web-scraping/references/patchright.md), [Camoufox 0.5.8](skills/web-scraping/references/camoufox.md) and [HeadlessX 2.1.2](skills/web-scraping/references/headlessx.md). The Scrapling, Crawl4AI, Patchright and Camoufox examples were run through a residential sticky session on 2026-10-07; the HeadlessX page is checked against its source.

The skill keeps clear limits: public data or accounts the user controls, polite rates, and no CAPTCHA-solving services. When two engines and two exits are both challenged, it stops and reports.

## proxy-setup

[![Proxy setup, made clear](assets/proxy-setup-cover.png)](skills/proxy-setup/SKILL.md)

Start with one verified proxy connection, then use it in your application. The skill collects the connection details without asking for passwords in chat, chooses rotating or sticky behavior, verifies one small request with curl or Python Requests, and walks the first failure to its cause. Full instructions: [`SKILL.md`](skills/proxy-setup/SKILL.md).

## Development

```sh
python3 -m unittest discover tests
```

Tests run offline against fixtures. Issues and pull requests are welcome; a failing page with the tool version, the verdict and steps to reproduce helps most.

[Website](https://proxylane.dev?utm_source=github&utm_medium=referral&utm_campaign=agent-skills&utm_content=readme) · [Documentation](https://docs.proxylane.dev?utm_source=github&utm_medium=referral&utm_campaign=agent-skills&utm_content=readme) · [MCP server](https://proxylane.dev/mcp-access?utm_source=github&utm_medium=referral&utm_campaign=agent-skills&utm_content=readme) · [skills.sh](https://skills.sh/ProxyLane/skills)

## License

Skill instructions, scripts and examples: [MIT](LICENSE). ProxyLane branding remains the property of ProxyLane.
