"""
Runtime settings store.
=======================

The writable configuration layer.

Why this exists
---------------
The operator-facing configuration used to live entirely in Docker Swarm configs:
read-only, immutable, and changed by editing JSON in Portainer and recreating the
config. That is a reasonable interface for a developer and a poor one for the
person this bot is actually for. Requiring someone to hand-edit a config to
switch on real trading is how mistakes happen - and one of those mistakes (a
mismatched `dry_run` / `db_url` pair) was already found and fixed in this repo.

So the operator gets a settings layer they can change from the UI. That does not
weaken the safety model, because the safety model is about *the AI* not changing
configuration behind the operator's back - not about preventing the operator from
deciding things. The two are kept apart deliberately:

    The AI                          The operator
    ------------------------------  ------------------------------
    reaches nl_config only          reaches this module only
    frozen keys refused             allowlisted keys accepted
    can only propose                changes take effect
    cannot write files              writes one file, validated first

Nothing here is reachable from a chat command, a proposal, or any plugin. The
only caller is the authenticated settings route, on an explicit human action.

How changes take effect
-----------------------
This module writes one file. Freqtrade is started with that file as its LAST
`--config`, so it overrides the Swarm configs for the keys it contains, and
`POST /reload_config` makes Freqtrade re-read its config files from disk and
rebuild the bot - no restart, and no Docker socket mounted anywhere (which would
be root-equivalent access to the host).

Two properties that make this safe rather than merely convenient
--------------------------------------------------------------
1. **`db_url` is derived, never accepted.** The operator sets `dry_run`; this
   module computes the matching database. The mismatch that would blend simulated
   and real trades, and that Freqtrade's own auto-selection cannot catch here
   (it only fires for an unset or default `db_url`), becomes unrepresentable
   rather than merely validated.
2. **Going live needs a typed confirmation.** Not a checkbox. See
   `LIVE_CONFIRMATION_PHRASE`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Where the writable layer lives. Overridable for tests and for running outside
#: a container.
SETTINGS_DIR = Path(os.environ.get("ORCHESTRATOR_SETTINGS_DIR", "/app/settings"))
SETTINGS_FILE = SETTINGS_DIR / "runtime_settings.json"
#: Kept so a bad change can be undone without anyone hand-editing a file.
BACKUP_FILE = SETTINGS_DIR / "runtime_settings.previous.json"

#: The database filenames. These are absolute paths because a relative one
#: resolves to the container's working directory, which is not a persistent
#: volume - trade history would vanish on the next redeploy.
DB_DIR = "/freqtrade/user_data/data"
DRY_RUN_DB = "sqlite:////%s/tradesv3.dryrun.sqlite" % DB_DIR.lstrip("/")
LIVE_DB = "sqlite:////%s/tradesv3.sqlite" % DB_DIR.lstrip("/")

#: The exact phrase required to turn off dry run. Deliberately something nobody
#: types by accident, and that a mis-click cannot produce.
LIVE_CONFIRMATION_PHRASE = "TRADE REAL MONEY"


# ---------------------------------------------------------------------------
# What may be changed
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Setting:
    """One editable setting, with the bound that keeps it survivable.

    Bounds are not decoration. Each one exists because the value on the other
    side of it turns a bad week into a lost account: too many concurrent
    positions multiplies every loss, and a stop loss looser than about 15% on a
    volatile pair is close to not having one.
    """

    key: str
    label: str
    kind: str  # "bool" | "int" | "float" | "ratio" | "percent" | "pairs"
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    help: str = ""
    #: Shown to a non-expert. The raw key means nothing to them; this is the
    #: sentence that lets them make a decision.
    explain: str = ""


#: The allowlist. Anything not in here is refused - including every credential,
#: every secret, the API server block, the exchange block, and `db_url` (which is
#: derived from `dry_run` rather than set).
EDITABLE: Tuple[Setting, ...] = (
    Setting(
        key="dry_run",
        label="Trading mode",
        kind="bool",
        help="true = simulate, false = trade real money",
        explain=(
            "In simulation the bot trades against real Kraken prices with a fake "
            "wallet. No real money moves. Turning this off places real orders "
            "with your real balance."
        ),
    ),
    Setting(
        key="max_open_trades",
        label="Maximum open trades",
        kind="int",
        minimum=1,
        maximum=5,
        help="How many positions can be open at once",
        explain=(
            "Each open position is money at risk at the same time. Fewer "
            "positions means a single bad call hurts less."
        ),
    ),
    Setting(
        key="stoploss",
        label="Stop loss",
        kind="percent",
        minimum=-0.15,
        maximum=-0.02,
        help="How much one trade may lose before it closes (e.g. -0.05 = -5%)",
        explain=(
            "The hard limit on a single loss. This is the setting that decides "
            "how bad one mistake can be, so it is the one worth thinking about "
            "most."
        ),
    ),
    Setting(
        key="tradable_balance_ratio",
        label="Balance used",
        kind="ratio",
        minimum=0.10,
        maximum=0.95,
        help="Share of the wallet the bot may use (0.9 = 90%)",
        explain=(
            "The rest stays untouched as cash. Keeping some back means a bad "
            "stretch cannot use up everything at once."
        ),
    ),
    Setting(
        key="dry_run_wallet",
        label="Simulation wallet",
        kind="float",
        minimum=100.0,
        maximum=1_000_000.0,
        help="Starting balance used while simulating",
        explain=(
            "Only used in simulation, and only affects how the numbers read. "
            "Match it to what you actually plan to invest so the results mean "
            "something."
        ),
    ),
    # The two below are here so that the AI's proposals can actually be applied.
    # `nl_config` can propose them, and before this they were refused by the
    # allowlist at apply time - so the operator was offered a change that could
    # not be carried out. Both are ordinary config keys, so the settings layer
    # can apply them; `strategy` is deliberately NOT here, because the stack
    # passes --strategy on the command line and Freqtrade's own
    # `_process_common_options` overwrites the config value with it, making a
    # settings-based strategy change a silent no-op.
    Setting(
        key="trailing_stop_positive",
        label="Trailing stop",
        kind="float",
        minimum=0.005,
        maximum=0.10,
        help="Once in profit by this much, follow the price up and exit on a pullback",
        explain=(
            "Lets a winning trade keep running instead of closing at a fixed "
            "target, but gives back this much of the peak before it exits. A "
            "smaller number locks in profit sooner."
        ),
    ),
    Setting(
        key="amount_reserve_percent",
        label="Fee buffer",
        kind="float",
        minimum=0.0,
        maximum=0.20,
        help="Extra balance held back to cover fees and slippage",
        explain=(
            "Stops the bot spending the last of the balance on a trade and then "
            "having nothing left for the exchange fee."
        ),
    ),
)

EDITABLE_BY_KEY: Dict[str, Setting] = {s.key: s for s in EDITABLE}

#: Settings this module writes but never accepts from a caller. `db_url` is
#: computed from `dry_run`; listing it here documents that it is written and
#: refused, rather than silently absent.
DERIVED_KEYS: Tuple[str, ...] = ("db_url",)


# ---------------------------------------------------------------------------
# Risk presets
# ---------------------------------------------------------------------------
#: One choice instead of three numbers. The README already described these
#: profiles in prose; this makes them selectable, which is the difference between
#: a paragraph someone has to translate into settings and a button.
#:
#: THIS IS THE ONLY DEFINITION. It used to exist twice - here and again inside
#: nl_config._get_risk_config - and the two copies disagreed on seven values.
#: Asking the assistant for "conservative" set tradable_balance_ratio to 0.80
#: while pressing the Conservative button set it to 0.50: the same word, 60% more
#: capital at risk, from two places an operator would reasonably assume agreed.
#: Nothing caught it because nothing compared them. test_risk_levels.py now does.
#:
#: The values kept are the curated ones, because these are the ones shown next to
#: their labels and blurbs. trailing_stop_positive came from the other copy - it
#: was the one thing that table had and this did not, and dropping it would have
#: silently stopped the assistant setting a trailing stop at all.
RISK_PRESETS: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "label": "Conservative",
        "blurb": "Fewer positions, tighter stop loss. Slower, and much harder to hurt.",
        "values": {
            "max_open_trades": 2,
            "stoploss": -0.04,
            "tradable_balance_ratio": 0.50,
            "trailing_stop_positive": 0.015,
        },
    },
    "moderate": {
        "label": "Moderate",
        "blurb": "The default. A middle ground between missing moves and taking damage.",
        "values": {
            "max_open_trades": 3,
            "stoploss": -0.08,
            "tradable_balance_ratio": 0.90,
            "trailing_stop_positive": 0.02,
        },
    },
    "aggressive": {
        "label": "Aggressive",
        "blurb": "More positions and a looser stop loss. Bigger swings in both directions.",
        "values": {
            "max_open_trades": 5,
            "stoploss": -0.15,
            "tradable_balance_ratio": 0.95,
            "trailing_stop_positive": 0.03,
        },
    },
}


class SettingsError(Exception):
    """A refusal, with a message written for the operator."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _coerce(setting: Setting, value: Any) -> Any:
    """Validate one value and return it in its canonical form.

    `bool` is rejected before anything numeric is considered, because
    `isinstance(True, int)` is True in Python - so a careless numeric check
    accepts `true` for `max_open_trades` and writes a setting that means
    something different from what it looks like.
    """
    if setting.kind == "bool":
        if not isinstance(value, bool):
            raise SettingsError(
                "%s must be true or false, not %r." % (setting.label, value)
            )
        return value

    if isinstance(value, bool):
        raise SettingsError(
            "%s must be a number, not true/false." % setting.label
        )

    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            raise SettingsError(
                "%s must be a number, not %r." % (setting.label, value)
            )

    if not isinstance(value, (int, float)):
        raise SettingsError("%s must be a number." % setting.label)

    number = float(value)

    # NaN and infinity pass every comparison below, so they are refused first.
    if number != number or number in (float("inf"), float("-inf")):
        raise SettingsError("%s must be a finite number." % setting.label)

    if setting.kind == "int":
        if number != int(number):
            raise SettingsError(
                "%s must be a whole number, not %s." % (setting.label, number)
            )
        number = int(number)

    if setting.minimum is not None and number < setting.minimum:
        raise SettingsError(
            "%s of %s is below the safe minimum of %s."
            % (setting.label, number, setting.minimum)
        )
    if setting.maximum is not None and number > setting.maximum:
        raise SettingsError(
            "%s of %s is above the safe maximum of %s."
            % (setting.label, number, setting.maximum)
        )

    return number


def _db_url_for(dry_run: bool) -> str:
    """The database that must accompany a trading mode.

    Derived rather than accepted. Freqtrade chooses its database from `dry_run`,
    but only when `db_url` is unset or exactly its own default - and this stack
    sets an absolute path, so that choice never fires. Left to a human, the two
    get out of step, and the consequences are silent: simulated profit mixed into
    real statistics, and open simulated trades that the bot then tries to sell on
    a real exchange.
    """
    return DRY_RUN_DB if dry_run else LIVE_DB


def validate(settings: Dict[str, Any], *, confirmation: Optional[str] = None) -> Dict[str, Any]:
    """Validate a requested settings payload and return what to write.

    Raises `SettingsError` with a message intended to be shown to the operator
    rather than logged. Returns the canonical dict, including the derived
    `db_url`.
    """
    if not isinstance(settings, dict):
        raise SettingsError("Settings must be an object.")

    unknown = sorted(set(settings) - set(EDITABLE_BY_KEY))
    if unknown:
        # Name the derived keys specifically: someone who read the config files
        # will reasonably try to set db_url, and "unknown setting" would be a
        # useless answer.
        derived = [k for k in unknown if k in DERIVED_KEYS]
        if derived:
            raise SettingsError(
                "%s is set automatically from the trading mode and cannot be set "
                "directly. Change the trading mode instead - that keeps the two "
                "in step." % ", ".join(derived)
            )
        raise SettingsError(
            "Not a setting that can be changed here: %s. Changeable settings are: %s."
            % (", ".join(unknown), ", ".join(sorted(EDITABLE_BY_KEY)))
        )

    if not settings:
        raise SettingsError("No settings supplied.")

    clean: Dict[str, Any] = {}
    for key, value in settings.items():
        clean[key] = _coerce(EDITABLE_BY_KEY[key], value)

    # Going live is the one change that cannot be undone by a reload, so it is
    # gated on a phrase that has to be typed. A checkbox gets clicked by
    # accident; this does not.
    if clean.get("dry_run") is False:
        if (confirmation or "").strip().upper() != LIVE_CONFIRMATION_PHRASE:
            raise SettingsError(
                'Turning off simulation places real orders with real money. To '
                'confirm, type exactly "%s".' % LIVE_CONFIRMATION_PHRASE
            )

    # If the mode is changing, the derived key comes along with it.
    if "dry_run" in clean:
        clean["db_url"] = _db_url_for(bool(clean["dry_run"]))

    return clean


def apply_preset(name: str) -> Dict[str, Any]:
    """The values a named risk preset expands to."""
    preset = RISK_PRESETS.get(name)
    if not preset:
        raise SettingsError(
            "Unknown risk level %r. Choose one of: %s."
            % (name, ", ".join(sorted(RISK_PRESETS)))
        )
    return dict(preset["values"])


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------
@dataclass
class SettingsSnapshot:
    """What is currently set, and where it came from."""

    settings: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None
    exists: bool = False
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "settings": self.settings,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "exists": self.exists,
            "error": self.error,
        }


def read() -> SettingsSnapshot:
    """Read the current runtime settings.

    A missing file is normal and means "nothing overridden yet" - the Swarm
    configs are in charge. A corrupt file is reported rather than raised: the bot
    is trading on the Swarm configs in that case, and refusing to answer would
    hide which settings are actually in force.
    """
    if not SETTINGS_FILE.exists():
        return SettingsSnapshot(exists=False)

    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Runtime settings file is unreadable: %s", exc)
        return SettingsSnapshot(exists=True, error=str(exc))

    if not isinstance(raw, dict):
        return SettingsSnapshot(exists=True, error="settings file is not an object")

    meta = raw.pop("_meta", {}) if isinstance(raw.get("_meta"), dict) else {}
    return SettingsSnapshot(
        settings=raw,
        updated_at=meta.get("updated_at"),
        updated_by=meta.get("updated_by"),
        exists=True,
    )


def write(settings: Dict[str, Any], *, actor: str) -> SettingsSnapshot:
    """Write validated settings, keeping the previous file as a backup.

    Atomic: written to a temporary file in the same directory and moved into
    place, so a crash mid-write cannot leave Freqtrade reading a half-written
    config - which would stop the bot from starting at all.

    The backup is taken so a change can be undone from the UI. Without it,
    "undo" means editing JSON in Portainer, which is the interface this module
    exists to avoid.
    """
    payload = dict(settings)
    payload["_meta"] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": actor,
    }

    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    if SETTINGS_FILE.exists():
        try:
            shutil.copy2(SETTINGS_FILE, BACKUP_FILE)
        except OSError as exc:
            logger.warning("Could not back up settings before writing: %s", exc)

    fd, tmp_name = tempfile.mkstemp(dir=str(SETTINGS_DIR), prefix=".settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, SETTINGS_FILE)
    except Exception:
        # Leave no partial file behind for Freqtrade to trip over.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    logger.info("Runtime settings written by %s: %s", actor, sorted(settings))
    return read()


def restore_backup(*, actor: str) -> SettingsSnapshot:
    """Put the previous settings back. Used by the UI's Undo."""
    if not BACKUP_FILE.exists():
        raise SettingsError(
            "There is no previous version to restore - settings have only been "
            "changed once, or never.",
            status_code=404,
        )
    try:
        previous = json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SettingsError("The backup file is unreadable: %s" % exc, status_code=500)

    previous.pop("_meta", None)
    if not isinstance(previous, dict):
        raise SettingsError("The backup file is not a settings object.", status_code=500)

    return write(previous, actor=actor)


def describe() -> Dict[str, Any]:
    """Everything the UI needs to render the settings panel."""
    snapshot = read()
    current = snapshot.settings

    # Match the current numbers back to a preset name, so the UI can show which
    # risk level is in force rather than three unrelated numbers.
    active_preset = None
    for name, preset in RISK_PRESETS.items():
        if all(current.get(k) == v for k, v in preset["values"].items()):
            active_preset = name
            break

    return {
        "editable": [
            {
                "key": s.key,
                "label": s.label,
                "kind": s.kind,
                "minimum": s.minimum,
                "maximum": s.maximum,
                "help": s.help,
                "explain": s.explain,
                "value": current.get(s.key),
            }
            for s in EDITABLE
        ],
        "derived": list(DERIVED_KEYS),
        "presets": {
            name: {"label": p["label"], "blurb": p["blurb"], "values": p["values"]}
            for name, p in RISK_PRESETS.items()
        },
        "active_preset": active_preset,
        "live_confirmation_phrase": LIVE_CONFIRMATION_PHRASE,
        "current": snapshot.as_dict(),
        "file": str(SETTINGS_FILE),
        "has_backup": BACKUP_FILE.exists(),
    }
