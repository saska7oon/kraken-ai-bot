"""
AI Orchestrator - FastAPI service
=================================

Exposes the orchestrator's REST API for natural-language commands, plugin
management, explanatory digests and monitoring.

Security model
--------------
* Every route except ``/health`` requires a bearer token read from the
  ``orchestrator_api_token`` Docker Swarm secret.
* If that secret is missing, the service **fails closed**: authenticated routes
  return 503 with an explanation rather than running open.
* There is no way to skip human approval. The old ``force`` flag on
  ``/api/v1/command`` used to call ``approve_and_apply`` directly, silently
  bypassing the approval gate; it has been removed and is now rejected.
* **An approval names a stored proposal.** ``/api/v1/approve`` takes a
  ``proposal_id`` that this process issued when the command was interpreted, and
  applies the change list stored under it - never a list from the request body.
  A request body used to be able to approve changes that were never proposed,
  including an instruction to set ``dry_run`` to false, and the audit log
  recorded it as an ordinary operator approval. Proposals are single-use, expire
  after 30 minutes, and are re-validated before they are applied.
* **The caller is identified.** ``approved_by`` in the audit log carries the
  authenticated operator name (see ``ORCHESTRATOR_OPERATOR_NAME`` and the
  ``X-Operator-Name`` header), not a hardcoded literal.
* The orchestrator never holds Kraken credentials - only the Freqtrade REST API
  password.
"""

import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ai_orchestrator.core.audit_logger import AuditLogger
from ai_orchestrator.core.freqtrade_api import (
    FreqtradeAPIClient,
    FreqtradeAPIError,
    UnsupportedOperation,
)
from ai_orchestrator.core.openrouter_client import OpenRouterClient
from ai_orchestrator.core.strategy_inspector import read_strategy_protections
from ai_orchestrator.core.plugin_manager import PluginManager
from ai_orchestrator.plugins.nl_config import ProposalError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
openrouter_client: Optional[OpenRouterClient] = None
freqtrade_client: Optional[FreqtradeAPIClient] = None
audit_logger: Optional[AuditLogger] = None
plugin_manager: Optional[PluginManager] = None


# ============================================================
# CONFIGURATION
# ============================================================
def load_config() -> Dict[str, Any]:
    """Load configuration from the Swarm-config-mounted YAML file."""
    import yaml

    config_path = os.environ.get("ORCHESTRATOR_CONFIG", "/app/config/ai_orchestrator.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    logger.warning("Config file %s not found; using defaults", config_path)
    return {}


def read_secret(secret_name: str) -> str:
    """Read a Docker Swarm secret by name from /run/secrets."""
    path = f"/run/secrets/{secret_name}"
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except OSError as e:
            logger.error("Could not read secret %s: %s", secret_name, e)
    return ""


API_TOKEN = read_secret("orchestrator_api_token")


# ============================================================
# AUTHENTICATION
# ============================================================
bearer_scheme = HTTPBearer(auto_error=False)

# Who to record in the audit log when the caller does not say. This used to be a
# hardcoded "operator", so every entry looked identical and the audit trail could
# not answer the one question that matters after an incident: who did this?
OPERATOR_NAME_HEADER = "X-Operator-Name"

# A name is copied into the audit log, so it is restricted to characters that are
# safe to store and read: letters, digits, space, dot, dash, underscore, plus and
# at-sign. Anything else (control characters, newlines, quotes) is discarded
# rather than stored, because an audit log that can be written into is not an
# audit log.
_OPERATOR_NAME_RE = re.compile(r"^[A-Za-z0-9 ._+@-]{1,64}$")

_configured_operator_name = os.environ.get("ORCHESTRATOR_OPERATOR_NAME", "").strip()
if _configured_operator_name and not _OPERATOR_NAME_RE.match(_configured_operator_name):
    # The environment value is checked with the same rule as the header: it ends
    # up in the audit log too, so it must be safe to store.
    logger.warning(
        "ORCHESTRATOR_OPERATOR_NAME contains characters that are not allowed in an "
        "audit log entry; using 'operator' instead."
    )
    _configured_operator_name = ""
DEFAULT_OPERATOR_NAME = _configured_operator_name or "operator"


def resolve_operator_name(supplied: Optional[str]) -> str:
    """
    Decide which operator name to attribute an authenticated action to.

    The name is a label, not a credential: the bearer token is what grants
    access. So an unusable name is not an error - it just falls back to the
    configured default, with a warning, rather than failing a legitimate request.
    """
    if supplied is None or not str(supplied).strip():
        return DEFAULT_OPERATOR_NAME
    candidate = str(supplied).strip()
    if not _OPERATOR_NAME_RE.match(candidate):
        logger.warning(
            "Ignoring an unusable %s header value (%d characters); using the "
            "default operator name instead.",
            OPERATOR_NAME_HEADER,
            len(candidate),
        )
        return DEFAULT_OPERATOR_NAME
    return candidate


def _token_matches(supplied: str, expected: str) -> bool:
    """
    Constant-time bearer-token comparison, on bytes.

    The token is compared as UTF-8 bytes on both sides. The old code passed the
    two ``str`` objects straight to :func:`secrets.compare_digest`, which raises
    ``TypeError: comparing strings with non-ASCII characters is not supported``
    for a non-ASCII credential - so a junk token produced an HTTP 500 instead of
    a 401. That failed closed, but it was noisy, and a noisy auth path is one
    people learn to ignore.

    Any encoding problem is treated as "does not match", never as an error and
    never as a match.
    """
    try:
        return secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError, TypeError) as e:
        logger.warning("Bearer token could not be compared as bytes (%s); rejected.", e)
        return False


async def require_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    x_operator_name: Optional[str] = Header(default=None, alias=OPERATOR_NAME_HEADER),
) -> str:
    """
    Validate the bearer token against the Swarm secret.

    Returns the authenticated operator name, so routes can record who acted
    instead of a hardcoded literal.

    Fails closed: with no token configured, no authenticated route works.
    """
    if not API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail=(
                "The 'orchestrator_api_token' Swarm secret is not configured, so the "
                "orchestrator API is locked. Create the secret in Portainer "
                "(Secrets -> Add secret) and redeploy the stack."
            ),
        )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison so the token cannot be guessed byte by byte.
    if not _token_matches(credentials.credentials, API_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return resolve_operator_name(x_operator_name)


# ============================================================
# LIFESPAN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global openrouter_client, freqtrade_client, audit_logger, plugin_manager

    logger.info("Starting AI Orchestrator...")

    if not API_TOKEN:
        logger.critical(
            "SECURITY: 'orchestrator_api_token' secret is missing. All API routes "
            "will return 503 until it is configured. This is intentional fail-closed "
            "behaviour."
        )

    config = load_config()
    openrouter_key = read_secret("openrouter_api_key")
    freqtrade_password = read_secret("freqtrade_api_password")

    if not openrouter_key:
        logger.warning(
            "OpenRouter API key not found. AI features will degrade gracefully; "
            "deterministic trading is unaffected."
        )
    if not freqtrade_password:
        logger.error("Freqtrade API password secret missing; the bot API is unreachable.")

    openrouter_client = OpenRouterClient(
        api_key=openrouter_key,
        default_model=config.get("model", ""),
        fallback_models=config.get("fallback_models", []),
        daily_request_budget=int(
            (config.get("safety", {}) or {}).get("max_daily_ai_requests", 180)
        ),
    )

    freqtrade_client = FreqtradeAPIClient(
        base_url=os.environ.get("FREQTRADE_API_URL", "http://freqtrade:8080"),
        username=os.environ.get("FREQTRADE_API_USERNAME", "freqtrade"),
        password=freqtrade_password,
    )

    audit_logger = AuditLogger(log_dir="/app/logs/audit")

    plugin_manager = PluginManager(
        openrouter_client=openrouter_client,
        freqtrade_client=freqtrade_client,
        audit_logger=audit_logger,
        config=config,
    )

    await plugin_manager.initialize()
    await plugin_manager.start_scheduler()

    if await freqtrade_client.health_check():
        logger.info("Freqtrade connection OK")
    else:
        logger.error("Cannot reach the Freqtrade API. Check the API password secret.")

    logger.info("AI Orchestrator started")
    yield

    logger.info("Shutting down AI Orchestrator...")
    if plugin_manager:
        await plugin_manager.shutdown()
    if openrouter_client:
        await openrouter_client.close()
    if freqtrade_client:
        await freqtrade_client.close()
    logger.info("AI Orchestrator shut down")


# ============================================================
# APP
# ============================================================
app = FastAPI(
    title="Kraken AI Orchestrator",
    description="AI orchestration for Freqtrade on Kraken Canada",
    version="1.1.0",
    lifespan=lifespan,
)

# Restricted CORS. The previous configuration used allow_origins=["*"] together
# with allow_credentials=True, which let any website the operator visited make
# authenticated calls from their browser.
_allowed_origins = [
    o.strip()
    for o in os.environ.get("ORCHESTRATOR_CORS_ORIGINS", "").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    # X-Operator-Name is the optional attribution label used for the audit log.
    # Without it here, a browser client could not send it at all.
    allow_headers=["Authorization", "Content-Type", OPERATOR_NAME_HEADER],
)


# ============================================================
# MODELS
# ============================================================
class CommandRequest(BaseModel):
    # extra="forbid" means a client still sending the removed "force" flag gets a
    # clear 422 instead of silently having it ignored.
    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., description="Natural language command")
    user_id: str = Field(default="operator", description="User identifier")


class CommandResponse(BaseModel):
    status: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    proposed_changes: Optional[list] = None
    message: Optional[str] = None
    result: Optional[dict] = None
    approval_required: Optional[bool] = None
    # The id the operator must send back to approve. Without it in the response
    # there would be nothing to approve by name, which is the whole point of
    # binding an approval to a stored proposal.
    proposal_id: Optional[str] = None
    expires_at: Optional[str] = None
    expires_in_seconds: Optional[int] = None


class ApprovalRequest(BaseModel):
    """
    The body of an approval.

    ``proposal_id`` names the proposal this process stored when it interpreted
    the operator's command; the stored change list is what gets applied.

    ``changes`` is accepted by the schema only so that a caller still using the
    old body shape gets a clear, actionable error instead of a confusing 422.
    It is never applied - see the route below.
    """

    model_config = ConfigDict(extra="forbid")

    approve: bool
    proposal_id: Optional[str] = Field(
        default=None,
        description="Id of the stored proposal to approve, from the command response",
    )
    changes: Optional[list] = Field(
        default=None,
        description=(
            "Not accepted. Approving applies the stored proposal; send proposal_id."
        ),
    )


class PluginControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str  # enable, disable, run, config
    config: Optional[dict] = None


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., description="Plain-language question about the bot")


class PublicHealth(BaseModel):
    """Deliberately minimal: this route is unauthenticated."""

    status: str
    timestamp: str


class WhitelistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairs: list[str]


# ============================================================
# ROUTES
# ============================================================
@app.get("/health", response_model=PublicHealth)
async def health_check():
    """
    Unauthenticated liveness probe used by the Docker healthcheck.

    Returns no configuration, plugin or credential information.
    """
    return PublicHealth(status="ok", timestamp=datetime.now(timezone.utc).isoformat())


@app.get("/api/v1/health/detail")
async def health_detail(_: str = Depends(require_api_token)):
    """Authenticated health detail."""
    freqtrade_healthy = bool(
        freqtrade_client and await freqtrade_client.health_check()
    )
    return {
        "status": "healthy" if freqtrade_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "freqtrade": freqtrade_healthy,
            "openrouter": bool(openrouter_client and openrouter_client.api_key),
            "audit_logger": audit_logger is not None,
        },
        "api_token_configured": bool(API_TOKEN),
    }


@app.get("/api/v1/safety")
async def safety_posture(_: str = Depends(require_api_token)):
    """
    Report the current safety posture in plain language.

    This exists so the operator (and any reviewer) can confirm at a glance that
    dry-run is still on, protections are active and autonomous trading is off.
    """
    posture: Dict[str, Any] = {
        "dry_run": None,
        "protections": None,
        "autonomous_agent_enabled": None,
        "notes": [],
    }

    strategy_name = None
    if freqtrade_client:
        try:
            cfg = await freqtrade_client.get_config()
            posture["dry_run"] = bool(cfg.get("dry_run", True))
            strategy_name = cfg.get("strategy")
        except FreqtradeAPIError as e:
            posture["notes"].append(f"Could not read bot config: {e}")

    # Protections live on the strategy, not in the config. Freqtrade 2026.x
    # rejects a `protections` config key outright, and the REST API does not
    # expose them, so the strategy source is the only source of truth. Reading
    # config["protections"] here would always be empty and would raise a false
    # "no trade protections are configured" alarm - the single most damaging
    # thing this endpoint could get wrong, because it would teach the operator
    # to distrust the safety report.
    #
    # None means "could not determine", [] means "genuinely none configured".
    posture["protections"] = read_strategy_protections(strategy_name or "")
    posture["protections_source"] = (
        "strategy:protections" if posture["protections"] is not None else None
    )
    posture["strategy_name"] = strategy_name

    if plugin_manager:
        info = plugin_manager.get_all_status().get("autonomous_agent")
        autonomous = plugin_manager.plugins.get("autonomous_agent")
        posture["autonomous_agent_enabled"] = bool(
            getattr(autonomous, "explicitly_enabled", False)
        )
        posture["autonomous_agent_status"] = info.status.value if info else "absent"

    if posture["dry_run"] is False:
        posture["notes"].append(
            "WARNING: the bot is in LIVE mode and can place real orders with real money."
        )
    if posture["protections"] == []:
        posture["notes"].append(
            "WARNING: no trade protections are configured. Consider MaxDrawdown, "
            "StoplossGuard and CooldownPeriod."
        )
    elif posture["protections"] is None:
        posture["notes"].append(
            "Protections could not be read from the strategy, so their status is "
            "unknown. This is NOT a confirmation that none are configured."
        )
    return posture


def get_nl_plugin():
    """
    The natural language config plugin, or a clear 503.

    Also checks that the plugin exposes the proposal API this version of the
    routes needs. A partially upgraded deployment (old plugin, new routes) must
    answer with an explanation rather than a 500 or, worse, an approval that
    quietly applies something.
    """
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")

    nl_plugin = plugin_manager.plugins.get("nl_config")
    if not nl_plugin:
        raise HTTPException(status_code=503, detail="NL config plugin not loaded")

    for method in ("approve_proposal", "reject_proposal", "list_pending_proposals"):
        if not callable(getattr(nl_plugin, method, None)):
            raise HTTPException(
                status_code=503,
                detail=(
                    "The NL config plugin does not support proposal-based approvals, "
                    "so approvals are disabled. Update the orchestrator so the API and "
                    "the plugin are the same version."
                ),
            )
    return nl_plugin


@app.post("/api/v1/command", response_model=CommandResponse)
async def process_command(
    request: CommandRequest, user: str = Depends(require_api_token)
):
    """
    Interpret a natural-language command.

    Changes that affect trading always come back with approval_required=true and a
    ``proposal_id``. There is intentionally no way to auto-approve them: the
    proposal id is what the operator sends back, and it is the only thing that can
    authorise the stored change list.
    """
    nl_plugin = get_nl_plugin()

    # ``actor`` is the authenticated operator name, taken from the token (plus the
    # optional name header). It is authoritative for the audit log and the
    # proposal record; the body's user_id is only a label the caller supplied.
    result = await nl_plugin.process_command(
        request.command, request.user_id, actor=user
    )
    return CommandResponse(**result)


@app.post("/api/v1/approve")
async def approve_changes(
    request: ApprovalRequest, user: str = Depends(require_api_token)
):
    """
    Approve or reject a proposal that this service previously stored.

    The request body names a proposal; it can never supply the changes. The
    operator approves a rendered message, so if the machine applied a list from
    the body the approval would mean nothing - which is exactly what used to
    happen: ``{"approve": true, "changes": [{"key": "dry_run", "value": false}]}``
    was accepted, audited as an approval, and handed back as an instruction to go
    live, without anything ever having been proposed.

    The stored proposal is re-validated (frozen keys, bounds, change types),
    checked against its fingerprint, checked for expiry, and consumed exactly
    once. Any failure is a refusal, never a partial application.
    """
    nl_plugin = get_nl_plugin()

    # The legacy shape is refused explicitly, with a message that says what to do
    # instead. It is checked first so that an old client gets this explanation
    # rather than a bare "field required".
    if request.changes is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Changes can no longer be sent with an approval. Approving means "
                "naming the proposal you were shown: send "
                '{"proposal_id": "...", "approve": true}, using the proposal_id from '
                "the command response. GET /api/v1/proposals lists what is waiting."
            ),
        )

    if not request.proposal_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "A proposal_id is required. Run the command first, then approve it "
                'with {"proposal_id": "...", "approve": true}. '
                "GET /api/v1/proposals lists what is waiting for approval."
            ),
        )

    try:
        if not request.approve:
            return await nl_plugin.reject_proposal(
                request.proposal_id, rejected_by=user
            )

        result = await nl_plugin.approve_proposal(
            request.proposal_id, approved_by=user
        )
    except ProposalError as e:
        # The plugin has already audited the refusal; the operator gets the same
        # plain-language reason over HTTP.
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return {"status": "approved", "result": result}


@app.get("/api/v1/proposals")
async def list_proposals(_: str = Depends(require_api_token)):
    """
    List the proposals waiting for approval.

    This exists so the operator can see what is actually queued - the change
    list, who asked for it, when it expires and its fingerprint - instead of
    having to trust a chat message. Read-only: it cannot approve anything.
    """
    nl_plugin = get_nl_plugin()
    proposals = nl_plugin.list_pending_proposals()
    return {
        "pending": len(proposals),
        "proposals": proposals,
        "note": (
            "Each proposal can be approved once, using its proposal_id, before it "
            "expires. Approving applies exactly the change list shown here."
        ),
    }


@app.post("/api/v1/explain/ask")
async def explain_ask(request: AskRequest, _: str = Depends(require_api_token)):
    """Answer a plain-language question about the bot's behaviour."""
    plugin = plugin_manager.plugins.get("explainer") if plugin_manager else None
    if not plugin:
        raise HTTPException(status_code=503, detail="Explainer plugin not loaded")
    return await plugin.answer_question(request.question)


@app.get("/api/v1/explain/digest")
async def explain_digest(_: str = Depends(require_api_token)):
    """Plain-language summary of the bot's current state."""
    plugin = plugin_manager.plugins.get("explainer") if plugin_manager else None
    if not plugin:
        raise HTTPException(status_code=503, detail="Explainer plugin not loaded")
    return await plugin.build_digest()


@app.get("/api/v1/plugins")
async def list_plugins(_: str = Depends(require_api_token)):
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")

    return {
        "plugins": {
            name: {
                "name": info.name,
                "status": info.status.value,
                "enabled": info.config.enabled,
                "schedule": info.config.schedule,
                "last_run": info.last_run.isoformat() if info.last_run else None,
                "run_count": info.run_count,
                "error_count": info.error_count,
                "last_error": info.last_error,
            }
            for name, info in plugin_manager.get_all_status().items()
        }
    }


@app.post("/api/v1/plugins/{plugin_name}/control")
async def control_plugin(
    plugin_name: str,
    request: PluginControlRequest,
    _: str = Depends(require_api_token),
):
    """Control a plugin (enable, disable, run, config)."""
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")

    if request.action == "enable":
        await plugin_manager.enable_plugin(plugin_name)
    elif request.action == "disable":
        await plugin_manager.disable_plugin(plugin_name)
    elif request.action == "run":
        result = await plugin_manager.run_plugin_now(plugin_name, **(request.config or {}))
        return {"status": "completed", "result": result}
    elif request.action == "config" and request.config:
        await plugin_manager.update_plugin_config(plugin_name, request.config)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")

    return {"status": "success", "plugin": plugin_name, "action": request.action}


@app.get("/api/v1/audit/recent")
async def get_recent_audit(limit: int = 50, _: str = Depends(require_api_token)):
    if not audit_logger:
        raise HTTPException(status_code=503, detail="Audit logger not initialized")

    return {
        "entries": [
            {
                "timestamp": e.timestamp,
                "action_id": e.action_id,
                "plugin": e.plugin,
                "action": e.action,
                "risk_level": e.risk_level,
                "user_initiated": e.user_initiated,
                "approved_by": e.approved_by,
            }
            for e in audit_logger.get_recent_entries(limit)
        ]
    }


@app.get("/api/v1/audit/verify")
async def verify_audit_integrity(_: str = Depends(require_api_token)):
    if not audit_logger:
        raise HTTPException(status_code=503, detail="Audit logger not initialized")
    return audit_logger.verify_integrity()


@app.get("/api/v1/status")
async def get_bot_status(_: str = Depends(require_api_token)):
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    status = await freqtrade_client.status()
    return {
        "state": status.state,
        "runmode": status.runmode,
        "version": status.version,
        "exchange": status.exchange,
        "strategy": status.strategy,
        "timeframe": status.timeframe,
        "stake_currency": status.stake_currency,
        "dry_run": status.dry_run,
        "open_trades": status.open_trades_count,
        "max_open_trades": status.max_open_trades,
        "starting_balance": status.starting_balance,
        "current_balance": status.current_balance,
        "profit_total": status.profit_total,
        "profit_pct": status.profit_pct,
    }


@app.get("/api/v1/trades")
async def get_trades(
    limit: int = 20, open_only: bool = False, _: str = Depends(require_api_token)
):
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    trades = (
        await freqtrade_client.get_open_trades()
        if open_only
        else await freqtrade_client.get_trades(limit=limit)
    )
    return {
        "trades": [
            {
                "trade_id": t.trade_id,
                "pair": t.pair,
                "is_open": t.is_open,
                "open_rate": t.open_rate,
                "close_rate": t.close_rate,
                "stake_amount": t.stake_amount,
                "amount": t.amount,
                "open_date": t.open_date.isoformat() if t.open_date else None,
                "close_date": t.close_date.isoformat() if t.close_date else None,
                "profit_ratio": t.profit_ratio,
                "profit_abs": t.profit_abs,
                "exit_reason": t.exit_reason,
                "enter_tag": t.enter_tag,
            }
            for t in trades
        ]
    }


@app.get("/api/v1/performance")
async def get_performance(_: str = Depends(require_api_token)):
    """
    Trading statistics.

    /performance only returns {pair, profit}; the aggregate statistics come from
    /profit and /stats. The old version invented win_rate, sharpe and drawdown
    fields that the API never returns.
    """
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    profit = await freqtrade_client.get_profit()
    return {
        "per_pair": await freqtrade_client.get_performance(),
        "total_profit": profit.get("profit_all_coin"),
        "total_profit_pct": profit.get("profit_all_percent"),
        "closed_trades": profit.get("closed_trade_count"),
        "win_rate": await freqtrade_client.get_win_rate(),
    }


@app.get("/api/v1/balance")
async def get_balance(_: str = Depends(require_api_token)):
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")
    return await freqtrade_client.get_balance()


@app.get("/api/v1/whitelist")
async def get_whitelist(_: str = Depends(require_api_token)):
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")
    return {
        "whitelist": await freqtrade_client.get_whitelist(),
        "blacklist": await freqtrade_client.get_blacklist(),
    }


@app.post("/api/v1/whitelist")
async def restrict_pairs(
    request: WhitelistRequest, _: str = Depends(require_api_token)
):
    """
    Restrict trading to the given pairs.

    Freqtrade has no runtime whitelist-write API, so this works by blacklisting
    the complement. It is runtime-only and is lost on restart; the durable
    setting lives in the 'freqtrade_canada_config' Swarm config.
    """
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    try:
        return await freqtrade_client.set_whitelist(request.pairs)
    except UnsupportedOperation as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", reload=False)
