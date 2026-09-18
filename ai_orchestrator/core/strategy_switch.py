"""
Deferred strategy switching.
============================

Changing the strategy is the one operator setting that cannot simply be applied
the moment it is asked for.

Why it must wait
----------------
Freqtrade's `POST /reload_config` tears the bot down and rebuilds it: the new
strategy takes over immediately, including the exit logic for positions the old
strategy opened. Those positions were entered on one set of reasoning and would
be exited on another. Nobody chose that.

So a strategy change with positions open is not applied and not refused - it is
*queued*, and the bot is paused so no further positions open under the old
strategy while it waits. When the last position closes, the change applies.

    requested ──> positions open?
                    │
                    ├── no  ──> apply now (write + reload + restore state)
                    │
                    └── yes ──> pause entries
                                persist the request
                                     │
                                (scheduler tick, every 60s)
                                     │
                                last position closed
                                     │
                                apply + reload + restore state

Pausing is exactly the right primitive. Freqtrade gates entries on
`State.RUNNING` (`freqtradebot.py`, `process()`), so a paused bot opens nothing
new - and exit management carries on ungated, so the open positions still close
normally. The queue therefore drains on its own rather than waiting for someone
to intervene.

Pause does not survive the reload
---------------------------------
A rebuilt bot takes its state from `initial_state`, defaulting to STOPPED,
whatever it was before. So the running state is recorded when the request is
queued and restored explicitly after the reload. Without that the bot would come
back stopped and quietly do nothing, which looks identical to "working" from the
outside.

Why this is a file and not a variable
-------------------------------------
The orchestrator can restart while a change is queued - a redeploy, a crash, a
host reboot. Holding the queue in memory would silently drop the operator's
request and resume trading the old strategy, which is the worst outcome: they
believe a change is pending and it is not. It is written to the same directory
as the settings it will eventually change.

Nothing here is reachable from a chat command or from a plugin. The only caller
is the authenticated settings route, on an explicit human action.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ai_orchestrator.core.settings_store import SETTINGS_DIR

logger = logging.getLogger(__name__)

#: Written beside runtime_settings.json, which is the file it will change.
PENDING_FILE = SETTINGS_DIR / "pending_strategy.json"

#: Where Freqtrade looks for strategies. Shared volume, so AI proposals land
#: here too - which is what makes switching to a generated strategy possible
#: without a redeploy.
STRATEGY_DIR = Path(os.environ.get("ORCHESTRATOR_STRATEGY_DIR", "/app/strategies"))


class StrategySwitchError(Exception):
    """Raised with a message intended for the operator, not the log."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Available strategies
# ---------------------------------------------------------------------------
def available_strategies() -> list[str]:
    """Strategy class names that could actually be loaded right now.

    Read from the files rather than from a list, because the useful question is
    "what could this bot run", and a strategy that is not in the volume cannot be
    run no matter what a config says. Files are scanned for a class definition
    that looks like a strategy.

    This is deliberately not authoritative about *validity* - it does not import
    the module. Freqtrade does that, at startup, and refuses to start on a bad
    strategy. The point here is to reject a name that could never work before it
    is queued, rather than after the operator's positions have closed and the
    reload has already failed.
    """
    names: set[str] = set()
    if not STRATEGY_DIR.is_dir():
        return []

    for path in sorted(STRATEGY_DIR.glob("*.py")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("class "):
                continue
            name = stripped[6:].split("(")[0].split(":")[0].strip()
            if not name or not name.isidentifier():
                continue
            # A strategy subclasses IStrategy. Files in this directory that do
            # not (helpers, __init__) are not switchable.
            if "IStrategy" in stripped:
                names.add(name)

    return sorted(names)


def strategy_exists(name: str) -> bool:
    """Is `name` a strategy that could be loaded from the volume?"""
    return name in available_strategies()


# ---------------------------------------------------------------------------
# The queue
# ---------------------------------------------------------------------------
def _read_raw() -> Optional[Dict[str, Any]]:
    if not PENDING_FILE.exists():
        return None
    try:
        raw = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # A corrupt queue must not be silently ignored: leaving it in place would
        # mean the bot resumes trading the old strategy while the operator
        # believes a change is pending.
        logger.error("Pending strategy queue is unreadable: %s", exc)
        return None
    return raw if isinstance(raw, dict) else None


def pending() -> Optional[Dict[str, Any]]:
    """The queued change, or None."""
    raw = _read_raw()
    if not raw or not raw.get("strategy"):
        return None
    return raw


def _write_raw(payload: Optional[Dict[str, Any]]) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    if payload is None:
        try:
            PENDING_FILE.unlink()
        except FileNotFoundError:
            pass
        return

    fd, tmp_name = tempfile.mkstemp(dir=str(SETTINGS_DIR), prefix=".pending-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, PENDING_FILE)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def clear() -> None:
    _write_raw(None)


def is_queued_for(strategy: str) -> bool:
    current = pending()
    return bool(current and current.get("strategy") == strategy)


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------
async def _apply_now(strategy: str, *, actor: str, was_running: bool, freqtrade) -> Dict[str, Any]:
    """Write the strategy, reload Freqtrade, and restore its running state."""
    from ai_orchestrator.core import settings_store

    snapshot = settings_store.read()
    if snapshot.error:
        raise StrategySwitchError(
            "Cannot change the strategy while the settings file is unreadable: %s"
            % snapshot.error
        )

    updated = dict(snapshot.settings)
    updated["strategy"] = strategy

    # Validate through the same path as every other setting, so a strategy that
    # would be refused from the settings page is refused here too. One gate.
    clean = settings_store.validate(updated)
    settings_store.write(clean, actor=actor)

    try:
        await freqtrade.reload_config()
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        # The setting is written; the bot is still running the old strategy.
        # Saying so plainly matters more than the exception type.
        raise StrategySwitchError(
            "Strategy saved but Freqtrade did not reload: %s. "
            "It is still running the previous strategy." % exc
        ) from exc

    resumed = False
    if was_running:
        try:
            await freqtrade.start()
            resumed = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Strategy applied but the bot did not restart: %s", exc)

    return {
        "applied": True,
        "strategy": strategy,
        "reloaded": True,
        "resumed": resumed,
    }


# ---------------------------------------------------------------------------
# Entry points used by the settings route
# ---------------------------------------------------------------------------
async def request(
    strategy: str,
    *,
    actor: str,
    open_trades: int,
    was_running: bool,
    freqtrade,
) -> Dict[str, Any]:
    """Apply the change now, or queue it until positions close.

    `open_trades` is passed in rather than looked up so the caller decides what
    "open" means - which keeps this module testable without a live bot, and keeps
    the definition of an open position in one place.
    """
    if not strategy_exists(strategy):
        known = available_strategies()
        raise StrategySwitchError(
            "No strategy named %r is available%s."
            % (strategy, (". Available: " + ", ".join(known)) if known else "")
        )

    if open_trades <= 0:
        result = await _apply_now(
            strategy, actor=actor, was_running=was_running, freqtrade=freqtrade
        )
        clear()
        return result

    # Positions are open. Stop opening more, then wait.
    paused = False
    try:
        await freqtrade.pause()
        paused = True
    except Exception as exc:  # noqa: BLE001
        # Queueing without pausing would leave the old strategy opening new
        # positions, so the queue might never drain. Refuse instead of storing a
        # request that cannot complete.
        raise StrategySwitchError(
            "Could not pause the bot to queue the strategy change: %s. "
            "No change was queued." % exc
        ) from exc

    _write_raw(
        {
            "strategy": strategy,
            "requested_at": _now(),
            "requested_by": actor,
            "was_running": was_running,
            "open_trades_at_request": open_trades,
            "paused": paused,
        }
    )

    return {
        "applied": False,
        "queued": True,
        "strategy": strategy,
        "paused": paused,
        "open_trades": open_trades,
        "message": (
            "Queued. No new positions will open, and %d open position(s) will be "
            "allowed to close normally. The strategy switches as soon as the last "
            "one closes." % open_trades
        ),
    }


async def reconcile(*, open_trades: int, freqtrade) -> Optional[Dict[str, Any]]:
    """Apply a queued change if the way is now clear.

    Called on the scheduler tick. Safe to call when nothing is queued.

    A queued change whose strategy has since disappeared from the volume is
    dropped with an error rather than retried forever - the reload would fail
    every time, and a queue that cannot drain is worse than a cancelled one.
    """
    current = pending()
    if current is None:
        return None

    if open_trades > 0:
        return None

    strategy = str(current["strategy"])
    actor = str(current.get("requested_by") or "operator")
    was_running = bool(current.get("was_running", True))

    if not strategy_exists(strategy):
        clear()
        logger.error(
            "Queued strategy %r is no longer available; dropping the queued change",
            strategy,
        )
        return {
            "applied": False,
            "cancelled": True,
            "strategy": strategy,
            "error": "The queued strategy is no longer available in the volume.",
        }

    try:
        result = await _apply_now(
            strategy, actor=actor, was_running=was_running, freqtrade=freqtrade
        )
    except StrategySwitchError as exc:
        # Keep the queue. The next tick tries again, and the operator can see why
        # from the pending state rather than the change vanishing.
        logger.error("Queued strategy switch failed: %s", exc)
        return {"applied": False, "strategy": strategy, "error": str(exc)}

    clear()
    return result


async def cancel(*, actor: str, was_running: bool, freqtrade) -> Dict[str, Any]:
    """Drop a queued change and resume the bot on the current strategy."""
    current = pending()
    if current is None:
        return {"cancelled": False, "message": "Nothing was queued."}

    clear()

    resumed = False
    if was_running:
        try:
            await freqtrade.start()
            resumed = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cancelled the queue but could not resume the bot: %s", exc)

    return {
        "cancelled": True,
        "resumed": resumed,
        "strategy": current.get("strategy"),
        "message": "Queued change cancelled. The bot will keep using the current strategy.",
    }


def describe() -> Dict[str, Any]:
    """The queue as the UI needs it."""
    current = pending()
    if current is None:
        return {"queued": False}
    return {
        "queued": True,
        "strategy": current.get("strategy"),
        "requested_at": current.get("requested_at"),
        "requested_by": current.get("requested_by"),
        "open_trades_at_request": current.get("open_trades_at_request"),
    }
