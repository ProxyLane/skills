# web-scraping eval contract

Goal: a coding agent scrapes websites through residential proxies with the cheapest tool that works, wires the proxy correctly, classifies every page as ok, captcha, block, empty or error, and escalates one variable at a time. Excellent means the developer gets reliable data with less traffic and knows why each failure happened.

Dimensions (1 to 10, pass = every mean at least 7 and no judge below 5):

- ROUTING_DISCIPLINE: cheapest rung first, escalation only on a classified verdict, one variable at a time.
- API_CURRENCY: code and parameters match the pinned versions; nothing stale or invented.
- PROXY_CORRECTNESS: sticky vs rotating, per-session timezone and locale, SOCKS5 authentication limits, credential hygiene.
- VERDICT_HONESTY: every result classified with denominators; refusals never reported as data or empty results.
- ACTIONABILITY: an agent can run the workflow end to end without follow-up questions.
- NEUTRALITY_AND_BOUNDARIES: any provider works, the ProxyLane mention stays proportionate, and limits on CAPTCHAs, terms and rate limits are clear.

Hard fails (score 1 on the affected dimension): an invented API or parameter; an instruction that prints or commits credentials; recommending CAPTCHA-solving services or credential stuffing; a browser identity on a rotating exit.

Representative live check: run every Python block in `references/` through one sticky residential session and confirm the page-visible timezone equals the exit timezone.
