"""
Dry-run reset.
==============

Starting the simulation over with a clean slate.

Why this exists
---------------
A dry run is only informative if you can compare like with like. Change a
setting, change the strategy, and the accumulated history is no longer a
measurement of the thing you are now running - it is an average of the old rules
and the new ones. The alternative to resetting is either never changing anything
or quietly averaging across changes and drawing conclusions from the mixture.

So the operator needs a way to start over. What they must not get is a way to
lose real trade history, or a reset that appears to work and leaves the bot
inert.

Three things make this safe rather than merely convenient
--------------------------------------------------------
1. **It refuses to run when the bot is live.** The trading mode is read from
   Freqtrade itself (`/show_config`), not from a file, so this cannot be fooled
   by a settings file that disagrees with the running bot. If the bot is placing
   real orders, nothing here is reachable. Deleting real trade history is not a
   mistake that can be undone, so it is not a possibility that is offered.
2. **It clears pair locks.** The strategy's protections write locks into a
   `pairlocks` table that survives a restart. Reset the trades but leave the
   locks, and the bot refuses to trade because of a drawdown that happened in a
   simulation that no longer exists. It would look broken while behaving exactly
   as designed - the worst kind of bug to hand to someone who is learning.
3. **It backs the trades up first.** "Start over" should mean a clean slate, not
   amnesia. The trades are written to JSON in the settings volume before they are
   deleted, so the previous run can still be read afterwards. For someone trying
   to learn what the bot actually did, that record is the whole point.

The deletion itself goes through Freqtrade's own API rather than the database
file, because that path cancels each trade's open orders and its on-exchange stop
loss first. Removing rows directly would leave real orders on the exchange with
nothing tracking them.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_orchestrator.core.settings_store import SETTINGS_DIR

logger = logging.getLogger(__name__)

#: Typed to confirm. A reset is recoverable only in the sense that the trade list
#: was copied aside - the positions and the profit curve are gone - so it gets
#: the same treatment as going live.
RESET_CONFIRMATION_PHRASE = "RESET DRY RUN"

#: How many trades the backup keeps in full detail. A long dry run can accumulate
#: thousands; the point is to preserve the record, not to guarantee a complete
#: export, and an unbounded file in a shared volume is its own problem.
BACKUP_TRADE_LIMIT = 2000


class ResetRefused(Exception):
    """A refusal, with a message written for the operator."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ResetPreview:
    """What a reset would do, before anything is touched."""

    allowed: bool = False
    dry_run: Optional[bool] = None
    open_trades: List[Dict[str, Any]] = field(default_factory=list)
    total_trades: int = 0
    locks: List[Dict[str, Any]] = field(default_factory=list)
    reason: Optional[str] = None
    confirmation_phrase: str = RESET_CONFIRMATION_PHRASE

    def as_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "dry_run": self.dry_run,
            "open_trades": self.open_trades,
            "open_trade_count": len(self.open_trades),
            "total_trades": self.total_trades,
            "locks": self.locks,
            "lock_count": len(self.locks),
            "reason": self.reason,
            "confirmation_phrase": self.confirmation_phrase,
        }


async def _effective_dry_run(client: Any) -> bool:
    """Read the trading mode from the running bot.

    Deliberately not read from the settings file or the Swarm configs. Those
    describe what the bot was *told*; `/show_config` reports what it is actually
    doing. When the two disagree - a settings change written but not yet applied
    by a reload - the file would say "simulation" while real orders are being
    placed, and a reset would delete real history.

    A bot that cannot be reached is treated as live. Failing closed costs a
    retry; failing open costs the trade history. Every failure mode is caught
    here rather than propagated, because a propagated exception would escape the
    refusal and the caller would have to remember to fail closed - which is
    exactly the kind of thing that gets forgotten. An earlier version of this
    function only guarded the missing-field case, and a connection error sailed
    past it.
    """
    try:
        config = await client.get_config()
    except Exception as exc:  # noqa: BLE001 - fail closed on anything at all
        raise ResetRefused(
            "Could not reach the bot to confirm its trading mode, so nothing "
            "was reset. This is deliberate: if the mode cannot be established, "
            "a reset might be deleting real trade history. (%s)" % exc,
            status_code=503,
        ) from exc

    if not isinstance(config, dict) or "dry_run" not in config:
        raise ResetRefused(
            "The bot did not report its trading mode, so nothing was reset. "
            "This is deliberate: if the mode cannot be established, the reset "
            "might be deleting real trade history.",
            status_code=503,
        )
    return bool(config["dry_run"])


def _trade_summary(trade: Any) -> Dict[str, Any]:
    """The fields worth keeping about a trade, defensively.

    `Trade` is a dataclass in this codebase, but the backup must not depend on
    that: it is written on the one code path where losing the trade list is
    permanent, so every field is fetched with a default.
    """
    def get(name: str, default: Any = None) -> Any:
        value = getattr(trade, name, default)
        return value if value is not None else default

    return {
        "id": get("id", get("trade_id")),
        "pair": get("pair"),
        "is_open": get("is_open", False),
        "open_date": str(get("open_date", "")) or None,
        "close_date": str(get("close_date", "")) or None,
        "amount": get("amount"),
        "open_rate": get("open_rate"),
        "close_rate": get("close_rate"),
        "profit_abs": get("profit_abs"),
        "profit_ratio": get("profit_ratio"),
        "exit_reason": get("exit_reason"),
        "enter_tag": get("enter_tag"),
        "stake_amount": get("stake_amount"),
    }


def _write_backup(trades: List[Dict[str, Any]], *, dry_run: bool) -> Optional[str]:
    """Copy the trade list aside before it is deleted.

    Best effort, and reported rather than raised: a backup failure is worth
    knowing about, but it should not be the reason someone cannot start over.
    The caller surfaces `backup_error` so the operator is told plainly that this
    reset has no record.
    """
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SETTINGS_DIR / f"dryrun-reset-{stamp}.json"

    payload = {
        "_meta": {
            "reset_at": datetime.now(timezone.utc).isoformat(),
            "trading_mode": "dry_run" if dry_run else "live",
            "trade_count": len(trades),
            "truncated": len(trades) > BACKUP_TRADE_LIMIT,
        },
        "trades": trades[:BACKUP_TRADE_LIMIT],
    }

    try:
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except OSError as exc:
        logger.error("Could not write dry-run reset backup: %s", exc)
        return None

    logger.info("Dry-run reset backup written to %s (%d trades)", path, len(trades))
    return str(path)


async def _release_all_locks(client: Any) -> Dict[str, Any]:
    """Release every active pair lock, reporting any that would not release.

    The loop lives here rather than on the API client so there is one
    implementation and this module's tests exercise it. A convenience wrapper on
    the client would be a second copy, and the copy that is not tested is the one
    that drifts.

    Freqtrade's bulk endpoint (POST /locks/delete) takes an explicit lockid or
    pair and clears nothing when given neither, so iterating is the only way to
    clear them all. A lock that disappears between the listing and the delete is
    not an error: the goal state is "no locks", and it is already true.
    """
    locks = await client.get_locks()
    deleted: List[int] = []
    failed: List[Dict[str, Any]] = []

    for lock in locks:
        lock_id = lock.get("id") if isinstance(lock, dict) else None
        if not isinstance(lock_id, int):
            continue
        try:
            await client.delete_lock(lock_id)
            deleted.append(lock_id)
        except Exception as exc:  # noqa: BLE001 - one failure must not stop the rest
            failed.append({"id": lock_id, "error": str(exc)})

    return {"deleted": deleted, "failed": failed, "count": len(deleted)}


async def preview(client: Any) -> ResetPreview:
    """Describe what a reset would do. Reads only."""
    try:
        dry_run = await _effective_dry_run(client)
    except ResetRefused as exc:
        return ResetPreview(allowed=False, reason=exc.message)
    except Exception as exc:  # noqa: BLE001 - fail closed, never fail open
        logger.error("Could not determine trading mode for reset preview: %s", exc)
        return ResetPreview(
            allowed=False,
            reason=(
                "Could not reach the bot to confirm its trading mode, so the "
                "reset is unavailable. (%s)" % exc
            ),
        )

    if not dry_run:
        return ResetPreview(
            allowed=False,
            dry_run=False,
            reason=(
                "The bot is trading real money, so the simulation reset is "
                "disabled. Real trade history is not deletable from here. To "
                "reset a simulation, switch back to dry run first - and close "
                "any open positions before you do."
            ),
        )

    trades = await client.get_trades(limit=10000)
    locks = await client.get_locks()

    return ResetPreview(
        allowed=True,
        dry_run=True,
        open_trades=[_trade_summary(t) for t in trades if getattr(t, "is_open", False)],
        total_trades=len(trades),
        locks=locks,
    )


async def reset(client: Any, *, confirmation: str, actor: str) -> Dict[str, Any]:
    """Delete every simulated trade and release every pair lock.

    Returns a report of what happened, including per-trade failures. A partial
    reset is reported as partial rather than as success: if some trades could not
    be deleted, the history is not clean and the operator needs to know before
    they start drawing conclusions from it.
    """
    if (confirmation or "").strip().upper() != RESET_CONFIRMATION_PHRASE:
        raise ResetRefused(
            'This deletes the entire simulated trade history. To confirm, type '
            'exactly "%s".' % RESET_CONFIRMATION_PHRASE
        )

    state = await preview(client)
    if not state.allowed:
        raise ResetRefused(state.reason or "Reset is not available.", status_code=403)

    trades = await client.get_trades(limit=10000)
    summaries = [_trade_summary(t) for t in trades]

    backup_path = _write_backup(summaries, dry_run=True)

    # Locks are released first. If trade deletion fails partway, a bot that is
    # still holding positions but no longer locked out is the more usable state;
    # the reverse - positions gone, still locked - looks like a dead bot.
    lock_report = await _release_all_locks(client)

    deleted: List[int] = []
    failed: List[Dict[str, Any]] = []

    for trade in trades:
        trade_id = getattr(trade, "id", None)
        if not isinstance(trade_id, int):
            continue
        try:
            await client.delete_trade(trade_id)
            deleted.append(trade_id)
        except Exception as exc:  # noqa: BLE001 - one failure must not stop the rest
            failed.append({"id": trade_id, "error": str(exc)})

    logger.info(
        "Dry-run reset by %s: %d trades deleted, %d failed, %d locks released",
        actor,
        len(deleted),
        len(failed),
        lock_report.get("count", 0),
    )

    complete = not failed

    return {
        "status": "reset" if complete else "partial",
        "trades_deleted": len(deleted),
        "trades_failed": failed,
        "locks_released": lock_report.get("count", 0),
        "locks_failed": lock_report.get("failed", []),
        "backup_path": backup_path,
        "backup_error": None if backup_path else "the trade list could not be copied aside",
        "summary": _summary(len(deleted), failed, lock_report, backup_path),
    }


def _summary(
    deleted: int,
    failed: List[Dict[str, Any]],
    lock_report: Dict[str, Any],
    backup_path: Optional[str],
) -> str:
    """A sentence for the operator, in plain language."""
    parts = ["Cleared %d simulated trade%s." % (deleted, "" if deleted == 1 else "s")]

    locks = lock_report.get("count", 0)
    if locks:
        parts.append(
            "Released %d trading lock%s the protections had put in place."
            % (locks, "" if locks == 1 else "s")
        )

    if backup_path:
        parts.append("The previous trades were saved to %s first." % Path(backup_path).name)
    else:
        parts.append(
            "WARNING: the previous trades could NOT be saved, so that record is gone."
        )

    if failed:
        parts.append(
            "%d trade%s could not be deleted, so this reset is incomplete - the "
            "history is not clean yet."
            % (len(failed), "" if len(failed) == 1 else "s")
        )

    if lock_report.get("failed"):
        parts.append(
            "%d lock%s could not be released; the bot may stay locked out of "
            "those pairs." % (len(lock_report["failed"]), "" if len(lock_report["failed"]) == 1 else "s")
        )

    return " ".join(parts)
