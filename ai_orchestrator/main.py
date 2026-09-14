"""
AI Orchestrator Main Entry Point

FastAPI service providing REST API for natural language commands,
plugin management, and system monitoring.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Core imports
from ai_orchestrator.core.openrouter_client import OpenRouterClient
from ai_orchestrator.core.freqtrade_api import FreqtradeAPIClient
from ai_orchestrator.core.audit_logger import AuditLogger
from ai_orchestrator.core.plugin_manager import PluginManager

# Setup logging
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
    """Load configuration from YAML file."""
    import yaml
    config_path = "/app/config/ai_orchestrator.yaml"
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def read_secret(secret_name: str) -> str:
    """Read secret from Docker secrets."""
    path = f"/run/secrets/{secret_name}"
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return ""


# ============================================================
# LIFESPAN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global openrouter_client, freqtrade_client, audit_logger, plugin_manager

    logger.info("Starting AI Orchestrator...")

    # Load config
    config = load_config()

    # Read secrets
    openrouter_key = read_secret("openrouter_api_key")
    freqtrade_password = read_secret("freqtrade_api_password")
    discord_webhook = read_secret("discord_webhook")

    if not openrouter_key:
        logger.warning("OpenRouter API key not found in secrets")

    # Initialize clients
    openrouter_client = OpenRouterClient(
        api_key=openrouter_key,
        default_model=config.get("model", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        fallback_models=config.get("fallback_models", []),
    )

    freqtrade_client = FreqtradeAPIClient(
        base_url="http://freqtrade:8080",
        username="freqtrade",
        password=freqtrade_password,
    )

    audit_logger = AuditLogger(
        log_dir="/app/logs/audit",
    )

    # Initialize plugin manager
    plugin_manager = PluginManager(
        openrouter_client=openrouter_client,
        freqtrade_client=freqtrade_client,
        audit_logger=audit_logger,
        config=config,
    )

    await plugin_manager.initialize()
    await plugin_manager.start_scheduler()

    # Test connections
    try:
        await freqtrade_client.health_check()
        logger.info("Freqtrade connection OK")
    except Exception as e:
        logger.error(f"Freqtrade connection failed: {e}")

    logger.info("AI Orchestrator started successfully")

    yield

    # Shutdown
    logger.info("Shutting down AI Orchestrator...")
    await plugin_manager.shutdown()
    if openrouter_client:
        await openrouter_client.__aexit__(None, None, None)
    if freqtrade_client:
        await freqtrade_client.__aexit__(None, None, None)
    logger.info("AI Orchestrator shut down")


# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(
    title="Kraken AI Orchestrator",
    description="AI-powered trading bot orchestration for Freqtrade on Kraken Canada",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Simple auth - in production use proper JWT."""
    # For now, just check if credentials exist
    if credentials:
        return credentials.credentials
    return "anonymous"


# ============================================================
# PYDANTIC MODELS
# ============================================================
class CommandRequest(BaseModel):
    command: str = Field(..., description="Natural language command")
    user_id: str = Field(default="user", description="User identifier")
    force: bool = Field(default=False, description="Force execution without approval")

class CommandResponse(BaseModel):
    status: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    proposed_changes: Optional[list] = None
    message: Optional[str] = None
    result: Optional[dict] = None
    approval_required: Optional[bool] = None

class ApprovalRequest(BaseModel):
    approve: bool
    changes: list

class PluginControlRequest(BaseModel):
    plugin: str
    action: str  # enable, disable, run
    config: Optional[dict] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, Any]
    plugins: Dict[str, Any]


# ============================================================
# ROUTES
# ============================================================
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    freqtrade_healthy = False
    if freqtrade_client:
        try:
            freqtrade_healthy = await freqtrade_client.health_check()
        except Exception:
            pass

    openrouter_healthy = False
    if openrouter_client:
        try:
            # Quick model list check
            await openrouter_client.list_models()
            openrouter_healthy = True
        except Exception:
            pass

    plugins_status = {}
    if plugin_manager:
        plugins_status = {
            name: info.status.value
            for name, info in plugin_manager.get_all_status().items()
        }

    return HealthResponse(
        status="healthy" if freqtrade_healthy else "degraded",
        timestamp=datetime.utcnow().isoformat() + "Z",
        services={
            "freqtrade": freqtrade_healthy,
            "openrouter": openrouter_healthy,
            "audit_logger": True,
        },
        plugins=plugins_status,
    )


@app.post("/api/v1/command", response_model=CommandResponse)
async def process_command(request: CommandRequest, user: str = Depends(get_current_user)):
    """Process natural language command."""
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")

    nl_plugin = plugin_manager.plugins.get("nl_config")
    if not nl_plugin:
        raise HTTPException(status_code=503, detail="NL Config plugin not loaded")

    result = await nl_plugin.process_command(request.command, request.user_id)

    # Handle force flag for auto-approval
    if request.force and result.get("approval_required"):
        result = await nl_plugin.approve_and_apply(result.get("proposed_changes", []))

    return CommandResponse(**result)


@app.post("/api/v1/approve")
async def approve_changes(request: ApprovalRequest, user: str = Depends(get_current_user)):
    """Approve or reject pending changes."""
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")

    nl_plugin = plugin_manager.plugins.get("nl_config")
    if not nl_plugin:
        raise HTTPException(status_code=503, detail="NL Config plugin not loaded")

    if request.approve:
        result = await nl_plugin.approve_and_apply(request.changes)
        return {"status": "approved", "result": result}
    else:
        return {"status": "rejected", "message": "Changes rejected by user"}


@app.get("/api/v1/plugins")
async def list_plugins():
    """List all plugins and their status."""
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
async def control_plugin(plugin_name: str, request: PluginControlRequest):
    """Control a plugin (enable, disable, run)."""
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
async def get_recent_audit(limit: int = 50):
    """Get recent audit log entries."""
    if not audit_logger:
        raise HTTPException(status_code=503, detail="Audit logger not initialized")

    entries = audit_logger.get_recent_entries(limit)
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
            for e in entries
        ]
    }


@app.get("/api/v1/audit/verify")
async def verify_audit_integrity():
    """Verify audit log integrity."""
    if not audit_logger:
        raise HTTPException(status_code=503, detail="Audit logger not initialized")

    return audit_logger.verify_integrity()


@app.get("/api/v1/status")
async def get_bot_status():
    """Get Freqtrade bot status."""
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    status = await freqtrade_client.status()
    return {
        "state": status.state,
        "runtime": status.runtime,
        "exchange": status.exchange,
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
async def get_trades(limit: int = 20, open_only: bool = False):
    """Get recent trades."""
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    trades = await freqtrade_client.get_trades(limit=limit, is_open=open_only if open_only else None)
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
                "open_date": t.open_date.isoformat(),
                "close_date": t.close_date.isoformat() if t.close_date else None,
                "profit_ratio": t.profit_ratio,
                "profit_abs": t.profit_abs,
                "exit_reason": t.exit_reason,
                "enter_tag": t.enter_tag,
                "strategy": t.strategy,
            }
            for t in trades
        ]
    }


@app.get("/api/v1/performance")
async def get_performance():
    """Get strategy performance."""
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    perf = await freqtrade_client.get_performance()
    return {
        "performance": [
            {
                "strategy": p.strategy,
                "total_trades": p.total_trades,
                "winning_trades": p.winning_trades,
                "losing_trades": p.losing_trades,
                "win_rate": p.win_rate,
                "avg_profit": p.avg_profit,
                "total_profit": p.total_profit,
                "max_drawdown": p.max_drawdown,
                "sharpe_ratio": p.sharpe_ratio,
                "expectancy": p.expectancy,
            }
            for p in perf
        ]
    }


@app.get("/api/v1/balance")
async def get_balance():
    """Get exchange balance."""
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    return await freqtrade_client.get_balance()


@app.get("/api/v1/whitelist")
async def get_whitelist():
    """Get current whitelist."""
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    return {"whitelist": await freqtrade_client.get_whitelist()}


@app.post("/api/v1/whitelist")
async def update_whitelist(pairs: list):
    """Update whitelist."""
    if not freqtrade_client:
        raise HTTPException(status_code=503, detail="Freqtrade client not initialized")

    result = await freqtrade_client.set_whitelist(pairs)
    return result


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8082"))
    # Pass the app object directly (not the "main:app" import string) so this
    # works regardless of how the process was started / what CWD is set.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )