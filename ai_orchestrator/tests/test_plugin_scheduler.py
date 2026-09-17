"""
Plugin scheduler regression tests.
==================================

Standalone (no pytest) so it runs anywhere, including CI with no dependencies:

    python3 ai_orchestrator/tests/test_plugin_scheduler.py

Why this file exists
--------------------
The scheduler used to parse a cron expression as:

    if hour_spec != "*" and int(hour_spec) != now.hour:

Two defects followed from that single line, and both were live in the shipped
configuration:

1. ``int("*/6")`` raises ``ValueError: invalid literal for int() with base 10:
   '*/6'``. ``param_optimizer`` is scheduled ``0 */6 * * *``, so it raised every
   time the scheduler looked at it. The exception was caught per-plugin, so the
   symptom was not a crash but a plugin that silently never ran - and an
   operator cannot distinguish "idle by design" from "broken" without a test
   like this one.

2. Day, month and weekday were never examined at all. ``strategy_generator`` is
   scheduled ``0 2 * * 0``, intended as Sundays only, but it actually fired
   EVERY day at 02:00 - seven times the intended AI spend, against a free tier
   with a daily request cap. A schedule that quietly means something other than
   what it says is worse than one that fails loudly, because nobody goes looking.

The lesson encoded here: a schedule is a promise about how often something
spends money and calls an external API. It deserves a test.
"""

from __future__ import annotations

import ast
import pathlib
import sys
from datetime import datetime
from typing import List, Optional, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MANAGER = REPO_ROOT / "ai_orchestrator" / "core" / "plugin_manager.py"


def _load_scheduler():
    """Extract the real methods from plugin_manager without importing it.

    Importing the module would drag in FastAPI and friends, which are not
    installed in every environment this test needs to run in. Parsing the source
    keeps the test honest - it exercises the shipped code, not a copy.
    """
    src = MANAGER.read_text()
    tree = ast.parse(src)

    namespace = {
        "datetime": datetime,
        "Optional": Optional,
        "logger": type("_L", (), {"warning": staticmethod(lambda *a, **k: None)})(),
    }

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
            "_cron_field_matches",
            "_should_run",
        ):
            segment = ast.get_source_segment(src, node).replace("@staticmethod", "")
            exec(segment, namespace)  # noqa: S102 - parsing our own source
            found.add(node.name)

    missing = {"_cron_field_matches", "_should_run"} - found
    if missing:
        raise AssertionError(f"scheduler methods missing from {MANAGER}: {missing}")

    class _Scheduler:
        _cron_field_matches = staticmethod(namespace["_cron_field_matches"])
        _should_run = namespace["_should_run"]

    return _Scheduler()


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------
#: The schedules that are actually configured. Every one of these must be
#: parseable; a failure here means a plugin silently never runs.
CONFIGURED: List[Tuple[str, str]] = [
    ("explainer", "0 8 * * *"),
    ("strategy_generator", "0 2 * * 0"),
    ("market_analyst", "0 * * * *"),
    ("param_optimizer", "0 */6 * * *"),
]

#: (expression, moment, expected, description)
MATCH_CASES: List[Tuple[str, datetime, bool, str]] = [
    ("* * * * *", datetime(2026, 3, 15, 13, 37), True, "every minute"),
    ("0 * * * *", datetime(2026, 3, 15, 13, 0), True, "hourly, on the hour"),
    ("0 * * * *", datetime(2026, 3, 15, 13, 5), False, "hourly, not at :05"),
    ("0 8 * * *", datetime(2026, 3, 15, 8, 0), True, "daily at 08:00"),
    ("0 8 * * *", datetime(2026, 3, 15, 9, 0), False, "not 09:00"),
    ("0 */6 * * *", datetime(2026, 3, 15, 0, 0), True, "every 6h at 00:00"),
    ("0 */6 * * *", datetime(2026, 3, 15, 6, 0), True, "every 6h at 06:00"),
    ("0 */6 * * *", datetime(2026, 3, 15, 12, 0), True, "every 6h at 12:00"),
    ("0 */6 * * *", datetime(2026, 3, 15, 13, 0), False, "every 6h, not 13:00"),
    # 2026-03-15 is a Sunday; 2026-03-16 is a Monday.
    ("0 2 * * 0", datetime(2026, 3, 15, 2, 0), True, "Sundays only (Sunday)"),
    ("0 2 * * 0", datetime(2026, 3, 16, 2, 0), False, "Sundays only (Monday)"),
    ("0 2 * * 7", datetime(2026, 3, 15, 2, 0), True, "Sunday as 7"),
    ("0 0 * * 1-5", datetime(2026, 3, 16, 0, 0), True, "weekdays (Monday)"),
    ("0 0 * * 1-5", datetime(2026, 3, 15, 0, 0), False, "weekdays (Sunday)"),
    ("0 0,12 * * *", datetime(2026, 3, 15, 12, 0), True, "comma list"),
    ("0 0,12 * * *", datetime(2026, 3, 15, 13, 0), False, "comma list, not 13:00"),
    ("30 9 1 * *", datetime(2026, 3, 1, 9, 30), True, "1st of the month"),
    ("30 9 1 * *", datetime(2026, 3, 2, 9, 30), False, "not the 2nd"),
    ("0 0 1 1 *", datetime(2026, 1, 1, 0, 0), True, "new year"),
    ("0 0 1 1 *", datetime(2026, 2, 1, 0, 0), False, "not February"),
    ("0 9-17/2 * * *", datetime(2026, 3, 15, 9, 0), True, "stepped range 9-17/2"),
    ("0 9-17/2 * * *", datetime(2026, 3, 15, 10, 0), False, "stepped range, not 10"),
    # Malformed input must be refused, never raise.
    ("bad expr", datetime(2026, 3, 15, 12, 0), False, "malformed expression"),
    ("0 8 * *", datetime(2026, 3, 15, 8, 0), False, "only four fields"),
    ("0 abc * * *", datetime(2026, 3, 15, 8, 0), False, "non-numeric hour"),
]


def main() -> int:
    scheduler = _load_scheduler()
    failures: List[str] = []

    print("Configured schedules (must all parse without raising):")
    for name, expression in CONFIGURED:
        try:
            scheduler._should_run(expression, datetime(2026, 3, 15, 8, 0), None)
            print(f"  ok    {name:20} {expression}")
        except Exception as exc:  # noqa: BLE001 - that is the point of the test
            failures.append(f"{name} ({expression}) raised {type(exc).__name__}: {exc}")
            print(f"  FAIL  {name:20} {expression} -> {type(exc).__name__}: {exc}")

    print()
    print("Cron matching:")
    for expression, moment, expected, description in MATCH_CASES:
        try:
            actual = scheduler._should_run(expression, moment, None)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{expression!r} raised {type(exc).__name__}: {exc}")
            print(f"  FAIL  {expression:16} raised {type(exc).__name__}")
            continue
        if actual != expected:
            failures.append(
                f"{expression!r} at {moment:%a %H:%M} gave {actual}, "
                f"expected {expected} ({description})"
            )
            print(f"  FAIL  {expression:16} {moment:%a %H:%M} -> {actual} ({description})")
        else:
            print(f"  ok    {expression:16} {moment:%a %H:%M} -> {actual} ({description})")

    print()
    print("Already-ran guard:")
    moment = datetime(2026, 3, 15, 8, 0)
    if scheduler._should_run("0 8 * * *", moment, moment):
        failures.append("re-ran within the same minute; the guard is not working")
        print("  FAIL  same minute re-runs")
    else:
        print("  ok    does not re-run within the same minute")

    print()
    print("=" * 66)
    if failures:
        print(f"FAILED - {len(failures)} problem(s)")
        for failure in failures:
            print("   - " + failure)
        return 1
    print(
        f"PASSED - {len(CONFIGURED)} configured schedules, "
        f"{len(MATCH_CASES)} matching cases"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
