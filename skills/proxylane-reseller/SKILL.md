---
name: proxylane-reseller
description: Run a ProxyLane residential proxy resale business through the Reseller API. Use when a reseller asks to buy wholesale traffic, create a sub-account or login for a client, add or take back a client's GB, pause or delete a client, generate proxy lists for a client, or report client traffic usage.
license: MIT
---

# ProxyLane reseller

By [ProxyLane](https://proxylane.dev?utm_source=skills.sh&utm_medium=referral&utm_campaign=agent-skills&utm_content=proxylane-reseller). The reseller buys residential traffic in bulk into a pool, gives each client a sub-account with its own login and traffic limit, and moves GB between them. Full reference: [Reseller docs](https://docs.proxylane.dev/resellers/overview?utm_source=skills.sh&utm_medium=referral&utm_campaign=agent-skills&utm_content=proxylane-reseller).

## 1. Connect

The key comes from the ProxyLane dashboard → **Reseller panel** → **Set up API**. It starts with `plr_`.

- Use `PROXYLANE_RESELLER_KEY` from the environment. If it is missing, ask the user to set it in their shell or secret store; do not ask them to paste it into chat.
- Never print, log or commit the key. The bundled script reads it and never echoes it.
- Check the connection with `python3 scripts/reseller.py account`. It shows the pool, the USD balance, the price per GB and the number of sub-accounts.

## 2. Know where the traffic is

| Place | Meaning |
| --- | --- |
| USD balance | Money the reseller topped up in the dashboard. Shared with ISP proxies |
| Pool | GB bought and not given to a client yet |
| Sub-account limit | GB given to one client. Only their traffic counts against it |
| Used | Traffic the client already sent. It cannot be returned |
| Available | Limit minus used. Can be returned to the pool |

1 GB is 1,000,000,000 bytes. The API takes GB with up to three decimals; purchases are whole GB.

## 3. Ask before spending or destroying

These need the user's explicit yes, with the amount stated, before you run them:

- `buy` spends the USD balance. Say the GB, the price per GB from `account` and the total.
- `delete` stops a client's login for good. Unused traffic returns to the pool.
- `suspend` cuts a paying client off. Confirm the client name.

`allocate` and `reclaim` only move traffic the reseller already owns; confirm them when the user did not name the client and the amount.

Top-ups of the USD balance happen in the dashboard (card, PayPal or crypto). There is no API for payment; send the user to **Reseller panel** → **Add funds**.

## 4. Do the work with the script

Run from the skill directory. Every command prints JSON.

```sh
python3 scripts/reseller.py account
python3 scripts/reseller.py buy 50
python3 scripts/reseller.py create "Acme" --external-id crm-1042 --gb 5
python3 scripts/reseller.py list --search crm-1042
python3 scripts/reseller.py allocate SUBACCOUNT_ID 10
python3 scripts/reseller.py reclaim SUBACCOUNT_ID 2
python3 scripts/reseller.py reclaim SUBACCOUNT_ID
python3 scripts/reseller.py suspend SUBACCOUNT_ID
python3 scripts/reseller.py resume SUBACCOUNT_ID
python3 scripts/reseller.py delete SUBACCOUNT_ID
python3 scripts/reseller.py usage SUBACCOUNT_ID --hourly --periods 24
python3 scripts/reseller.py proxies SUBACCOUNT_ID --country US --session sticky --count 10 --format host_first > acme-us.txt
python3 scripts/reseller.py history --limit 20
```

`buy`, `create`, `allocate` and `reclaim` send a fresh `Idempotency-Key`. If a response is lost, retry once with the same key, placed before the command: `python3 scripts/reseller.py --key KEY_FROM_FIRST_TRY buy 50`. The API then returns the first result instead of charging or moving traffic twice.

Find clients by your own ID with `list --search`; `external_id` is unique per account. Keep the returned `id` for later calls.

## 5. Common jobs

**New client.** `account` → if the pool is short, propose `buy` with the total and wait for yes → `create` with the client's name, CRM ID and GB → hand over `login` (host, port, username, password) or a `proxies` file. Tell the user a brand-new login can take a few hours to work on every gateway; `login_warming_until` shows until when.

**Client renewed their plan.** `list --search CRM_ID` → `allocate` the new GB. To reset to a fixed monthly amount, `reclaim` the unused part first, then `allocate`.

**Client stopped paying.** `suspend`. If they leave for good, confirm and `delete`, which returns the unused GB.

**Usage report.** `list` for every client's `traffic_used_gb` and `traffic_available_gb`, `usage ID` for the daily series, `account` for totals. Flag clients under 10% available.

## 6. Read errors

Errors are `{"error": {"code", "message", ...}}` on stderr with exit code 1.

| Code | Next step |
| --- | --- |
| `insufficient_balance` | Ask the user to add funds in the dashboard; `required_cents` is the price |
| `insufficient_pool_traffic` | Propose a `buy`; `available_bytes` is the pool |
| `insufficient_subaccount_traffic` | Return less; `available_bytes` is what is left |
| `idempotency_key_reused` | The key belongs to a different request; use a new one |
| `idempotency_in_progress` | Wait a few seconds and retry with the same key |
| `operation_in_review` | ProxyLane is checking that sub-account; stop and tell the user |
| `subaccount_deleted`, `subaccount_not_found` | Re-list; the ID is gone or wrong |
| `unauthenticated` | The key is wrong or revoked; ask for a new one from the panel |
| `rate_limited` | Slow down; 120 requests per minute per key |

`"updating": true` on a sub-account means a change is being applied; read it again a few seconds later. Do not repeat the change.
