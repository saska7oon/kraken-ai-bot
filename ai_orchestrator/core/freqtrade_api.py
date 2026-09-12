"""
Freqtrade REST API Client for AI Orchestrator

Provides read/write access to Freqtrade via REST API.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp
from aiohttp import ClientTimeout, BasicAuth
import json

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade representation."""
    trade_id: int
    pair: str
    is_open: bool
    open_rate: float
    close_rate: Optional[float]
    stake_amount: float
    amount: float
    open_date: datetime
    close_date: Optional[datetime]
    profit_ratio: Optional[float]
    profit_abs: Optional[float]
    exit_reason: Optional[str]
    enter_tag: Optional[str]
    strategy: str


@dataclass
class PairCandle:
    """Candle data for a pair."""
    pair: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    date: datetime


@dataclass
class StrategyPerformance:
    """Strategy performance metrics."""
    strategy: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_profit: float
    total_profit: float
    max_drawdown: float
    sharpe_ratio: float
    expectancy: float


@dataclass
class BotStatus:
    """Bot status information."""
    state: str  # running, stopped, starting, etc.
    runtime: str
    version: str
    exchange: str
    stake_currency: str
    dry_run: bool
    max_open_trades: int
    open_trades_count: int
    starting_balance: float
    current_balance: float
    profit_total: float
    profit_pct: float


class FreqtradeAPIClient:
    """
    Async client for Freqtrade REST API.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        username: str = "freqtrade",
        password: str = "",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth = BasicAuth(username, password) if password else None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            await self.__aenter__()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Any:
        """Make authenticated request to Freqtrade API."""
        await self._ensure_session()

        url = f"{self.base_url}{endpoint}"
        try:
            async with self.session.request(
                method,
                url,
                params=params,
                json=json_data,
                auth=self.auth,
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    raise Exception("Authentication failed - check API credentials")
                elif response.status == 404:
                    raise Exception(f"Endpoint not found: {endpoint}")
                else:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"Connection error: {e}")

    # ============================================================
    # HEALTH & STATUS
    # ============================================================
    async def ping(self) -> Dict[str, str]:
        """Health check endpoint."""
        return await self._request("GET", "/api/v1/ping")

    async def status(self) -> BotStatus:
        """Get bot status."""
        data = await self._request("GET", "/api/v1/status")
        return BotStatus(**data.get("data", {}))

    async def version(self) -> Dict[str, str]:
        """Get version info."""
        return await self._request("GET", "/api/v1/version")

    # ============================================================
    # TRADES
    # ============================================================
    async def get_trades(
        self,
        limit: int = 100,
        offset: int = 0,
        pair: Optional[str] = None,
        is_open: Optional[bool] = None,
    ) -> List[Trade]:
        """Get trade history."""
        params = {"limit": limit, "offset": offset}
        if pair:
            params["pair"] = pair
        if is_open is not None:
            params["is_open"] = str(is_open).lower()

        data = await self._request("GET", "/api/v1/trades", params=params)
        trades = []
        for t in data.get("data", []):
            trades.append(Trade(
                trade_id=t["trade_id"],
                pair=t["pair"],
                is_open=t["is_open"],
                open_rate=t["open_rate"],
                close_rate=t.get("close_rate"),
                stake_amount=t["stake_amount"],
                amount=t["amount"],
                open_date=datetime.fromisoformat(t["open_date"].replace("Z", "+00:00")),
                close_date=datetime.fromisoformat(t["close_date"].replace("Z", "+00:00")) if t.get("close_date") else None,
                profit_ratio=t.get("profit_ratio"),
                profit_abs=t.get("profit_abs"),
                exit_reason=t.get("exit_reason"),
                enter_tag=t.get("enter_tag"),
                strategy=t.get("strategy", ""),
            ))
        return trades

    async def get_trade(self, trade_id: int) -> Trade:
        """Get specific trade by ID."""
        data = await self._request("GET", f"/api/v1/trade/{trade_id}")
        t = data.get("data", {})
        return Trade(
            trade_id=t["trade_id"],
            pair=t["pair"],
            is_open=t["is_open"],
            open_rate=t["open_rate"],
            close_rate=t.get("close_rate"),
            stake_amount=t["stake_amount"],
            amount=t["amount"],
            open_date=datetime.fromisoformat(t["open_date"].replace("Z", "+00:00")),
            close_date=datetime.fromisoformat(t["close_date"].replace("Z", "+00:00")) if t.get("close_date") else None,
            profit_ratio=t.get("profit_ratio"),
            profit_abs=t.get("profit_abs"),
            exit_reason=t.get("exit_reason"),
            enter_tag=t.get("enter_tag"),
            strategy=t.get("strategy", ""),
        )

    async def force_exit(self, trade_id: int) -> Dict[str, Any]:
        """Force exit a trade."""
        return await self._request("POST", f"/api/v1/trade/{trade_id}/exit")

    async def delete_trade(self, trade_id: int) -> Dict[str, Any]:
        """Delete a trade (dry-run only)."""
        return await self._request("DELETE", f"/api/v1/trade/{trade_id}")

    # ============================================================
    # PAIRS & MARKET DATA
    # ============================================================
    async def get_pairs(self) -> List[Dict[str, Any]]:
        """Get available pairs from exchange."""
        data = await self._request("GET", "/api/v1/pairs")
        return data.get("data", [])

    async def get_whitelist(self) -> List[str]:
        """Get current whitelist."""
        data = await self._request("GET", "/api/v1/whitelist")
        return data.get("data", [])

    async def set_whitelist(self, pairs: List[str]) -> Dict[str, Any]:
        """Set whitelist (requires reload)."""
        return await self._request("POST", "/api/v1/whitelist", json_data={"pairs": pairs})

    async def add_to_whitelist(self, pairs: List[str]) -> Dict[str, Any]:
        """Add pairs to whitelist."""
        return await self._request("POST", "/api/v1/whitelist/add", json_data={"pairs": pairs})

    async def remove_from_whitelist(self, pairs: List[str]) -> Dict[str, Any]:
        """Remove pairs from whitelist."""
        return await self._request("POST", "/api/v1/whitelist/remove", json_data={"pairs": pairs})

    async def get_blacklist(self) -> List[str]:
        """Get current blacklist."""
        data = await self._request("GET", "/api/v1/blacklist")
        return data.get("data", [])

    async def set_blacklist(self, pairs: List[str]) -> Dict[str, Any]:
        """Set blacklist."""
        return await self._request("POST", "/api/v1/blacklist", json_data={"pairs": pairs})

    async def get_candles(
        self,
        pair: str,
        timeframe: str = "5m",
        limit: int = 100,
    ) -> List[PairCandle]:
        """Get candle data for a pair."""
        params = {"pair": pair, "timeframe": timeframe, "limit": limit}
        data = await self._request("GET", "/api/v1/candles", params=params)
        candles = []
        for c in data.get("data", []):
            candles.append(PairCandle(
                pair=c["pair"],
                timeframe=c["timeframe"],
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
                date=datetime.fromisoformat(c["date"].replace("Z", "+00:00")),
            ))
        return candles

    async def get_ticker(self, pair: Optional[str] = None) -> Dict[str, Any]:
        """Get ticker data."""
        params = {}
        if pair:
            params["pair"] = pair
        data = await self._request("GET", "/api/v1/ticker", params=params)
        return data.get("data", {})

    # ============================================================
    # CONFIGURATION
    # ============================================================
    async def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        data = await self._request("GET", "/api/v1/config")
        return data.get("data", {})

    async def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration (requires reload)."""
        return await self._request("POST", "/api/v1/config", json_data=config)

    async def reload_config(self) -> Dict[str, Any]:
        """Reload configuration."""
        return await self._request("POST", "/api/v1/reload_config")

    # ============================================================
    # STRATEGY
    # ============================================================
    async def get_strategy(self) -> Dict[str, Any]:
        """Get current strategy info."""
        data = await self._request("GET", "/api/v1/strategy")
        return data.get("data", {})

    async def list_strategies(self) -> List[str]:
        """List available strategies."""
        data = await self._request("GET", "/api/v1/strategies")
        return data.get("data", [])

    async def set_strategy(self, strategy: str) -> Dict[str, Any]:
        """Change strategy (requires reload)."""
        return await self._request("POST", "/api/v1/strategy", json_data={"strategy": strategy})

    # ============================================================
    # PROFIT & PERFORMANCE
    # ============================================================
    async def get_profit(self) -> Dict[str, Any]:
        """Get profit statistics."""
        data = await self._request("GET", "/api/v1/profit")
        return data.get("data", {})

    async def get_performance(self) -> List[StrategyPerformance]:
        """Get strategy performance."""
        data = await self._request("GET", "/api/v1/performance")
        performances = []
        for p in data.get("data", []):
            performances.append(StrategyPerformance(**p))
        return performances

    async def get_daily_profit(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily profit history."""
        params = {"days": days}
        data = await self._request("GET", "/api/v1/daily_profit", params=params)
        return data.get("data", [])

    # ============================================================
    # BALANCE
    # ============================================================
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        data = await self._request("GET", "/api/v1/balance")
        return data.get("data", {})

    # ============================================================
    # BOT CONTROL
    # ============================================================
    async def start(self) -> Dict[str, Any]:
        """Start the bot."""
        return await self._request("POST", "/api/v1/start")

    async def stop(self) -> Dict[str, Any]:
        """Stop the bot."""
        return await self._request("POST", "/api/v1/stop")

    async def restart(self) -> Dict[str, Any]:
        """Restart the bot."""
        return await self._request("POST", "/api/v1/restart")

    async def pause(self) -> Dict[str, Any]:
        """Pause trading (keep bot running)."""
        return await self._request("POST", "/api/v1/pause")

    async def resume(self) -> Dict[str, Any]:
        """Resume trading."""
        return await self._request("POST", "/api/v1/resume")

    # ============================================================
    # LOGS
    # ============================================================
    async def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs."""
        params = {"limit": limit}
        data = await self._request("GET", "/api/v1/logs", params=params)
        return data.get("data", [])

    # ============================================================
    # EDGE
    # ============================================================
    async def get_edge_info(self) -> Dict[str, Any]:
        """Get Edge (position sizing) info."""
        data = await self._request("GET", "/api/v1/edge")
        return data.get("data", {})

    # ============================================================
    # PLOTTING
    # ============================================================
    async def get_plot_config(self) -> Dict[str, Any]:
        """Get plot configuration."""
        data = await self._request("GET", "/api/v1/plot_config")
        return data.get("data", {})

    async def get_plot_data(
        self,
        pair: str,
        timeframe: str = "5m",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get plot data for a pair."""
        params = {"pair": pair, "timeframe": timeframe, "limit": limit}
        data = await self._request("GET", "/api/v1/plot", params=params)
        return data.get("data", {})

    # ============================================================
    # HELPER METHODS
    # ============================================================
    async def get_open_trades(self) -> List[Trade]:
        """Get all open trades."""
        return await self.get_trades(is_open=True)

    async def get_closed_trades(self, limit: int = 50) -> List[Trade]:
        """Get recent closed trades."""
        return await self.get_trades(is_open=False, limit=limit)

    async def get_total_profit(self) -> float:
        """Get total profit."""
        profit = await self.get_profit()
        return profit.get("profit_total", 0.0)

    async def get_win_rate(self) -> float:
        """Get win rate from performance."""
        perf = await self.get_performance()
        if perf:
            return perf[0].win_rate
        return 0.0

    async def health_check(self) -> bool:
        """Simple health check."""
        try:
            result = await self.ping()
            return result.get("status") == "pong"
        except Exception:
            return False