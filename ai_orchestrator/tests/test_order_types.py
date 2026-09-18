#!/usr/bin/env python3
"""Check that the bot actually pays the maker rate it is configured for.

The trap
--------
Whether a bot pays 0.40% or 0.80% per trade is decided by an interaction between
two config keys that never appear together and are documented separately:

    order_types.entry          "limit"
    entry_pricing.price_side   "same"

"limit" alone does NOT mean maker. A limit order that crosses the spread is a taker
order - it is the *combination* that decides. From
freqtrade/exchange/exchange.py::_get_price_side:

    ("entry", "long", "same"):  "bid"    resting buy  -> maker
    ("entry", "long", "other"): "ask"    crossing buy -> taker
    ("exit",  "long", "same"):  "ask"    resting sell -> maker
    ("exit",  "long", "other"): "bid"    crossing sell-> taker

So flipping price_side from "same" to "other" doubles the fee on both legs, and
nothing errors, nothing warns, and the config still reads "limit" in both places.
The only visible symptom is that the account bleeds faster than the backtest said.

This was not hypothetical. The fee block in base.json originally justified its
taker-rate number with the claim that price_side "same" fills immediately as taker.
That was backwards. The bot had been paying maker all along and the written
reasoning was wrong in a way no test would have caught, because no test read the
mapping.

What is checked
---------------
 1. entry and exit are limit orders, and price_side is the resting side for both,
    so the maker rate applies.
 2. stoploss and emergency_exit are market orders. This is deliberate - a limit
    stoploss at a running price does not fill - and it is also why the `fee` is
    charged at the taker rate.
 3. An unfilled-order timeout exists. A resting order that is never reached would
    otherwise sit forever.
 4. The fee is not below the maker rate, since even the best case costs that much.
 5. The reasoning is recorded, including the correction, so the next person does
    not repeat the mistake in either direction.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from preflight_config import load_config  # noqa: E402

BASE = REPO / "config" / "base.json"

#: Verified from Kraken's published schedule, kraken.com/ca/features/fee-schedule.
KRAKEN_TIER1_MAKER = 0.004
KRAKEN_TIER1_TAKER = 0.008

#: The resting side for each leg, from freqtrade's own price_map.
#: "same" on a long entry is the bid; "same" on a long exit is the ask.
RESTING_SIDE = {"entry_pricing": "same", "exit_pricing": "same"}

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
    print("=" * 72)
    print("The bot must pay the maker rate it is configured for")
    print("=" * 72)

    cfg = load_config(BASE)
    ot = cfg.get("order_types") or {}
    fee = cfg.get("fee")

    print("\nBoth legs rest on the book (maker):")
    for leg in ("entry", "exit"):
        check(
            f"order_types.{leg} is limit",
            ot.get(leg) == "limit",
            f"is {ot.get(leg)!r} — a market order is a taker order",
        )
    for block, expected in RESTING_SIDE.items():
        pricing = cfg.get(block) or {}
        side = pricing.get("price_side")
        check(
            f"{block}.price_side is {expected!r} (resting)",
            side == expected,
            f"is {side!r} — 'other' crosses the spread and pays "
            f"{KRAKEN_TIER1_TAKER*100:.2f}% instead of {KRAKEN_TIER1_MAKER*100:.2f}%",
        )

    print("\nThe exit paths that must NOT rest:")
    for leg in ("stoploss", "emergency_exit"):
        check(
            f"order_types.{leg} is market",
            ot.get(leg) == "market",
            f"is {ot.get(leg)!r} — a limit order at a running price does not fill, "
            "and the position is kept along with the loss",
        )

    print("\nAn unfilled order does not sit forever:")
    timeout = cfg.get("unfilledtimeout") or {}
    check("unfilledtimeout is set", bool(timeout), "absent — resting orders never expire")
    for leg in ("entry", "exit"):
        val = timeout.get(leg)
        check(
            f"unfilledtimeout.{leg} is a positive number",
            isinstance(val, (int, float)) and val > 0,
            f"is {val!r}",
        )

    print("\nThe simulated fee is not below the floor:")
    check("fee is present", fee is not None, "absent")
    if fee is not None:
        check(
            f"fee >= the maker rate ({KRAKEN_TIER1_MAKER*100:.2f}%)",
            fee >= KRAKEN_TIER1_MAKER,
            f"{fee} is below even the best case",
        )
        # The fee is charged at taker on purpose. If someone lowers it to the maker
        # rate, the stoploss exits become under-charged - so this asserts the
        # reasoning is still present rather than pinning the value.
        raw = BASE.read_text(encoding="utf-8")
        check(
            "the taker-rate choice is explained",
            "stoploss" in raw and "adverse selection" in raw,
            "the justification for charging taker is missing",
        )

    print("\nThe correction is recorded:")
    raw = BASE.read_text(encoding="utf-8")
    low = raw.lower()
    check(
        "the price_side mapping is documented",
        '"bid"' in low and "maker" in low,
        "the mapping that decides maker vs taker is not written down",
    )

    print()
    print("  What the configuration actually costs:")
    print(f"    normal path  entry maker {KRAKEN_TIER1_MAKER*100:.2f}% + "
          f"exit maker {KRAKEN_TIER1_MAKER*100:.2f}% = "
          f"{KRAKEN_TIER1_MAKER*2*100:.2f}% round trip")
    print(f"    stoploss     entry maker {KRAKEN_TIER1_MAKER*100:.2f}% + "
          f"exit taker {KRAKEN_TIER1_TAKER*100:.2f}% = "
          f"{(KRAKEN_TIER1_MAKER+KRAKEN_TIER1_TAKER)*100:.2f}% round trip")
    print(f"    simulated as {fee*2*100:.2f}% (taker both sides, deliberately "
          "pessimistic)")

    print()
    print("=" * 72)
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} of {CHECKS} checks")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print(f"PASSED — {CHECKS} checks: the bot rests on the book and pays maker")
    return 0


if __name__ == "__main__":
    sys.exit(main())
