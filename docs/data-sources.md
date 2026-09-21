# Data sources and limits

Nomina reads public data only: US government statistics (public domain), values published to
the public Ethereum ledger, and GDELT's openly released news records. No source needs a key or
an account. Commercial market-data vendors were evaluated and excluded because their
self-serve plans license data for internal or personal use only. Each source's basis, the
obligations it imposes, and how Nomina meets them:

| Source | What Nomina reads | Basis and obligations |
|---|---|---|
| **Chainlink Data Feeds** on Ethereum mainnet | Price feeds for crypto, FX, gold and silver, and a few US equities/ETFs; every historical round on-chain | Feed values are state on a public blockchain, read with ordinary `eth_call`s. The only Chainlink-operated interface Nomina uses is the public feed directory that powers `docs.chain.link`, used under Chainlink's [Terms of Service](https://chain.link/terms). Feeds carry Chainlink's risk categories; Nomina serves `low`, `medium`, `high` and `new` and skips `custom`, `deprecating` and `hidden`. |
| **Public JSON-RPC gateways**: [PublicNode](https://publicnode.com) (Allnodes) and [MEV Blocker](https://mevblocker.io) | The `eth_call`s above | Free public RPC endpoints published for programmatic use; neither publishes a rate limit and PublicNode returns HTTP 429 under bursts. Nomina batches (≤100 calls), paces (~12 batches/s), limits concurrency (4), cools a gateway down after a 429 and rotates to the other. |
| **US Department of the Treasury** | Daily par yield curve rates (1 month – 30 years), CSV | US government work, public domain ([17 U.S.C. § 105](https://www.law.cornell.edu/uscode/text/17/105)). |
| **US Bureau of Labor Statistics** public API v1 | CPI-U (all items, SA), unemployment rate, nonfarm payrolls, average hourly earnings | US government work, public domain; the [API terms](https://www.bls.gov/developers/termsOfService.htm) place no controls on end use but require citing the retrieval date and stating "BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov." Every response containing BLS data carries `retrieved_at` and that statement in `caveats`. The terms also bar modifying or misrepresenting BLS content: Nomina reports BLS values exactly as published, and the period changes it computes from them are labelled as Nomina's arithmetic, not BLS figures. v1 allows 25 requests per day per IP. Nomina requests all four series together in ten-year blocks anchored at the current year, so every symbol and window shares at most three cached responses (six-hour TTL) — normally 4–12 requests a day for the whole server — and a process-wide counter refuses to send more than 25 in a day, reporting the exhausted allowance instead of exceeding it. |
| **SEC EDGAR** | `company_tickers.json`, XBRL company facts, filing index | US government work, public domain; the [fair-access policy](https://www.sec.gov/os/accessing-edgar-data) requires an identifying `User-Agent` and at most 10 requests per second. Nomina sends `Nomina MCP <contact>` and makes at most three requests per tool call. |
| **The GDELT Project** DOC 2.0 API | Article records (title, link, date, domain) | Released "for unlimited and unrestricted use for any academic, commercial, or governmental use of any kind" with [citation](https://www.gdeltproject.org/about.html); one request per five seconds, which Nomina enforces process-wide. |

## Methodology and limits

- **On-chain closes.** A feed's value for a UTC calendar day is its last on-chain update before
  midnight UTC, found by searching round timestamps. Feeds update on a heartbeat (hourly for
  major crypto, daily for FX, metals and equities) or when the price moves past a deviation
  threshold, so a close can lag an exchange close, and equity/FX feeds have no weekend
  observations. History starts at the feed's first phase on record; earlier dates are
  reported as unavailable, never estimated.
- **Series alignment.** Comparisons use only dates every retrieved series shares. Monthly
  series (BLS) align with daily series only on month-start dates.
- **Changes.** Prices change in percent; yields and rates change in percentage points; a
  selection mixing the two is flagged as not directly comparable rather than blended.
- **Statistics.** Drawdown uses the running peak; volatility is the sample standard deviation of
  log returns annualized by √252 (daily), √52 (weekly) or √12 (monthly). They describe the
  returned series only.
- **Fundamentals.** Values are as filed in XBRL (US-GAAP); filers reporting under IFRS have no
  US-GAAP facts and are reported as such. Restatements appear as later filings.
- **Headlines** are records of article titles and links, not article text or a complete news
  search; GDELT availability varies and failures are reported, not hidden.
- **No individual stock prices** beyond the equities that have on-chain feeds.

## Branding

The name "Nomina" and `icon.png` belong to [Nomina](https://www.nomina.io). `icon.png` is
Nomina's own square icon asset from its public brand page; see `manifest.json`'s `_meta` field
for provenance.
