"""
Freqtrade REST API Client for the AI Orchestrator
=================================================

This client is written against the **real** Freqtrade REST API. Every endpoint
below was verified against freqtrade/rpc/api_server/*.py.

Why this file was rewritten
---------------------------
The previous version called a large number of endpoints that do not exist
(`POST /api/v1/config`, `POST /api/v1/whitelist`, `GET /api/v1/candles`,
`GET /api/v1/ticker`, `POST /api/v1/strategy`, `GET /api/v1/strategies`,
`GET /api/v1/edge`, `GET /api/v1/plot`, ...). Those calls returned 404, which
was swallowed by broad `except Exception` handlers, so the AI subsystem
appeared to work while doing nothing at all.

It also assumed every response was wrapped in a `{"data": ...}` envelope.
Freqtrade returns its response models directly; only a few endpoints nest
(`/trades` -> "trades", `/markets` -> "markets", `/daily` -> "data",
`/logs` -> "logs", `/whitelist` -> "whitelist", `/blacklist` -> "blacklist").

Design rules followed here
--------------------------
1. Only real endpoints. Anything Freqtrade cannot do at runtime raises
   ``UnsupportedOperation`` with an explanation, rather than silently failing.
2. Defensive parsing: schema drift must never raise ``KeyError``.
3. Read-only by default. Mutating helpers are few, explicit and clearly named.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import BasicAuth, ClientTimeout

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONS
# =============================================================================
class FreqtradeAPIError(Exception):
    """Any failure talking to the Freqtrade REST API."""


class FreqtradeAuthError(FreqtradeAPIError):
    """Authentication with the Freqtrade REST API failed."""


class UnsupportedOperation(FreqtradeAPIError):
    """
    Raised when something is requested that the Freqtrade REST API genuinely
    cannot do. This is deliberately loud: the previous implementation silently
    swallowed these cases and pretended to succeed.
    """


# =============================================================================
# DATA MODELS
# =============================================================================
@dataclass
class Trade:
    """A single trade, open or closed."""

    trade_id: int
    pair: str
    is_open: bool = False
    open_rate: float = 0.0
    close_rate: Optional[float] = None
    stake_amount: float = 0.0
    amount: float = 0.0
    open_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    profit_ratio: Optional[float] = None
    profit_abs: Optional[float] = None
    exit_reason: Optional[str] = None
    enter_tag: Optional[str] = None
    strategy: str = ""

    @classmethod
    def from_api(cls, t: Dict[str, Any]) -> "Trade":
        return cls(
            trade_id=int(t.get("trade_id", 0)),
            pair=t.get("pair", ""),
            is_open=bool(t.get("is_open", False)),
            open_rate=float(t.get("open_rate") or 0.0),
            close_rate=t.get("close_rate"),
            stake_amount=float(t.get("stake_amount") or 0.0),
            amount=float(t.get("amount") or 0.0),
            open_date=_parse_dt(t.get("open_date")),
            close_date=_parse_dt(t.get("close_date")),
            profit_ratio=t.get("profit_ratio"),
            profit_abs=t.get("profit_abs"),
            exit_reason=t.get("exit_reason"),
            enter_tag=t.get("enter_tag"),
            strategy=t.get("strategy") or "",
        )


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp from the API without ever raising."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


@dataclass
class PairCandle:
    """One OHLCV candle for a pair."""

    pair: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    date: datetime


@dataclass
class BotStatus:
    """
    Bot status.

    Freqtrade has no single "status" endpoint - the old client wrongly read
    ``GET /api/v1/status`` (which actually returns the list of OPEN TRADES) and
    tried to unpack it as a status object. This is composed from the endpoints
    that really carry the data: ``/show_config``, ``/count``, ``/profit`` and
    ``/balance``.
    """

    state: str = "unknown"
    runmode: str = "unknown"
    version: str = ""
    exchange: str = ""
    strategy: str = ""
    timeframe: str = ""
    stake_currency: str = ""
    dry_run: bool = True
    max_open_trades: int = 0
    open_trades_count: int = 0
    starting_balance: float = 0.0
    current_balance: float = 0.0
    profit_total: float = 0.0
    profit_pct: float = 0.0

    @property
    def is_running(self) -> bool:
        return self.state == "running"


@dataclass
class BacktestJob:
    """Result of asking Freqtrade to run a backtest."""

    status: str
    job_id: Optional[str] = None
    running: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CLIENT
# =============================================================================
class FreqtradeAPIClient:
    """Async client for the Freqtrade REST API."""

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

    # ------------------------------------------------------------------ session
    async def __aenter__(self) -> "FreqtradeAPIClient":
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    async def _ensure_session(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated request to the Freqtrade API."""
        await self._ensure_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.request(
                method, url, params=params, json=json_data, auth=self.auth
            ) as response:
                if response.status in (200, 201):
                    # Some endpoints legitimately return an empty body.
                    text = await response.text()
                    if not text:
                        return {}
                    try:
                        return await response.json()
                    except Exception:
                        return {"raw": text}

                if response.status == 401:
                    raise FreqtradeAuthError(
                        "Freqtrade rejected the API credentials. Check that the "
                        "'freqtrade_api_password' Swarm secret matches the "
                        "api_server password in the generated private config."
                    )
                if response.status == 404:
                    raise FreqtradeAPIError(
                        f"Freqtrade returned 404 for {method} {endpoint}. "
                        f"This endpoint does not exist in this Freqtrade version."
                    )

                detail = await response.text()
                raise FreqtradeAPIError(
                    f"Freqtrade API error {response.status} on {method} {endpoint}: {detail[:500]}"
                )

        except aiohttp.ClientError as e:
            raise FreqtradeAPIError(f"Cannot reach Freqtrade at {url}: {e}") from e

    # ============================================================ health & info
    async def ping(self) -> Dict[str, Any]:
        """Public health endpoint."""
        return await self._request("GET", "/api/v1/ping")

    async def version(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/version")

    async def get_config(self) -> Dict[str, Any]:
        """Full effective bot configuration (GET /show_config)."""
        return await self._request("GET", "/api/v1/show_config")

    async def get_count(self) -> Dict[str, Any]:
        """Open/max trade counts."""
        return await self._request("GET", "/api/v1/count")

    async def status(self) -> BotStatus:
        """Compose the bot status from the endpoints that actually carry it."""
        cfg = await self.get_config()

        count: Dict[str, Any] = {}
        profit: Dict[str, Any] = {}
        balances: Dict[str, Any] = {}

        # Each of these is optional: a partial status beats no status.
        for label, coro, sink in (
            ("count", self.get_count(), "count"),
            ("profit", self._request("GET", "/api/v1/profit"), "profit"),
            ("balance", self._request("GET", "/api/v1/balance"), "balance"),
        ):
            try:
                value = await coro
            except FreqtradeAPIError as e:
                logger.warning("status(): %s unavailable: %s", label, e)
                continue
            if sink == "count":
                count = value or {}
            elif sink == "profit":
                profit = value or {}
            else:
                balances = value or {}

        try:
            max_open = int(cfg.get("max_open_trades", 0))
        except (TypeError, ValueError):
            max_open = 0

        return BotStatus(
            state=str(cfg.get("state", "unknown")),
            runmode=str(cfg.get("runmode", "unknown")),
            version=str(cfg.get("version", "")),
            exchange=str(cfg.get("exchange", "")),
            strategy=str(cfg.get("strategy") or ""),
            timeframe=str(cfg.get("timeframe") or ""),
            stake_currency=str(cfg.get("stake_currency", "")),
            dry_run=bool(cfg.get("dry_run", True)),
            max_open_trades=max_open,
            open_trades_count=int(count.get("current", 0) or 0),
            starting_balance=float(balances.get("starting_capital", 0.0) or 0.0),
            current_balance=float(balances.get("total", 0.0) or 0.0),
            profit_total=float(profit.get("profit_all_coin", 0.0) or 0.0),
            profit_pct=float(profit.get("profit_all_ratio", 0.0) or 0.0) * 100.0,
        )

    # ================================================================= trades
    async def get_trades(
        self,
        limit: int = 100,
        offset: int = 0,
        pair: Optional[str] = None,
    ) -> List[Trade]:
        """Closed and open trade history (GET /trades -> {"trades": [...]})."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        data = await self._request("GET", "/api/v1/trades", params=params)
        trades = data.get("trades", data.get("data", [])) if isinstance(data, dict) else []
        result = [Trade.from_api(t) for t in trades]
        if pair:
            result = [t for t in result if t.pair == pair]
        return result

    async def get_open_trades(self) -> List[Trade]:
        """
        Currently open trades (GET /status returns open trades directly).

        Note this is the endpoint the old client mistakenly treated as
        bot status.
        """
        data = await self._request("GET", "/api/v1/status")
        if not isinstance(data, list):
            return []
        return [Trade.from_api(t) for t in data]

    async def get_closed_trades(self, limit: int = 50) -> List[Trade]:
        trades = await self.get_trades(limit=limit)
        return [t for t in trades if not t.is_open]

    async def get_trade(self, trade_id: int) -> Optional[Trade]:
        try:
            data = await self._request("GET", f"/api/v1/trade/{trade_id}")
        except FreqtradeAPIError:
            return None
        return Trade.from_api(data) if isinstance(data, dict) else None

    async def force_exit(self, trade_id: int, ordertype: str = "market") -> Dict[str, Any]:
        """
        Force-close a trade (POST /forceexit).

        The old client posted to /trade/{id}/exit, which does not exist.
        """
        return await self._request(
            "POST", "/api/v1/forceexit", json_data={"tradeid": str(trade_id), "ordertype": ordertype}
        )

    async def cancel_open_order(self, trade_id: int) -> Dict[str, Any]:
        return await self._request("DELETE", f"/api/v1/trades/{trade_id}/open-order")

    # ================================================================ markets
    async def get_markets(self) -> Dict[str, Any]:
        """All markets known to the exchange (GET /markets -> {"markets": {...}})."""
        data = await self._request("GET", "/api/v1/markets")
        return data.get("markets", {}) if isinstance(data, dict) else {}

    async def get_pairs(self) -> List[str]:
        """
        Pair names.

        The old client read GET /api/v1/pairs, which does not exist.
        """
        return sorted(await self.get_markets())

    async def get_whitelist(self) -> List[str]:
        """Current whitelist (GET /whitelist -> {"whitelist": [...]})."""
        data = await self._request("GET", "/api/v1/whitelist")
        return list(data.get("whitelist", [])) if isinstance(data, dict) else []

    async def get_blacklist(self) -> List[str]:
        """Current runtime blacklist (GET /blacklist -> {"blacklist": [...]})."""
        data = await self._request("GET", "/api/v1/blacklist")
        return list(data.get("blacklist", [])) if isinstance(data, dict) else []

    async def add_to_blacklist(self, pairs: List[str]) -> Dict[str, Any]:
        """Add pairs to the RUNTIME blacklist (POST /blacklist)."""
        return await self._request("POST", "/api/v1/blacklist", json_data={"blacklist": pairs})

    async def remove_from_blacklist(self, pairs: List[str]) -> Dict[str, Any]:
        """Remove pairs from the runtime blacklist (DELETE /blacklist)."""
        return await self._request("DELETE", "/api/v1/blacklist", json_data={"blacklist": pairs})

    async def set_whitelist(self, pairs: List[str]) -> Dict[str, Any]:
        """
        Restrict trading to exactly ``pairs``.

        The Freqtrade REST API has **no** whitelist mutation endpoint - the
        whitelist is produced by the configured pairlist handler. The only
        supported runtime equivalent is to blacklist the complement.

        This is intentionally explicit about that, because the effect differs
        from "set the whitelist": the change is runtime-only and disappears when
        the bot restarts, and the blacklist is what actually gates trading.
        """
        available = await self.get_pairs()
        wanted = set(pairs)
        if not wanted:
            raise UnsupportedOperation(
                "Refusing to restrict trading to an empty pair list - that would "
                "blacklist every market. Pass at least one pair."
            )

        unknown = sorted(wanted - set(available))
        if unknown:
            raise UnsupportedOperation(
                f"These pairs are not available on the exchange: {', '.join(unknown)}"
            )

        complement = sorted(set(available) - wanted)
        result = await self.add_to_blacklist(complement)
        return {
            "mode": "blacklist_complement",
            "trading_restricted_to": sorted(wanted),
            "pairs_blacklisted": len(complement),
            "runtime_only": True,
            "raw": result,
        }

    async def get_candles(
        self,
        pair: str,
        timeframe: str = "5m",
        limit: int = 100,
    ) -> List[PairCandle]:
        """
        Analysed candles for a pair (GET /pair_candles).

        The response is column-oriented: ``{"columns": [...], "data": [[...]]}``.
        The old client read GET /api/v1/candles, which does not exist, so this
        always returned nothing.
        """
        data = await self._request(
            "GET",
            "/api/v1/pair_candles",
            params={"pair": pair, "timeframe": timeframe, "limit": limit},
        )
        if not isinstance(data, dict):
            return []

        columns = data.get("columns") or []
        rows = data.get("data") or []
        if not columns or not rows:
            return []

        idx = {name: i for i, name in enumerate(columns)}
        required = ("date", "open", "high", "low", "close", "volume")
        if any(k not in idx for k in required):
            logger.warning(
                "pair_candles for %s is missing expected columns (got %s)", pair, columns
            )
            return []

        candles: List[PairCandle] = []
        for row in rows:
            try:
                candles.append(
                    PairCandle(
                        pair=data.get("pair", pair),
                        timeframe=data.get("timeframe", timeframe),
                        open=float(row[idx["open"]]),
                        high=float(row[idx["high"]]),
                        low=float(row[idx["low"]]),
                        close=float(row[idx["close"]]),
                        volume=float(row[idx["volume"]]),
                        date=datetime.fromtimestamp(
                            float(row[idx["date"]]) / 1000.0, tz=timezone.utc
                        ),
                    )
                )
            except (TypeError, ValueError, IndexError) as e:
                logger.debug("Skipping malformed candle row for %s: %s", pair, e)
        return candles

    # ========================================================= strategy & stats
    async def get_ticker_snapshot(self, pair: str) -> Dict[str, Any]:
        """
        A price snapshot **derived from candles**.

        Freqtrade has no ticker/orderbook endpoint, so the old ``get_ticker``
        call always 404'd. The last price, 24h change and 24h volume are derived
        from real candles; bid/ask are genuinely unavailable and are returned as
        ``None`` rather than invented.

        The ``source`` field records that this is derived, so nothing downstream
        can mistake it for exchange-native ticker data.
        """
        hourly = await self.get_candles(pair, "1h", 25)
        if not hourly:
            # Fall back to 5m candles if hourly data is not available.
            hourly = await self.get_candles(pair, "5m", 288)

        if not hourly:
            return {
                "pair": pair,
                "last": None,
                "change_24h_pct": None,
                "volume_24h": None,
                "bid": None,
                "ask": None,
                "source": "unavailable",
            }

        last = hourly[-1].close
        window = hourly[-24:] if len(hourly) >= 24 else hourly
        first = window[0].open or window[0].close
        change_pct = ((last - first) / first * 100.0) if first else None
        volume = sum(c.volume for c in window)

        return {
            "pair": pair,
            "last": last,
            "change_24h_pct": change_pct,
            "volume_24h": volume,
            "bid": None,
            "ask": None,
            "source": "derived_from_candles",
        }

    async def get_strategy(self, strategy: str) -> Dict[str, Any]:
        """Info for a named strategy (GET /strategy/{strategy})."""
        return await self._request("GET", f"/api/v1/strategy/{strategy}")

    async def get_profit(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/profit")

    async def get_performance(self) -> List[Dict[str, Any]]:
        """Per-pair performance (GET /performance -> list of {pair, profit})."""
        data = await self._request("GET", "/api/v1/performance")
        return list(data) if isinstance(data, list) else []

    async def get_stats(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/stats")

    async def get_daily_profit(self, days: int = 30) -> List[Dict[str, Any]]:
        """Daily profit records (GET /daily?timescale=N)."""
        data = await self._request("GET", "/api/v1/daily", params={"timescale": days})
        return list(data.get("data", [])) if isinstance(data, dict) else []

    async def get_balance(self) -> Dict[str, Any]:
        """Account balances (GET /balance)."""
        return await self._request("GET", "/api/v1/balance")

    async def get_logs(self, limit: int = 100) -> List[Any]:
        """Recent log lines (GET /logs -> {"logs": [...]})."""
        data = await self._request("GET", "/api/v1/logs", params={"limit": limit})
        return list(data.get("logs", [])) if isinstance(data, dict) else []

    # ============================================================ bot control
    async def start(self) -> Dict[str, Any]:
        return await self._request("POST", "/api/v1/start")

    async def stop(self) -> Dict[str, Any]:
        return await self._request("POST", "/api/v1/stop")

    async def pause(self) -> Dict[str, Any]:
        """Stop entering new trades but keep managing open ones."""
        return await self._request("POST", "/api/v1/pause")

    async def reload_config(self) -> Dict[str, Any]:
        """Re-read the config from disk (POST /reload_config)."""
        return await self._request("POST", "/api/v1/reload_config")

    async def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        There is no runtime config-write endpoint in the Freqtrade REST API.

        The old client POSTed to /api/v1/config, which 404s. Raising here means
        callers cannot silently believe a change was applied.
        """
        raise UnsupportedOperation(
            "Freqtrade cannot change its configuration at runtime over the REST API. "
            "Settings such as stoploss, minimal_roi and max_open_trades are read at "
            "startup. To change them, update the 'freqtrade_canada_config' Swarm "
            "config in Portainer and redeploy the stack."
        )

    # ================================================== data download & backtest
    async def download_data(
        self,
        pairs: List[str],
        timeframes: Optional[List[str]] = None,
        days: Optional[int] = None,
        timerange: Optional[str] = None,
        download_trades: bool = False,
    ) -> Dict[str, Any]:
        """
        Start a historical data download (POST /download_data).

        Required before backtesting: Freqtrade cannot backtest without local
        candle data, and Kraken only serves ~720 candles per REST request.
        """
        payload: Dict[str, Any] = {
            "pairs": pairs,
            "timeframes": timeframes or ["5m"],
            "download_trades": download_trades,
        }
        # days and timerange are mutually exclusive in the API.
        if timerange:
            payload["timerange"] = timerange
        else:
            payload["days"] = days if days is not None else 30
        return await self._request("POST", "/api/v1/download_data", json_data=payload)

    async def start_backtest(
        self,
        strategy: str,
        timeframe: Optional[str] = None,
        timerange: Optional[str] = None,
        enable_protections: bool = True,
        dry_run_wallet: Optional[float] = None,
    ) -> BacktestJob:
        """Start a backtest (POST /backtest)."""
        payload: Dict[str, Any] = {
            "strategy": strategy,
            "enable_protections": enable_protections,
        }
        if timeframe:
            payload["timeframe"] = timeframe
        if timerange:
            payload["timerange"] = timerange
        if dry_run_wallet is not None:
            payload["dry_run_wallet"] = dry_run_wallet

        data = await self._request("POST", "/api/v1/backtest", json_data=payload)
        data = data if isinstance(data, dict) else {}
        return BacktestJob(
            status=str(data.get("status", "unknown")),
            job_id=data.get("job_id"),
            running=str(data.get("status", "")).lower() == "running",
            raw=data,
        )

    async def get_backtest_status(self) -> BacktestJob:
        """Poll a running backtest (GET /backtest)."""
        data = await self._request("GET", "/api/v1/backtest")
        data = data if isinstance(data, dict) else {}
        return BacktestJob(
            status=str(data.get("status", "unknown")),
            job_id=data.get("job_id"),
            running=str(data.get("status", "")).lower() == "running",
            raw=data,
        )

    async def abort_backtest(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/backtest/abort")

    async def get_backtest_history(self) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/api/v1/backtest/history")
        if isinstance(data, list):
            return data
        return list(data.get("history", [])) if isinstance(data, dict) else []

    async def get_backtest_result(self, filename: str, strategy: str) -> Dict[str, Any]:
        """Fetch a stored backtest result."""
        return await self._request(
            "GET",
            "/api/v1/backtest/history/result",
            params={"filename": filename, "strategy": strategy},
        )

    # ============================================================== conveniences
    async def get_total_profit(self) -> float:
        profit = await self.get_profit()
        return float(profit.get("profit_all_coin", 0.0) or 0.0)

    async def get_win_rate(self) -> float:
        """
        Win rate as a ratio (0.0-1.0), derived from profit statistics.

        The old client read ``performance[0].win_rate``, but /performance only
        returns {pair, profit} entries.
        """
        profit = await self.get_profit()
        closed = profit.get("closed_trade_count")
        try:
            closed = int(closed)
            winners = int(profit.get("winning_trades", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
        return (winners / closed) if closed else 0.0

    async def health_check(self) -> bool:
        try:
            result = await self.ping()
        except FreqtradeAPIError:
            return False
        if isinstance(result, dict):
            return str(result.get("status", "")).lower() == "pong"
        return False
