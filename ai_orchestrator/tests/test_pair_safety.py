"""Tests for the pair-list safety rules.

The pair list is the one setting that decides WHAT the bot buys, and it arrives as
free text from a language model. Two rules protect it:

  * the quote currency must match the wallet, because a CAD bot cannot settle a
    BTC/USD trade and quietly accepting one leaves the operator holding a
    position in a currency they never chose;
  * leveraged tokens are refused, because they move several times faster than the
    coin they track, reset daily, and can lose most of their value even when the
    underlying is flat. A beginner holding one can be wiped out without the coin
    itself moving against them.

The rules are checked in two places on purpose: the validator stops a bad list
being *proposed*, and the handler stops one reaching the exchange. Two copies of
the rule would drift, and the copy that drifted would be the one guarding the
money - so there is one implementation, called from both, and this file proves
both call it.

Run with:
    python3 ai_orchestrator/tests/test_pair_safety.py
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

# `nl_config` reaches `freqtrade_api`, which imports aiohttp. The dev environment
# has no aiohttp and installing one would make this test need the network. The
# stub is enough: nothing here performs a request, and the rule under test is
# decided before any client is used.
if "aiohttp" not in sys.modules:
    _aiohttp = types.ModuleType("aiohttp")

    class _ClientError(Exception):
        pass

    _aiohttp.ClientError = _ClientError
    _aiohttp.ClientSession = object
    _aiohttp.ClientTimeout = lambda *a, **k: None
    _aiohttp.BasicAuth = lambda *a, **k: None
    sys.modules["aiohttp"] = _aiohttp

nl_config = importlib.import_module("ai_orchestrator.plugins.nl_config")

PASSED = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILURES.append("%s%s" % (label, (" -> " + str(detail)) if detail else ""))
        print("  [FAIL] %s%s" % (label, (" -> " + str(detail)) if detail else ""))


def plugin(quotes=None):
    """A plugin instance with only what the rule needs.

    Built with __new__ rather than __init__ so the test does not depend on the
    orchestrator, the HTTP client or the audit logger - none of which the rule
    touches. A test that needed all of those would be testing them instead.
    """
    instance = nl_config.NLConfigPlugin.__new__(nl_config.NLConfigPlugin)
    instance.logger = logging.getLogger("test")
    instance.allowed_quote_currencies = (
        tuple(quotes) if quotes else nl_config.DEFAULT_ALLOWED_QUOTES
    )
    return instance


p = plugin()

# ------------------------------------------------------------ acceptable lists
print("1. Acceptable pair lists")
for good in (["BTC/CAD"], ["BTC/CAD", "ETH/CAD"], ["XRP/CAD", "SOL/CAD", "ADA/CAD"]):
    check("%s accepted" % (good,), p._check_pair_list(good) is None, p._check_pair_list(good))

# --------------------------------------------------------- wrong quote currency
print()
print("2. Wrong quote currency is refused")
for bad in (["BTC/USD"], ["BTC/EUR"], ["ETH/USDT"], ["BTC/CAD", "ETH/USD"]):
    problem = p._check_pair_list(bad)
    check("%s refused" % (bad,), problem is not None)
    # The message has to name the offending currency, or the operator cannot tell
    # which of their pairs was the problem.
    check(
        "%s refusal names the currency" % (bad,),
        bool(problem and any(c in problem for c in ("USD", "EUR", "USDT"))),
        problem,
    )

# ------------------------------------------------------------- leveraged tokens
print()
print("3. Leveraged tokens are refused")
for bad in (["BTCUP/CAD"], ["ETHDOWN/CAD"], ["BTC3L/CAD"], ["ETH5S/CAD"], ["SOL3X/CAD"]):
    problem = p._check_pair_list(bad)
    check("%s refused" % (bad,), problem is not None)
    # It must say WHY, because "not allowed" teaches the operator nothing and
    # they will simply ask again.
    check(
        "%s refusal explains why" % (bad,),
        bool(problem and "leveraged" in problem.lower()),
        problem,
    )

# ------------------------------------------------- real coins that look similar
print()
print("4. Real coins that merely resemble a leverage marker")
# The pattern is anchored at the end for exactly this reason. Catching these
# would refuse a legitimate coin, which is a different kind of failure - it would
# silently shrink the set of things the bot can trade.
for ok in (["BULLISH/CAD"], ["UPTREND/CAD"], ["SUPER/CAD"], ["LINK/CAD"], ["DOWNTOWN/CAD"]):
    check("%s accepted" % (ok,), p._check_pair_list(ok) is None, p._check_pair_list(ok))

# ------------------------------------------------------------------- malformed
print()
print("5. Malformed and empty lists")
for bad in ([], None, "BTC/CAD", [123], [None], ["BTCCAD"], ["/CAD"], ["BTC/"], ["BTC/CAD/X"]):
    check("%r refused" % (bad,), p._check_pair_list(bad) is not None)

# --------------------------------------------------------------- normalisation
print()
print("6. Case and whitespace are normalised rather than refused")
check("lowercase accepted", p._check_pair_list(["btc/cad"]) is None, p._check_pair_list(["btc/cad"]))
check("padded accepted", p._check_pair_list(["  BTC/CAD  "]) is None, p._check_pair_list(["  BTC/CAD  "]))
# A model that writes "btc/cad" is not wrong, and refusing it would be noise.
check("the rule is case-insensitive for the marker too",
      p._check_pair_list(["btcup/cad"]) is not None)

# -------------------------------------------------------------- configurability
print()
print("7. The allowed quote list is configuration, not a hardcoded assumption")
usd = plugin(["USD"])
check("USD accepted when configured", usd._check_pair_list(["BTC/USD"]) is None,
      usd._check_pair_list(["BTC/USD"]))
check("CAD refused when only USD is configured",
      usd._check_pair_list(["BTC/CAD"]) is not None)
multi = plugin(["CAD", "USD"])
check("both accepted when both are configured",
      multi._check_pair_list(["BTC/CAD", "ETH/USD"]) is None,
      multi._check_pair_list(["BTC/CAD", "ETH/USD"]))

# ------------------------------------------------- the handler's own guard
print()
print("8. The handler refuses independently of the validator")


class _FakeClient:
    """Records whether the exchange was reached.

    The point of this section is that a bad list must never get as far as the
    API call, so the test asserts on `called` and not only on the return value.
    A refusal that still called the exchange would be no refusal at all.
    """

    def __init__(self):
        self.called = False

    async def set_whitelist(self, pairs):
        self.called = True
        return {"ok": True}


for bad in (["BTC/USD"], ["BTCUP/CAD"], []):
    handler = plugin()
    handler.freqtrade = _FakeClient()
    result = asyncio.run(handler._handle_restrict_pairs({"pairs": bad}))
    check("handler refuses %s" % (bad,), result["status"] == "refused", result)
    check("handler did not reach the exchange for %s" % (bad,), handler.freqtrade.called is False)

handler = plugin()
handler.freqtrade = _FakeClient()
result = asyncio.run(handler._handle_restrict_pairs({"pairs": ["BTC/CAD"]}))
check("handler allows a valid list", result["status"] == "success", result)
check("handler did reach the exchange for a valid list", handler.freqtrade.called is True)

# The validator and the handler must agree. If the handler were stricter, a
# proposal would be approved and then fail; if it were looser, the validator
# would be decorative.
print()
print("9. The two gates agree")
for pairs in (["BTC/CAD"], ["BTC/USD"], ["BTCUP/CAD"], []):
    validator_says = p._check_pair_list(pairs) is None
    handler = plugin()
    handler.freqtrade = _FakeClient()
    handler_says = asyncio.run(handler._handle_restrict_pairs({"pairs": pairs}))["status"] == "success"
    check("%s judged the same by both gates" % (pairs,), validator_says == handler_says,
          "validator=%s handler=%s" % (validator_says, handler_says))


print()
print("=" * 70)
if FAILURES:
    print("FAILED: %d of %d" % (len(FAILURES), PASSED + len(FAILURES)))
    for failure in FAILURES:
        print("  - %s" % failure)
    sys.exit(1)
print("PASSED: %d checks" % PASSED)
print("Pair-list safety rules hold.")
