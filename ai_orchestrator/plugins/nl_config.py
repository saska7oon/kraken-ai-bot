"""
Natural Language Configuration Plugin
=====================================

Translates plain-language commands into either:

1. **Runtime actions** that Freqtrade genuinely supports over its REST API -
   pause, resume, pair restriction, status queries. These are executed for real.

2. **Configuration proposals** - everything else (stoploss, margin of capital at
   risk, profit targets, max open trades, strategy choice). Freqtrade reads its
   configuration at startup and has **no** runtime config-write endpoint, and
   this process cannot write the Swarm config either. A proposal is therefore
   recorded, explained, audited, and handed back with the exact values to apply
   by updating the Swarm config and redeploying.

Why this file was rewritten
---------------------------
The previous version POSTed to ``/api/v1/config`` (which does not exist) and
reported ``"status": "success"`` for every change. It also POSTed to
``/api/v1/whitelist/add`` and ``/whitelist/remove`` (also nonexistent) and
called ``/api/v1/resume`` (nonexistent). Every "applied" change was a lie: the
errors were caught by a broad ``except`` and returned as failed results that
nothing surfaced.

It also allowed ``dry_run`` to be treated as an ordinary config value. Switching
a bot from simulation to real money is not an ordinary config change, and for a
non-expert operator it is the single most dangerous action available.

Security model
--------------
Every control in this file exists because of a specific way the previous code
could be abused. They are listed here so that a future change does not quietly
remove one of them.

1. **Frozen keys.** ``dry_run`` and every credential path can never be proposed
   or applied through this interface, at any confidence level. Keys are
   normalised (stripped and lower-cased) before the check, because
   ``"DRY_RUN"``, ``" dry_run"`` and ``"Dry_Run"`` all mean the same thing to a
   human and must all be refused.

2. **Bounds and an explicit allowlist.** A numeric setting is accepted only if
   it is inside :data:`BOUNDS`, and a key that has no bounds is refused rather
   than silently passed through. Booleans are rejected before anything else is
   tried, because ``isinstance(True, int)`` is ``True`` in Python and ``True``
   would otherwise be read as the number 1 - which is a legal value for some
   settings. Non-finite numbers are rejected too, since ``float("nan")``
   compares false against every bound and would slip through.

3. **Proposal binding.** An approval must name a proposal *this process
   created* (``proposal_id``) and apply exactly the change list that was stored
   under it. The API no longer accepts a change list from the request body: the
   operator approves a rendered message, so if the machine could apply a
   different list the approval would be meaningless. Stored proposals are
   single-use, expire after :data:`PROPOSAL_TTL_SECONDS`, are fingerprinted with
   SHA-256, and are re-validated against controls 1 and 2 immediately before
   they are applied. They live in memory only, so a restart discards them.

4. **Audit before apply.** The intent, the full change list and its hash are
   written to the audit log *before* the first change runs, each change is
   isolated so one failure cannot skip the rest, and a completion entry is
   always written - including when a change raises. The previous code audited
   once, after the loop, so a change that raised half way through was applied
   and never recorded.

5. **No plugin runs from an approval.** A ``trigger`` change is refused. Plugin
   runs have their own authenticated endpoint
   (``POST /api/v1/plugins/{name}/control`` with ``action="run"``); letting an
   "approval" start an arbitrary plugin turned the approval gate into a generic
   command executor.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ai_orchestrator.core import settings_store
from ai_orchestrator.core.freqtrade_api import FreqtradeAPIError, UnsupportedOperation
from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig
from ai_orchestrator.core.settings_store import RISK_PRESETS

logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY BOUNDS AND FROZEN KEYS
# =============================================================================
# Keys that may never be proposed, let alone changed, through this interface.
# Switching to live trading must be a deliberate, out-of-band act.
FROZEN_KEYS: Dict[str, str] = {
    "dry_run": (
        "Switching between simulation and live trading cannot be done through the AI "
        "interface, with or without approval. This is deliberate: live mode places "
        "real orders with real money, so it is the operator's decision alone. Use the "
        "Settings panel and type the confirmation phrase. You should have weeks of "
        "satisfactory dry-run results first."
    ),
    "exchange": "Exchange credentials are managed as Swarm secrets only.",
    "exchange.key": "Exchange credentials are managed as Swarm secrets only.",
    "exchange.secret": "Exchange credentials are managed as Swarm secrets only.",
    "api_server": "API server credentials are managed as Swarm secrets only.",
    "jwt_secret_key": "Secret material; managed as Swarm secrets only.",
    "ws_token": "Secret material; managed as Swarm secrets only.",
}

# Hard bounds. Anything outside these is refused regardless of what was asked.
BOUNDS: Dict[str, Dict[str, Any]] = {
    "stoploss": {
        "min": -0.15,
        "max": -0.02,
        "explain": (
            "The stop loss is how much a single trade can lose before it is closed "
            "automatically. -8% is the moderate default; the loosest permitted is -15%."
        ),
    },
    "max_open_trades": {
        "min": 1,
        "max": 5,
        "explain": (
            "How many trades can be open at the same time. More trades means more of "
            "your money is in the market at once."
        ),
    },
    "tradable_balance_ratio": {
        "min": 0.10,
        "max": 0.95,
        "explain": (
            "The share of your wallet the bot is allowed to use. 0.90 means 90%, "
            "keeping 10% back."
        ),
    },
    "trailing_stop_positive": {
        "min": 0.005,
        "max": 0.10,
        "explain": (
            "Once a trade is in profit by this much, the bot follows the price up and "
            "closes if it falls back."
        ),
    },
    "amount_reserve_percent": {"min": 0.0, "max": 0.20, "explain": "Fee/slippage buffer."},
}

# Intents that are executed for real over the REST API.
RUNTIME_ACTIONS = {"pause_resume", "show_status", "explain_trade", "restrict_pairs"}
# Intents that only ever produce a proposal.
PROPOSAL_INTENTS = {"change_risk", "change_stoploss", "change_position_size", "change_strategy"}

# Settings whose value must be a whole number. Freqtrade accepts 3.0 for these
# but writes it back as a float, and a non-expert reading "max_open_trades: 3.0"
# cannot tell whether something odd happened. Integral floats are converted, and
# 2.5 is refused rather than rounded - rounding a risk limit in either direction
# silently changes how much money is at risk.
INTEGER_KEYS = frozenset({"max_open_trades"})

# -----------------------------------------------------------------------------
# THE EXPLICIT ALLOWLIST OF PROPOSABLE SETTINGS
# -----------------------------------------------------------------------------
# A key with no entry here is refused outright. The old code only looked up
# BOUNDS and, finding nothing, accepted the value unchecked - so an unknown or
# misspelled key ("stoploss " with a trailing space, "unbounded_key") was
# carried straight through to the operator as a "validated" proposal. Adding a
# setting to this interface is now a deliberate edit to this set.
PROPOSABLE_KEYS = frozenset(set(BOUNDS) | {"strategy"})

# Change types an approval is allowed to carry out.
#   proposal_only - a setting to put into the Swarm config out of band
#   bot_control   - pause/resume over the Freqtrade REST API
#   runtime_pairs - restrict the traded pairs over the Freqtrade REST API
#   query         - read-only lookups
#   note / clarification - text for the operator, no action
APPROVABLE_CHANGE_TYPES = frozenset(
    {"proposal_only", "bot_control", "runtime_pairs", "query", "note", "clarification"}
)

# Change types that must NEVER be carried out by an approval. Running a plugin
# has its own authenticated endpoint; routing it through an approval made the
# approval gate a generic "run any plugin" button.
PLUGIN_RUN_CHANGE_TYPES = frozenset({"trigger"})

BOT_CONTROL_ACTIONS = frozenset({"pause", "resume"})

# A strategy name ends up in the Swarm config, so it must look like a Python
# class name and nothing else - no paths, no spaces, no punctuation.
_STRATEGY_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
# A trading pair such as BTC/CAD. Deliberately strict: this value is handed to
# the bot's whitelist/blacklist machinery.
_PAIR_RE = re.compile(r"^[A-Za-z0-9]{2,15}/[A-Za-z0-9]{2,15}$")

# Quote currencies the operator is willing to hold. Freqtrade's stake_currency is
# CAD for this bot, and a pair quoted in anything else does not match the wallet:
# the bot would be asked to buy something it cannot pay for with the balance it
# has, or to value trades in a currency the operator never chose. Configurable,
# so changing stake_currency does not silently leave this behind.
DEFAULT_ALLOWED_QUOTES = ("CAD",)

# Kraken lists 3x leveraged tokens that LOOK like ordinary coins. They reset
# daily, decay in a sideways market, and can lose most of their value in days -
# the single most dangerous thing a beginner can be talked into buying. The
# strategy is spot-only long, so these are never appropriate here.
#
# Matched on the base asset. Anchored at the end so a real coin that merely
# contains these letters (e.g. "BULLISH") is not caught by accident, and
# case-insensitive because Kraken's own symbols are inconsistent.
LEVERAGED_TOKEN_PATTERN = re.compile(
    r"(?:"
    r"\d+L|\d+S"          # 3L, 5S - the Bybit/Binance style
    r"|UP$|DOWN$"           # BTCUP, ETHDOWN
    r"|BULL$|BEAR$"         # XBTEURBULL style
    r"|3X$|5X$"             # explicit leverage markers
    r")",
    re.IGNORECASE,
)

# -----------------------------------------------------------------------------
# PENDING PROPOSAL STORE
# -----------------------------------------------------------------------------
# How long an approval stays valid. Long enough for an operator to read the
# proposal, look at their bot and decide; short enough that a proposal left open
# on a screen overnight is not still actionable tomorrow morning.
PROPOSAL_TTL_SECONDS = 30 * 60

# The TTL can be tuned from the plugin config, but only inside these limits, so
# a configuration mistake cannot create proposals that never expire.
MIN_PROPOSAL_TTL_SECONDS = 60
MAX_PROPOSAL_TTL_SECONDS = 60 * 60

# An upper bound on stored proposals so a burst of commands cannot grow this
# process's memory without limit. The oldest pending proposal is discarded (and
# the discard is audited) to make room.
MAX_PENDING_PROPOSALS = 25

# An upper bound on the size of a single stored change list.
MAX_CHANGES_PER_PROPOSAL = 25


@dataclass
class NLCommand:
    """Parsed natural language command."""

    intent: str
    parameters: Dict[str, Any]
    confidence: float
    original_text: str
    requires_approval: bool = True


# =============================================================================
# PROPOSAL PLUMBING
# =============================================================================
def _canonical_json(payload: Any) -> str:
    """
    Deterministic JSON, used for fingerprinting a change list.

    Sorted keys and compact separators mean the same logical list always hashes
    to the same value, whatever order a dictionary happened to be built in.
    ``default=str`` keeps this from raising on an unusual value type - a
    fingerprint that raises would be a way to make an approval unverifiable.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_changes(changes: Any) -> str:
    """SHA-256 fingerprint of a change list."""
    return hashlib.sha256(_canonical_json(changes).encode("utf-8")).hexdigest()


def _fmt_percent(value: Any) -> str:
    """
    Render a ratio as a friendly percentage: -0.08 -> '8%'.

    Never raises. The old code built the stop-loss description with an inline
    f-string, so an LLM answer of ``{"value": "aggressive"}`` raised ValueError
    while the description was being *formatted* - before validation could mark
    the change invalid - and the operator saw an HTTP 500 instead of a refusal.
    """
    try:
        text = f"{abs(float(value)) * 100:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "an unknown percentage"
    if not text:
        text = "0"
    return f"{text}%"


def _iso(timestamp: float) -> str:
    """Epoch seconds as a UTC ISO-8601 string, for anything the operator reads."""
    try:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return "unknown"


class ProposalError(Exception):
    """
    An approval could not be honoured.

    Carries an HTTP status so the API layer does not have to guess, and a message
    written for a non-expert operator. Every raise site has already recorded the
    refusal in the audit log, so a refusal is never silent.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class PendingProposal:
    """
    One change list waiting for the operator to approve or reject it.

    Everything the approval decision needs is captured here at propose time, so
    that approving cannot be influenced by whatever the caller sends later.
    ``change_hash`` is the SHA-256 of the canonical JSON of ``changes`` and is
    re-checked at approval time: if the stored list ever stopped matching its
    fingerprint, the proposal is refused rather than applied.
    """

    proposal_id: str
    created_at: float
    expires_at: float
    requested_by: str
    user_id: str
    intent: str
    confidence: float
    changes: List[Dict[str, Any]]
    change_hash: str
    command_text: str = ""
    message: str = ""

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (time.time() if now is None else now) >= self.expires_at

    def seconds_remaining(self) -> int:
        return max(0, int(self.expires_at - time.time()))

    def public_dict(self) -> Dict[str, Any]:
        """
        The operator-facing view of this proposal.

        Includes the change list, because the whole point of the endpoint is that
        the operator can read what is awaiting approval and compare it with the
        message they were shown. It cannot contain secret material: frozen keys
        are refused long before a proposal is stored.
        """
        return {
            "proposal_id": self.proposal_id,
            "status": "pending_approval",
            "intent": self.intent,
            "confidence": self.confidence,
            "requested_by": self.requested_by,
            "user_id": self.user_id,
            "created_at": _iso(self.created_at),
            "expires_at": _iso(self.expires_at),
            "expires_in_seconds": self.seconds_remaining(),
            "change_count": len(self.changes),
            "change_hash": self.change_hash,
            "changes": self.changes,
            "message": self.message,
        }


#: Human-readable phrasing for a risk-preset value, derived from the value.
#:
#: These used to be hand-written strings sitting next to each number, in a second
#: copy of the presets that had drifted from the first. Generating them removes
#: the only way a description can disagree with the value it describes - which is
#: how "Use at most 80% of the wallet" came to sit beside a panel saying 50%.
def _describe_risk_value(key: str, value: Any) -> str:
    if key == "max_open_trades":
        return f"At most {value} trades at once"
    if key == "stoploss":
        return f"Stop loss of {abs(float(value)) * 100:.0f}%"
    if key == "tradable_balance_ratio":
        return f"Use at most {float(value) * 100:.0f}% of the wallet"
    if key == "trailing_stop_positive":
        return f"Follow profit from {float(value) * 100:.1f}%"
    return f"{key} = {value}"


class NLConfigPlugin(BasePlugin):
    """
    Natural language to configuration translator.

    Commands such as "make it more conservative", "pause trading",
    "why did it sell ETH?".
    """

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)
        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger

        self.auto_apply_safe = config.config.get("auto_apply_safe", False)

        # Quote currencies the operator is willing to hold, defaulting to CAD.
        # Read from plugin config so a change to the bot's stake_currency does not
        # leave this rule silently enforcing the wrong currency.
        configured_quotes = config.config.get("allowed_quote_currencies")
        if isinstance(configured_quotes, list) and configured_quotes:
            self.allowed_quote_currencies = tuple(
                str(q).strip().upper() for q in configured_quotes if str(q).strip()
            ) or DEFAULT_ALLOWED_QUOTES
        else:
            self.allowed_quote_currencies = DEFAULT_ALLOWED_QUOTES
        self.require_approval_for = config.config.get(
            "require_approval_for",
            ["change_risk", "whitelist_change", "strategy_change", "stoploss_change"],
        )

        # Proposals awaiting approval, keyed by a random, unguessable id.
        #
        # In memory only, and deliberately so: a proposal that survived a restart
        # would be an approval of something the operator may no longer be looking
        # at. If the process restarts, pending proposals are gone and the operator
        # simply re-issues the command - failing closed costs one retyped sentence.
        self._pending_proposals: Dict[str, PendingProposal] = {}

        # Clamped: a configuration typo must not be able to create proposals that
        # never expire, nor ones that expire before the operator can read them.
        try:
            ttl = int(config.config.get("proposal_ttl_seconds", PROPOSAL_TTL_SECONDS))
        except (TypeError, ValueError):
            ttl = PROPOSAL_TTL_SECONDS
        self.proposal_ttl_seconds = max(
            MIN_PROPOSAL_TTL_SECONDS, min(MAX_PROPOSAL_TTL_SECONDS, ttl)
        )

        try:
            cap = int(config.config.get("max_pending_proposals", MAX_PENDING_PROPOSALS))
        except (TypeError, ValueError):
            cap = MAX_PENDING_PROPOSALS
        self.max_pending_proposals = max(1, min(200, cap))

        self.intent_patterns = {
            "change_risk": [
                r"(more|less|higher|lower|increase|decrease).*(risk|aggressive|conservative)",
                r"(conservative|moderate|aggressive)\s*mode",
            ],
            "restrict_pairs": [
                r"(add|remove|include|exclude).*(pair|whitelist|coin|token)",
                r"whitelist.*(add|remove)",
            ],
            "change_stoploss": [
                r"(tighten|loosen|widen|change).*(stoploss|stop.loss|stop)",
            ],
            "change_position_size": [
                r"(increase|decrease|change).*(position|stake|size|amount)",
            ],
            "pause_resume": [
                r"(pause|stop|halt|resume|start|continue)\s*(trading|bot)?",
            ],
            "change_strategy": [
                r"(switch|change|use).*(strategy|approach|method)",
            ],
            "show_status": [
                r"(show|display|get|what).*(status|performance|trades|profit|balance)",
                r"how('s| is| are)\s+(things|it|everything)\s*(going|doing)?",
            ],
            # Deliberately separate from show_status: this asks about the coins,
            # not the account. When it was missing entirely, the fallback had no
            # way to express "how are the markets?" at all.
            "market_analysis": [
                r"(market|markets|conditions|sentiment|volatility).*(condition|doing|look|analysis|now)?",
                r"what('s| is| are).*(market|btc|eth|sol|xrp|bitcoin|ethereum|doing|happening)",
            ],
            "explain_trade": [
                # "sold" alone missed "why did it sell ETH?" - the most natural
                # way to ask. Both tenses are listed now.
                r"(why|explain|reason).*(bought|buy|sold|sell|selling|"
                r"trade|entry|exit|close|closed)",
            ],
        }

    async def initialize(self) -> bool:
        self.logger.info("Natural language config plugin initialized")
        if self.auto_apply_safe:
            self.logger.warning(
                "auto_apply_safe is set, but config changes are never applied "
                "automatically by this plugin - only runtime actions can execute."
            )
        self.logger.info(
            "Approvals must name a stored proposal (id from the command response); "
            "proposals expire after %d seconds and can be used once.",
            self.proposal_ttl_seconds,
        )
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """Event-driven plugin; can also be invoked manually with a command."""
        command = kwargs.get("command")
        if command:
            return await self.process_command(command)
        return {"status": "idle", "message": "NL config plugin ready for commands"}

    # ------------------------------------------------------------------ command
    async def process_command(
        self,
        text: str,
        user_id: str = "operator",
        actor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Interpret a command and either execute it or return a proposal.

        ``user_id`` is the label the caller supplied with the request; ``actor``
        is the authenticated operator identity taken from the bearer token (and
        its optional name header). The authenticated value is authoritative for
        the audit log and for the proposal record, so ``approved_by`` carries
        real attribution instead of a hardcoded "operator".
        """
        self.logger.info("Processing command: %s", text)

        requester = str(actor or "").strip() or str(user_id or "").strip() or "operator"

        parsed = await self._parse_intent(text)
        if not parsed or parsed.confidence < 0.5:
            return {
                "status": "unclear",
                "message": (
                    "I could not understand that. Try something like: "
                    "'show my status', 'pause trading', or 'make it more conservative'."
                ),
                "suggestions": self._get_suggestions(),
            }

        changes = await self._generate_changes(parsed)
        if not changes:
            return {
                "status": "no_action",
                "intent": parsed.intent,
                "message": (
                    "I understood the request but it does not map to something I can "
                    "change. Nothing was modified."
                ),
            }

        # Refuse anything frozen or invalid outright, before anything is proposed.
        #
        # A refusal must not be turned into a proposal: the old code only checked
        # frozen keys here, so an out-of-bounds value or a plugin-run request was
        # packaged as a "pending approval" and the operator was invited to approve
        # something that should never have been offered. Every refusal is audited,
        # because a refused attempt to change safety settings is exactly the kind
        # of event an operator wants to be able to find later.
        refused = [c for c in changes if c.get("frozen") or c.get("invalid")]
        if refused:
            audited = await self._audit_refused(parsed, refused, requester, user_id_body=user_id)
            message = self._format_refusal(refused)
            if not audited:
                # The refusal itself changes nothing, so it is still safe; but the
                # operator must not be told something was recorded when it was not.
                message += (
                    "\n\nNote: the audit log could not be written, so this refusal "
                    "could not be recorded."
                )
            return {
                "status": "refused",
                "intent": parsed.intent,
                "message": message,
                "refused_changes": refused,
            }

        requires_approval = self._requires_approval(parsed, changes)

        audited = await self._write_audit(
            action="command_received",
            input_data={"command": text, "user": user_id, "authenticated_as": requester},
            output_data={
                "intent": parsed.intent,
                "parameters": parsed.parameters,
                "confidence": parsed.confidence,
                "changes": changes,
                "requires_approval": requires_approval,
            },
            reasoning=f"Parsed intent: {parsed.intent} (confidence {parsed.confidence:.0%})",
            risk_level="high" if requires_approval else "low",
            approved_by=requester if not requires_approval else None,
        )
        if not audited:
            # Fail closed. If the decision cannot be recorded, no proposal is
            # created and nothing is applied - an unrecorded change is worse than
            # no change, because nobody can find out afterwards what happened.
            return {
                "status": "error",
                "intent": parsed.intent,
                "message": (
                    "The audit log could not be written, so nothing was done and no "
                    "proposal was created. Check the orchestrator's log storage and "
                    "try again."
                ),
            }

        if requires_approval:
            proposal = await self._store_proposal(
                parsed,
                changes,
                requested_by=requester,
                user_id=user_id,
                command_text=text,
            )
            return {
                "status": "pending_approval",
                "intent": parsed.intent,
                "confidence": parsed.confidence,
                # The operator needs this id: an approval names the stored
                # proposal, it does not resend the change list.
                "proposal_id": proposal.proposal_id,
                "expires_at": _iso(proposal.expires_at),
                "expires_in_seconds": proposal.seconds_remaining(),
                "proposed_changes": changes,
                "message": self._format_changes_message(parsed, changes, proposal),
                "approval_required": True,
            }

        result = await self._apply_changes(
            changes, approved_by=requester, source="command_no_approval"
        )
        return {
            "status": "applied",
            "intent": parsed.intent,
            "changes": changes,
            "result": result,
        }

    # ------------------------------------------------------------------- intent
    async def _parse_intent(self, text: str) -> Optional[NLCommand]:
        prompt = f"""Parse this trading bot command into a structured intent.

COMMAND: "{text}"

CONTEXT:
- Bot: Freqtrade on Kraken Canada (CAD markets)
- Pairs: BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD
- Current: dry-run (simulation), 1000 CAD, moderate risk
- Strategy: ModerateMultiPairStrategy

AVAILABLE INTENTS:
1. change_risk - Adjust risk level (conservative/moderate/aggressive)
2. restrict_pairs - Restrict which pairs are traded
3. change_stoploss - Adjust stoploss percentage
4. change_position_size - Adjust stake amount / max open trades
5. pause_resume - Pause or resume trading
6. change_strategy - Switch strategy
7. show_status - Questions about THIS ACCOUNT: balance, profit, open trades,
   whether the bot is running or paused, how things are going overall
8. explain_trade - Explain a specific trade decision
9. optimize_params - Trigger parameter optimization
10. generate_strategy - Request new strategy generation
11. market_analysis - Questions about THE MARKET: prices, trends, volatility,
    what the coins are doing, market conditions, whether now is a good time

show_status and market_analysis are different questions and must not be
confused. show_status is about the operator's own money and the bot's state.
market_analysis is about the coins themselves. "How's things going?" and
"what's my balance?" are show_status. "What are the market conditions?",
"how are the markets?", and "what's BTC doing?" are market_analysis.

Return JSON with: intent, parameters, confidence (0-1), original_text.

Examples:
"make it more conservative" -> {{"intent": "change_risk", "parameters": {{"risk_level": "conservative"}}, "confidence": 0.9}}
"why did it sell ETH?" -> {{"intent": "explain_trade", "parameters": {{"pair": "ETH/CAD", "side": "sell"}}, "confidence": 0.9}}
"how's things going?" -> {{"intent": "show_status", "parameters": {{}}, "confidence": 0.9}}
"what are the market conditions?" -> {{"intent": "market_analysis", "parameters": {{}}, "confidence": 0.9}}"""

        messages = [
            {
                "role": "system",
                "content": "You are a trading bot command parser. Extract intent and parameters accurately.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                max_tokens=1024,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0]["message"]["content"]
            result = json.loads(content)
            return NLCommand(
                intent=result.get("intent", "unknown"),
                parameters=result.get("parameters", {}) or {},
                confidence=float(result.get("confidence", 0.0) or 0.0),
                original_text=text,
            )
        except Exception as e:
            # AI unavailable or budget exhausted is a normal state, not an error.
            self.logger.info("LLM parsing unavailable (%s); using pattern fallback", e)
            return self._fallback_parse(text)

    def _fallback_parse(self, text: str) -> Optional[NLCommand]:
        """Deterministic pattern-based parsing, used when the AI is unavailable."""
        text_lower = text.lower()

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if not re.search(pattern, text_lower):
                    continue

                params: Dict[str, Any] = {}
                if intent == "change_risk":
                    for level in ("conservative", "moderate", "aggressive"):
                        if level in text_lower:
                            params["risk_level"] = level
                            break
                elif intent == "restrict_pairs":
                    params["action"] = "add" if any(
                        w in text_lower for w in ("add", "include")
                    ) else "remove"
                    pairs = re.findall(r"([A-Z]{2,5}/CAD)", text.upper())
                    if pairs:
                        params["pairs"] = pairs
                elif intent == "pause_resume":
                    params["action"] = "pause" if any(
                        w in text_lower for w in ("pause", "stop", "halt")
                    ) else "resume"

                return NLCommand(
                    intent=intent, parameters=params, confidence=0.7, original_text=text
                )

        return None

    # ------------------------------------------------------------------ changes
    async def _generate_changes(self, parsed: NLCommand) -> List[Dict[str, Any]]:
        changes: List[Dict[str, Any]] = []

        if parsed.intent == "change_risk":
            risk_level = str(parsed.parameters.get("risk_level", "moderate")).lower()
            changes.extend(self._get_risk_config(risk_level))

        elif parsed.intent == "restrict_pairs":
            action = parsed.parameters.get("action", "add")
            pairs = parsed.parameters.get("pairs", []) or []
            if pairs:
                changes.append(
                    {
                        "type": "runtime_pairs",
                        "action": "restrict",
                        "pairs": pairs,
                        "description": (
                            f"Restrict trading to {', '.join(pairs)} "
                            f"(runtime only; {action} requested)"
                        ),
                        "plain_language": (
                            "This changes which coins the bot is allowed to trade right "
                            "now. It does not survive a restart - to make it permanent, "
                            "update the pair list in the Swarm config."
                        ),
                    }
                )

        elif parsed.intent == "change_stoploss":
            value = parsed.parameters.get("value") or parsed.parameters.get("stoploss")
            if value is not None:
                # No description is passed in on purpose. The description is built
                # from the *validated* value inside _config_change, because the old
                # inline f-string called float(value) while formatting - so an LLM
                # answer of {"value": "aggressive"} raised ValueError before
                # validation could refuse it, and the operator got an HTTP 500
                # with nothing in the audit log.
                changes.append(self._config_change("stoploss", value))
            else:
                changes.append(
                    {
                        "type": "clarification",
                        "description": (
                            "A stop loss change needs a specific percentage, e.g. "
                            "'set the stop loss to 6 percent'."
                        ),
                    }
                )

        elif parsed.intent == "change_position_size":
            if "max_open_trades" in parsed.parameters:
                changes.append(
                    self._config_change(
                        "max_open_trades",
                        parsed.parameters["max_open_trades"],
                        "Change how many trades can be open at once",
                    )
                )
            elif "tradable_balance_ratio" in parsed.parameters:
                changes.append(
                    self._config_change(
                        "tradable_balance_ratio",
                        parsed.parameters["tradable_balance_ratio"],
                        "Change how much of the wallet the bot may use",
                    )
                )
            else:
                changes.append(
                    {
                        "type": "clarification",
                        "description": (
                            "Specify either how many simultaneous trades you want, or "
                            "what share of your wallet the bot may use."
                        ),
                    }
                )

        elif parsed.intent == "pause_resume":
            action = parsed.parameters.get("action", "pause")
            changes.append(
                {
                    "type": "bot_control",
                    "action": action,
                    "description": (
                        "Pause trading (open trades are still managed)"
                        if action == "pause"
                        else "Resume taking new trades"
                    ),
                    "plain_language": (
                        "Pausing stops the bot opening NEW trades. It keeps managing "
                        "anything already open, so your positions are not abandoned."
                        if action == "pause"
                        else "The bot will start looking for new trades again."
                    ),
                }
            )

        elif parsed.intent == "change_strategy":
            strategy = parsed.parameters.get("strategy") or parsed.parameters.get("strategy_name")
            if strategy:
                changes.append(
                    {
                        "type": "proposal_only",
                        "key": "strategy",
                        "value": strategy,
                        "description": f"Switch strategy to {strategy}",
                        "plain_language": (
                            "The strategy decides when to buy and sell. Changing it "
                            "changes the bot's entire behaviour, so this needs a "
                            "backtest before it is worth considering."
                        ),
                    }
                )
            else:
                changes.append(
                    {
                        "type": "clarification",
                        "description": "Name the strategy you want to switch to.",
                    }
                )

        elif parsed.intent == "show_status":
            changes.append({"type": "query", "action": "status", "description": "Show current status"})

        elif parsed.intent == "explain_trade":
            changes.append(
                {
                    "type": "query",
                    "action": "explain_trade",
                    "pair": parsed.parameters.get("pair"),
                    "side": parsed.parameters.get("side"),
                    "description": "Explain a trade decision",
                }
            )

        elif parsed.intent in ("optimize_params", "generate_strategy", "market_analysis"):
            plugin = {
                "optimize_params": "param_optimizer",
                "generate_strategy": "strategy_generator",
                "market_analysis": "market_analyst",
            }[parsed.intent]
            changes.append(
                {
                    "type": "trigger",
                    "action": plugin,
                    "description": f"Run the {plugin} plugin now",
                }
            )

        # Final safety pass.
        #
        # Every change is normalised and re-validated here, and the *same*
        # function is used again on the approve path (see
        # _validate_stored_changes). One validator, used twice, is the point: the
        # previous code validated only while proposing, so the approve path
        # carried out whatever list it was handed.
        return [self._validate_change(change) for change in changes]

    # ------------------------------------------------------------- change helpers
    @staticmethod
    def _normalise_key(key: Any) -> str:
        """
        Normalise a configuration key for comparison: strip, then lower-case.

        'DRY_RUN', 'Dry_Run', ' dry_run' and 'dry_run ' are the same setting to a
        human, so they must be the same setting to the safety check. The old
        exact-match, case-sensitive comparison said False for all of them while
        saying True for 'dry_run' - a frozen key that could be reached by typing
        it differently.
        """
        if key is None:
            return ""
        if isinstance(key, bool):  # a bool key is nonsense; do not stringify it
            return ""
        return str(key).strip().lower()

    def _is_frozen(self, key: Any) -> bool:
        """Is this key (in any spelling) one this interface may never touch?"""
        normalised = self._normalise_key(key)
        if not normalised:
            return False
        if normalised in FROZEN_KEYS:
            return True
        # Nested paths: 'exchange.secret' and anything beneath a frozen root.
        return any(normalised.startswith(f"{root}.") for root in FROZEN_KEYS)

    def _frozen_reason(self, key: Any) -> str:
        normalised = self._normalise_key(key)
        for candidate in (normalised, normalised.split(".")[0]):
            if candidate in FROZEN_KEYS:
                return FROZEN_KEYS[candidate]
        return f"Changing '{key}' is not permitted through this interface."

    def _validate_value(self, key: str, value: Any) -> Tuple[bool, Any, Optional[str]]:
        """
        Check and normalise one value for one setting.

        Returns ``(ok, normalised_value, reason)``. ``reason`` is written for a
        non-expert operator and explains what to do instead.

        Two traps this closes:

        * ``isinstance(True, int)`` is ``True`` in Python, so a bare bool would be
          read as 1 or 0. ``True`` is a legal value for ``max_open_trades``, so an
          LLM answering "yes" would have silently set a real trading limit.
          Booleans are therefore rejected *before* any numeric handling.
        * ``float("nan")`` compares false against every bound, so a NaN passed the
          old min/max check untouched. Non-finite values are refused.
        """
        if key == "strategy":
            # A strategy name is the one proposable setting that is not a number.
            # It is checked strictly because it is copied into the Swarm config.
            if isinstance(value, bool) or not isinstance(value, str):
                return (
                    False,
                    value,
                    "A strategy has to be named as a single word, for example "
                    "'ModerateMultiPairStrategy'. Nothing else can be used.",
                )
            candidate = value.strip()
            if not _STRATEGY_NAME_RE.match(candidate):
                return (
                    False,
                    value,
                    f"'{value}' is not a usable strategy name. Use the plain class "
                    "name of the strategy, for example 'ModerateMultiPairStrategy'.",
                )
            return True, candidate, None

        bounds = BOUNDS.get(key)
        if bounds is None:
            # No bounds means no agreed safety limit for this setting, so it
            # cannot be proposed at all. Refusing is the only safe reading:
            # accepting it would mean any key at all could be "validated" through.
            return (
                False,
                value,
                f"'{key}' is not a setting this interface is allowed to change. "
                f"The settings it can change are: {', '.join(sorted(PROPOSABLE_KEYS))}.",
            )

        if isinstance(value, bool):
            return (
                False,
                value,
                f"'{key}' needs a number, not a yes/no answer. A yes/no value would "
                "be read as 1 or 0, which is a real trading limit, so it is refused.",
            )
        if value is None:
            return False, value, f"'{key}' needs a number, but none was given."

        if isinstance(value, (int, float)):
            numeric: float = float(value)
        elif isinstance(value, str):
            text = value.strip()
            try:
                numeric = float(text)
            except ValueError:
                return (
                    False,
                    value,
                    f"I could not read '{value}' as a number, so I did not change "
                    f"'{key}'. Give a plain number, for example -0.06.",
                )
        else:
            return (
                False,
                value,
                f"'{key}' needs a number, but it was given as "
                f"{type(value).__name__}, which cannot be checked.",
            )

        if not math.isfinite(numeric):
            return (
                False,
                value,
                f"'{key}' was given a value that is not a real number "
                f"({value!r}). It is refused because it cannot be compared against "
                "the safety limits.",
            )

        if numeric < bounds["min"] or numeric > bounds["max"]:
            return (
                False,
                value,
                f"'{key}' must be between {bounds['min']} and {bounds['max']}; you "
                f"asked for {numeric}. {bounds.get('explain', '')}".strip(),
            )

        if key in INTEGER_KEYS:
            if numeric != int(numeric):
                return (
                    False,
                    value,
                    f"'{key}' must be a whole number, and {numeric} is not. Rounding "
                    "it either way would change how much money is at risk, so it is "
                    "refused.",
                )
            return True, int(numeric), None

        return True, numeric, None

    def _validate_change(self, change: Any) -> Dict[str, Any]:
        """
        Normalise and validate one change dictionary.

        Always returns a dict, and never raises: an unexpected value becomes a
        change marked ``invalid``, which the caller refuses. The returned dict has

        * ``key`` normalised (stripped, lower-cased) and ``value`` coerced for
          numeric settings, so what is displayed is what would be applied;
        * ``frozen``/``frozen_reason`` when the key may never be touched;
        * ``invalid``/``reason`` when the change cannot be carried out.
        """
        if not isinstance(change, dict):
            return {
                "type": "unknown",
                "invalid": True,
                "reason": (
                    "One of the requested changes was not in a form this service "
                    "understands, so it was refused."
                ),
            }

        normalised: Dict[str, Any] = dict(change)
        kind = normalised.get("type")
        if not isinstance(kind, str) or not kind:
            normalised["type"] = "unknown"
            normalised["invalid"] = True
            normalised["reason"] = (
                "A change arrived without a type, so there is no way to tell what it "
                "would do. It was refused."
            )
            return normalised
        kind = kind.strip().lower()
        normalised["type"] = kind

        if kind == "proposal_only":
            key = self._normalise_key(normalised.get("key"))
            normalised["key"] = key
            if not key:
                normalised["invalid"] = True
                normalised["reason"] = (
                    "A settings change arrived without naming a setting, so it was "
                    "refused."
                )
                return normalised

            if self._is_frozen(key):
                normalised["frozen"] = True
                normalised["frozen_reason"] = self._frozen_reason(key)
                return normalised

            ok, value, reason = self._validate_value(key, normalised.get("value"))
            if not ok:
                normalised["invalid"] = True
                normalised["reason"] = reason
                return normalised
            normalised["value"] = value
            return normalised

        if kind == "bot_control":
            action = normalised.get("action")
            action = action.strip().lower() if isinstance(action, str) else ""
            normalised["action"] = action
            if action not in BOT_CONTROL_ACTIONS:
                normalised["invalid"] = True
                normalised["reason"] = (
                    f"'{normalised.get('action')}' is not something this interface "
                    "can do to the bot. The only choices are 'pause' and 'resume'."
                )
            return normalised

        if kind == "runtime_pairs":
            pairs = normalised.get("pairs")
            if not isinstance(pairs, list) or not pairs:
                normalised["invalid"] = True
                normalised["reason"] = (
                    "A pair restriction arrived without a list of coins, so there was "
                    "nothing to restrict trading to. It was refused."
                )
                return normalised
            if len(pairs) > MAX_CHANGES_PER_PROPOSAL * 4:
                normalised["invalid"] = True
                normalised["reason"] = (
                    "That is far more coins than this bot is set up to trade, so the "
                    "request was refused."
                )
                return normalised
            problem = self._check_pair_list(pairs)
            if problem is not None:
                normalised["invalid"] = True
                normalised["reason"] = problem
                return normalised
            normalised["pairs"] = [p.strip().upper() for p in pairs]
            return normalised

        if kind in PLUGIN_RUN_CHANGE_TYPES:
            # An "approval" must never be able to start a plugin. Running a plugin
            # has its own authenticated endpoint; routing it through the approval
            # gate turned "approve the message you were shown" into "run anything".
            plugin_name = normalised.get("action")
            normalised["invalid"] = True
            normalised["reason"] = (
                "Approving cannot start a plugin run. To run "
                f"'{plugin_name}', use the plugin control endpoint: "
                f"POST /api/v1/plugins/{plugin_name}/control with "
                '{"action": "run"}. That endpoint is authenticated and recorded in '
                "the audit log."
            )
            return normalised

        # note / clarification / query need no value validation: they carry no
        # setting and change nothing on the bot.
        return normalised

    def _default_description(self, key: str, value: Any) -> str:
        """
        A plain-language description built from an already-validated value.

        This is the replacement for the old inline ``f"{abs(float(value)) * 100:.1f}%"``,
        which evaluated ``float(value)`` before the value had been checked.
        """
        if key == "stoploss":
            return f"Set the stop loss to {_fmt_percent(value)}"
        if key == "trailing_stop_positive":
            return f"Follow profit from {_fmt_percent(value)}"
        if key == "tradable_balance_ratio":
            return f"Use at most {_fmt_percent(value)} of the wallet"
        if key == "amount_reserve_percent":
            return f"Keep a {_fmt_percent(value)} buffer for fees and slippage"
        if key == "max_open_trades":
            return f"Allow at most {value} trades at once"
        if key == "strategy":
            return f"Switch strategy to {value}"
        return f"Change {key} to {value}"

    def _config_change(
        self, key: str, value: Any, description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a config proposal and validate it.

        The description is built *after* validation and from the normalised value,
        so nothing in this method can raise on a value the LLM invented. If the
        change is refused, a readable description is still produced, because the
        operator has to be told what was refused.
        """
        change: Dict[str, Any] = {
            "type": "proposal_only",
            "key": key,
            "value": value,
            "description": description,
            # How an approval would take effect.
            #
            #   "settings" - applied to the running bot through the operator
            #                settings layer, because Freqtrade's reload_config
            #                does re-read its config files. This used to be
            #                "config_redeploy", from when nothing could change a
            #                running bot and the operator had to hand-edit a
            #                Swarm config.
            #
            #   "redeploy" - genuinely needs a redeploy. The strategy is set by
            #                a --strategy command-line argument, and Freqtrade's
            #                `_process_common_options` overwrites the config
            #                value with it:
            #                    if self.args.get("strategy") or not config.get(...):
            #                        config.update({"strategy": self.args.get("strategy")})
            #                So a strategy written into the settings file would be
            #                silently ignored. Claiming otherwise would be worse
            #                than the old message, because the operator would
            #                approve a change, see success, and get nothing.
            "applies_via": "redeploy" if key == "strategy" else "settings",
            "plain_language": "",
        }

        change = self._validate_change(change)

        if change.get("invalid") or change.get("frozen"):
            # Keep something readable in "description" so the refusal message and
            # the audit entry identify the setting without a KeyError.
            if not change.get("description"):
                change["description"] = f"Change '{change.get('key') or key}'"
            return change

        bounds = BOUNDS.get(change["key"])
        if bounds:
            change["plain_language"] = bounds["explain"]
        if not change.get("description"):
            change["description"] = self._default_description(
                change["key"], change["value"]
            )
        return change

    def _get_risk_config(self, risk_level: str) -> List[Dict[str, Any]]:
        """
        Map a risk profile to a set of proposals.

        The values come from settings_store.RISK_PRESETS, which is the single
        definition of what each level means. This method used to carry its own
        copy, and the two had drifted apart on seven values - "conservative" set
        tradable_balance_ratio to 0.80 here and 0.50 in the settings panel. Two
        answers to the same question, and the operator would only ever see one of
        them depending on whether they typed or clicked.

        Descriptions are generated from the values rather than hand-written, so a
        number can no longer be described as something it is not.
        """
        profile = RISK_PRESETS.get(risk_level)
        if profile is None:
            return [
                {
                    "type": "clarification",
                    "description": (
                        "Choose one of: "
                        + ", ".join(sorted(RISK_PRESETS))
                        + "."
                    ),
                }
            ]

        changes = [
            self._config_change(key, value, _describe_risk_value(key, value))
            for key, value in profile["values"].items()
        ]

        if risk_level == "aggressive":
            changes.append(
                {
                    "type": "note",
                    "description": "Higher risk",
                    "plain_language": (
                        "The aggressive profile allows larger losses on a single trade "
                        "(12%) and keeps less of your wallet in reserve. It can lose "
                        "money faster than the moderate profile."
                    ),
                }
            )
        return changes

    def _requires_approval(self, parsed: NLCommand, changes: List[Dict]) -> bool:
        """Queries run immediately; anything that alters behaviour needs approval."""
        if not changes:
            return False
        kinds = [c.get("type") if isinstance(c, dict) else None for c in changes]
        if all(kind == "clarification" for kind in kinds):
            return False
        if all(kind == "query" for kind in kinds):
            return False
        return True

    def _format_refusal(self, refused: List[Dict[str, Any]]) -> str:
        """
        Plain-language explanation of a refusal.

        A refusal has to say what was refused and why, in words an operator who
        does not read code can act on - otherwise the safe answer looks like a
        broken service.
        """
        lines = ["I did not make that change. Here is why:", ""]
        for change in refused:
            description = change.get("description") or change.get("key") or change.get("type")
            reason = change.get("frozen_reason") or change.get("reason") or "Refused by policy."
            lines.append(f"  - {description}: {reason}")
        lines += [
            "",
            "Nothing was changed and nothing was proposed. This refusal has been "
            "recorded in the audit log.",
        ]
        return "\n".join(lines)

    def _format_changes_message(
        self,
        parsed: NLCommand,
        changes: List[Dict],
        proposal: Optional[PendingProposal] = None,
    ) -> str:
        """
        The message the operator reads before deciding.

        When a proposal id exists it is printed here, together with a short form of
        the change-list fingerprint. The operator can then check that the id and
        fingerprint on the /api/v1/proposals list are the same as the ones on the
        message they approved - which is the whole point of binding an approval to
        a stored proposal instead of to a rendered message.
        """
        lines = [
            f'Command understood as: {parsed.intent} (confidence {parsed.confidence:.0%})',
            "",
            "Requested changes:",
        ]
        for change in changes:
            marker = "  - "
            if change.get("invalid"):
                lines.append(
                    f"{marker}REFUSED: {change.get('description')} - {change.get('reason')}"
                )
                continue
            lines.append(f"{marker}{change.get('description') or change.get('type')}")
            if change.get("plain_language"):
                lines.append(f"      What this means: {change['plain_language']}")

        if any(c.get("applies_via") == "settings" for c in changes):
            lines += [
                "",
                "Approving applies these to the running bot. Freqtrade re-reads its",
                "configuration on request, so no redeploy is needed.",
                "Nothing changes unless you approve.",
            ]

        if any(c.get("applies_via") == "redeploy" for c in changes):
            lines += [
                "",
                "One of these cannot be applied to a running bot: the strategy is set",
                "by a command-line argument, which overrides the config, so it needs a",
                "redeploy. Approving it records your decision and tells you the value",
                "to set; nothing changes until you redeploy.",
            ]

        if proposal is not None:
            remaining = proposal.seconds_remaining()
            valid_for = (
                f"{remaining // 60} minutes" if remaining >= 60 else f"{remaining} seconds"
            )
            lines += [
                "",
                "To approve, send this id back - nothing else is accepted:",
                f"  proposal_id: {proposal.proposal_id}",
                f"  fingerprint: {proposal.change_hash[:16]}",
                f"This proposal expires at {_iso(proposal.expires_at)} "
                f"({valid_for} from now) and can be used once. Approving applies "
                "exactly the list above; if the list ever stops matching the "
                "fingerprint, it is refused.",
            ]
        return "\n".join(lines)

    def _get_suggestions(self) -> List[str]:
        return [
            "show my status",
            "pause trading",
            "make it more conservative",
            "why did my last trade close?",
        ]

    # ------------------------------------------------------------------- apply
    async def _apply_config_change(
        self, change: Dict[str, Any], *, approved_by: str
    ) -> Dict[str, Any]:
        """Apply one approved configuration change to the running bot.

        Reached only from an approved proposal. The gate lives in
        `_apply_one_change`, which requires both a named approver and the
        approval source - so this method existing is not itself a capability.

        The value is validated a second time here, against the operator settings
        allowlist, even though `_validate_change` already bounded it. That is
        deliberate duplication: `_validate_change` encodes what the AI is allowed
        to *ask* for, while the settings allowlist encodes what may reach the
        bot's configuration at all. Those are different rules, and the second one
        has to hold regardless of how a value arrived.
        """
        key = change.get("key")
        value = change.get("value")

        if not isinstance(key, str) or key not in settings_store.EDITABLE_BY_KEY:
            # The allowlist is the second gate, and `strategy` is the case that
            # makes it load-bearing: `_validate_change` permits it, but it cannot
            # be applied here, because the stack passes --strategy and Freqtrade
            # overwrites the config value with that argument.
            self.logger.error(
                "Refused an approved config change to non-editable key %r", key
            )
            if change.get("applies_via") == "redeploy":
                reason = (
                    "The strategy is set by a command-line argument, which "
                    "overrides the configuration, so it cannot be changed on a "
                    "running bot. Change the --strategy argument in the stack and "
                    "redeploy. Your decision has been recorded."
                )
            else:
                reason = "%s is not a setting that can be changed here." % key
            return {"change": change, "status": "refused", "reason": reason}

        try:
            clean = settings_store.validate({key: value})
        except settings_store.SettingsError as e:
            return {"change": change, "status": "refused", "reason": e.message}

        # Merged onto what is already set rather than replacing it, or approving
        # one change would silently discard every earlier one.
        merged = dict(settings_store.read().settings)
        merged.update(clean)

        try:
            settings_store.write(merged, actor=approved_by)
        except OSError as e:
            return {
                "change": change,
                "status": "failed",
                "reason": "Could not save the setting: %s" % e,
            }

        applied = True
        reload_error: Optional[str] = None
        if self.freqtrade is not None:
            try:
                await self.freqtrade.reload_config()
            except Exception as e:  # noqa: BLE001 - report, never raise
                applied = False
                reload_error = str(e)
        else:
            applied = False
            reload_error = "the Freqtrade API client is not available"

        return {
            "change": change,
            "status": "applied" if applied else "saved_not_applied",
            "key": key,
            "value": clean.get(key),
            "description": change.get("description"),
            "applied": applied,
            "reload_error": reload_error,
            "note": (
                "Applied to the running bot."
                if applied
                else (
                    "Saved, but the bot has not picked it up yet: %s. It will take "
                    "effect on the next restart." % reload_error
                )
            ),
        }

    async def _apply_changes(
        self,
        changes: List[Dict[str, Any]],
        *,
        approved_by: Optional[str] = None,
        proposal_id: Optional[str] = None,
        source: str = "direct",
    ) -> Dict[str, Any]:
        """
        Execute a change list, auditing first, isolating each change, and always
        writing a completion entry.

        Runtime actions run for real. Config proposals are NOT applied - they are
        returned as instructions, because nothing in this system can change the
        bot's configuration while it is running.

        The ordering here is the fix for a verified defect:

        * The **intent** (the whole list plus its SHA-256 fingerprint) is written
          to the audit log *before* the first change runs. The old code wrote a
          single entry after the loop returned, so a list like
          ``[{bot_control: pause}, {runtime_pairs}]`` really paused the bot, then
          raised ``KeyError('pairs')``, returned HTTP 500, and left no audit
          record at all. Whoever could reach the API could pick which state
          changes left no trace.
        * Each change is wrapped in its own ``try/except`` inside
          :meth:`_apply_one_change`, so one failure cannot skip the rest and
          cannot skip the completion entry.
        * The completion entry is written in a ``finally`` block, so it happens
          even if something unexpected escapes.

        If the audit log cannot be written, **nothing is applied** and the caller
        is told so: an unrecorded change to a live trading bot is worse than no
        change, because nobody can find out afterwards what happened.
        """
        # Defensive: the loop below must not be able to raise before the
        # completion entry is written, so a non-list is treated as "nothing to
        # apply" rather than iterated over.
        if not isinstance(changes, list):
            self.logger.warning(
                "_apply_changes was given %s instead of a list; applying nothing.",
                type(changes).__name__,
            )
            changes = []

        change_hash = _hash_changes(changes)

        # A list that only reads (a status query) is not a high-risk event, and
        # marking it as one would train the operator to ignore high-risk entries.
        # Anything that can change the bot or its configuration is high risk.
        risk_level = (
            "high"
            if any(
                isinstance(change, dict)
                and change.get("type") in ("proposal_only", "bot_control", "runtime_pairs")
                for change in changes
            )
            else "low"
        )

        started = await self._write_audit(
            action="command_apply_started",
            input_data={
                "changes": changes,
                "change_hash": change_hash,
                "change_count": len(changes),
                "proposal_id": proposal_id,
                "source": source,
            },
            output_data={"status": "applying"},
            reasoning=(
                "Applying a change list"
                + (f" from approved proposal {proposal_id}" if proposal_id else "")
                + ". This entry is written before anything runs so that a change "
                "which fails part way through is still recorded."
            ),
            risk_level=risk_level,
            approved_by=approved_by,
        )

        if not started:
            return {
                "executed": [],
                "proposals": [],
                "proposals_applied": False,
                "status": "refused",
                "change_hash": change_hash,
                "error": (
                    "The audit log could not be written, so nothing was applied. "
                    "Every change has to be recorded before it happens; check the "
                    "orchestrator's log storage and try again."
                ),
                "summary": self._summarise([]),
                "note": "Nothing was applied because it could not be recorded.",
            }

        executed: List[Dict[str, Any]] = []
        try:
            for change in changes:
                executed.append(
                    await self._apply_one_change(
                        change, approved_by=approved_by, source=source
                    )
                )
        finally:
            # Always written, including when a change raised. Without this the
            # audit trail would show an apply that never ended.
            summary = self._summarise(executed)
            await self._write_audit(
                action="command_apply_completed",
                input_data={
                    "changes": changes,
                    "change_hash": change_hash,
                    "proposal_id": proposal_id,
                    "source": source,
                },
                output_data={"status": "completed", "summary": summary, "results": executed},
                reasoning=(
                    "Finished applying the change list. Per-change results are "
                    "recorded so a partial failure is visible instead of silent."
                ),
                risk_level=risk_level,
                approved_by=approved_by,
            )

        proposals = [
            {
                "key": entry.get("key"),
                "value": entry.get("value"),
                "description": entry.get("description"),
            }
            for entry in executed
            if entry.get("status") == "proposed"
        ]
        summary = self._summarise(executed)

        return {
            "executed": executed,
            "proposals": proposals,
            "proposals_applied": False,
            "change_hash": change_hash,
            "proposal_id": proposal_id,
            "summary": summary,
            "status": "completed" if summary["failed"] == 0 else "completed_with_failures",
            "note": (
                "Proposed settings are not applied automatically. Update the "
                "'freqtrade_canada_config' Swarm config and redeploy to apply them."
                if proposals
                else "No configuration changes were required."
            ),
        }

    @staticmethod
    def _summarise(executed: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count the per-change outcomes so a partial failure is impossible to miss."""
        summary = {
            "total": len(executed),
            "applied": 0,
            "proposed": 0,
            "refused": 0,
            "failed": 0,
            "other": 0,
        }
        for entry in executed:
            status = entry.get("status") if isinstance(entry, dict) else None
            if status in ("success", "triggered", "applied"):
                summary["applied"] += 1
            elif status == "proposed":
                summary["proposed"] += 1
            elif status in ("refused", "unsupported"):
                summary["refused"] += 1
            elif status in ("failed", "unavailable"):
                summary["failed"] += 1
            else:
                summary["other"] += 1
        return summary

    async def _apply_one_change(
        self,
        change: Any,
        *,
        approved_by: Optional[str] = None,
        source: str = "direct",
    ) -> Dict[str, Any]:
        """
        Carry out one change. Never raises.

        Any failure becomes a per-change result with ``status: "failed"``, so the
        caller can report exactly which change failed instead of losing the whole
        response - and instead of aborting the changes that came after it.

        ``approved_by`` and ``source`` decide whether a configuration change is
        actually applied. Only an approved proposal applies one; every other path
        returns the values as a proposal for the operator to act on. This is the
        single gate that keeps "the AI may propose" and "the AI may apply" apart,
        so it is checked here rather than trusted to the caller.
        """
        try:
            if not isinstance(change, dict):
                return {
                    "change": change,
                    "status": "refused",
                    "reason": "That change was not in a form this service understands.",
                }

            kind = change.get("type")

            if kind == "proposal_only":
                if change.get("frozen") or change.get("invalid"):
                    return {
                        "change": change,
                        "status": "refused",
                        "reason": change.get("frozen_reason") or change.get("reason"),
                    }

                # Applying requires a named approver AND the approval source.
                # Requiring both means a future caller that passes one but not
                # the other gets the propose-only behaviour rather than an
                # accidental write.
                if approved_by and source == "approval":
                    return await self._apply_config_change(change, approved_by=approved_by)

                return {
                    "change": change,
                    "status": "proposed",
                    "key": change.get("key"),
                    "value": change.get("value"),
                    "description": change.get("description"),
                }

            if kind in ("note", "clarification"):
                return {"change": change, "status": "skipped"}

            if kind == "query":
                return await self._handle_query(change)

            if kind in PLUGIN_RUN_CHANGE_TYPES:
                # Defence in depth. _validate_change already refuses these, so a
                # trigger change should never reach here; if one ever does, it is
                # refused rather than run. An approval must not be able to start a
                # plugin, and neither must any other path through this method.
                plugin_name = change.get("action")
                self.logger.warning(
                    "Refused an attempt to run plugin '%s' through the change-apply path",
                    plugin_name,
                )
                return {
                    "change": change,
                    "status": "refused",
                    "reason": (
                        "Approving cannot start a plugin run. Use "
                        f"POST /api/v1/plugins/{plugin_name}/control with "
                        '{"action": "run"} instead.'
                    ),
                }

            if kind == "bot_control":
                return await self._handle_bot_control(change)

            if kind == "runtime_pairs":
                return await self._handle_restrict_pairs(change)

            return {
                "change": change,
                "status": "unsupported",
                "reason": f"Unknown change type '{kind}'",
            }
        except Exception as e:
            # Includes the KeyError that used to escape and turn a real state
            # change into an unrecorded HTTP 500.
            self.logger.error("Change failed: %s: %s", type(e).__name__, e)
            return {
                "change": change,
                "status": "failed",
                "error": f"{type(e).__name__}: {e}",
            }

    async def _handle_query(self, change: Dict[str, Any]) -> Dict[str, Any]:
        action = change.get("action")
        if action == "status":
            try:
                status = await self.freqtrade.status()
                return {
                    "change": change,
                    "status": "success",
                    "data": {
                        "state": status.state,
                        "dry_run": status.dry_run,
                        "open_trades": status.open_trades_count,
                        "max_open_trades": status.max_open_trades,
                        "current_balance": status.current_balance,
                        "profit_pct": round(status.profit_pct, 2),
                    },
                }
            except FreqtradeAPIError as e:
                return {"change": change, "status": "failed", "error": str(e)}

        if action == "explain_trade":
            explainer = self.orchestrator.plugins.get("explainer")
            if not explainer:
                return {
                    "change": change,
                    "status": "unavailable",
                    "error": "Explainer plugin is not loaded.",
                }
            trades = await self.freqtrade.get_trades(limit=5)
            if change.get("pair"):
                trades = [t for t in trades if t.pair == change["pair"]] or trades
            if not trades:
                return {
                    "change": change,
                    "status": "no_data",
                    "error": "No closed trades found to explain yet.",
                }
            explanation = await explainer.explain_trade(trades[0])
            return {"change": change, "status": "success", "data": explanation}

        return {"change": change, "status": "unsupported", "error": f"Unknown query '{action}'"}

    async def _handle_bot_control(self, change: Dict[str, Any]) -> Dict[str, Any]:
        action = change.get("action")
        action = action.strip().lower() if isinstance(action, str) else ""
        try:
            if action == "pause":
                result = await self.freqtrade.pause()
            elif action == "resume":
                result = await self.freqtrade.start()
            else:
                return {
                    "change": change,
                    "status": "unsupported",
                    "error": (
                        f"'{change.get('action')}' is not something this interface can "
                        "do to the bot. The only choices are 'pause' and 'resume'."
                    ),
                }
            return {"change": change, "status": "success", "result": result}
        except FreqtradeAPIError as e:
            return {"change": change, "status": "failed", "error": str(e)}

    def _check_pair_list(self, pairs: Any) -> Optional[str]:
        """Why this pair list is unacceptable, or None if it is fine.

        One implementation used by both the validator and the handler. The
        validator stops a bad list from ever being *proposed*; the handler stops
        one from reaching the exchange. Two copies of this rule would drift, and
        the copy that drifted would be the one guarding the money.

        The rules exist because the pair list is the one setting that decides
        WHAT the bot buys, and it arrives as free text from a language model.
        """
        if not isinstance(pairs, list) or not pairs:
            return "No list of coins was given."

        allowed_quotes = getattr(self, "allowed_quote_currencies", DEFAULT_ALLOWED_QUOTES)

        for pair in pairs:
            if not isinstance(pair, str):
                return "'%s' is not a trading pair I recognise. Pairs look like 'BTC/CAD'." % (pair,)

            cleaned = pair.strip().upper()
            if not _PAIR_RE.match(cleaned):
                return (
                    "'%s' is not a trading pair I recognise. Pairs look like "
                    "'BTC/CAD'." % pair
                )

            base, quote = cleaned.split("/", 1)

            # The quote currency has to match the wallet. A CAD bot cannot settle
            # a BTC/USD trade, and quietly accepting one would leave the operator
            # holding a position in a currency they never chose.
            if quote not in allowed_quotes:
                return (
                    "%s is priced in %s, but this bot trades in %s. Only %s pairs "
                    "can be used, because that is the currency your balance is in."
                    % (cleaned, quote, " or ".join(allowed_quotes), "/".join(allowed_quotes))
                )

            # Leveraged tokens reset daily and decay; a beginner holding one can
            # lose most of their money without the price of the underlying moving
            # against them at all.
            if LEVERAGED_TOKEN_PATTERN.search(base):
                return (
                    "%s looks like a leveraged token. Those move several times "
                    "faster than the coin they track, reset daily, and can lose "
                    "most of their value even when the coin itself is flat. This "
                    "bot does not trade them." % cleaned
                )

        return None

    async def _handle_restrict_pairs(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """
        Restrict trading to a set of pairs.

        The pair list is checked here as well as in _validate_change. The old code
        indexed ``change["pairs"]`` directly, so a change that arrived without a
        pair list raised ``KeyError('pairs')`` - which is exactly the failure that
        let a real pause happen and then lose its audit record.
        """
        pairs = change.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            return {
                "change": change,
                "status": "refused",
                "error": (
                    "No list of coins was given, so there was nothing to restrict "
                    "trading to. Nothing was changed."
                ),
            }

        # Checked again here, and not only in the validator, because this is the
        # call that reaches the exchange. The validator guards the proposal; this
        # guards the money, and it has to hold even if a change arrives by a path
        # that skipped validation.
        problem = self._check_pair_list(pairs)
        if problem is not None:
            self.logger.warning("Refused a pair list at the exchange call: %s", problem)
            return {"change": change, "status": "refused", "error": problem}

        try:
            result = await self.freqtrade.set_whitelist(pairs)
            return {"change": change, "status": "success", "result": result}
        except UnsupportedOperation as e:
            return {"change": change, "status": "refused", "error": str(e)}
        except FreqtradeAPIError as e:
            return {"change": change, "status": "failed", "error": str(e)}

    # ------------------------------------------------------------------- audit
    async def _write_audit(
        self,
        *,
        action: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        reasoning: str,
        risk_level: str = "low",
        approved_by: Optional[str] = None,
        user_initiated: bool = True,
    ) -> bool:
        """
        Write one audit entry. Returns True on success, False on any failure.

        Never raises: an audit failure has to be *handled* by the caller (which
        fails closed and refuses to act), not turned into a 500 that hides what
        happened. The failure is logged at CRITICAL because a trading bot with no
        working audit trail is a serious condition, not a warning.
        """
        if self.audit is None:
            self.logger.critical(
                "SECURITY: the audit logger is not available, so '%s' could not be "
                "recorded. Failing closed.",
                action,
            )
            return False
        try:
            await self.audit.log(
                plugin="nl_config",
                action=action,
                user_initiated=user_initiated,
                input_data=input_data,
                output_data=output_data,
                decision_reasoning=reasoning,
                risk_level=risk_level,
                approved_by=approved_by,
            )
            return True
        except Exception as e:
            self.logger.critical(
                "SECURITY: could not write the '%s' audit entry (%s: %s). Failing closed.",
                action,
                type(e).__name__,
                e,
            )
            return False

    async def _audit_refused(
        self,
        parsed: NLCommand,
        refused: List[Dict[str, Any]],
        user_id: str,
        user_id_body: Optional[str] = None,
    ) -> bool:
        """
        Record a refused command. Returns True if the refusal was recorded.

        Frozen-key attempts and out-of-bounds values are both refused here, and
        both are recorded: an operator investigating "did anything try to change
        my stop loss?" needs to find the attempts that were stopped, not only the
        ones that succeeded.
        """
        return await self._write_audit(
            action="command_refused",
            input_data={
                "command": parsed.original_text,
                "user": user_id,
                "supplied_user_id": user_id_body,
            },
            output_data={"refused": refused},
            reasoning=(
                "Command was refused by policy before anything was proposed "
                f"({', '.join(str(c.get('key') or c.get('type')) for c in refused)}). "
                "Refusals are recorded so attempts to touch frozen or out-of-bounds "
                "settings remain visible."
            ),
            risk_level="high",
            approved_by=None,
        )

    # --------------------------------------------------------------- proposals
    def _purge_expired(self, now: Optional[float] = None) -> List[PendingProposal]:
        """Drop expired proposals and return them, so the caller can audit them."""
        moment = time.time() if now is None else now
        expired = [p for p in self._pending_proposals.values() if p.is_expired(moment)]
        for proposal in expired:
            self._pending_proposals.pop(proposal.proposal_id, None)
        return expired

    async def _store_proposal(
        self,
        parsed: NLCommand,
        changes: List[Dict[str, Any]],
        *,
        requested_by: str,
        user_id: str = "operator",
        command_text: str = "",
        message: str = "",
    ) -> PendingProposal:
        """
        Store a change list under a fresh random id and return it.

        The id comes from :func:`secrets.token_urlsafe`, so it cannot be guessed
        from a previous one. A collision is checked for anyway: if two proposals
        shared an id, approving one could apply the other.
        """
        now = time.time()
        for expired in self._purge_expired(now):
            await self._write_audit(
                action="proposal_expired",
                input_data={
                    "proposal_id": expired.proposal_id,
                    "changes": expired.changes,
                    "change_hash": expired.change_hash,
                },
                output_data={"status": "expired"},
                reasoning=(
                    "A proposal passed its expiry time without being approved. "
                    "Expired proposals cannot be approved later."
                ),
                risk_level="low",
                approved_by=None,
            )

        # Keep the store bounded. The oldest is discarded first, and the discard
        # is recorded, because a proposal silently vanishing is exactly the kind
        # of thing an operator would later be unable to explain.
        while len(self._pending_proposals) >= self.max_pending_proposals:
            oldest = min(
                self._pending_proposals.values(), key=lambda p: p.created_at, default=None
            )
            if oldest is None:
                break
            self._pending_proposals.pop(oldest.proposal_id, None)
            self.logger.warning(
                "Discarding pending proposal %s to make room (limit %d)",
                oldest.proposal_id,
                self.max_pending_proposals,
            )
            await self._write_audit(
                action="proposal_discarded",
                input_data={
                    "proposal_id": oldest.proposal_id,
                    "changes": oldest.changes,
                    "change_hash": oldest.change_hash,
                },
                output_data={"status": "discarded", "reason": "store_full"},
                reasoning=(
                    "Too many proposals were waiting for approval, so the oldest was "
                    "discarded to keep the service's memory bounded. It can no "
                    "longer be approved; re-issue the command if it is still wanted."
                ),
                risk_level="low",
                approved_by=None,
            )

        proposal_id = secrets.token_urlsafe(32)
        while proposal_id in self._pending_proposals:
            proposal_id = secrets.token_urlsafe(32)

        # Store a deep copy, and fingerprint the copy that is actually stored.
        # A shallow copy would leave nested values (a pair list, say) shared with
        # the caller, so a later mutation could change the stored proposal - which
        # the fingerprint check would then refuse, but only after confusing the
        # operator. Hashing the stored copy keeps "what was shown" and "what is
        # applied" provably identical.
        try:
            stored_changes = copy.deepcopy(list(changes))
        except Exception as e:  # pragma: no cover - defensive
            self.logger.warning(
                "Could not deep-copy the change list (%s); storing a shallow copy.", e
            )
            stored_changes = [dict(change) for change in changes if isinstance(change, dict)]

        proposal = PendingProposal(
            proposal_id=proposal_id,
            created_at=now,
            expires_at=now + self.proposal_ttl_seconds,
            requested_by=requested_by or "unknown",
            user_id=user_id or "operator",
            intent=parsed.intent,
            confidence=parsed.confidence,
            changes=stored_changes,
            change_hash=_hash_changes(stored_changes),
            command_text=command_text,
            message=message,
        )
        self._pending_proposals[proposal_id] = proposal

        await self._write_audit(
            action="proposal_created",
            input_data={
                "proposal_id": proposal_id,
                "command": command_text,
                "requested_by": proposal.requested_by,
                "changes": proposal.changes,
                "change_hash": proposal.change_hash,
                "expires_at": _iso(proposal.expires_at),
            },
            output_data={"status": "pending_approval"},
            reasoning=(
                "A change list was stored for approval. It is single-use, expires "
                f"in {self.proposal_ttl_seconds} seconds, and is fingerprinted so "
                "the approved list can be proven to be the list that was shown."
            ),
            risk_level="high",
            approved_by=None,
        )
        return proposal

    def list_pending_proposals(self) -> List[Dict[str, Any]]:
        """
        Every proposal waiting for approval, newest first.

        This exists so the operator can see, without trusting a chat message, what
        is actually queued to happen. Expired proposals are dropped first, so the
        list never offers something that would be refused.
        """
        self._purge_expired()
        return [
            proposal.public_dict()
            for proposal in sorted(
                self._pending_proposals.values(), key=lambda p: p.created_at, reverse=True
            )
        ]

    def _validate_stored_changes(
        self, changes: Any, proposal_id: str
    ) -> List[Dict[str, Any]]:
        """
        Re-run every safety check against a stored proposal, and return the
        validated list to apply.

        This is the check that was missing entirely: validation used to happen
        only while *proposing*, so approving carried out whatever list it was
        handed. Raises :class:`ProposalError` if anything is wrong - the whole
        proposal is refused rather than partially applied, because the operator
        approved a specific list and applying part of it would be applying
        something they did not approve.
        """
        if not isinstance(changes, list) or not changes:
            raise ProposalError(
                "That proposal does not contain any changes, so there is nothing to "
                "apply. It has been discarded; please issue the command again.",
                400,
            )
        if len(changes) > MAX_CHANGES_PER_PROPOSAL:
            raise ProposalError(
                f"That proposal contains {len(changes)} changes, which is more than "
                f"this service will apply at once (limit {MAX_CHANGES_PER_PROPOSAL}). "
                "It has been refused; please issue the changes in smaller groups.",
                400,
            )

        validated: List[Dict[str, Any]] = []
        problems: List[str] = []
        for raw in changes:
            change = self._validate_change(raw)
            validated.append(change)
            kind = change.get("type")
            if change.get("frozen"):
                problems.append(change.get("frozen_reason") or "A frozen setting was requested.")
            elif change.get("invalid"):
                problems.append(change.get("reason") or "A change was not valid.")
            elif kind not in APPROVABLE_CHANGE_TYPES:
                problems.append(
                    f"An approval cannot carry out a change of type '{kind}'. Running "
                    "plugins and anything else outside the approved set has its own "
                    "endpoint."
                )

        if problems:
            raise ProposalError(
                "This proposal was refused when it was re-checked against the safety "
                "rules, so nothing was applied: " + " ".join(problems),
                400,
            )
        return validated

    async def reject_proposal(
        self, proposal_id: str, rejected_by: str = "operator"
    ) -> Dict[str, Any]:
        """Reject a stored proposal and forget it. Nothing is applied."""
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ProposalError(
                "A proposal id is required. Use the id from the command response, or "
                "GET /api/v1/proposals to see what is waiting.",
                400,
            )
        proposal_id = proposal_id.strip()
        proposal = self._pending_proposals.pop(proposal_id, None)
        if proposal is None:
            raise ProposalError(
                "There is no proposal waiting with that id. It may already have been "
                "approved, rejected or expired. GET /api/v1/proposals lists what is "
                "waiting.",
                404,
            )

        if proposal.is_expired():
            await self._write_audit(
                action="proposal_expired",
                input_data={
                    "proposal_id": proposal_id,
                    "changes": proposal.changes,
                    "change_hash": proposal.change_hash,
                },
                output_data={"status": "expired", "attempted_by": rejected_by},
                reasoning="An expired proposal was rejected. Nothing was applied.",
                risk_level="low",
                approved_by=None,
            )
            raise ProposalError(
                "That proposal had already expired, so there was nothing to reject. "
                "Nothing was applied. Please issue the command again if you still want "
                "the change.",
                410,
            )

        await self._write_audit(
            action="command_rejected",
            input_data={
                "proposal_id": proposal_id,
                "changes": proposal.changes,
                "change_hash": proposal.change_hash,
                "requested_by": proposal.requested_by,
            },
            output_data={"status": "rejected"},
            reasoning="The operator rejected this proposal. Nothing was applied.",
            risk_level="low",
            approved_by=rejected_by,
        )
        return {
            "status": "rejected",
            "proposal_id": proposal_id,
            "message": "Changes rejected. Nothing was applied.",
        }

    async def approve_proposal(
        self, proposal_id: str, approved_by: str = "operator"
    ) -> Dict[str, Any]:
        """
        Apply a proposal that *this process* stored, and nothing else.

        The caller supplies an id, never a change list: the operator approves a
        message they were shown, so if the request body could supply the list the
        approval would be meaningless. The stored proposal is re-checked against
        the frozen-key rules, the bounds and the change-type allowlist, its
        fingerprint must still match, it must not have expired, and it can be used
        only once.

        Raises :class:`ProposalError` (already audited) when an approval cannot be
        honoured. Nothing is applied unless every check passes.
        """
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ProposalError(
                "A proposal id is required. Approving means naming the proposal you "
                "were shown - use the id from the command response, or "
                "GET /api/v1/proposals.",
                400,
            )
        proposal_id = proposal_id.strip()

        # Single use, from the very first moment: the proposal is removed before
        # any await, so two simultaneous approvals cannot both apply it, and a
        # replay finds nothing.
        proposal = self._pending_proposals.pop(proposal_id, None)
        if proposal is None:
            raise ProposalError(
                "There is no proposal waiting with that id. It may already have been "
                "approved, rejected or expired - each proposal can be used once. "
                "GET /api/v1/proposals lists what is waiting.",
                404,
            )

        if proposal.is_expired():
            await self._write_audit(
                action="proposal_expired",
                input_data={
                    "proposal_id": proposal_id,
                    "changes": proposal.changes,
                    "change_hash": proposal.change_hash,
                },
                output_data={"status": "expired", "attempted_by": approved_by},
                reasoning=(
                    "An approval arrived after the proposal had expired, so it was "
                    "refused. Nothing was applied."
                ),
                risk_level="high",
                approved_by=None,
            )
            raise ProposalError(
                "That proposal expired and can no longer be approved. Nothing was "
                "applied. If you still want the change, please issue the command again "
                "and approve the new proposal promptly.",
                410,
            )

        # Fingerprint check: proves the list being applied is the list that was
        # stored and shown.
        recomputed = _hash_changes(proposal.changes)
        if not secrets.compare_digest(recomputed, proposal.change_hash):
            await self._write_audit(
                action="proposal_refused",
                input_data={
                    "proposal_id": proposal_id,
                    "changes": proposal.changes,
                    "stored_hash": proposal.change_hash,
                    "recomputed_hash": recomputed,
                },
                output_data={"status": "refused", "reason": "fingerprint_mismatch"},
                reasoning=(
                    "The stored proposal no longer matches its own fingerprint, so it "
                    "cannot be trusted and was refused. Nothing was applied."
                ),
                risk_level="high",
                approved_by=None,
            )
            raise ProposalError(
                "This proposal does not match its own fingerprint, so it cannot be "
                "trusted. Nothing was applied, and the proposal has been discarded. "
                "Please issue the command again.",
                409,
            )

        # Re-run the safety rules against the stored list. Validation happens
        # again here, not only at propose time.
        try:
            validated = self._validate_stored_changes(proposal.changes, proposal_id)
        except ProposalError as e:
            await self._write_audit(
                action="proposal_refused",
                input_data={
                    "proposal_id": proposal_id,
                    "changes": proposal.changes,
                    "change_hash": proposal.change_hash,
                    "requested_by": proposal.requested_by,
                },
                output_data={"status": "refused", "reason": e.message},
                reasoning=(
                    "The stored proposal failed the safety checks when it was "
                    "re-checked at approval time, so nothing was applied."
                ),
                risk_level="high",
                approved_by=None,
            )
            raise

        # The approval decision itself is recorded BEFORE anything is applied, so
        # an approval that then fails part way through still leaves a record of
        # what was authorised, by whom.
        audited = await self._write_audit(
            action="proposal_approved",
            input_data={
                "proposal_id": proposal_id,
                "changes": validated,
                "change_hash": proposal.change_hash,
                "requested_by": proposal.requested_by,
                "requested_at": _iso(proposal.created_at),
                "intent": proposal.intent,
            },
            output_data={"status": "approved_pending_apply"},
            reasoning=(
                "Operator approved this stored proposal. The change list applied is "
                "the stored, re-validated list - not anything from the request body."
            ),
            risk_level="high",
            approved_by=approved_by,
        )
        if not audited:
            raise ProposalError(
                "The approval could not be written to the audit log, so nothing was "
                "applied. The proposal has been discarded; please issue the command "
                "again once the audit log is working.",
                503,
            )

        result = await self._apply_changes(
            validated,
            approved_by=approved_by,
            proposal_id=proposal_id,
            source="approval",
        )
        result["proposal_id"] = proposal_id
        result["approved_by"] = approved_by
        result["requested_by"] = proposal.requested_by
        return result

    async def approve_and_apply(
        self, changes: List[Dict[str, Any]], approved_by: str = "operator"
    ) -> Dict[str, Any]:
        """
        Removed as an entry point; kept only so that anything still calling it
        fails closed with an explanation instead of applying a change list.

        This used to apply whatever list it was given. A request body could
        therefore approve changes that were never proposed - including an
        instruction to set ``dry_run`` to false - and the audit log recorded it as
        a normal operator approval. Approvals now name a stored proposal
        (:meth:`approve_proposal`); a caller-supplied list cannot be applied at
        all.
        """
        await self._write_audit(
            action="approval_refused",
            input_data={"changes": changes, "attempted_by": approved_by},
            output_data={"status": "refused", "reason": "caller_supplied_change_list"},
            reasoning=(
                "An attempt was made to apply a caller-supplied change list. Approvals "
                "must name a stored proposal, so this was refused and nothing was "
                "applied."
            ),
            risk_level="high",
            approved_by=None,
        )
        raise ProposalError(
            "Changes can no longer be applied from a request body. Approving means "
            "sending back the proposal_id you were given: POST /api/v1/approve with "
            '{"proposal_id": "...", "approve": true}. GET /api/v1/proposals lists the '
            "proposals that are waiting.",
            400,
        )

    async def shutdown(self) -> None:
        if self._pending_proposals:
            self.logger.info(
                "Discarding %d pending proposal(s) on shutdown; they are in memory "
                "only and must be re-issued after a restart.",
                len(self._pending_proposals),
            )
            self._pending_proposals.clear()
        self.logger.info("Natural language config plugin shut down")
