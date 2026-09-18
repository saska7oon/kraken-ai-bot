#!/usr/bin/env python3
"""Check that simulated trading is charged what Kraken actually charges.

Why this needs a test
---------------------
The wrong value produces no error, no warning and no failing log line. Backtests
and dry-run simply report better results than reality, and the operator has no way
to tell - which is the worst possible failure mode for a number that decides
whether a strategy looks profitable.

What was actually wrong
-----------------------
No `fee` was set, so Freqtrade asked ccxt for the exchange's rate. ccxt reads the
market's `taker` field, which Kraken's API returns EMPTY (verified live: `"fees": []`
and `"fees_maker": []` on XBTCAD), so ccxt fell back to its own hardcoded default of
0.0026 taker. Kraken's published Tier 1 rate is 0.80% taker - three times higher.

    0.26% x 2 = 0.52% round trip assumed
    0.80% x 2 = 1.60% round trip actual

On a 5-minute timeframe that gap is decisive: the mean BTC/CAD 5m candle moves
0.076% in total, so the fee is roughly 21 candles' worth of movement to break even.

This test pins the number, and pins the reason for it, so that neither the value
nor its justification can quietly disappear.

What is checked
---------------
 1. `fee` is set explicitly - the whole point is not to inherit a library default.
 2. It is at least Kraken's Tier 1 taker rate. Under-charging is the failure this
    exists to catch; over-charging is merely conservative.
 3. It is not absurdly high, which would make every strategy look unviable and
    send someone hunting for a bug that is not there.
 4. The canada_kraken overlay does not silently override it.
 5. The fee is documented in the config, because the number is only defensible
    alongside the reasoning that produced it.

Note the asymmetry in (2) and (3): a range, not an equality. Pinning the exact
value would fail the moment Kraken changes its schedule, and the useful question is
"is this at least realistic", not "is this exactly 0.008".
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from preflight_config import load_config  # noqa: E402

BASE = REPO / "config" / "base.json"
CANADA = REPO / "config" / "canada_kraken.json"

#: Kraken Tier 1, $0+ 30-day volume, from kraken.com/ca/features/fee-schedule.
#: Taker, because the bot's limit orders sit at the touch of the book where they
#: often fill immediately and are charged as taker.
KRAKEN_TIER1_TAKER = 0.008
#: ccxt's hardcoded fallback, which was silently in use. Named so a regression to
#: it is recognisable rather than merely "too low".
CCXT_DEFAULT_TAKER = 0.0026

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  ok    {label}")
    else:
        FAILURES.append(label)
        print(f"  FAIL  {label}{(' — ' + detail) if detail else ''}")


def main() -> int:
    print("=" * 70)
    print("Simulated trading must be charged Kraken's real fee")
    print("=" * 70)

    base = load_config(BASE)
    canada = load_config(CANADA)
    fee = base.get("fee")

    print("\nThe fee is set explicitly:")
    if fee is None:
        check("fee is present in base.json", False,
              "absent — Freqtrade will inherit ccxt's %.4f default" % CCXT_DEFAULT_TAKER)
        print()
        print("=" * 70)
        print("FAILED — the fee is unset, so simulations understate cost")
        return 1
    check("fee is present in base.json", True)

    print("\nIt is realistic:")
    check(
        "at least Kraken's Tier 1 taker rate (%.2f%%)" % (KRAKEN_TIER1_TAKER * 100),
        fee >= KRAKEN_TIER1_TAKER,
        "%.4f is below it — this is the under-charging bug" % fee,
    )
    check(
        "not above 1.5%% per side",
        fee <= 0.015,
        "%.4f would make every strategy look unviable" % fee,
    )
    check(
        "not the ccxt default (%.2f%%)" % (CCXT_DEFAULT_TAKER * 100),
        abs(fee - CCXT_DEFAULT_TAKER) > 1e-9,
        "this is the exact value that was silently in use",
    )

    print("\nThe overlay does not undo it:")
    check(
        "canada_kraken.json does not set a lower fee",
        canada.get("fee") is None or canada.get("fee") >= KRAKEN_TIER1_TAKER,
        "overlay fee is %r" % canada.get("fee"),
    )

    print("\nIt is documented:")
    raw = BASE.read_text(encoding="utf-8")
    # The number is only defensible next to its reasoning. A bare "fee": 0.008
    # invites someone to "fix" it back down.
    for needed, why in (
        ("Tier 1", "names the tier the rate comes from"),
        ("0.80", "records Kraken's actual taker rate"),
        ("ccxt", "records what was silently used instead"),
        ("dry_run", "notes it only affects simulation"),
    ):
        check(f"the comment {why}", needed in raw)

    print("\nWhat this means in practice:")
    print(f"    assumed round trip before : {CCXT_DEFAULT_TAKER * 2 * 100:.2f}%")
    print(f"    charged now               : {fee * 2 * 100:.2f}%")
    print(f"    it was                    : {(fee * 2) / (CCXT_DEFAULT_TAKER * 2):.1f}x too optimistic")

    print()
    print("=" * 70)
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} of {CHECKS} checks")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print(f"PASSED — {CHECKS} checks: simulations are charged Kraken's real fee")
    return 0


if __name__ == "__main__":
    sys.exit(main())
