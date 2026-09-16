# ProxyLane Skills

[![skills.sh](https://skills.sh/b/ProxyLane/skills)](https://skills.sh/ProxyLane/skills)

Practical agent skills from [ProxyLane](https://proxylane.dev). Start with one verified proxy connection, then use it in your application.

## Install

```sh
npx skills add ProxyLane/skills --skill proxy-setup
```

For Codex, globally:

```sh
npx skills add ProxyLane/skills --skill proxy-setup --agent codex -g -y
```

Ask your agent: **“Set up my residential proxy in Python and verify the exit IP.”** Or: **“Diagnose this proxy connection error without exposing my credentials.”**

The skill works with your existing provider. You supply the endpoint and credentials privately. It does not create accounts, purchase traffic, or require a ProxyLane SDK.

[Website](https://proxylane.dev) · [Documentation](https://proxylane.dev/docs) · [Skill source](skills/proxy-setup/SKILL.md) · [skills.sh](https://skills.sh/ProxyLane/skills/proxy-setup)

## The skill

The full instructions below are also distributed as [`SKILL.md`](skills/proxy-setup/SKILL.md).

# Proxy setup

[![Proxy setup, made clear](https://raw.githubusercontent.com/ProxyLane/skills/main/assets/proxy-setup-cover.png)](https://proxylane.dev)

By [ProxyLane](https://proxylane.dev), residential proxies for your next working request. Configure a connection, verify its exit IP, and carry the working settings into your app. No SDK required.

## 1. Establish the connection details

Inspect the current project's proxy configuration and runtime before editing. Keep the user's chosen provider. For ProxyLane, start with the [website](https://proxylane.dev) and [documentation](https://proxylane.dev/docs); obtain exact connection values from the user's dashboard. Never invent a gateway, port, username suffix, API, or SDK.

Collect the protocol, host, port, authentication method, target URL, and whether the workflow needs a stable session. Ask only for missing non-secret choices. Have the user load credentials into their existing secret store or local environment; never ask them to paste passwords into chat. If credentials are unavailable, prepare the configuration and report that the live check remains unverified.

Use these environment names in the examples:

- `PROXY_SERVER`: provider-issued scheme, host and port, with no credentials
- `PROXY_USERNAME` and `PROXY_PASSWORD`: raw credentials, loaded privately
- `PROXY_URL`: complete proxy URL, with percent-encoded username/password when present

Do not print these values, commit them, enable shell tracing, or include them in screenshots or logs. Preserve existing secret-handling conventions and unrelated settings.

## 2. Choose the route

| Need | Configuration |
| --- | --- |
| Independent requests | Provider's rotating mode; rotation cadence depends on its gateway |
| Multi-step login or checkout test | Sticky session; keep the same provider session identifier across steps |
| A specific region | Copy the provider's documented targeting configuration |
| HTTP client with HTTPS targets | HTTP proxy with CONNECT, or HTTPS proxy if explicitly supported |
| SOCKS with remote DNS | `socks5h://` in curl or Requests; confirm client support |

Sticky sessions can expire or lose their peer. Repeated exit IPs do not prove rotation is broken, and a changed IP alone does not establish residential origin or geographic accuracy. Do not guess country/city/session username syntax.

## 3. Verify one small request

Use a user-approved HTTPS IP echo endpoint, such as `https://api.ipify.org?format=json`. The endpoint sees the exit IP; never send it proxy credentials as URL parameters or destination headers. Begin with one request, a timeout, and no retries. Keep TLS verification enabled.

For a shell with a private, already-populated `PROXY_URL`, use curl's environment support so the secret is not expanded into a command-line argument:

```sh
https_proxy="${PROXY_URL:?Load PROXY_URL privately first}" HTTPS_PROXY= ALL_PROXY= all_proxy= NO_PROXY= no_proxy= \
  curl --disable --fail --silent --show-error \
  --connect-timeout 10 --max-time 30 \
  'https://api.ipify.org?format=json'
```

`--disable` must be curl's first option; it ignores local curl configuration. The empty bypass variables prevent an inherited `NO_PROXY` rule from skipping this HTTPS test. Avoid verbose traces and sanitize error text before sharing it. Use the provider's actual scheme; an HTTPS target does not imply an HTTPS proxy gateway.

For Python with Requests already installed, construct the URL from separately loaded credentials:

```python
import os
from urllib.parse import quote, urlsplit, urlunsplit
import requests

server = urlsplit(os.environ["PROXY_SERVER"])
assert server.scheme in {"http", "https", "socks5", "socks5h"}
assert server.hostname and server.port and not server.username
assert server.path in {"", "/"} and not server.query and not server.fragment
user = quote(os.environ["PROXY_USERNAME"], safe="")
password = quote(os.environ["PROXY_PASSWORD"], safe="")
proxy = urlunsplit((server.scheme, f"{user}:{password}@{server.netloc}", "", "", ""))

with requests.Session() as client:
    client.trust_env = False
    try:
        response = client.get(
            "https://api.ipify.org?format=json",
            proxies={"http": proxy, "https": proxy},
            timeout=(10, 30),
        )
        response.raise_for_status()
        print(response.json()["ip"])
    except requests.RequestException as error:
        raise SystemExit(f"Proxy check failed: {type(error).__name__}") from None
```

For IP-allowlist authentication, use `PROXY_SERVER` directly as `proxy` and omit username/password handling. SOCKS requires Requests' optional `requests[socks]` dependency; use the project's package manager if installation is authorized. `trust_env=False` also disables environment-provided CA settings; supply an approved CA bundle explicitly if the environment needs one.

Record status, exit IP and test time without credentials. Compare against a known direct egress IP only when a direct connection is acceptable. A successful echo response proves that request, not access to every target. Then test one small request to the intended authorized target. Do not silently fall back to a direct connection.

## 4. Diagnose the first failure

| Observation | Next check |
| --- | --- |
| 407 or proxy authentication failure | Credentials, auth method, allowlisted client IP, account status |
| Cannot resolve gateway / connection refused | Exact host, port, protocol, local DNS and firewall |
| Timeout | Gateway reachability, target availability, provider session; avoid retry storms |
| TLS certificate error | System clock, trust store, gateway scheme; never disable verification |
| 403, 429 or challenge page | Determine whether proxy or destination returned it; respect target rules and rate limits |
| Unexpected exit IP | Bypass rules, client config, sticky-session lifetime and provider targeting |

Do not claim a CAPTCHA or access restriction is a proxy configuration defect. Stop at an unresolved authentication or access boundary and state the missing fact.

## 5. Deliver the working configuration

Apply only the tested settings to the requested client. For other tools, consult their current proxy documentation and check HTTP/SOCKS authentication support rather than transplanting URL syntax blindly. Report the changed file, selected protocol/session behavior, completed checks, and anything still unverified. Keep credentials redacted.

References: [curl manual](https://curl.se/docs/manpage.html) · [Requests proxies](https://requests.readthedocs.io/en/latest/user/advanced/#proxies) · [ProxyLane](https://proxylane.dev)

## License

Skill instructions and examples: [MIT](LICENSE). ProxyLane branding remains the property of ProxyLane.
