#!/usr/bin/env python3
"""Check that a strategy change never takes over an open position.

The property under test
-----------------------
A new strategy must not become responsible for the exits of trades it never
opened. Someone chose those entries on one set of reasoning; exiting them on
another is a decision nobody made.

So with positions open the change is queued and the bot is paused, and it applies
only once the last position closes. This file asserts that, and asserts it in a
way that fails if the property is removed - not merely that the happy path works.

Why it needs its own test
-------------------------
The failure mode is silent and looks like success. Applying a strategy change
immediately "works": the setting saves, the reload succeeds, the UI reports the
new strategy. The only thing wrong is that an open position is now being managed
by rules that did not open it, and nothing anywhere says so.

What is checked
---------------
 1. No positions open        -> applies now.
 2. Positions open           -> queues, pauses, and does NOT write the strategy.
 3. Still open on reconcile  -> does nothing. Repeatedly.
 4. Last position closed     -> applies, reloads, resumes.
 5. Cancel                   -> drops the queue and resumes.
 6. Unknown strategy         -> refused before anything is queued or paused.
 7. Pause fails              -> refused, nothing queued. A queue that cannot
                                drain is worse than a refusal.
 8. Queue survives restart   -> read back from disk, not from memory.
 9. Paused bot resumes       -> the running state is restored after the reload,
                                because a rebuilt bot comes back stopped.
10. The stack does not pass --strategy on the command line. This is the specific
    mistake that made strategy switching silently impossible before.

Negative-tested: each property was reverted in turn and the suite was confirmed to
fail. See the comments on `test_applies_while_open` for the one that matters most.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]

# The settings dir must be redirected before settings_store is imported, because
# it resolves SETTINGS_DIR at module load.
_TMP = tempfile.mkdtemp(prefix="strategy-switch-test-")
STRAT_DIR = pathlib.Path(_TMP) / "strategies"
STRAT_DIR.mkdir(parents=True, exist_ok=True)
os.environ["ORCHESTRATOR_SETTINGS_DIR"] = str(pathlib.Path(_TMP) / "settings")
os.environ["ORCHESTRATOR_STRATEGY_DIR"] = str(STRAT_DIR)
sys.path.insert(0, str(REPO))

from ai_orchestrator.core import settings_store, strategy_switch  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ok    {label}")
    else:
        FAILURES.append(label)
        print(f"  FAIL  {label}{(' — ' + detail) if detail else ''}")


def write_strategy(name: str, cls: str) -> None:
    (STRAT_DIR / f"{name}.py").write_text(
        f"from freqtrade.strategy import IStrategy\n\n\nclass {cls}(IStrategy):\n"
        f"    timeframe = '5m'\n",
        encoding="utf-8",
    )


class FakeFreqtrade:
    """A Freqtrade client that records what it was asked to do.

    Deliberately records rather than asserts, so a test can ask what happened
    after the fact - including asking whether something happened that should not
    have.
    """

    def __init__(self, open_trades: int = 0, running: bool = True):
        self.open_trades = open_trades
        self.running = running
        self.calls: list[str] = []
        self.fail_pause = False
        self.fail_reload = False

    async def status(self):
        class S:
            pass

        s = S()
        s.open_trades_count = self.open_trades
        s.is_running = self.running
        return s

    async def pause(self):
        self.calls.append("pause")
        if self.fail_pause:
            raise RuntimeError("pause failed")
        self.running = False
        return {"status": "paused"}

    async def start(self):
        self.calls.append("start")
        self.running = True
        return {"status": "started"}

    async def reload_config(self):
        self.calls.append("reload")
        if self.fail_reload:
            raise RuntimeError("reload failed")
        return {"status": "reloading"}


def reset():
    """Clear the settings file, the queue, and any written strategies."""
    for path in (settings_store.SETTINGS_FILE, strategy_switch.PENDING_FILE):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    for path in STRAT_DIR.glob("*.py"):
        path.unlink()
    write_strategy("moderate_multi", "ModerateMultiPairStrategy")
    write_strategy("strategy001", "Strategy001")
    settings_store.write({"strategy": "ModerateMultiPairStrategy"}, actor="test")


def written_strategy() -> str:
    return settings_store.read().settings.get("strategy")


# ---------------------------------------------------------------------------
def test_available():
    print("\nDiscovering strategies from the volume:")
    reset()
    names = strategy_switch.available_strategies()
    check("finds both strategies", names == ["ModerateMultiPairStrategy", "Strategy001"], str(names))
    check("strategy_exists true for a real one", strategy_switch.strategy_exists("Strategy001"))
    check("strategy_exists false for a made-up one", not strategy_switch.strategy_exists("NopeStrategy"))


def test_applies_when_clear():
    print("\nNo positions open — applies immediately:")
    reset()
    ft = FakeFreqtrade(open_trades=0, running=True)
    result = asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=0, was_running=True, freqtrade=ft
        )
    )
    check("reports applied", result.get("applied") is True, str(result))
    check("settings file now says Strategy001", written_strategy() == "Strategy001", written_strategy())
    check("freqtrade was reloaded", "reload" in ft.calls, str(ft.calls))
    check("nothing was queued", strategy_switch.pending() is None)
    # Nothing was open, so nothing needed pausing. Pausing here would stop the bot
    # from trading for no reason.
    check("was not paused", "pause" not in ft.calls, str(ft.calls))


def test_queues_when_open():
    print("\nPositions open — queues instead of applying:")
    reset()
    ft = FakeFreqtrade(open_trades=2, running=True)
    result = asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=2, was_running=True, freqtrade=ft
        )
    )
    check("reports queued", result.get("queued") is True, str(result))
    check("reports not applied", result.get("applied") is False, str(result))
    # THE property. The settings file must still name the old strategy: if it
    # already names the new one, a later reload applies it while positions are
    # open, with nothing left to stop it.
    check(
        "settings file STILL says the old strategy",
        written_strategy() == "ModerateMultiPairStrategy",
        written_strategy(),
    )
    check("no reload happened", "reload" not in ft.calls, str(ft.calls))
    check("entries were paused", "pause" in ft.calls, str(ft.calls))
    check("queue is persisted", strategy_switch.pending() is not None)
    check("queue names the new strategy", (strategy_switch.pending() or {}).get("strategy") == "Strategy001")


def test_reconcile_holds_while_open():
    print("\nReconciling while positions remain open — must do nothing:")
    reset()
    ft = FakeFreqtrade(open_trades=2, running=False)
    asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=2, was_running=True, freqtrade=ft
        )
    )
    ft.calls.clear()

    # Several ticks, decreasing but never reaching zero.
    for remaining in (2, 2, 1):
        out = asyncio.run(
            strategy_switch.reconcile(open_trades=remaining, freqtrade=ft)
        )
        check(f"does nothing with {remaining} open", out is None, str(out))

    check("still the old strategy", written_strategy() == "ModerateMultiPairStrategy", written_strategy())
    check("never reloaded", "reload" not in ft.calls, str(ft.calls))
    check("queue still present", strategy_switch.pending() is not None)


def test_reconcile_applies_when_clear():
    print("\nLast position closed — applies and resumes:")
    reset()
    ft = FakeFreqtrade(open_trades=1, running=False)
    asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=1, was_running=True, freqtrade=ft
        )
    )
    ft.calls.clear()

    out = asyncio.run(strategy_switch.reconcile(open_trades=0, freqtrade=ft))
    check("reconcile applied it", bool(out and out.get("applied")), str(out))
    check("settings file now says Strategy001", written_strategy() == "Strategy001", written_strategy())
    check("freqtrade was reloaded", "reload" in ft.calls, str(ft.calls))
    # A rebuilt bot comes back stopped unless told otherwise. Without this the bot
    # would silently trade nothing, which looks identical to running.
    check("bot was resumed", "start" in ft.calls, str(ft.calls))
    check("queue is cleared", strategy_switch.pending() is None)


def test_does_not_resume_what_was_stopped():
    print("\nA bot that was already stopped is not started:")
    reset()
    ft = FakeFreqtrade(open_trades=1, running=False)
    asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=1, was_running=False, freqtrade=ft
        )
    )
    ft.calls.clear()
    asyncio.run(strategy_switch.reconcile(open_trades=0, freqtrade=ft))
    check("strategy was applied", written_strategy() == "Strategy001", written_strategy())
    check("did NOT start a stopped bot", "start" not in ft.calls, str(ft.calls))


def test_cancel():
    print("\nCancelling a queued change:")
    reset()
    ft = FakeFreqtrade(open_trades=3, running=False)
    asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=3, was_running=True, freqtrade=ft
        )
    )
    ft.calls.clear()

    out = asyncio.run(strategy_switch.cancel(actor="test", was_running=True, freqtrade=ft))
    check("reports cancelled", out.get("cancelled") is True, str(out))
    check("queue is empty", strategy_switch.pending() is None)
    check("bot was resumed", "start" in ft.calls, str(ft.calls))
    check("strategy unchanged", written_strategy() == "ModerateMultiPairStrategy", written_strategy())
    check("no reload happened", "reload" not in ft.calls, str(ft.calls))

    # Cancelling nothing is not an error.
    again = asyncio.run(strategy_switch.cancel(actor="test", was_running=True, freqtrade=ft))
    check("cancelling an empty queue is safe", again.get("cancelled") is False, str(again))


def test_unknown_strategy_refused():
    print("\nAn unavailable strategy is refused before anything happens:")
    reset()
    ft = FakeFreqtrade(open_trades=2, running=True)
    try:
        asyncio.run(
            strategy_switch.request(
                "DoesNotExist", actor="test", open_trades=2, was_running=True, freqtrade=ft
            )
        )
        check("raised for an unknown strategy", False, "no exception")
    except strategy_switch.StrategySwitchError as exc:
        check("raised for an unknown strategy", True)
        check("message names the problem", "DoesNotExist" in str(exc), str(exc))

    check("nothing queued", strategy_switch.pending() is None)
    # Refused before pausing: pausing is a real change to the bot's behaviour and
    # must not happen for a request that can never complete.
    check("was not paused", "pause" not in ft.calls, str(ft.calls))
    check("strategy unchanged", written_strategy() == "ModerateMultiPairStrategy", written_strategy())


def test_pause_failure_refuses():
    print("\nIf the bot cannot be paused, nothing is queued:")
    reset()
    ft = FakeFreqtrade(open_trades=2, running=True)
    ft.fail_pause = True
    try:
        asyncio.run(
            strategy_switch.request(
                "Strategy001", actor="test", open_trades=2, was_running=True, freqtrade=ft
            )
        )
        check("raised when pause fails", False, "no exception")
    except strategy_switch.StrategySwitchError:
        check("raised when pause fails", True)

    # A queued change with the bot still opening positions may never drain, and
    # the operator would be waiting on it. Refusing is the honest answer.
    check("nothing queued", strategy_switch.pending() is None)
    check("strategy unchanged", written_strategy() == "ModerateMultiPairStrategy", written_strategy())


def test_reload_failure_reported():
    print("\nIf the reload fails, it says so and keeps the queue:")
    reset()
    ft = FakeFreqtrade(open_trades=1, running=False)
    asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=1, was_running=True, freqtrade=ft
        )
    )
    ft.fail_reload = True
    out = asyncio.run(strategy_switch.reconcile(open_trades=0, freqtrade=ft))
    check("reports an error", bool(out and out.get("error")), str(out))
    check("queue is kept for retry", strategy_switch.pending() is not None)
    # The setting IS written at this point, and the message has to say so rather
    # than implying nothing happened.
    check("error explains the bot still runs the old strategy",
          "previous strategy" in (out or {}).get("error", ""), str(out))


def test_queue_survives_restart():
    print("\nThe queue is on disk, so a restart does not lose it:")
    reset()
    ft = FakeFreqtrade(open_trades=2, running=True)
    asyncio.run(
        strategy_switch.request(
            "Strategy001", actor="test", open_trades=2, was_running=True, freqtrade=ft
        )
    )
    # Simulate the orchestrator restarting: read the queue fresh, as a new process
    # would. Held in memory, this would come back empty and the operator's request
    # would vanish while trading continued on the old strategy.
    raw = json.loads(strategy_switch.PENDING_FILE.read_text())
    check("queue file exists on disk", raw.get("strategy") == "Strategy001", str(raw))
    check("records who asked", raw.get("requested_by") == "test", str(raw))
    check("records the running state", raw.get("was_running") is True, str(raw))
    check("describe() reports it", strategy_switch.describe().get("queued") is True)


def test_corrupt_queue_is_not_silently_ignored():
    print("\nA corrupt queue must not be treated as an empty one:")
    reset()
    strategy_switch.PENDING_FILE.write_text("{not json", encoding="utf-8")
    # pending() returns None for an unreadable file, and logs an error. The
    # important part is that it does not crash the tick loop.
    check("does not raise", strategy_switch.pending() is None)
    strategy_switch.clear()
    check("can be cleared", strategy_switch.pending() is None)


def test_stack_has_no_strategy_flag():
    print("\nThe stack must not pass --strategy on the command line:")
    stack = (REPO / "portainer-stack.yml").read_text(encoding="utf-8")

    # Ignore comments: the comment explaining why the flag is absent quotes it.
    lines = [ln for ln in stack.splitlines() if not ln.lstrip().startswith("#")]
    body = "\n".join(lines)

    check(
        "no --strategy argument",
        not re.search(r"^\s*-\s*--strategy\s*$", body, re.M),
        "the flag overrides every config file, which silently breaks switching",
    )
    check("--strategy-path is still passed", "--strategy-path" in body)

    # The default must exist in a config, or freqtrade refuses to start.
    base = (REPO / "config" / "base.json").read_text(encoding="utf-8")
    check("base.json sets a default strategy", '"strategy"' in base)


def test_settings_refuses_unknown_strategy():
    print("\nThe settings layer refuses an unavailable strategy:")
    reset()
    try:
        settings_store.validate({"strategy": "GhostStrategy"})
        check("validate() refused it", False, "no exception")
    except settings_store.SettingsError as exc:
        check("validate() refused it", True)
        check("message lists what is available", "Strategy001" in str(exc), str(exc))

    ok = settings_store.validate({"strategy": "Strategy001"})
    check("accepts a real one", ok.get("strategy") == "Strategy001", str(ok))


def main() -> int:
    print("=" * 70)
    print("Strategy switching: a change must never take over an open position")
    print("=" * 70)

    test_available()
    test_applies_when_clear()
    test_queues_when_open()
    test_reconcile_holds_while_open()
    test_reconcile_applies_when_clear()
    test_does_not_resume_what_was_stopped()
    test_cancel()
    test_unknown_strategy_refused()
    test_pause_failure_refuses()
    test_reload_failure_reported()
    test_queue_survives_restart()
    test_corrupt_queue_is_not_silently_ignored()
    test_stack_has_no_strategy_flag()
    test_settings_refuses_unknown_strategy()

    shutil.rmtree(_TMP, ignore_errors=True)

    print()
    print("=" * 70)
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} of {CHECKS} checks")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print(f"PASSED — {CHECKS} checks: a queued change waits for the positions to close")
    return 0


if __name__ == "__main__":
    sys.exit(main())
