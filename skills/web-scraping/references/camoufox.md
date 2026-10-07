# Camoufox (0.5.8)

Firefox with fingerprint injection at the C++ level. Use it when Chromium-based tools are fingerprinted or when an identity must stay consistent with its exit location.

```sh
pip install -U "camoufox[geoip]"     # Python 3.10+
python -m camoufox fetch             # set GITHUB_TOKEN to avoid GitHub rate limits
```

## Authenticated proxy with geo from the exit

```python
import os
from urllib.parse import urlsplit, unquote
from camoufox.sync_api import Camoufox

url = urlsplit(os.environ["PROXY_URL"].replace("{session}", "acct01"))
proxy = {"server": f"http://{url.hostname}:{url.port}",
         "username": unquote(url.username), "password": unquote(url.password)}

# headless="virtual" on Linux with Xvfb; True elsewhere
with Camoufox(proxy=proxy, geoip=True, humanize=True, headless=True) as browser:
    page = browser.new_page()
    page.goto("https://example.com/")
```

- `geoip=True` looks up the exit IP once, at launch, through the proxy, and sets timezone, locale, geolocation and the WebRTC address from it. A rotating exit makes those values wrong after the first change, so use a sticky session, ideally city-pinned.
- The lookup result is cached per proxy URL for the life of the Python process. Launching twice with the same rotating URL reuses the first exit's geo.
- Without `geoip`, a proxied launch warns about leaks. To skip the lookup, pass `geoip="<exit IP>"` from `proxy_doctor.py`.
- `headless="virtual"` (Linux, needs Xvfb) is preferred over `headless=True` by the maintainers.
- SOCKS5 with authentication is not confirmed to work. Use the HTTP port.

## Persistent identity

`persistent_context=True` with `user_data_dir=` keeps cookies and storage only. Without a pinned fingerprint, every launch gets a new one. Save `fingerprint_preset` once and pass the same dict and the same session id on every launch.

## Verify consistency in the page

Run this inside the `with` block, after `page.goto(...)`:

```python
info = page.evaluate("""async () => {
  const j = await (await fetch('https://ipinfo.io/json')).json();
  return {ip: j.ip, ipTz: j.timezone, jsTz: Intl.DateTimeFormat().resolvedOptions().timeZone,
          lang: navigator.language};
}""")
assert info["ipTz"] == info["jsTz"], info
```

A mismatch means the exit changed after launch or the geo databases disagree. Relaunch on a fresh sticky session.

Remote use from other languages: `python -m camoufox server` prints a `ws://` endpoint for `firefox.connect()`. It runs one browser instance and does not accept persistent profiles.
