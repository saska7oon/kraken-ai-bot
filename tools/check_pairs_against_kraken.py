#!/usr/bin/env python3
"""Check the configured pair whitelist against Kraken's real market list.

Why this exists
---------------
ADA/CAD was added to the whitelist on the strength of Kraken's public
`/convert/ada/cad` page. That page shows a *converted price*; it is not an order
book, and ADA/CAD is not a Kraken market. Kraken lists ADA against AUD, EUR,
GBP, USD, USDC, USDT, XBT and ETH - not CAD.

Nothing in the repo caught it. Freqtrade did, at runtime, by quietly dropping
the pair:

    WARNING - Pair ADA/CAD is not compatible with exchange Kraken.
              Removing it from whitelist..
    INFO - Whitelist with 4 pairs: ['BTC/CAD', 'ETH/CAD', 'SOL/CAD', 'XRP/CAD']

A silent drop is a poor way to find out. The bot ran, the whitelist looked
populated in the config, and the only sign anything was wrong was a warning line
in a log nobody reads until something else breaks. Worse, the AI's context
prompts still said the bot traded ADA/CAD, so the assistant would have answered
questions about a pair that did not exist.

This checks the same thing freqtrade checks, at build time, against the
exchange's own market list - the source of truth that a marketing page is not.

Usage
-----
    python3 tools/check_pairs_against_kraken.py
    python3 tools/check_pairs_against_kraken.py --config config/canada_kraken.json

Exit codes
----------
    0  every configured pair is a real Kraken market (or the API was unreachable
       and the check was skipped, which is reported as a skip, not a pass)
    1  a configured pair is not a Kraken market
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ASSET_PAIRS_URL = "https://api.kraken.com/0/public/AssetPairs"
DEFAULT_CONFIG = pathlib.Path("config/canada_kraken.json")
TIMEOUT = 45


def _strip_jsonc(raw: str) -> str:
    """Freqtrade configs are JSON with // and /* */ comments."""
    raw = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
    return re.sub(r"/\*.*?\*/", "", raw, flags=re.S)


def load_whitelist(path: pathlib.Path) -> list[str]:
    data = json.loads(_strip_jsonc(path.read_text(encoding="utf-8")))
    pairs = data.get("exchange", {}).get("pair_whitelist")
    if not pairs:
        raise SystemExit(f"FAIL - no exchange.pair_whitelist found in {path}")
    return list(pairs)


def fetch_markets() -> dict | None:
    """Return Kraken's markets, or None if it could not be reached."""
    try:
        with urllib.request.urlopen(ASSET_PAIRS_URL, timeout=TIMEOUT) as r:
            payload = json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        print(f"SKIPPED - could not reach Kraken ({type(e).__name__}: {e})")
        print("          this is a skip, not a pass: the whitelist was NOT checked")
        return None

    if payload.get("error"):
        print(f"SKIPPED - Kraken returned an error: {payload['error']}")
        return None
    return payload["result"]


def build_index(markets: dict) -> tuple[set[str], set[str]]:
    """Every name a pair might legitimately be written as.

    Kraken uses legacy asset codes (XBT for BTC, XDG for DOGE) and reports both
    a `wsname` like "XBT/CAD" and an `altname` like "XBTCAD". Freqtrade accepts
    the modern spelling, so both are indexed rather than assuming one form.
    """
    names: set[str] = set()
    quotes: set[str] = set()
    for raw_name, info in markets.items():
        ws = info.get("wsname") or raw_name
        alt = info.get("altname") or ""
        names.add(ws.upper())
        names.add(raw_name.upper())
        if alt:
            names.add(alt.upper())
            # altname has no separator: XBTCAD -> XBT/CAD
            for q in ("CAD", "USD", "EUR", "GBP", "AUD", "USDT", "USDC", "XBT", "ETH"):
                if alt.upper().endswith(q) and len(alt) > len(q):
                    names.add(f"{alt[:-len(q)]}/{q}".upper())
                    break
        q = info.get("quote", "")
        if q:
            quotes.add(q.upper())
    # Modern spellings for Kraken's legacy codes.
    for legacy, modern in (("XBT", "BTC"), ("XDG", "DOGE"), ("XETC", "ETC")):
        for n in list(names):
            if legacy in n:
                names.add(n.replace(legacy, modern))
    return names, quotes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG),
                    help="config file to read exchange.pair_whitelist from")
    args = ap.parse_args()

    cfg = pathlib.Path(args.config)
    if not cfg.exists():
        print(f"FAIL - config not found: {cfg}")
        return 1

    whitelist = load_whitelist(cfg)
    print(f"Configured pairs ({cfg}): {whitelist}")

    markets = fetch_markets()
    if markets is None:
        return 0

    names, _ = build_index(markets)
    print(f"Kraken reports {len(markets)} markets")

    bad = []
    print()
    for pair in whitelist:
        ok = pair.upper() in names
        print(f"  {'ok  ' if ok else 'FAIL'} {pair}")
        if not ok:
            bad.append(pair)

    # Show what the quote currency does offer, so a wrong symbol can be fixed
    # without a second round trip.
    for pair in bad:
        quote = pair.split("/")[-1].upper()
        siblings = sorted({
            (i.get("wsname") or n) for n, i in markets.items()
            if i.get("quote", "").upper() in (quote, "Z" + quote)
            and "/" in (i.get("wsname") or "")
        })
        print()
        print(f"  {quote} markets that DO exist on Kraken ({len(siblings)}):")
        for s in siblings:
            print(f"    {s}")
        base = pair.split("/")[0].upper()
        base_quotes = sorted({
            (i.get("wsname") or n) for n, i in markets.items()
            if (i.get("wsname") or "").upper().startswith(base + "/")
        })
        if base_quotes:
            print(f"  {base} markets that DO exist ({len(base_quotes)}):")
            for s in base_quotes:
                print(f"    {s}")
        else:
            print(f"  {base} is not listed on Kraken at all")

    print()
    if bad:
        print(f"FAILED - {len(bad)} pair(s) are not Kraken markets: {', '.join(bad)}")
        print("         Freqtrade would drop these silently at startup.")
        return 1
    print("PASSED - every configured pair is a real Kraken market")
    return 0


if __name__ == "__main__":
    sys.exit(main())
