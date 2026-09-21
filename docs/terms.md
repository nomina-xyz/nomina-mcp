# Terms of use

These terms cover the Nomina MCP server published at
<https://github.com/nomina-xyz/nomina-mcp> in every distribution form — the hosted endpoint
(`https://mcp.nomina.io/mcp`), the Claude Desktop extension, the container image, and the
stdio server run from a clone — and its listings in agent directories. By using the server you
accept them. Effective 2026-09-21.

## What the service is

Nomina is a read-only research tool. It retrieves and arranges public market data — on-chain
oracle prices, US Treasury yields, Bureau of Labor Statistics series, SEC EDGAR filings, and
GDELT news records — and returns it with source links, observation timestamps, and caveats.
It has no accounts, holds no funds, places no orders, and takes no action on anyone's behalf.

## Not advice

Nothing Nomina returns is investment, financial, legal, or tax advice, an offer or solicitation,
or a recommendation to buy, sell, or hold any asset. Figures are the sources' published data
or arithmetic derived from it (period changes, drawdown, volatility), reported as of the
observation dates shown. Prices from on-chain feeds can lag exchange prices; statistics
describe past observations and are not forecasts. Verify anything material against the linked
primary source before acting on it.

## Data sources and their terms

Each source's terms are summarized, with links, on
[Data sources and limits](data-sources/). US government data is public domain; BLS asks that
its data be shown with the retrieval date and the statement that BLS.gov cannot vouch for
data or analyses after retrieval, which Nomina includes; GDELT is used under its open release
with citation; on-chain values are public blockchain state. Nomina does not grant you any
rights in those sources beyond what their own terms allow.

## Acceptable use

Use the service for lawful research. Do not attempt to overload it, probe or circumvent its
rate limits or host checks, or resell access to it. The hosted endpoint is shared and rate
limited; sustained automated load may be throttled or blocked.

## Availability and changes

The hosted endpoint is provided as-is and as-available, without uptime commitments; it runs on
a free hosting tier and may be slow to wake after idle periods. Tools, symbols, sources, and
these terms can change; changes are recorded in the [changelog](announcements/) and in this
page's effective date. The software is MIT-licensed (see `LICENSE` in the repository).

## Disclaimer and limitation of liability

To the fullest extent permitted by law, the service is provided without warranties of any kind,
express or implied, including accuracy, completeness, timeliness, merchantability, and fitness
for a particular purpose, and Nomina and its contributors are not liable for any loss or
damage arising from its use or from reliance on anything it returns.

## Privacy

See the [privacy policy](privacy/). Nomina stores no queries, conversations, accounts, or
credentials.

## Contact

<https://github.com/nomina-xyz/nomina-mcp/issues>
