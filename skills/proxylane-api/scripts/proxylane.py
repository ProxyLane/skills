#!/usr/bin/env python3
"""ProxyLane API client for agents. Standard library only.

The API key is read from PROXYLANE_API_KEY (PROXYLANE_RESELLER_KEY still works) and is never printed.
Writes that buy or move traffic send an Idempotency-Key; pass --key to retry
the same action safely after a lost response.

Examples:
  python3 proxylane.py account
  python3 proxylane.py buy 50
  python3 proxylane.py create "Office Kyiv" --external-id office-1 --gb 100
  python3 proxylane.py allocate SUBUSER_ID 10
  python3 proxylane.py reclaim SUBUSER_ID            # everything unused
  python3 proxylane.py proxies SUBUSER_ID --country US --count 10
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_BASE_URL = "https://proxylane.dev/api/v1"
KEYED = {"buy", "create", "allocate", "reclaim"}


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def base_url():
    return (os.environ.get("PROXYLANE_API") or os.environ.get("PROXYLANE_RESELLER_API") or DEFAULT_BASE_URL).rstrip("/")


def api_key():
    key = (os.environ.get("PROXYLANE_API_KEY") or os.environ.get("PROXYLANE_RESELLER_KEY") or "").strip()
    if not key.startswith("plr_"):
        raise SystemExit("Set PROXYLANE_API_KEY to an API key from the ProxyLane dashboard, Settings → API keys (it starts with plr_).")
    return key


def call(method, path, body=None, query=None, idempotency_key=None, opener=urllib.request.urlopen):
    url = base_url() + path
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    headers = {"Authorization": "Bearer " + api_key(), "Accept": "application/json", "User-Agent": "proxylane-api-skill/1.0"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with opener(request, timeout=60) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read().decode() or "{}").get("error", {})
        except ValueError:
            payload = {}
        details = {k: v for k, v in payload.items() if k not in ("code", "message")}
        raise ApiError(error.code, payload.get("code", "http_error"), payload.get("message", error.reason), details) from None


def parser():
    p = argparse.ArgumentParser(description="ProxyLane API")
    p.add_argument("--key", help="Idempotency-Key to reuse when retrying a buy, create, allocate or reclaim")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("account", help="Traffic balance, USD balance, prices and sub-user totals")
    s = sub.add_parser("buy", help="Buy whole GB of residential traffic from the USD balance")
    s.add_argument("gb", type=int)
    s = sub.add_parser("history", help="Purchases and traffic moves between the balance and sub-users")
    s.add_argument("--limit", type=int, default=50)
    s = sub.add_parser("list", help="List sub-users")
    s.add_argument("--search")
    s.add_argument("--status", choices=["active", "suspended", "deleted", "all"])
    s.add_argument("--page", type=int)
    s = sub.add_parser("create", help="Create a sub-user with its own login and GB limit")
    s.add_argument("name")
    s.add_argument("--external-id")
    s.add_argument("--gb", type=float, default=0)
    for name, text in (("get", "Show one sub-user"), ("suspend", "Pause the login"), ("resume", "Resume the login"), ("delete", "Delete and return unused traffic")):
        sub.add_parser(name, help=text).add_argument("id")
    s = sub.add_parser("rename", help="Change name or external ID")
    s.add_argument("id")
    s.add_argument("--name")
    s.add_argument("--external-id")
    s = sub.add_parser("allocate", help="Move GB from the balance to a sub-user")
    s.add_argument("id")
    s.add_argument("gb", type=float)
    s = sub.add_parser("reclaim", help="Return unused GB to the balance; omit gb to return all")
    s.add_argument("id")
    s.add_argument("gb", type=float, nargs="?")
    s = sub.add_parser("usage", help="Sub-user traffic per day or hour")
    s.add_argument("id")
    s.add_argument("--hourly", action="store_true")
    s.add_argument("--periods", type=int)
    s = sub.add_parser("proxies", help="Generate connection strings for a sub-user")
    s.add_argument("id")
    s.add_argument("--country")
    s.add_argument("--region")
    s.add_argument("--city")
    s.add_argument("--isp")
    s.add_argument("--session", choices=["rotating", "sticky", "timed"], default="sticky")
    s.add_argument("--ttl", type=int)
    s.add_argument("--protocol", choices=["http", "socks5"], default="socks5")
    s.add_argument("--gateway", choices=["europe", "america", "asia"], default="europe")
    s.add_argument("--count", type=int, default=1)
    s.add_argument("--format", choices=["url", "host_first", "user_first"], default="url")
    s = sub.add_parser("locations", help="Countries, or regions, cities and ISPs of one country")
    s.add_argument("--country")
    return p


def run(args, call=call):
    """Maps a parsed command to one API request and returns its JSON."""
    key = (args.key or str(uuid.uuid4())) if args.command in KEYED else None
    sid = getattr(args, "id", None)
    path = f"/subaccounts/{urllib.parse.quote(sid, safe='')}" if sid else None
    if args.command == "account":
        return call("GET", "/account")
    if args.command == "buy":
        return call("POST", "/traffic/purchase", {"gb": args.gb}, idempotency_key=key)
    if args.command == "history":
        return call("GET", "/traffic/history", query={"limit": args.limit})
    if args.command == "list":
        return call("GET", "/subaccounts", query={"search": args.search, "status": args.status, "page": args.page})
    if args.command == "create":
        return call("POST", "/subaccounts", {"name": args.name, "external_id": args.external_id, "traffic_gb": args.gb}, idempotency_key=key)
    if args.command == "get":
        return call("GET", path)
    if args.command == "rename":
        body = {k: v for k, v in (("name", args.name), ("external_id", args.external_id)) if v is not None}
        return call("PATCH", path, body)
    if args.command == "allocate":
        return call("POST", path + "/allocate", {"gb": args.gb}, idempotency_key=key)
    if args.command == "reclaim":
        return call("POST", path + "/reclaim", {} if args.gb is None else {"gb": args.gb}, idempotency_key=key)
    if args.command in ("suspend", "resume"):
        return call("POST", f"{path}/{args.command}")
    if args.command == "delete":
        return call("DELETE", path)
    if args.command == "usage":
        return call("GET", path + "/usage", query={"granularity": "hour" if args.hourly else "day", "periods": args.periods})
    if args.command == "proxies":
        body = {"session_mode": args.session, "protocol": args.protocol, "gateway": args.gateway, "count": args.count, "format": args.format}
        body.update({k: v for k, v in (("country", args.country), ("region", args.region), ("city", args.city), ("isp", args.isp), ("ttl", args.ttl)) if v is not None})
        return call("POST", path + "/proxies", body)
    if args.command == "locations":
        return call("GET", "/locations", query={"country": args.country})
    raise SystemExit(f"Unknown command {args.command}")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except ApiError as error:
        print(json.dumps({"error": {"status": error.status, "code": error.code, "message": error.message, **error.details}}, indent=2), file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(json.dumps({"error": {"code": "network_error", "message": str(error.reason)}}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
