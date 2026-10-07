# Sticky sessions

A sticky session asks the gateway for the same exit IP on every connection that carries the same session id. Most providers put the id in the proxy username; the exact syntax is provider-specific, so copy it from the provider's dashboard or documentation.

## Rules

- One identity, one session id, one browser profile. Do not reuse a session id across profiles or switch ids inside a profile.
- Sticky means "while the exit stays available", not "reserved for weeks". Expect an occasional replacement and detect it: run `scripts/proxy_doctor.py --sticky` before a long job and compare the page-visible IP at checkpoints.
- Pin the city when timezone consistency matters. A country-only sticky session can be replaced by an exit in another timezone; a city-pinned one keeps the timezone even when the IP changes.
- Set the browser `timezone_id` and `locale` from the exit of that same session id, not from the machine or another session: `proxy_doctor.py --session job01`, or `browser_settings(proxy_url)` in Python. Two ids on the same country gateway can exit in different timezones.
- Use `http://` for authenticated proxies in Chromium. Chromium does not support SOCKS5 with a username and password; Playwright raises `Browser does not support socks5 proxy authentication`.

## Templates

Put `{session}` where the session id goes, keep the template in `PROXY_URL`, and substitute one id per worker:

```python
import os
template = os.environ["PROXY_URL"]          # e.g. http://USER_s_{session}:PASS@HOST:PORT
proxies = [template.replace("{session}", f"job{n:02d}") for n in range(1, 11)]
```

For browser APIs that want a dict:

```python
from urllib.parse import urlsplit, unquote

def proxy_dict(url: str) -> dict:
    parts = urlsplit(url)
    return {
        "server": f"{parts.scheme}://{parts.hostname}:{parts.port}",
        "username": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
    }
```

## ProxyLane

The dashboard and the MCP server (`create_connections` with `session_mode: sticky` and `session_prefix: job`) build the username for you. Its shape is `USER_c_<COUNTRY>[_city_<City>]_s_<session>`, with `_ttl_<seconds>s` added for a timed session, on the gateways `us.gw.proxylane.dev`, `eu.gw.proxylane.dev` and `asia.gw.proxylane.dev`. Choose the gateway nearest the exit country. A sticky session holds while its exit stays online; a timed session rotates after its TTL, from 1 second to 72 hours.
