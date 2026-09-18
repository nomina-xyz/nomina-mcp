# Data sources and limits

- Source: Yahoo Finance's unofficial public chart and search endpoints. No key, no
  guaranteed uptime, no rate-limit SLA — expect delayed, incomplete, or throttled responses,
  surfaced as explicit tool errors rather than fabricated data.
- **Yahoo's terms restrict automated collection without prior permission and prohibit
  redistributing the data.** Keyless HTTP access does not establish that permission. This
  project discloses that limitation; it does not resolve it. Review Yahoo's terms and obtain
  any permission you need before operating this at scale or on others' behalf.
- Headlines are links and titles only — not article text, not a complete news search.
- No fundamentals, no macroeconomic series, no order execution, no account access.
- Adjusted-close and raw-close bases are never mixed within a return calculation; if a full
  adjusted series isn't available, the whole series falls back to raw closes and says so.
- Comparisons align on shared exchange-local session dates and report local currencies with
  no FX conversion; a return with no valid shared basis is reported as unavailable, not
  estimated.

Yahoo's terms of use: <https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html>.

## Branding

The name "Nomina" and `icon.png` belong to [Nomina](https://www.nomina.io) (formerly Omni).
`icon.png` is their own unmodified square icon asset, sourced from their public brand page —
see `manifest.json`'s `_meta` field for exact provenance. That is not an independent
trademark grant; confirm brand-use rights with Nomina before relying on this outside
internal/personal use.
