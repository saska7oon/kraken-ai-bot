"""
Regression tests for the strategy safety validator.

Run with:

    python3 -m ai_orchestrator.tests.test_proposal_validator

No third-party test framework is required, so this runs anywhere the
orchestrator source is present - including inside the container, where the
real dependency set is installed.

The cases marked "bypass" are the ones that were found by adversarially
attacking the validator after its first version was written. They all passed
validation before the fixes; each one is now a permanent regression guard.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Callable, List, Tuple

from ai_orchestrator.core.proposal_validator import validate_strategy_code

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
BASE = '''
from freqtrade.strategy import IStrategy

class TestStrat(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    stoploss = -0.08
    minimal_roi = {"0": 0.04, "60": 0.02}

    def populate_indicators(self, dataframe, metadata):
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe
'''

_ROI_LINE = '    minimal_roi = {"0": 0.04, "60": 0.02}'


def add_class_attr(snippet: str) -> str:
    """Insert lines into the strategy class body."""
    return BASE.replace(_ROI_LINE, _ROI_LINE + "\n" + snippet)


def replace(line: str, replacement: str) -> str:
    return BASE.replace(line, replacement)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_STRATEGY = REPO_ROOT / "config" / "strategies" / "moderate_multi.py"


# --------------------------------------------------------------------------
# Cases: (name, code, expected_error_code)
#
# expected_error_code of None means "must validate cleanly".
# --------------------------------------------------------------------------
Cases = List[Tuple[str, str, "str | None"]]

MUST_BLOCK: Cases = [
    # --- the four bypasses found by adversarial review -------------------
    (
        "bypass: duplicate stoploss (safe first, unsafe last)",
        replace("    stoploss = -0.08", "    stoploss = -0.08\n    stoploss = -0.30"),
        "stoploss_too_wide",
    ),
    (
        "bypass: duplicate leverage",
        add_class_attr("    leverage = 1.0\n    leverage = 10"),
        "leverage_not_one",
    ),
    (
        "bypass: duplicate can_short",
        add_class_attr("    can_short = False\n    can_short = True"),
        "can_short_enabled",
    ),
    (
        "bypass: open() reads the Kraken key (no import needed)",
        add_class_attr("    LEAK = open('/run/secrets/kraken_api_key').read()"),
        "secret_access",
    ),
    (
        "bypass: margin_mode set",
        add_class_attr('    margin_mode = "isolated"'),
        "margin_mode_set",
    ),
    (
        "bypass: trading_mode futures",
        add_class_attr('    trading_mode = "futures"'),
        "trading_mode_not_spot",
    ),
    (
        "bypass: leveraged token in a class pair list",
        add_class_attr('    pairs = ["BTCUP/CAD"]'),
        "leveraged_pair",
    ),
    (
        "bypass: inverse token in pair_whitelist",
        add_class_attr('    pair_whitelist = ["ETH3L/CAD"]'),
        "leveraged_pair",
    ),
    (
        "bypass: short token in pairs",
        add_class_attr('    pairs = ["BCHSHORT/USD"]'),
        "leveraged_pair",
    ),
    # --- pre-existing checks, kept as guards -----------------------------
    ("stoploss too wide", add_class_attr("    stoploss = -0.30"), "stoploss_too_wide"),
    ("stoploss too tight", add_class_attr("    stoploss = -0.005"), "stoploss_too_tight"),
    ("stoploss missing", BASE.replace("    stoploss = -0.08\n", ""), "stoploss_missing"),
    ("leverage 10", add_class_attr("    leverage = 10"), "leverage_not_one"),
    ("can_short True", add_class_attr("    can_short = True"), "can_short_enabled"),
    ("import os", "import os\n" + BASE, "forbidden_import"),
    ("import subprocess", "import subprocess\n" + BASE, "forbidden_import"),
    ("import socket", "import socket\n" + BASE, "forbidden_import"),
    ("import requests", "import requests\n" + BASE, "forbidden_import"),
    ("eval()", add_class_attr("    X = eval('1+1')"), "forbidden_call"),
    ("position adjustment", add_class_attr("    position_adjustment_enable = True"),
     "position_adjustment_enabled"),
    ("syntax error", "this is not python ((", "syntax_error"),
    ("no stoploss at all", BASE.replace("    stoploss = -0.08\n", ""), "stoploss_missing"),
]

MUST_PASS: Cases = [
    ("plain valid strategy", BASE, None),
    ("CAD pairs", add_class_attr('    pairs = ["BTC/CAD", "ETH/CAD"]'), None),
    ("spot trading_mode", add_class_attr('    trading_mode = "spot"'), None),
    ("lambda in class body", add_class_attr("    F = lambda x: x + 1"), None),
    (
        "inert string mentioning a secret path",
        add_class_attr('    """we never read /run/secrets here"""\n    X = 1'),
        None,
    ),
    (
        "docstring URL",
        BASE.replace('"""\nfrom freqtrade', '"""See https://www.freqtrade.io\n"""\nfrom freqtrade'),
        None,
    ),
]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
def _run(label: str, cases: Cases, expect_block: bool) -> List[str]:
    failures: List[str] = []
    for name, code, expected_code in cases:
        result = validate_strategy_code(code, profile="moderate")
        codes = [issue.code for issue in result.errors()]

        if expect_block:
            if not codes:
                failures.append(f"{label}: '{name}' was ALLOWED but must be blocked")
            elif expected_code and expected_code not in codes:
                failures.append(
                    f"{label}: '{name}' blocked as {codes}, expected to include "
                    f"'{expected_code}'"
                )
        else:
            if codes:
                failures.append(f"{label}: '{name}' was BLOCKED but must pass: {codes}")
        print(f"  {'ok  ' if not _failed(failures, label, name) else 'FAIL'}  {name}")
    return failures


def _failed(failures: List[str], label: str, name: str) -> bool:
    return any(name in f for f in failures)


def main() -> int:
    failures: List[str] = []

    print("Must be blocked:")
    failures += _run("block", MUST_BLOCK, expect_block=True)

    print()
    print("Must pass:")
    failures += _run("pass", MUST_PASS, expect_block=False)

    print()
    print("Real strategy in this repository:")
    if REAL_STRATEGY.exists():
        result = validate_strategy_code(REAL_STRATEGY.read_text(), profile="moderate")
        codes = [issue.code for issue in result.errors()]
        if codes:
            failures.append(f"real strategy failed validation: {codes}")
            print(f"  FAIL  {REAL_STRATEGY.name} -> {codes}")
        else:
            print(f"  ok    {REAL_STRATEGY.name} (0 errors)")
    else:
        print(f"  skip  {REAL_STRATEGY} not found")

    print()
    print("Invariants (every case):")
    invariant_failures: List[str] = []
    for name, code, _ in MUST_BLOCK + MUST_PASS:
        result = validate_strategy_code(code, profile="moderate")
        if result.ok != (len(result.errors()) == 0):
            invariant_failures.append(f"{name}: ok flag disagrees with error count")
        for issue in result.issues:
            if issue.severity not in ("error", "warning"):
                invariant_failures.append(f"{name}: bad severity {issue.severity!r}")
            if not issue.code or not issue.message:
                invariant_failures.append(f"{name}: empty code or message")
        try:
            result.summary()
        except Exception as exc:  # summary() must never raise
            invariant_failures.append(f"{name}: summary() raised {exc!r}")

    # The validator must never raise, whatever it is handed.
    for junk in (None, 123, "", "def f(:", b"\x00\x01\x02", "x" * 100000):
        try:
            validate_strategy_code(junk)  # type: ignore[arg-type]
        except Exception as exc:
            invariant_failures.append(f"non-string input {junk!r} raised {exc!r}")

    if invariant_failures:
        failures += invariant_failures
        for f in invariant_failures:
            print("  FAIL  " + f)
    else:
        print("  ok    ok-flag consistency, severities, messages, summary(), no-raise")

    print()
    print("=" * 66)
    total = len(MUST_BLOCK) + len(MUST_PASS)
    if failures:
        print(f"FAILED - {len(failures)} problem(s) across {total} cases")
        for f in failures:
            print("   - " + f)
        return 1
    print(f"PASSED - {total} cases, all invariants held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
