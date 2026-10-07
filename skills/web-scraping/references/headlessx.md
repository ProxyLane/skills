# HeadlessX (2.1.2)

A self-hosted scraping platform: Express API, dashboard, queue worker and an MCP endpoint, backed by Postgres and Redis, driving a Camoufox-based browser. Use it when several people or agents should share one scraping service.

```sh
npm i -g @headlessx-cli/core && headlessx init --mode production
# or: cd infra/docker && cp .env.example .env && docker compose --profile all up --build -d
```

Set `DASHBOARD_INTERNAL_API_KEY` and `CREDENTIAL_ENCRYPTION_KEY` in `.env`. The API listens on port 38473 and the dashboard on 34872. Create an API key in the dashboard; every call except `/api/health` sends it as `x-api-key`.

## Proxy

The proxy is global to the instance, not per request. A `proxy` field in a scrape request body is accepted but ignored in 2.1.2. Set it once; this restarts the browser:

```sh
python3 -c 'import json, os; print(json.dumps({"proxyEnabled": True, "proxyUrl": os.environ["PROXY_URL"], "proxyProtocol": "http"}))' \
  | curl -X PATCH "$HX/api/config" -H "x-api-key: $HX_KEY" -H 'content-type: application/json' --data @-
```

The JSON goes through stdin, so the proxy password stays out of shell history and process listings.

The instance is one browser identity, so give it a sticky session, never a rotating gateway. For many independent pages, rotate by switching the instance to a new session id between batches, or run one instance per session or country.

## Scrape

```sh
curl -X POST "$HX/api/operators/website/scrape/content" -H "x-api-key: $HX_KEY" \
  -H 'content-type: application/json' -d '{"url":"https://example.com","stealth":true}'
```

Other routes under `/api/operators/website/`: `scrape/html`, `scrape/html-js`, `scrape/screenshot`, `scrape/stream`, `map`, `crawl` (needs Redis). A Cloudflare challenge returns HTTP 403 with a `challenge` object. `stats.statusCode` falls back to 200 when no response was matched, so classify the returned HTML with `scripts/verdict.py` instead of trusting it.

## MCP

Streamable HTTP inside the API, authenticated with a dashboard key:

```json
{"mcpServers": {"headlessx": {"transport": "http", "url": "http://localhost:38473/mcp", "headers": {"x-api-key": "hx_..."}}}}
```

Website tools: `headlessx_website_get_html`, `headlessx_website_get_markdown`, `headlessx_website_map_links` (inputs `url`, `render_javascript`, `wait_for_selector`, `timeout_ms`, `stealth`). They take no proxy argument; the instance proxy applies.

The maintainers also publish a CLI skill: `npx skills add https://github.com/saifyxpro/HeadlessX --skill cli`.
