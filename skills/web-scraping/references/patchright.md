# Patchright (1.63.0)

A drop-in Playwright replacement for Chromium that removes the automation leaks most detectors check (`Runtime.enable`, automation flags). It does not spoof fingerprints, does not handle WebRTC, and is not designed for headless use.

```sh
pip install patchright && patchright install chrome     # Python 3.10+
npm i patchright && npx patchright install chrome        # Node 20+
```

## Recommended launch with a sticky proxy

```python
import os, sys
from urllib.parse import urlsplit, unquote
from patchright.sync_api import sync_playwright

sys.path.insert(0, "path/to/web-scraping/scripts")   # this skill's scripts folder
from proxy_doctor import browser_settings

proxy_url = os.environ["PROXY_URL"].replace("{session}", "acct01")
geo = browser_settings(proxy_url)        # timezone and locale of this session's exit
url = urlsplit(proxy_url)
proxy = {"server": f"http://{url.hostname}:{url.port}",
         "username": unquote(url.username), "password": unquote(url.password)}

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir="profiles/acct01",      # one profile per session id
        channel="chrome",                     # real Chrome, as the maintainers recommend
        headless=False,
        no_viewport=True,
        proxy=proxy,
        timezone_id=geo["timezone_id"],
        locale=geo["locale"],
        args=["--webrtc-ip-handling-policy=disable_non_proxied_udp",
              "--force-webrtc-ip-handling-policy"],
    )
    page = context.new_page()
    page.goto("https://example.com/", wait_until="domcontentloaded")
    seen = page.evaluate("""async () => {
      const j = await (await fetch('https://ipinfo.io/json')).json();
      return {ipTz: j.timezone, jsTz: Intl.DateTimeFormat().resolvedOptions().timeZone};
    }""")
    assert seen["ipTz"] == seen["jsTz"], seen   # the exit moved: relaunch on a new session
    context.close()
```

- Do not set `user_agent` or extra headers; the maintainers advise against it.
- Authenticated SOCKS5 does not work in Chromium. Use the provider's HTTP port.
- `page.evaluate` runs in an isolated world by default. Pass `isolated_context=False` to read the page's own JavaScript variables.
- Patchright disables the console domain to avoid detection, so `page.on("console")` may not deliver page logs. Test it on your target before relying on it.
- `add_init_script` and `expose_function` behind a proxy have caused tunnel failures in past releases. Avoid them unless tested on your version.
- On a server without a display, run headed under Xvfb (`xvfb-run python script.py`) rather than `headless=True`.

Keep the profile directory and the session id together for the life of an account. Changing either makes the site see a new device or a new network.
