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

import asyncio
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ai_orchestrator.core.audit_logger import AuditLogger
from ai_orchestrator.core import dryrun_reset, settings_store, strategy_switch
from ai_orchestrator.core.freqtrade_api import (
    FreqtradeAPIClient,
    FreqtradeAPIError,
    UnsupportedOperation,
)
from ai_orchestrator.core.openrouter_client import OpenRouterClient
from ai_orchestrator.core.strategy_inspector import (
    describe_strategy,
    read_strategy_protections,
)
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

    # Bound before anything can fail, so the shutdown path below can always refer
    # to it even if startup died earlier.
    strategy_queue_task = None

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

    # Wait for Freqtrade to become reachable, rather than checking once and
    # declaring failure.
    #
    # In a Swarm stack both containers start together and freqtrade is far
    # slower: it loads ccxt, resolves the strategy, validates its config and
    # syncs wallets before its API server binds. A single check therefore failed
    # on every ordinary startup and logged "Cannot reach the Freqtrade API.
    # Check the API password secret." - naming the one thing that was fine,
    # while the real cause was that the other container was not listening yet.
    # Anyone reading that would go and re-create a secret that was never wrong.
    #
    # Retrying costs nothing and removes the false alarm. If it still cannot
    # connect after the deadline, the message names both plausible causes and is
    # then worth acting on.
    freqtrade_ready = False
    waited = 0.0
    delay = 1.0
    while waited < 90.0:
        if await freqtrade_client.health_check():
            freqtrade_ready = True
            break
        await asyncio.sleep(delay)
        waited += delay
        delay = min(delay * 1.5, 5.0)

    if freqtrade_ready:
        logger.info(
            "Freqtrade connection OK%s",
            "" if waited == 0 else f" (waited {waited:.0f}s for it to start)",
        )
    else:
        logger.error(
            "Freqtrade API still unreachable after %.0fs. Either the bot is "
            "taking longer than usual to start, or 'freqtrade_api_password' "
            "does not match the api_server password in the generated private "
            "config. The orchestrator's views will show no data until this "
            "resolves, and it will retry on each request.",
            waited,
        )

    logger.info("AI Orchestrator started")

    # Drains the queued-strategy file once open positions close. Started even when
    # Freqtrade was unreachable above: the queue is a file on disk, and a change
    # queued before an outage should still apply after it.
    strategy_queue_task = asyncio.create_task(_strategy_queue_loop(freqtrade_client))

    yield

    logger.info("Shutting down AI Orchestrator...")
    if strategy_queue_task:
        strategy_queue_task.cancel()
        try:
            await strategy_queue_task
        except asyncio.CancelledError:
            pass
    if plugin_manager:
        await plugin_manager.shutdown()
    if openrouter_client:
        await openrouter_client.close()
    if freqtrade_client:
        await freqtrade_client.close()
    logger.info("AI Orchestrator shut down")


#: How often to check whether a queued strategy change can be applied. The queue
#: only drains when the last open position closes, which happens on the strategy's
#: own timeframe - minutes, not seconds. A minute is responsive without adding
#: load: each check is one status call.
STRATEGY_QUEUE_INTERVAL_SECS = 60


async def _strategy_queue_loop(freqtrade_client) -> None:
    """Apply a queued strategy change once the open positions have closed.

    This is what makes the queue a queue rather than a refusal. Without it a
    queued change would sit in the file forever and the operator would be left
    waiting for something that was never going to happen - which is worse than
    being told no, because a wait looks like it might end.

    Only ever acts when something is queued, so an idle bot does no extra work
    beyond reading one small file per minute.
    """
    while True:
        try:
            await asyncio.sleep(STRATEGY_QUEUE_INTERVAL_SECS)

            if strategy_switch.pending() is None:
                continue

            try:
                status = await freqtrade_client.status()
                open_trades = status.open_trades_count
            except FreqtradeAPIError as e:
                # Cannot see the positions, so cannot know it is safe. Leave the
                # queue alone and try again next tick.
                logger.warning("Could not check open trades for the queued strategy: %s", e)
                continue

            result = await strategy_switch.reconcile(
                open_trades=open_trades, freqtrade=freqtrade_client
            )
            if not result:
                continue

            logger.info("Queued strategy change: %s", result)
            try:
                await audit_log.record(
                    plugin="settings",
                    action="strategy_switch_applied",
                    user_initiated=True,
                    input_data={"open_trades_before": open_trades},
                    output_data=result,
                    decision_reasoning=(
                        "Open positions closed; the queued strategy change was "
                        "applied and the bot restarted."
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not audit the applied strategy change: %s", exc)

        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            # One bad tick must not end the loop: that would strand a queued
            # change permanently, silently.
            logger.error("Strategy queue check failed: %s", exc)


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


class BotControlRequest(BaseModel):
    """Start, pause or stop the running bot.

    A closed set of three actions rather than a free-text command. The
    natural-language path already understands "pause trading", but it goes
    through intent parsing, and an operator pressing a button labelled Stop is
    entitled to have exactly that happen rather than whatever the parser made
    of the sentence it generated.
    """

    model_config = ConfigDict(extra="forbid")

    action: str


class SettingsRequest(BaseModel):
    """A change the operator is making deliberately.

    `confirmation` is required only to turn off dry run. It is a separate field
    rather than a flag inside `settings` so that it cannot be written into the
    settings file by mistake - `settings` is validated against an allowlist and
    persisted, and the confirmation must never be persisted.
    """

    model_config = ConfigDict(extra="forbid")

    settings: Dict[str, Any]
    confirmation: Optional[str] = Field(
        default=None,
        description='Required to disable dry run. Must be exactly "TRADE REAL MONEY".',
    )


class PresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: str


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: str = Field(
        ...,
        description='Must be exactly "RESET DRY RUN".',
    )


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


# ---------------------------------------------------------------------------
# Operator UI
# ---------------------------------------------------------------------------
#: Location of the single-page UI, shipped inside the package so the existing
#: `COPY ai_orchestrator/ /app/ai_orchestrator/` in the Dockerfile picks it up.
UI_DIR = Path(__file__).resolve().parent / "ui"
UI_FILE = UI_DIR / "index.html"


def _render_ui() -> str:
    """Read the UI page from disk, or return an explanatory placeholder.

    Read per request rather than cached at import: the file is a few tens of
    kilobytes and reading it keeps a UI fix deployable without a rebuild. A
    missing file must not take the service down - this route is a convenience,
    and the API it fronts is the actual product - so failure is reported as a
    readable page rather than a 500.
    """
    try:
        return UI_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("UI page missing at %s", UI_FILE)
        return (
            "<!doctype html><html><body style=\"font-family:system-ui;"
            "background:#05070d;color:#e8ecf6;padding:40px\">"
            "<h1>Operator UI not found</h1>"
            "<p>The page should be at <code>" + str(UI_FILE) + "</code>. "
            "The REST API is unaffected and still available under "
            "<code>/api/v1/</code>.</p></body></html>"
        )


@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
async def operator_ui():
    """Serve the operator UI.

    Deliberately **unauthenticated**, and deliberately harmless: the response is
    a static page containing no configuration, no credentials and no data. The
    bearer token is entered by the operator in the browser and kept in that
    browser's storage; the page never receives it from the server. Every API
    call the page makes is authenticated exactly as any other client's would be,
    so serving this HTML grants no access that a `curl` user does not already
    have.

    Requiring a token to fetch the page would not add security - it would only
    mean the operator has to paste the token into a prompt to receive a page
    that then asks them to paste the token.
    """
    return HTMLResponse(content=_render_ui())


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
    posture["strategy"] = describe_strategy(strategy_name)

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


# =============================================================================
# Operator settings
# =============================================================================
# These routes are how the operator changes configuration without hand-editing
# JSON in Portainer. They are deliberately separate from everything the AI can
# reach:
#
#   * No plugin, no chat command and no proposal can call them. `nl_config` keeps
#     its own frozen-key list, and nothing in the command path imports this
#     module. A test asserts the AI-reachable surface cannot write settings.
#   * Credentials are never accepted here. The allowlist in settings_store has no
#     key for an API key, a secret, or the exchange block - so "change the API
#     key from the UI" is not a guarded operation, it is an absent one.
#   * `db_url` is derived from `dry_run` rather than accepted, which makes the
#     mismatched-pair bug unrepresentable instead of merely validated.
#
# Every change is audited, and applied with a config reload rather than a
# restart, so a change is one action rather than a trip to Portainer.


async def _audit_settings(
    actor: str, changes: Dict[str, Any], reasoning: str
) -> Optional[str]:
    """Record a settings change, and say so if it could not be recorded.

    Deliberately non-blocking, unlike the read-only audit routes which return
    503. Blocking would mean an operator cannot move *back* to dry run because
    the audit log is unavailable, and that is the wrong direction to fail in: the
    safe change should always be reachable.

    It is not silent either. An unrecorded configuration change is a real gap in
    a tamper-evident trail, so the response says so rather than letting the
    operator assume it was logged.
    """
    if audit_logger is None:
        logger.error("Settings change by %s was NOT audited (logger unavailable)", actor)
        return (
            "This change was not written to the audit log because the audit "
            "logger is unavailable. The change itself did apply."
        )

    try:
        await audit_logger.log_config_change(
            plugin="operator_settings",
            config_changes=changes,
            reasoning=reasoning,
            user_initiated=True,
            approved_by=actor,
        )
    except Exception as e:  # noqa: BLE001 - an audit failure must not undo a change
        logger.error("Failed to audit settings change by %s: %s", actor, e)
        return "This change could not be written to the audit log: %s" % e

    return None


async def _apply_and_reload(actor: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Write settings, then ask Freqtrade to pick them up.

    A failed reload is reported as `applied: false` rather than raised. The
    settings are on disk either way, so the operator needs to know the file
    changed but the running bot has not caught up - telling them it failed
    outright would invite them to change it again.
    """
    result: Dict[str, Any] = {
        "settings": changes,
        "applied": False,
        "reload_error": None,
    }

    if freqtrade_client is None:
        result["reload_error"] = "The Freqtrade API client is not available."
        return result

    try:
        await freqtrade_client.reload_config()
        result["applied"] = True
    except FreqtradeAPIError as e:
        result["reload_error"] = (
            "Saved, but the bot has not applied it yet: %s. It will take effect "
            "the next time the bot restarts." % e
        )

    return result


@app.get("/api/v1/settings")
async def get_settings(_: str = Depends(require_api_token)):
    """Everything needed to render the settings panel, plus what is in force."""
    payload = settings_store.describe()

    # Which strategies could actually be switched to. Read from the volume, so
    # this cannot offer something the bot would fail to load.
    payload["available_strategies"] = strategy_switch.available_strategies()
    # A queued change, if one is waiting for positions to close.
    payload["pending_strategy"] = strategy_switch.describe()

    # The running bot's view, which is what actually matters. If this disagrees
    # with the settings file, the file was written but not applied - worth
    # showing rather than hiding.
    if freqtrade_client:
        try:
            cfg = await freqtrade_client.get_config()
            payload["effective"] = {
                "dry_run": cfg.get("dry_run"),
                "max_open_trades": cfg.get("max_open_trades"),
                "stoploss": cfg.get("stoploss"),
                "tradable_balance_ratio": cfg.get("tradable_balance_ratio"),
                "dry_run_wallet": cfg.get("dry_run_wallet"),
                "db_url": cfg.get("db_url"),
                # Shown because it is now the thing that can be out of step with
                # the settings file while a change is queued.
                "strategy": cfg.get("strategy"),
            }
        except FreqtradeAPIError as e:
            payload["effective"] = None
            payload["effective_error"] = str(e)
    else:
        payload["effective"] = None
        payload["effective_error"] = "The Freqtrade API client is not available."

    return payload


@app.post("/api/v1/settings/strategy/cancel")
async def cancel_strategy_switch(user: str = Depends(require_api_token)):
    """Drop a queued strategy change and resume the bot on the current strategy."""
    actor = resolve_operator_name(user)
    if not freqtrade_client:
        raise HTTPException(
            status_code=503, detail="The Freqtrade API client is not available."
        )

    was_running = True
    try:
        was_running = (await freqtrade_client.status()).is_running
    except FreqtradeAPIError:
        # Default to resuming. A bot left paused because a status call failed
        # would look fine from outside and trade nothing.
        was_running = True

    result = await strategy_switch.cancel(
        actor=actor, was_running=was_running, freqtrade=freqtrade_client
    )

    try:
        await audit_log.record(
            plugin="settings",
            action="strategy_switch_cancelled",
            user_initiated=True,
            input_data={"actor": actor},
            output_data=result,
            decision_reasoning="Operator cancelled a queued strategy change.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not audit the strategy cancellation: %s", exc)

    return result


@app.post("/api/v1/settings")
async def update_settings(
    request: SettingsRequest, user: str = Depends(require_api_token)
):
    """Validate, write, audit and apply a settings change.

    The strategy is handled separately, because it is the one setting that cannot
    always take effect at once. With positions open, applying it would hand those
    positions' exits to a strategy that never opened them. So instead of applying
    or refusing, it is queued and the bot is paused until they close.
    """
    actor = resolve_operator_name(user)

    try:
        changes = settings_store.validate(
            request.settings, confirmation=request.confirmation
        )
    except settings_store.SettingsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # Split the strategy out of the batch. Everything else can apply right now,
    # and should: refusing to change max_open_trades because a strategy switch is
    # waiting would be a worse answer than doing the part that is safe.
    requested_strategy = changes.pop("strategy", None)
    strategy_result: Optional[Dict[str, Any]] = None

    # How many positions are open decides whether the strategy applies now.
    open_trades = 0
    was_running = True
    if requested_strategy is not None and freqtrade_client:
        try:
            status = await freqtrade_client.status()
            open_trades = status.open_trades_count
            was_running = status.is_running
        except FreqtradeAPIError as e:
            # Cannot tell whether positions are open, so cannot safely apply.
            # Queue rather than guess: guessing "none open" is the one answer that
            # can hand open positions to a different strategy.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not read the bot's open trade count, so the strategy "
                    "change was not made. %s" % e
                ),
            )

    if requested_strategy is not None and open_trades > 0:
        # Defer. The other changes in this request still go through below.
        if not freqtrade_client:
            raise HTTPException(
                status_code=503, detail="The Freqtrade API client is not available."
            )
        try:
            strategy_result = await strategy_switch.request(
                requested_strategy,
                actor=actor,
                open_trades=open_trades,
                was_running=was_running,
                freqtrade=freqtrade_client,
            )
            await _audit_strategy_switch(actor, strategy_result)
        except strategy_switch.StrategySwitchError as e:
            raise HTTPException(status_code=409, detail=str(e))
    elif requested_strategy is not None:
        # No positions open - it can go through the ordinary path with everything
        # else in one write and one reload.
        changes["strategy"] = requested_strategy

    if not changes:
        # Only a queued strategy change. Report the queue, not a settings write
        # that did not happen.
        return {
            "applied": False,
            "changes": {},
            "strategy": strategy_result,
            "summary": (strategy_result or {}).get("message")
            or "Nothing to change.",
        }

    try:
        settings_store.write(changes, actor=actor)
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not save the settings: %s. The settings volume may not be "
                "writable." % e
            ),
        )

    audit_note = await _audit_settings(
        actor, changes, "Operator changed settings through the UI."
    )

    result = await _apply_and_reload(actor, changes)
    result["summary"] = _settings_summary(changes, result)
    result["audit_note"] = audit_note
    result["strategy"] = strategy_result
    return result


async def _audit_strategy_switch(actor: str, result: Dict[str, Any]) -> None:
    """Record that a strategy change was requested and what happened to it."""
    try:
        await audit_log.record(
            plugin="settings",
            action="strategy_switch_requested",
            user_initiated=True,
            input_data={"actor": actor},
            output_data=result,
            decision_reasoning=(
                "Operator asked to change strategy; queued until open positions close."
                if result.get("queued")
                else "Operator changed strategy; applied immediately."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not audit the strategy change: %s", exc)


def _settings_summary(changes: Dict[str, Any], result: Dict[str, Any]) -> str:
    """One plain sentence about what just happened."""
    parts = []

    if changes.get("dry_run") is False:
        parts.append(
            "LIVE TRADING IS NOW ON. The bot can place real orders with real "
            "money from now on."
        )
    elif changes.get("dry_run") is True:
        parts.append("Back in simulation. No real orders will be placed.")

    described = [
        "%s is now %s" % (settings_store.EDITABLE_BY_KEY[k].label, v)
        for k, v in sorted(changes.items())
        if k in settings_store.EDITABLE_BY_KEY
    ]
    if described:
        parts.append("Changed: " + "; ".join(described) + ".")

    if result.get("applied"):
        parts.append("The bot has picked the change up.")
    else:
        parts.append(result.get("reload_error") or "The bot has not picked it up yet.")

    return " ".join(parts)


@app.post("/api/v1/settings/preset")
async def apply_risk_preset(
    request: PresetRequest, user: str = Depends(require_api_token)
):
    """Apply a named risk level in one action.

    Three numbers with no explanation is the wrong interface for someone who does
    not trade. A named level with a sentence about what it means is one they can
    actually choose from.
    """
    actor = resolve_operator_name(user)

    try:
        values = settings_store.apply_preset(request.preset)
        changes = settings_store.validate(values)
    except settings_store.SettingsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    try:
        settings_store.write(changes, actor=actor)
    except OSError as e:
        raise HTTPException(status_code=500, detail="Could not save: %s" % e)

    audit_note = await _audit_settings(
        actor, changes, "Operator applied the %r risk level." % request.preset
    )

    result = await _apply_and_reload(actor, changes)
    result["audit_note"] = audit_note
    preset = settings_store.RISK_PRESETS[request.preset]
    result["summary"] = "%s applied. %s %s" % (
        preset["label"],
        preset["blurb"],
        "The bot has picked it up." if result.get("applied") else result.get("reload_error", ""),
    )
    return result


@app.post("/api/v1/settings/undo")
async def undo_settings(user: str = Depends(require_api_token)):
    """Put the previous settings back."""
    actor = resolve_operator_name(user)

    try:
        snapshot = settings_store.restore_backup(actor=actor)
    except settings_store.SettingsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except OSError as e:
        raise HTTPException(status_code=500, detail="Could not restore: %s" % e)

    audit_note = await _audit_settings(
        actor, snapshot.settings, "Operator undid the previous settings change."
    )

    result = await _apply_and_reload(actor, snapshot.settings)
    result["audit_note"] = audit_note
    result["settings"] = snapshot.settings
    result["summary"] = "Previous settings restored. " + (
        "The bot has picked it up."
        if result.get("applied")
        else (result.get("reload_error") or "")
    )
    return result


# ----------------------------------------------------------------- dry-run reset
@app.get("/api/v1/settings/reset-dryrun")
async def preview_dryrun_reset(_: str = Depends(require_api_token)):
    """What a reset would remove. Reads only - nothing is changed."""
    if freqtrade_client is None:
        raise HTTPException(
            status_code=503, detail="The Freqtrade API client is not available."
        )
    return (await dryrun_reset.preview(freqtrade_client)).as_dict()


@app.post("/api/v1/settings/reset-dryrun")
async def reset_dryrun(
    request: ResetRequest, user: str = Depends(require_api_token)
):
    """Clear every simulated trade and release every pair lock.

    Refuses outright when the bot is live. That check reads the trading mode from
    the running bot rather than from a file, so a settings change that has been
    written but not yet applied cannot make this think it is in simulation while
    real orders are being placed.
    """
    if freqtrade_client is None:
        raise HTTPException(
            status_code=503, detail="The Freqtrade API client is not available."
        )

    actor = resolve_operator_name(user)

    try:
        report = await dryrun_reset.reset(
            freqtrade_client, confirmation=request.confirmation, actor=actor
        )
    except dryrun_reset.ResetRefused as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except FreqtradeAPIError as e:
        raise HTTPException(status_code=502, detail="Could not reach the bot: %s" % e)

    report["audit_note"] = await _audit_settings(
        actor,
        {
            "action": "reset_dry_run",
            "trades_deleted": report["trades_deleted"],
            "trades_failed": report["trades_failed"],
            "locks_released": report["locks_released"],
            "backup_path": report["backup_path"],
        },
        "Operator cleared the simulated trade history to start over.",
    )

    return report


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
        # The raw class name is kept because it is what identifies the strategy in
        # the logs and in freqtrade's own output, and someone comparing the two
        # needs them to match. `strategy_label` and `strategy_description` are what
        # the UI shows, so a non-expert is not asked to read CamelCase.
        "strategy": status.strategy,
        **describe_strategy(status.strategy),
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


#: The three things an operator may do to the running bot. A closed set, so an
#: unrecognised action is refused rather than passed to freqtrade.
BOT_CONTROL_ACTIONS: Dict[str, str] = {
    "start": "Start trading (the bot looks for new trades again)",
    "pause": "Pause trading (open trades are still managed)",
    "stop": "Stop the bot (it stops managing open trades too)",
}


@app.post("/api/v1/bot/control")
async def bot_control(
    request: BotControlRequest, user: str = Depends(require_api_token)
):
    """Start, pause or stop the bot, and say plainly what that did.

    The distinction between pause and stop is the whole reason this endpoint
    explains itself. Freqtrade's /stop takes the bot out of its trading loop:
    open positions are no longer managed, so a trailing stop stops trailing and
    the ROI exit stops being evaluated. /pause only stops new entries.

    An operator who does not know that difference will reach for "stop" when
    they mean "stop buying", and quietly stop managing a position that is
    already open. The response spells the consequence out rather than returning
    a bare status code, and the audit log records who did it.
    """
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    action = (request.action or "").strip().lower()
    if action not in BOT_CONTROL_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "'%s' is not something this interface can do to the bot. The "
                "choices are: %s." % (request.action, ", ".join(sorted(BOT_CONTROL_ACTIONS)))
            ),
        )

    actor = resolve_operator_name(user)

    # How many positions would stop being managed. Read before the action, and
    # failure to read is not fatal - it only changes the wording of the reply.
    open_trades = 0
    try:
        status = await freqtrade_client.status()
        open_trades = int(getattr(status, "open_trades_count", 0) or 0)
    except (FreqtradeAPIError, TypeError, ValueError):
        pass

    try:
        if action == "start":
            result = await freqtrade_client.start()
        elif action == "pause":
            result = await freqtrade_client.pause()
        else:
            result = await freqtrade_client.stop()
    except FreqtradeAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if action == "stop":
        if open_trades:
            message = (
                "Bot stopped. You have %d open trade%s, and the bot has stopped "
                "managing %s. A stoploss held at the exchange still protects "
                "%s, but the trailing stop and the profit target are no longer "
                "being watched. Pause instead if you only wanted it to stop "
                "buying."
                % (
                    open_trades,
                    "" if open_trades == 1 else "s",
                    "it" if open_trades == 1 else "them",
                    "it" if open_trades == 1 else "them",
                )
            )
        else:
            message = "Bot stopped. It is not trading and has no open positions."
    elif action == "pause":
        message = (
            "Trading paused. No new trades will be opened. "
            + (
                "Your %d open trade%s still being managed normally." % (
                    open_trades, " is" if open_trades == 1 else "s are"
                )
                if open_trades
                else "There were no open trades."
            )
        )
    else:
        message = "Bot started. It will look for new trades on the next candle."

    await _record_bot_control(actor, action, open_trades)

    return {
        "action": action,
        "description": BOT_CONTROL_ACTIONS[action],
        "message": message,
        "open_trades_at_time_of_action": open_trades,
        "result": result,
    }


async def _record_bot_control(actor: str, action: str, open_trades: int) -> None:
    """Audit a bot control action, without letting an audit failure undo it.

    Same reasoning as the settings path: refusing to pause the bot because the
    audit log is unavailable is the wrong direction to fail in.
    """
    if audit_logger is None:
        logger.error("Bot control '%s' by %s was NOT audited (logger unavailable)", action, actor)
        return

    try:
        await audit_logger.log_config_change(
            plugin="operator_bot_control",
            config_changes={"bot_state": action},
            reasoning=(
                "Operator used the control panel to %s the bot%s."
                % (action, "" if not open_trades else " with %d open trade(s)" % open_trades)
            ),
            user_initiated=True,
            approved_by=actor,
        )
    except Exception as e:  # noqa: BLE001 - an audit failure must not undo the action
        logger.error("Failed to audit bot control '%s' by %s: %s", action, actor, e)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", reload=False)
