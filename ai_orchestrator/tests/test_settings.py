"""
Settings and dry-run reset test suite.
======================================

These two features exist so a non-expert can control the bot from the UI. That
makes them the most safety-critical code in the project, because they are the
first place where the operator's own actions can change how the bot trades.

The tests are grouped by the property they defend:

  1. The allowlist     - what can be changed, and what cannot be reached at all
  2. Bounds            - values that keep a bad week survivable
  3. The pairing       - db_url always matches dry_run, by construction
  4. Going live        - requires a typed phrase, not a click
  5. The reset         - refuses when live; clears locks; keeps a record
  6. AI unreachability - the AI-facing surface cannot write settings

Run: python3 ai_orchestrator/tests/test_settings.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Point the store at a scratch directory before importing it, so no test can
# touch a real settings volume.
_TMP = tempfile.mkdtemp(prefix="settings-test-")
os.environ["ORCHESTRATOR_SETTINGS_DIR"] = _TMP

# A strategies directory with a real strategy in it, for the same reason.
#
# Without this the directory does not exist, every strategy lookup returns empty,
# and the settings validator refuses any strategy name for not existing. That
# masked a real bug: the test asserting "an approved strategy change is refused"
# passed because the name was unknown, not because the chat is barred from writing
# it - so removing the bar changed nothing and went undetected. Here the name is
# valid, so the only thing that can refuse it is the bar itself.
_STRAT_DIR = Path(_TMP) / "strategies"
_STRAT_DIR.mkdir(parents=True, exist_ok=True)
(_STRAT_DIR / "moderate_multi.py").write_text(
    "from freqtrade.strategy import IStrategy\n\n\n"
    "class ModerateMultiPairStrategy(IStrategy):\n    timeframe = '5m'\n",
    encoding="utf-8",
)
os.environ["ORCHESTRATOR_STRATEGY_DIR"] = str(_STRAT_DIR)

from ai_orchestrator.core import dryrun_reset, settings_store  # noqa: E402
from ai_orchestrator.core.settings_store import (  # noqa: E402
    LIVE_CONFIRMATION_PHRASE,
    SettingsError,
)

PASSED = 0
FAILED = 0
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
    else:
        FAILED += 1
        FAILURES.append("%s%s" % (name, (": " + detail) if detail else ""))
        print("  FAIL  %s%s" % (name, ("  -> " + detail) if detail else ""))


def refuses(name: str, payload, *, confirmation=None, expect_in: str = "") -> None:
    """Assert that a payload is refused, and that the reason is useful."""
    try:
        settings_store.validate(payload, confirmation=confirmation)
    except SettingsError as e:
        if expect_in and expect_in.lower() not in e.message.lower():
            check(name, False, "refused, but the message did not mention %r: %s" % (expect_in, e.message))
        else:
            check(name, True)
        return
    check(name, False, "was accepted but should have been refused")


def accepts(name: str, payload, *, confirmation=None) -> dict:
    try:
        return settings_store.validate(payload, confirmation=confirmation)
    except SettingsError as e:
        check(name, False, "was refused: %s" % e.message)
        return {}
    check(name, True)
    return {}
def _is_refused(payload, confirmation=None) -> bool:
    try:
        settings_store.validate(payload, confirmation=confirmation)
        return False
    except SettingsError:
        return True


# ===========================================================================
print("\n1. The allowlist")
# ===========================================================================
refuses("unknown key is refused", {"stoploss": -0.05, "nonsense": 1}, expect_in="nonsense")

# The whole point of the allowlist: a credential must have no path in.
for forbidden in [
    "exchange",
    "api_server",
    "jwt_secret_key",
    "ws_token",
    "db_url",
    "internals",
    "dataformat_ohlcv",
    "telegram",
    "discord",
    "strategy",
    "pairlists",
    "protections",
    "position_adjustment_enable",
]:
    refuses("%r cannot be set" % forbidden, {forbidden: "x"})

# db_url deserves a specific message, because anyone who has read the config
# files will reasonably try to set it.
try:
    settings_store.validate({"db_url": "sqlite:////tmp/evil.sqlite"})
    check("db_url refusal explains itself", False, "was accepted")
except SettingsError as e:
    check(
        "db_url refusal explains itself",
        "trading mode" in e.message.lower() and "automatically" in e.message.lower(),
        e.message,
    )

check("empty payload is refused", _is_refused({}))
check(
    "every allowlisted key is documented",
    all(s.label and s.explain and s.help for s in settings_store.EDITABLE),
)


# ===========================================================================
print("2. Bounds")
# ===========================================================================
refuses("stoploss looser than -15% is refused", {"stoploss": -0.30}, expect_in="safe")
refuses("stoploss tighter than -2% is refused", {"stoploss": -0.001}, expect_in="safe")
refuses("too many open trades is refused", {"max_open_trades": 50}, expect_in="safe")
refuses("zero open trades is refused", {"max_open_trades": 0}, expect_in="safe")
refuses("using 100% of the balance is refused", {"tradable_balance_ratio": 1.0}, expect_in="safe")

# bool is an int in Python, so a careless numeric check accepts True for a count
# and writes a setting that means something other than it appears to.
refuses("true is refused for a numeric setting", {"max_open_trades": True}, expect_in="number")
refuses("a string is refused for a bool setting", {"dry_run": "false"}, expect_in="true or false")
refuses("a float is refused for an int setting", {"max_open_trades": 2.5}, expect_in="whole number")

# NaN and infinity pass every comparison, so they must be refused explicitly.
refuses("NaN is refused", {"stoploss": float("nan")}, expect_in="finite")
refuses("infinity is refused", {"max_open_trades": float("inf")}, expect_in="finite")

# Numeric strings are a convenience, not a hole: they still get bounded.
check("a numeric string is accepted", accepts("numeric string", {"max_open_trades": "3"}).get("max_open_trades") == 3)
refuses("a numeric string is still bounded", {"max_open_trades": "99"}, expect_in="safe")

check("in-range values are accepted", accepts("valid payload", {
    "max_open_trades": 3,
    "stoploss": -0.08,
    "tradable_balance_ratio": 0.9,
}).get("max_open_trades") == 3)


# ===========================================================================
print("3. The dry-run / database pairing")
# ===========================================================================
# The property that matters: whatever the operator does, db_url matches dry_run.
dry = accepts("dry_run true accepted", {"dry_run": True})
check("dry_run true derives the dry-run database", "dryrun" in dry.get("db_url", ""), dry.get("db_url"))

live = accepts(
    "dry_run false accepted with confirmation",
    {"dry_run": False},
    confirmation=LIVE_CONFIRMATION_PHRASE,
)
check("dry_run false derives the live database",
      "dryrun" not in live.get("db_url", "") and live.get("db_url", "").endswith("tradesv3.sqlite"),
      live.get("db_url"))

# Flipping back and forth must always land on the matching pair.
for target in [True, False, True, False, True]:
    result = settings_store.validate({"dry_run": target}, confirmation=LIVE_CONFIRMATION_PHRASE)
    matches = ("dryrun" in result["db_url"]) == target
    check("mode %s always pairs with the right database" % target, matches, result["db_url"])

# And the pairing survives a payload that tries to set both.
refuses("db_url cannot be smuggled in alongside dry_run",
        {"dry_run": False, "db_url": "sqlite:////freqtrade/user_data/data/tradesv3.dryrun.sqlite"})


# ===========================================================================
print("4. Going live")
# ===========================================================================
refuses("going live without confirmation is refused", {"dry_run": False}, expect_in="confirm")
refuses("a wrong phrase is refused", {"dry_run": False}, confirmation="yes", expect_in="confirm")
refuses("a near-miss phrase is refused", {"dry_run": False}, confirmation="TRADE REAL MONEY!", expect_in="confirm")
refuses("an empty phrase is refused", {"dry_run": False}, confirmation="   ", expect_in="confirm")

check("the exact phrase is accepted",
      accepts("live with phrase", {"dry_run": False}, confirmation=LIVE_CONFIRMATION_PHRASE))
check("the phrase is case-insensitive and trimmed",
      accepts("live, lowercased", {"dry_run": False}, confirmation="  trade real money  "))
check("returning to simulation needs no confirmation",
      accepts("back to dry run", {"dry_run": True}))

# The confirmation must never be persisted: it is a gate, not a setting.
written = settings_store.validate({"dry_run": False}, confirmation=LIVE_CONFIRMATION_PHRASE)
check("the confirmation phrase is not persisted",
      LIVE_CONFIRMATION_PHRASE not in json.dumps(written))


# ===========================================================================
print("5. Risk presets")
# ===========================================================================
for name, preset in settings_store.RISK_PRESETS.items():
    values = settings_store.apply_preset(name)
    ok = True
    try:
        settings_store.validate(values)
    except SettingsError as e:
        ok = False
        detail = e.message
    check("preset %r is valid" % name, ok, "" if ok else detail)

check("presets are ordered by risk",
      settings_store.RISK_PRESETS["conservative"]["values"]["max_open_trades"]
      < settings_store.RISK_PRESETS["moderate"]["values"]["max_open_trades"]
      < settings_store.RISK_PRESETS["aggressive"]["values"]["max_open_trades"])
check("presets tighten the stop loss as risk falls",
      settings_store.RISK_PRESETS["conservative"]["values"]["stoploss"]
      > settings_store.RISK_PRESETS["moderate"]["values"]["stoploss"]
      > settings_store.RISK_PRESETS["aggressive"]["values"]["stoploss"])

try:
    settings_store.apply_preset("yolo")
    check("an unknown preset is refused", False, "was accepted")
except SettingsError as e:
    check("an unknown preset is refused", "yolo" in e.message and "conservative" in e.message, e.message)


# ===========================================================================
print("6. Writing, reading, undoing")
# ===========================================================================
snapshot = settings_store.read()
check("a missing file reads as 'nothing overridden'", snapshot.exists is False and snapshot.error is None)

settings_store.write({"max_open_trades": 2}, actor="alice")
after = settings_store.read()
check("a written setting reads back", after.settings.get("max_open_trades") == 2)
check("the writer is recorded", after.updated_by == "alice", str(after.updated_by))
check("a timestamp is recorded", bool(after.updated_at))

settings_store.write({"max_open_trades": 4}, actor="bob")
check("a second write updates the value", settings_store.read().settings.get("max_open_trades") == 4)

restored = settings_store.restore_backup(actor="carol")
check("undo restores the previous value", restored.settings.get("max_open_trades") == 2,
      str(restored.settings))
check("undo is recorded as a new change, not a silent revert", restored.updated_by == "carol")

# A corrupt file must be reported, not raised: the bot is trading on the Swarm
# configs in that case, and refusing to answer would hide what is in force.
settings_store.SETTINGS_FILE.write_text("{not json", encoding="utf-8")
broken = settings_store.read()
check("a corrupt settings file is reported, not raised", broken.error is not None and broken.exists)
settings_store.SETTINGS_FILE.unlink()


# ===========================================================================
print("7. The dry-run reset")
# ===========================================================================
class FakeTrade:
    def __init__(self, tid, pair="BTC/CAD", is_open=False):
        self.id = tid
        self.pair = pair
        self.is_open = is_open
        self.open_date = "2026-01-01T00:00:00Z"
        self.close_date = None if is_open else "2026-01-02T00:00:00Z"
        self.amount = 0.01
        self.open_rate = 50000.0
        self.close_rate = 51000.0
        self.profit_abs = 10.0
        self.profit_ratio = 0.02
        self.exit_reason = "roi"
        self.enter_tag = "trend"
        self.stake_amount = 100.0


class FakeClient:
    """Stands in for the Freqtrade API, and records what was called."""

    def __init__(self, *, dry_run=True, trades=None, locks=None, fail_delete=(), fail_locks=()):
        self.dry_run = dry_run
        self.trades = list(trades or [])
        self.locks = list(locks or [])
        self.fail_delete = set(fail_delete)
        self.fail_locks = set(fail_locks)
        self.calls = []

    async def get_config(self):
        return {"dry_run": self.dry_run}

    async def get_trades(self, limit=10000):
        return list(self.trades)

    async def get_locks(self):
        return list(self.locks)

    async def delete_trade(self, trade_id):
        self.calls.append(("delete_trade", trade_id))
        if trade_id in self.fail_delete:
            raise RuntimeError("simulated failure")
        self.trades = [t for t in self.trades if t.id != trade_id]
        return {"result": "success"}

    async def delete_lock(self, lock_id):
        self.calls.append(("delete_lock", lock_id))
        if lock_id in self.fail_locks:
            raise RuntimeError("simulated failure")
        self.locks = [l for l in self.locks if l.get("id") != lock_id]
        return {}


def expect_refusal(name: str, coro) -> None:
    """Assert a coroutine raises ResetRefused, not some other exception.

    A raw exception escaping here is itself the bug: it means a failure mode got
    past the refusal instead of failing closed. Reporting it as a failed check
    keeps the rest of the suite running, so one regression does not hide the
    others.
    """
    global PASSED, FAILED
    try:
        asyncio.run(coro)
    except dryrun_reset.ResetRefused:
        PASSED += 1
        return
    except Exception as e:  # noqa: BLE001 - any other exception IS the failure
        FAILED += 1
        FAILURES.append(
            "%s: raised %s instead of failing closed (%s)" % (name, type(e).__name__, e)
        )
        print("  FAIL  %s: raised %s instead of failing closed" % (name, type(e).__name__))
        return
    FAILED += 1
    FAILURES.append("%s: was allowed" % name)
    print("  FAIL  %s: was allowed" % name)


def run(coro):
    return asyncio.run(coro)


# --- refuses when live: the most important property of this feature ---------
live_client = FakeClient(dry_run=False, trades=[FakeTrade(1), FakeTrade(2)])
live_preview = run(dryrun_reset.preview(live_client))
check("a live bot is not resettable", live_preview.allowed is False)
check("the live refusal says why", "real money" in (live_preview.reason or "").lower(),
      str(live_preview.reason))
check("a live refusal reads the mode from the bot", live_preview.dry_run is False)

expect_refusal(
    "reset on a live bot fails closed",
    dryrun_reset.reset(live_client, confirmation=dryrun_reset.RESET_CONFIRMATION_PHRASE, actor="alice"),
)
check("a live refusal deletes nothing", live_client.trades != [] and live_client.calls == [],
      str(live_client.calls))

# A bot that cannot be reached must fail closed, not open.
class UnreachableClient(FakeClient):
    async def get_config(self):
        raise RuntimeError("connection refused")

try:
    unreachable = run(dryrun_reset.preview(UnreachableClient()))
    check("an unreachable bot is not resettable", unreachable.allowed is False)
    check("the unreachable refusal explains the caution",
          "trading mode" in (unreachable.reason or "").lower(), str(unreachable.reason))
except Exception as e:  # noqa: BLE001
    check("an unreachable bot is not resettable", False,
          "raised %s instead of failing closed" % type(e).__name__)
    check("the unreachable refusal explains the caution", False, "preview raised")

# A bot that reports no dry_run field at all must also fail closed.
class NoModeClient(FakeClient):
    async def get_config(self):
        return {"strategy": "ModerateMultiPairStrategy"}

try:
    no_mode = run(dryrun_reset.preview(NoModeClient()))
    check("a bot with no reported mode is not resettable", no_mode.allowed is False)
except Exception as e:  # noqa: BLE001
    check("a bot with no reported mode is not resettable", False,
          "raised %s instead of failing closed" % type(e).__name__)


# --- the confirmation gate -------------------------------------------------
dry_client = FakeClient(dry_run=True, trades=[FakeTrade(1)])
expect_refusal(
    "reset without the phrase fails closed",
    dryrun_reset.reset(dry_client, confirmation="yes", actor="alice"),
)
check("a refused reset deletes nothing", len(dry_client.trades) == 1)


# --- a successful reset ----------------------------------------------------
trades = [FakeTrade(1), FakeTrade(2, is_open=True), FakeTrade(3)]
locks = [{"id": 10, "pair": "BTC/CAD", "reason": "MaxDrawdown"}, {"id": 11, "pair": "ETH/CAD"}]
client = FakeClient(dry_run=True, trades=trades, locks=locks)

report = run(dryrun_reset.reset(client, confirmation=dryrun_reset.RESET_CONFIRMATION_PHRASE, actor="alice"))

check("every trade is deleted", report["trades_deleted"] == 3, str(report["trades_deleted"]))
check("no trades remain", client.trades == [])
check("the report says it completed", report["status"] == "reset", report["status"])

# The trap this feature exists to avoid: locks outlive the trades they came from.
check("pair locks are released", report["locks_released"] == 2, str(report["locks_released"]))
check("no locks remain", client.locks == [])
check("locks are cleared before trades",
      [c for c in client.calls if c[0] == "delete_lock"] != []
      and client.calls.index(("delete_lock", 10)) < client.calls.index(("delete_trade", 1)),
      str(client.calls[:4]))

check("a backup is written", report["backup_path"] is not None)
if report["backup_path"]:
    backup = json.loads(Path(report["backup_path"]).read_text())
    check("the backup holds every trade", len(backup["trades"]) == 3, str(len(backup["trades"])))
    check("the backup records the reset time", "_meta" in backup and backup["_meta"]["reset_at"])
    check("the backup records it was a simulation", backup["_meta"]["trading_mode"] == "dry_run")
    check("the backup keeps the pair", backup["trades"][0]["pair"] == "BTC/CAD")
    check("the backup marks open trades", any(t["is_open"] for t in backup["trades"]))
    check("the summary names the backup file",
          Path(report["backup_path"]).name in report["summary"], report["summary"])

# Open positions are surfaced before anything is deleted, because they are about
# to be cancelled.
preview_client = FakeClient(dry_run=True, trades=[FakeTrade(1, is_open=True), FakeTrade(2)])
preview = run(dryrun_reset.preview(preview_client))
check("the preview counts open trades", preview.as_dict()["open_trade_count"] == 1)
check("the preview lists open trades", preview.open_trades[0]["id"] == 1)
check("the preview counts locks", preview.as_dict()["lock_count"] == 0)


# --- a partial failure must not be reported as success ---------------------
partial_client = FakeClient(dry_run=True, trades=[FakeTrade(1), FakeTrade(2), FakeTrade(3)], fail_delete={2})
partial = run(dryrun_reset.reset(partial_client, confirmation=dryrun_reset.RESET_CONFIRMATION_PHRASE, actor="alice"))
check("a partial reset is reported as partial", partial["status"] == "partial", partial["status"])
check("a partial reset counts the failures", len(partial["trades_failed"]) == 1)
check("a partial reset still deletes the rest", partial["trades_deleted"] == 2)
check("a partial reset says the history is not clean",
      "not clean" in partial["summary"], partial["summary"])
check("a partial reset names the failed trade", partial["trades_failed"][0]["id"] == 2)

# A lock that will not release must be surfaced, because the bot stays locked out.
lockfail_client = FakeClient(dry_run=True, trades=[FakeTrade(1)], locks=[{"id": 5}], fail_locks={5})
lockfail = run(dryrun_reset.reset(lockfail_client, confirmation=dryrun_reset.RESET_CONFIRMATION_PHRASE, actor="alice"))
check("a failed lock release is reported", len(lockfail["locks_failed"]) == 1)
check("a failed lock release warns about being locked out",
      "locked out" in lockfail["summary"], lockfail["summary"])


# ===========================================================================
print("8. The AI-facing surface cannot write settings")
# ===========================================================================
# The safety model is that the AI may propose but never apply. If a plugin, a
# chat command or a proposal could reach the settings writer, that model is gone.
import ast  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PLUGINS = REPO / "ai_orchestrator" / "plugins"

# `nl_config` is the one plugin allowed to reach the settings writer, because an
# approved proposal now applies a configuration change instead of handing the
# operator values to paste into a Swarm config. That makes the gate - not the
# import - the thing to test, which the behavioural checks below do.
#
# Every OTHER plugin must stay away from it entirely.
for path in sorted(PLUGINS.glob("*.py")):
    if path.name == "nl_config.py":
        continue
    source = path.read_text(encoding="utf-8")
    check("%s does not import settings_store" % path.name, "settings_store" not in source)
    check("%s does not import dryrun_reset" % path.name, "dryrun_reset" not in source)
    check("%s does not call settings_store.write" % path.name, "settings_store.write" not in source)

# And no plugin may write the settings file by path.
for path in sorted(PLUGINS.glob("*.py")):
    source = path.read_text(encoding="utf-8")
    check("%s does not name the settings file" % path.name, "runtime_settings" not in source)


# --- the approval gate, tested behaviourally -------------------------------
# The claim is not "the AI cannot touch settings" - it is "the AI cannot change
# settings without the operator approving a specific, fingerprinted, unexpired
# proposal". That is a runtime property, so it is tested at runtime.
import asyncio as _asyncio  # noqa: E402
import importlib  # noqa: E402
import types  # noqa: E402

# `nl_config` reaches `freqtrade_api`, which imports aiohttp. The dev environment
# has no aiohttp, and installing one just to import a module would make this test
# depend on the network. A stub is enough: nothing below performs a request - the
# gate is decided before any client is used, which is exactly the property being
# tested.
if "aiohttp" not in sys.modules:
    _aiohttp = types.ModuleType("aiohttp")

    class _ClientError(Exception):
        pass

    class _ClientSession:  # pragma: no cover - never instantiated here
        def __init__(self, *a, **k):
            self.closed = False

    _aiohttp.ClientError = _ClientError
    _aiohttp.ClientSession = _ClientSession
    _aiohttp.ClientTimeout = lambda *a, **k: None
    _aiohttp.BasicAuth = lambda *a, **k: None
    sys.modules["aiohttp"] = _aiohttp

nl_config = importlib.import_module("ai_orchestrator.plugins.nl_config")


class _StubAudit:
    """Records nothing, succeeds at everything.

    `_apply_changes` fails closed when the audit log cannot be written, so a stub
    that raised would make every gate test pass for the wrong reason - the write
    would be skipped because auditing failed, not because approval was missing.
    """

    def __init__(self):
        self.entries = []

    async def log(self, **kwargs):
        self.entries.append(kwargs)
        return True

    async def log_config_change(self, **kwargs):
        self.entries.append(kwargs)
        return True


class _StubOrchestrator:
    openrouter_client = None
    freqtrade_client = None
    audit_logger = _StubAudit()


def _plugin():
    plugin = nl_config.NLConfigPlugin.__new__(nl_config.NLConfigPlugin)
    plugin.openrouter = None
    plugin.freqtrade = None
    plugin.audit = _StubAudit()
    plugin.logger = __import__("logging").getLogger("test")
    plugin._pending_proposals = {}
    plugin.proposal_ttl_seconds = 1800
    plugin.auto_apply_safe = False
    plugin.require_approval_for = []
    return plugin


def _config_change():
    return {
        "type": "proposal_only",
        "key": "max_open_trades",
        "value": 2,
        "description": "Allow at most 2 trades at once",
        "applies_via": "settings",
    }


def _write_count():
    return len(list(settings_store.SETTINGS_DIR.glob("*.json")))


def _run_apply(plugin, changes, **kwargs):
    return _asyncio.run(plugin._apply_changes(changes, **kwargs))


# Reset the settings directory so the count is meaningful.
for f in settings_store.SETTINGS_DIR.glob("*.json"):
    f.unlink()

before = settings_store.read().settings
plugin = _plugin()

# 1. No approver, no approval source: must propose, must not write.
result = _run_apply(plugin, [_config_change()], source="command_no_approval")
check("an unapproved change is not written",
      settings_store.read().settings == before, str(settings_store.read().settings))
check("an unapproved change reports as proposed",
      result["executed"] and result["executed"][0]["status"] == "proposed",
      str(result["executed"]))

# 2. An approver but the WRONG source: still must not write. This is the case a
#    future caller is most likely to get wrong.
result = _run_apply(plugin, [_config_change()], approved_by="alice", source="command_no_approval")
check("an approver with the wrong source is not written",
      settings_store.read().settings == before, str(settings_store.read().settings))
check("an approver with the wrong source reports as proposed",
      result["executed"][0]["status"] == "proposed", str(result["executed"][0]))

# 3. The right source but NO approver: still must not write.
result = _run_apply(plugin, [_config_change()], source="approval")
check("the approval source without an approver is not written",
      settings_store.read().settings == before, str(settings_store.read().settings))

# 4. Both, as an approved proposal supplies: now it applies.
result = _run_apply(plugin, [_config_change()], approved_by="alice", source="approval")
check("an approved change is written",
      settings_store.read().settings.get("max_open_trades") == 2,
      str(settings_store.read().settings))
check("an approved change reports as applied",
      result["executed"][0]["status"] in ("applied", "saved_not_applied"),
      str(result["executed"][0]))

# 5. dry_run stays frozen even on the approved path: the AI can never propose the
#    live switch, so an approval can never carry it.
frozen_change = plugin._config_change("dry_run", False)
check("dry_run is refused at proposal time", frozen_change.get("frozen") is True
      or frozen_change.get("invalid") is True, str(frozen_change))
result = _run_apply(plugin, [frozen_change], approved_by="alice", source="approval")
check("an approved list cannot carry dry_run",
      settings_store.read().settings.get("dry_run") is None,
      str(settings_store.read().settings))
check("dry_run in an approved list is refused",
      result["executed"][0]["status"] == "refused", str(result["executed"][0]))

# 6. A key the AI may PROPOSE but this plugin must never WRITE is refused at apply
#    time. This is the case that makes the second gate load-bearing.
#
#    `strategy` is exactly this shape. It became an editable setting when runtime
#    strategy switching was added, so the allowlist check no longer excludes it -
#    and without a separate refusal an approved strategy change would be written
#    straight to the settings file from chat, bypassing the queue that waits for
#    open positions to close. The change would then land on the next reload and
#    take over the exits of trades it never opened.
#
#    Note the value is a REAL strategy name. The earlier version of this test used
#    a made-up one, which was refused by the settings validator for not existing -
#    so it passed for the wrong reason and would not have caught the bypass.
strategy_change = plugin._config_change("strategy", "ModerateMultiPairStrategy")
check("strategy is proposable", not strategy_change.get("invalid")
      and not strategy_change.get("frozen"), str(strategy_change))
check("a strategy proposal points at the Settings page",
      strategy_change.get("applies_via") == "settings_page",
      str(strategy_change.get("applies_via")))

before_strategy = settings_store.read().settings
result = _run_apply(plugin, [strategy_change], approved_by="alice", source="approval")
check("an approved strategy change is refused",
      result["executed"][0]["status"] == "refused", str(result["executed"][0]))
check("a refused strategy change writes nothing",
      settings_store.read().settings == before_strategy,
      str(settings_store.read().settings))
# The refusal must point somewhere useful. "Not allowed" alone would leave the
# operator with an approved decision and no idea where to apply it.
check("the strategy refusal points at the Settings page",
      "settings" in (result["executed"][0].get("reason") or "").lower(),
      str(result["executed"][0].get("reason")))

# A genuinely unknown key is refused too.
rogue = {"type": "proposal_only", "key": "api_server", "value": "x", "description": "x"}
result = _run_apply(plugin, [rogue], approved_by="alice", source="approval")
check("a non-editable key is refused on the approved path",
      result["executed"][0]["status"] == "refused", str(result["executed"][0]))

# 6b. The two keys the AI proposes and the settings layer CAN apply must agree,
#     or the operator is offered a change that cannot be carried out.
for proposable in ("trailing_stop_positive", "amount_reserve_percent", "stoploss",
                   "max_open_trades", "tradable_balance_ratio"):
    check("%s is both proposable and applicable" % proposable,
          proposable in nl_config.PROPOSABLE_KEYS
          and proposable in settings_store.EDITABLE_BY_KEY,
          "proposable=%s applicable=%s" % (
              proposable in nl_config.PROPOSABLE_KEYS,
              proposable in settings_store.EDITABLE_BY_KEY))

# Everything else the AI can propose must be honestly marked as not applicable
# here, rather than silently failing at apply time.
for proposable in sorted(nl_config.PROPOSABLE_KEYS):
    if proposable in settings_store.EDITABLE_BY_KEY:
        continue
    check("%s is marked as needing a redeploy" % proposable,
          plugin._config_change(proposable, 1).get("applies_via") == "redeploy",
          str(plugin._config_change(proposable, 1).get("applies_via")))

# 7. The old marker must be gone from the CODE, or the operator still gets told
#    to paste values into a Swarm config. Comments are excluded deliberately: the
#    code explains what it used to do, and a naive substring check would flag its
#    own explanation.
import io  # noqa: E402
import tokenize  # noqa: E402

_literals = []
with (PLUGINS / "nl_config.py").open("rb") as _fh:
    for _tok in tokenize.tokenize(_fh.readline):
        if _tok.type == tokenize.STRING:
            _literals.append(_tok.string)

check("no code still claims a change needs a redeploy",
      not any("config_redeploy" in lit for lit in _literals),
      "found in a string literal")
check("the check can see string literals at all",
      any("settings" in lit for lit in _literals),
      "tokenizer found no strings, so the check above proves nothing")

# The command path must not route to the settings routes.
main_source = (REPO / "ai_orchestrator" / "main.py").read_text(encoding="utf-8")
command_section = main_source.split("@app.post(\"/api/v1/command\"", 1)
if len(command_section) > 1:
    handler = command_section[1].split("@app.", 1)[0]
    check("the command handler does not write settings", "settings_store.write" not in handler)
    check("the command handler does not reset the dry run", "dryrun_reset.reset" not in handler)
else:
    check("the command handler was located", False, "could not find /api/v1/command")

# nl_config must keep dry_run frozen, or the AI could propose the switch.
nl_config = (PLUGINS / "nl_config.py").read_text(encoding="utf-8")
check("nl_config keeps dry_run frozen", "dry_run" in nl_config and "FROZEN" in nl_config.upper())

# The settings routes must all require authentication.
tree = ast.parse(main_source)
settings_routes = []
for node in ast.walk(tree):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    for decorator in node.decorator_list:
        text = ast.unparse(decorator)
        if "/api/v1/settings" in text:
            settings_routes.append((text, node))

check("settings routes were found", len(settings_routes) >= 5, str(len(settings_routes)))
for route_text, node in settings_routes:
    defaults = [ast.unparse(d) for d in node.args.defaults]
    authenticated = any("require_api_token" in d for d in defaults)
    # The unauthenticated routes must be exactly the UI and health endpoints.
    check("route %s requires auth" % route_text[:52], authenticated,
          "no require_api_token dependency")


# ===========================================================================
print("\n" + "=" * 72)
print("PASSED: %d   FAILED: %d" % (PASSED, FAILED))
if FAILURES:
    print("\nFailures:")
    for failure in FAILURES:
        print("  - %s" % failure)
    sys.exit(1)
print("All settings and dry-run reset invariants held.")
