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

    # Protections are compulsory since Freqtrade 2026.x moved them from the
    # config onto the strategy. A valid strategy now means one that carries its
    # own circuit breakers, so the fixture has to include them - otherwise every
    # "this should pass" case below would fail on protections_missing.
    @property
    def protections(self):
        return [
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 288,
                "trade_limit": 10,
                "stop_duration_candles": 288,
                "max_allowed_drawdown": 0.10,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 3,
                "stop_duration_candles": 96,
                "only_per_pair": False,
            },
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 12,
            },
        ]
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

# --------------------------------------------------------------------------
# Regression tests for the adversarial audit.
#
# Every case below was a CONFIRMED, executed bypass or a confirmed silent
# safety gap. They are grouped here so a future change that reopens one of them
# fails loudly in CI rather than quietly in production - where the consequence
# is arbitrary code running in the container that holds the Kraken API key.
# --------------------------------------------------------------------------
_BASE_NO_PROTECTIONS = BASE[: BASE.index("    # Protections are compulsory")]


def _swap_protections(replacement: str) -> str:
    """Replace the fixture's protections property with something else."""
    start = BASE.index("    # Protections are compulsory")
    return BASE[:start] + replacement


AUDIT_REGRESSIONS: Cases = [
    # -- F2: validator bypasses that computed a forbidden name at runtime -----
    (
        "getattr(__builtins__,'ev'+'al')",
        add_class_attr("    x = getattr(__builtins__, 'ev'+'al')"),
        "dunder_not_allowed",
    ),
    (
        "builtins.__dict__['__imp'+'ort__']",
        "import builtins\n" + BASE,
        "import_not_allowed",
    ),
    (
        "open(''.join(chr(c) for c in [...]))",
        add_class_attr("    open(''.join(chr(c) for c in [47,114,117,110]))"),
        "forbidden_name",
    ),
    (
        "getattr(object,'__subcl'+'asses__')()",
        add_class_attr("    getattr(object, '__subcl'+'asses__')()"),
        "dunder_not_allowed",
    ),
    ("import io", "import io\n" + BASE, "import_not_allowed"),
    ("relative import", "from .helpers import thing\n" + BASE, "relative_import"),
    # -- F2: the primitive that defeated every name-based check --------------
    ("getattr", add_class_attr("    x = getattr(y, 'z')"), "forbidden_name"),
    ("open", add_class_attr("    open('/etc/passwd')"), "forbidden_name"),
    ("chr", add_class_attr("    chr(65)"), "forbidden_name"),
    ("vars", add_class_attr("    vars()"), "forbidden_name"),
    # -- F2: double underscores as ATTRIBUTE, STRING, NAME and DEF ----------
    ("__dict__ attribute", add_class_attr("    x = self.__dict__"), "dunder_not_allowed"),
    ("__subclasses__ as string", add_class_attr("    x = '__subclasses__'"), "dunder_not_allowed"),
    ("__import__ as name", add_class_attr("    x = __import__"), "dunder_not_allowed"),
    ("dunder method definition", add_class_attr("    def __init__(self):\n        pass"), "dunder_not_allowed"),
    ("super().__init__()", add_class_attr("    x = super().__init__()"), "dunder_not_allowed"),
    # -- F3: a generated strategy must always carry its own safety net -------
    (
        "protections missing entirely",
        _BASE_NO_PROTECTIONS,
        "protections_missing",
    ),
    (
        "protections incomplete (MaxDrawdown only)",
        _swap_protections(
            "    @property\n"
            "    def protections(self):\n"
            "        return [\n"
            '            {"method": "MaxDrawdown", "max_allowed_drawdown": 0.1}\n'
            "        ]\n"
        ),
        "protections_incomplete",
    ),
    (
        "protections computed at runtime",
        _swap_protections(
            "    @property\n"
            "    def protections(self):\n"
            "        return build_protections()\n"
        ),
        "protections_not_readable",
    ),
    (
        "custom stop loss enabled",
        add_class_attr("    use_custom_stoploss = True"),
        "custom_stoploss_enabled",
    ),
    (
        "protections as a plain attribute, not a property",
        _swap_protections(
            '    protections = [{"method": "MaxDrawdown"}]\n'
        ),
        "protections_missing",
    ),
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
    print("Adversarial audit regressions (must all be blocked):")
    failures += _run("audit", AUDIT_REGRESSIONS, expect_block=True)

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
    for name, code, _ in MUST_BLOCK + AUDIT_REGRESSIONS + MUST_PASS:
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
    total = len(MUST_BLOCK) + len(AUDIT_REGRESSIONS) + len(MUST_PASS)
    if failures:
        print(f"FAILED - {len(failures)} problem(s) across {total} cases")
        for f in failures:
            print("   - " + f)
        return 1
    print(f"PASSED - {total} cases, all invariants held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
