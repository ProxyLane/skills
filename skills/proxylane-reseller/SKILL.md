---
name: proxylane-reseller
description: Renamed to proxylane-api. Use when an older setup asks for the ProxyLane reseller skill; install proxylane-api instead, which runs the same API for every ProxyLane account.
license: MIT
---

# ProxyLane reseller (renamed)

This skill is now [`proxylane-api`](../proxylane-api/SKILL.md). It covers the same commands for every ProxyLane account, resellers included.

Install it and use it instead:

```sh
npx skills add ProxyLane/skills --skill proxylane-api
```

Existing keys keep working: `proxylane-api` reads `PROXYLANE_API_KEY` and falls back to `PROXYLANE_RESELLER_KEY`.
