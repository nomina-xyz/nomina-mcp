"""SEC EDGAR company tickers, XBRL company facts and filings (public domain, no key).

SEC's fair-access policy: identify the client in User-Agent and stay under ten requests per
second. Company facts are cached for six hours.
"""

from __future__ import annotations

from typing import Any

from nomina.sources.common import Fetcher, MarketDataError

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FILING_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
COMPANY_PAGE = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"
# SEC fair-access policy: identify the client as "Company contact@email" (no URLs in the UA).
USER_AGENT = "Nomina MCP indifallacy2@gmail.com"
_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
_FILING_FORMS = ("10-K", "10-Q", "8-K", "20-F", "6-K", "S-1")

# Reported name -> candidate us-gaap concepts, in preference order
_CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss",),
    "operating_income": ("OperatingIncomeLoss",),
    "diluted_eps": ("EarningsPerShareDiluted",),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "stockholders_equity": ("StockholdersEquity",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}
_DURATION_CONCEPTS = {
    "revenue",
    "net_income",
    "operating_income",
    "diluted_eps",
    "operating_cash_flow",
}


class Edgar:
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher

    async def companies(self) -> list[dict[str, Any]]:
        payload = await self.fetcher.request(
            "GET", TICKERS_URL, subject="SEC EDGAR company list", ttl=86400, headers=_HEADERS
        )
        if not isinstance(payload, dict):
            raise MarketDataError("SEC EDGAR company list returned an unexpected payload.")
        return [
            {
                "cik": int(item["cik_str"]),
                "ticker": str(item["ticker"]).upper(),
                "name": str(item["title"]),
            }
            for item in payload.values()
            if isinstance(item, dict) and "cik_str" in item
        ]

    async def resolve(self, ticker: str) -> dict[str, Any] | None:
        wanted = ticker.strip().upper()
        for company in await self.companies():
            if company["ticker"] == wanted:
                return company
        return None

    async def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if not needle:
            return []
        companies = await self.companies()
        exact = [c for c in companies if c["ticker"].lower() == needle]
        partial = [c for c in companies if needle in c["name"].lower() and c not in exact]
        return (exact + partial)[:limit]

    async def fundamentals(self, company: dict[str, Any]) -> dict[str, Any]:
        cik = company["cik"]
        facts = await self.fetcher.request(
            "GET",
            FACTS_URL.format(cik=cik),
            subject="SEC EDGAR company facts",
            ttl=6 * 3600,
            headers=_HEADERS,
        )
        gaap = ((facts.get("facts") or {}).get("us-gaap") or {}) if isinstance(facts, dict) else {}
        if not gaap:
            raise MarketDataError(
                f"SEC EDGAR has no US-GAAP facts for {company['ticker']}; the filer may report under IFRS."
            )
        annual: dict[str, Any] = {}
        quarterly: dict[str, Any] = {}
        for label, concepts in _CONCEPTS.items():
            observations: list[dict[str, Any]] = []
            for concept in concepts:
                observations.extend(_flatten((gaap.get(concept) or {}).get("units") or {}))
            if not observations:
                continue
            duration = label in _DURATION_CONCEPTS
            annual_obs = [
                o for o in observations if o["form"] == "10-K" and (not duration or _is_annual(o))
            ]
            quarterly_obs = [
                o for o in observations if o["form"] == "10-Q" and (not duration or _is_quarter(o))
            ]
            if annual_obs:
                annual[label] = _latest(annual_obs)
            if quarterly_obs:
                quarterly[label] = _latest(quarterly_obs)
        filings = await self._filings(cik)
        return {
            "ticker": company["ticker"],
            "name": company["name"],
            "cik": cik,
            "source": {
                "name": "SEC EDGAR company facts (XBRL)",
                "url": FACTS_URL.format(cik=cik),
                "company_page": COMPANY_PAGE.format(cik=cik),
            },
            "latest_annual": annual,
            "latest_quarterly": quarterly,
            "recent_filings": filings,
        }

    async def _filings(self, cik: int) -> list[dict[str, str]]:
        payload = await self.fetcher.request(
            "GET",
            SUBMISSIONS_URL.format(cik=cik),
            subject="SEC EDGAR filings",
            ttl=6 * 3600,
            headers=_HEADERS,
        )
        recent = (
            ((payload.get("filings") or {}).get("recent") or {})
            if isinstance(payload, dict)
            else {}
        )
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        documents = recent.get("primaryDocument") or []
        filings: list[dict[str, str]] = []
        for form, filed, accession, document in zip(
            forms, dates, accessions, documents, strict=False
        ):
            if form not in _FILING_FORMS:
                continue
            folder = accession.replace("-", "")
            filings.append(
                {
                    "form": form,
                    "filed": filed,
                    "url": FILING_INDEX.format(cik=cik, accession=folder) + document,
                }
            )
            if len(filings) == 8:
                break
        return filings


def _flatten(units: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for unit, items in units.items():
        for item in items or []:
            if not isinstance(item, dict) or "val" not in item or "end" not in item:
                continue
            observations.append(
                {
                    "value": item["val"],
                    "unit": unit,
                    "start": item.get("start"),
                    "end": item["end"],
                    "fiscal_year": item.get("fy"),
                    "fiscal_period": item.get("fp"),
                    "form": item.get("form"),
                    "filed": item.get("filed"),
                    "frame": item.get("frame"),
                }
            )
    return observations


def _days(observation: dict[str, Any]) -> int | None:
    from datetime import date

    if not observation.get("start"):
        return None
    try:
        return (
            date.fromisoformat(observation["end"]) - date.fromisoformat(observation["start"])
        ).days
    except ValueError:
        return None


def _is_annual(observation: dict[str, Any]) -> bool:
    days = _days(observation)
    return days is not None and 340 <= days <= 380


def _is_quarter(observation: dict[str, Any]) -> bool:
    days = _days(observation)
    return days is not None and 80 <= days <= 100


def _latest(observations: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(observations, key=lambda o: (o["end"], o.get("filed") or ""))
    return {
        "value": best["value"],
        "unit": best["unit"],
        "period_start": best["start"],
        "period_end": best["end"],
        "fiscal_year": best["fiscal_year"],
        "fiscal_period": best["fiscal_period"],
        "form": best["form"],
        "filed": best["filed"],
    }
