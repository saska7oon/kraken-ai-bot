"""
Audit Logger for AI Orchestrator

Provides tamper-evident logging of all AI actions for compliance and debugging.
"""

import json
import logging
import hashlib
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
import aiofiles
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """Single audit log entry."""
    timestamp: str
    action_id: str
    plugin: str
    action: str
    user_initiated: bool
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    decision_reasoning: str
    risk_level: str  # low, medium, high, critical
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    hash: Optional[str] = None
    previous_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Compute SHA256 hash of this entry (excluding hash field)."""
        data = asdict(self)
        data.pop("hash", None)
        data.pop("previous_hash", None)
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditLogger:
    """
    Tamper-evident audit logger with hash chaining.
    Each entry includes hash of previous entry for integrity verification.
    """

    def __init__(
        self,
        log_dir: str = "/app/logs/audit",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 10,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit.log"
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._last_hash: Optional[str] = None
        self._setup_logger()
        self._load_last_hash()

    def _setup_logger(self):
        """Setup rotating file handler for audit logs."""
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        handler = RotatingFileHandler(
            self.log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    def _load_last_hash(self):
        """Load the hash of the last entry for chaining."""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    lines = f.readlines()
                    if lines:
                        last_entry = json.loads(lines[-1])
                        self._last_hash = last_entry.get("hash")
            except Exception as e:
                logger.warning(f"Could not load last hash: {e}")

    def _verify_chain(self) -> bool:
        """Verify the integrity of the audit log chain."""
        if not self.log_file.exists():
            return True

        try:
            with open(self.log_file, "r") as f:
                previous_hash = None
                for line_num, line in enumerate(f, 1):
                    entry = json.loads(line)
                    stored_hash = entry.get("hash")
                    stored_prev_hash = entry.get("previous_hash")

                    # Verify previous hash chain
                    if stored_prev_hash != previous_hash:
                        logger.error(f"Hash chain broken at line {line_num}")
                        return False

                    # Verify current hash
                    computed_hash = hashlib.sha256(
                        json.dumps(
                            {k: v for k, v in entry.items() if k not in ["hash", "previous_hash"]},
                            sort_keys=True,
                            default=str
                        ).encode()
                    ).hexdigest()

                    if computed_hash != stored_hash:
                        logger.error(f"Hash mismatch at line {line_num}")
                        return False

                    previous_hash = stored_hash
            return True
        except Exception as e:
            logger.error(f"Chain verification failed: {e}")
            return False

    async def log(
        self,
        plugin: str,
        action: str,
        user_initiated: bool,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        decision_reasoning: str,
        risk_level: str = "low",
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """
        Log an AI action with full audit trail.
        """
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            action_id=hashlib.sha256(
                f"{plugin}{action}{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16],
            plugin=plugin,
            action=action,
            user_initiated=user_initiated,
            input_data=input_data,
            output_data=output_data,
            decision_reasoning=decision_reasoning,
            risk_level=risk_level,
            approved_by=approved_by,
            approval_timestamp=datetime.utcnow().isoformat() + "Z" if approved_by else None,
            previous_hash=self._last_hash,
        )

        entry.hash = entry.compute_hash()
        self._last_hash = entry.hash

        # Write to log
        self.logger.info(json.dumps(entry.to_dict(), default=str))

        # Also write to daily JSONL file for easy querying
        daily_file = self.log_dir / f"audit_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        async with aiofiles.open(daily_file, "a") as f:
            await f.write(json.dumps(entry.to_dict(), default=str) + "\n")

        return entry

    async def log_config_change(
        self,
        plugin: str,
        config_changes: Dict[str, Any],
        reasoning: str,
        user_initiated: bool = True,
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """Log a configuration change."""
        return await self.log(
            plugin=plugin,
            action="config_change",
            user_initiated=user_initiated,
            input_data={"changes": config_changes},
            output_data={"status": "pending_approval" if not approved_by else "applied"},
            decision_reasoning=reasoning,
            risk_level="high",
            approved_by=approved_by,
        )

    async def log_trade_decision(
        self,
        plugin: str,
        pair: str,
        decision: str,
        reasoning: str,
        confidence: float,
        market_context: Dict[str, Any],
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """Log a trading decision."""
        risk_level = "critical" if decision in ["buy", "sell"] else "medium"
        return await self.log(
            plugin=plugin,
            action="trade_decision",
            user_initiated=False,
            input_data={
                "pair": pair,
                "decision": decision,
                "confidence": confidence,
                "market_context": market_context,
            },
            output_data={"executed": approved_by is not None},
            decision_reasoning=reasoning,
            risk_level=risk_level,
            approved_by=approved_by,
        )

    async def log_strategy_generation(
        self,
        strategy_code: str,
        pair: str,
        reasoning: str,
        backtest_results: Optional[Dict[str, Any]] = None,
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """Log strategy generation."""
        return await self.log(
            plugin="strategy_generator",
            action="generate_strategy",
            user_initiated=False,
            input_data={
                "pair": pair,
                "backtest_results": backtest_results or {},
            },
            output_data={
                "strategy_hash": hashlib.sha256(strategy_code.encode()).hexdigest()[:16],
                "code_length": len(strategy_code),
            },
            decision_reasoning=reasoning,
            risk_level="high",
            approved_by=approved_by,
        )

    def get_recent_entries(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent audit entries."""
        entries = []
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                lines = f.readlines()[-limit:]
                for line in lines:
                    try:
                        data = json.loads(line)
                        entries.append(AuditEntry(**data))
                    except Exception:
                        continue
        return entries

    def get_entries_by_plugin(self, plugin: str, limit: int = 100) -> List[AuditEntry]:
        """Get entries filtered by plugin."""
        entries = []
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("plugin") == plugin:
                            entries.append(AuditEntry(**data))
                            if len(entries) >= limit:
                                break
                    except Exception:
                        continue
        return entries[::-1][:limit]  # Reverse to get most recent

    def get_entries_by_risk_level(self, risk_level: str, limit: int = 100) -> List[AuditEntry]:
        """Get entries filtered by risk level."""
        entries = []
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("risk_level") == risk_level:
                            entries.append(AuditEntry(**data))
                            if len(entries) >= limit:
                                break
                    except Exception:
                        continue
        return entries[::-1][:limit]

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit log integrity."""
        is_valid = self._verify_chain()
        entry_count = 0
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                entry_count = sum(1 for _ in f)
        return {
            "valid": is_valid,
            "entry_count": entry_count,
            "last_hash": self._last_hash,
            "log_file": str(self.log_file),
        }

    async def export_audit_trail(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Export audit trail for date range."""
        entries = []
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        entry_time = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                        if start_date and entry_time < start_date:
                            continue
                        if end_date and entry_time > end_date:
                            continue
                        entries.append(data)
                    except Exception:
                        continue
        return entries