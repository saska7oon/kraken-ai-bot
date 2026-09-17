"""Tests for presenting a strategy to someone who does not read code.

The operator is a beginner. A stat card reading "ModerateMultiPairStrategy" tells
them nothing about what their money is doing, and the fix for that is the subject
of this file.

Run with:
    python3 ai_orchestrator/tests/test_strategy_naming.py

Two properties matter here and they pull in opposite directions:

  * A readable name must ALWAYS exist, because a blank label where a strategy
    should be reads as a broken bot. So the name is derived from the class name,
    which every strategy has, rather than only from a description the strategy
    may not carry.

  * A missing description must never be invented. "Could not determine" and
    "there is none" are different answers, and the UI has to be able to tell
    them apart to avoid printing an empty line or, worse, a plausible guess.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ai_orchestrator.core.strategy_inspector import (  # noqa: E402
    describe_strategy,
    friendly_strategy_name,
    read_strategy_description,
)

PASSED = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
        print("  [PASS] %s" % label)
    else:
        FAILURES.append("%s%s" % (label, (" -> " + detail) if detail else ""))
        print("  [FAIL] %s%s" % (label, (" -> " + detail) if detail else ""))


def eq(label: str, actual, expected) -> None:
    check(label, actual == expected, "got %r, expected %r" % (actual, expected))


REPO = pathlib.Path(__file__).resolve().parents[2]
STRATEGIES = REPO / "config" / "strategies"


# ---------------------------------------------------------------- readable names
print("1. Readable names")
eq("the shipped strategy reads as English",
   friendly_strategy_name("ModerateMultiPairStrategy"), "Moderate multi-pair")
eq("an acronym stays uppercase", friendly_strategy_name("RSIMeanReversion"), "RSI mean reversion")
eq("a short acronym stays uppercase", friendly_strategy_name("EmaTrendStrategy"), "EMA trend")
eq("a compound modifier is hyphenated",
   friendly_strategy_name("MultiTimeframeTrendStrategy"), "Multi-timeframe trend")
eq("a version suffix stays attached to a one-letter word",
   friendly_strategy_name("MyCoolBot_v2"), "My cool bot v2")
eq("a version suffix separates from a real word",
   friendly_strategy_name("MultiPair2Strategy"), "Multi-pair 2")
eq("the Strategy suffix is dropped", friendly_strategy_name("BreakoutStrategy"), "Breakout")
eq("a strategy literally named Strategy keeps its name",
   friendly_strategy_name("Strategy"), "Strategy")
eq("a lowercase name is capitalised", friendly_strategy_name("dip_buyer"), "Dip buyer")

# The label must never be blank for a real name, or the card shows nothing and
# the operator cannot tell whether the bot is running a strategy at all.
for odd in ["A", "Z9", "X_", "a" * 120, "Ünicode", "123", "9Lives", "CamelCASE", "snake_case"]:
    result = friendly_strategy_name(odd)
    check("%r produces a non-empty label" % odd[:20], bool(result.strip()), repr(result))
    check("%r does not leak the Strategy suffix" % odd[:20],
          not (result.endswith("Strategy") and odd != "Strategy"), repr(result))

# Empty and non-string input must not raise: this is called with whatever the
# bot's config happens to contain.
for nothing in ["", "   ", None, 123, [], {}]:
    try:
        eq("%r yields no label" % (nothing,), friendly_strategy_name(nothing), "")
    except Exception as exc:  # noqa: BLE001
        check("%r does not raise" % (nothing,), False, repr(exc))


# ------------------------------------------------------------ reading a strategy
print()
print("2. Reading the shipped strategy")
described = describe_strategy("ModerateMultiPairStrategy", STRATEGIES)
eq("the class name is reported", described["class_name"], "ModerateMultiPairStrategy")
eq("the readable name is reported", described["friendly_name"], "Moderate multi-pair")
check("a description is found", bool(described["description"]), str(described))
check("the description is the authored one, not the docstring",
      described["description_source"] == "strategy:DESCRIPTION",
      str(described["description_source"]))
check("the description is prose, not an identifier",
      " " in (described["description"] or ""), str(described["description"]))

# The docstring is the fallback when a strategy has no DESCRIPTION attribute, so
# a strategy from elsewhere still gets described.
docstring_only = read_strategy_description("ModerateMultiPairStrategy", STRATEGIES)
check("a description is returned for the shipped strategy", bool(docstring_only))


# ----------------------------------------------------- unknown is not "none"
print()
print("3. Unknown is not the same as none")
unknown = describe_strategy("NoSuchStrategyAtAll", STRATEGIES)
check("a missing strategy still gets a readable name",
      unknown["friendly_name"] == "No such strategy at all", str(unknown))
eq("a missing strategy has no description", unknown["description"], None)
eq("a missing strategy has no description source", unknown["description_source"], None)

# A junk value must not be echoed back as though it were a strategy. This is the
# value that ends up in a config file, so it is not trusted.
for junk in ["../../etc/passwd", "a/b", "name;rm -rf /", "", None, "has space", "a" * 200]:
    result = describe_strategy(junk, STRATEGIES)
    eq("%r is not reported as a strategy" % (junk,), result["class_name"], None)
    eq("%r yields no label" % (junk,), result["friendly_name"], None)

# A missing directory is "unknown", not an exception and not an empty string.
missing_dir = describe_strategy("ModerateMultiPairStrategy", "/nonexistent/dir")
eq("a missing directory yields no description", missing_dir["description"], None)
check("a missing directory still yields a readable name",
      missing_dir["friendly_name"] == "Moderate multi-pair", str(missing_dir))


# ------------------------------------------------------- what the UI receives
print()
print("4. The shape the UI depends on")
required = {"class_name", "friendly_name", "description", "description_source"}
eq("every key the UI reads is present", set(described), required)
eq("the unknown case has the same keys", set(unknown), required)

# The UI does `s.friendly_name || s.strategy`, so an empty string would fall
# through to the class name. That is a safe fallback, but it means an empty
# string here is a silent regression, so it is checked rather than assumed.
for name in ["ModerateMultiPairStrategy", "BreakoutStrategy", "X"]:
    value = describe_strategy(name, STRATEGIES)["friendly_name"]
    check("%s never yields an empty friendly_name" % name, bool(value and value.strip()), repr(value))


print()
print("=" * 70)
if FAILURES:
    print("FAILED: %d of %d" % (len(FAILURES), PASSED + len(FAILURES)))
    for failure in FAILURES:
        print("  - %s" % failure)
    sys.exit(1)
print("PASSED: %d checks" % PASSED)
print("Strategy naming behaves correctly.")
