# Data sources and limits

Nomina uses only sources whose published terms allow their data to be read programmatically
and shown to users through an application, without a key or an account. Commercial market-data
vendors were evaluated and excluded because their self-serve plans license data for internal
or personal use only.

| Source | What Nomina reads | Terms |
|---|---|---|
| **Chainlink Data Feeds** on Ethereum mainnet, via public JSON-RPC gateways (`ethereum.publicnode.com`, `rpc.mevblocker.io`) and Chainlink's public feed directory | Price feeds for crypto, FX, gold and silver, and a few US equities/ETFs; every historical round on-chain | Public blockchain state. Chainlink's [Terms of Service](https://chain.link/terms) grant a licence to access and use the feeds through their public interfaces for their intended use and impose no display or redistribution restriction beyond compliance with applicable open-source licences. Feeds carry Chainlink's risk categories; Nomina uses `low`, `medium`, `high` and `new` and skips `custom`, `deprecating` and `hidden`. |
| **US Department of the Treasury** | Daily par yield curve rates (1 month – 30 years), CSV | US government work, public domain |
| **US Bureau of Labor Statistics** public API v1 | CPI-U (all items, SA), unemployment rate, nonfarm payrolls, average hourly earnings | US government work, public domain; 25 requests per day per IP, hence long caching |
| **SEC EDGAR** | `company_tickers.json`, XBRL company facts, filing index | US government work, public domain; [fair-access policy](https://www.sec.gov/os/accessing-edgar-data) (identified User-Agent, ≤10 requests/s) |
| **The GDELT Project** DOC 2.0 API | Article records (title, link, date, domain) | Open for any academic, commercial or government use with [citation](https://www.gdeltproject.org/about.html); one request per five seconds |

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
