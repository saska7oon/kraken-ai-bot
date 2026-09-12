"""
Natural Language Configuration Plugin

Translates natural language commands into Freqtrade configuration changes.
This is the primary interface for user interaction.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig

logger = logging.getLogger(__name__)


@dataclass
class NLCommand:
    """Parsed natural language command."""
    intent: str
    parameters: Dict[str, Any]
    confidence: float
    original_text: str
    requires_approval: bool = True


class NLConfigPlugin(BasePlugin):
    """
    Natural language to configuration translator.
    Handles commands like: "reduce position sizes", "add SOL/CAD to whitelist", etc.
    """

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)
        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger

        # Config
        self.auto_apply_safe = config.config.get("auto_apply_safe", False)
        self.require_approval_for = config.config.get("require_approval_for", [
            "risk_change", "whitelist_change", "strategy_change", "stoploss_change"
        ])

        # Intent patterns (fallback for when LLM unavailable)
        self.intent_patterns = {
            "change_risk": [
                r"(more|less|higher|lower|increase|decrease).*(risk|aggressive|conservative)",
                r"(conservative|moderate|aggressive)\s*mode",
            ],
            "change_whitelist": [
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
            ],
            "explain_trade": [
                r"(why|explain|reason).*(bought|sold|trade|entry|exit)",
            ],
        }

    async def initialize(self) -> bool:
        """Initialize plugin."""
        self.logger.info("Natural Language Config Plugin initialized")
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """This plugin is event-driven, not scheduled."""
        # Used for manual command processing
        command = kwargs.get("command")
        if command:
            return await self.process_command(command)
        return {"status": "idle", "message": "NL Config plugin ready for commands"}

    async def process_command(self, text: str, user_id: str = "user") -> Dict[str, Any]:
        """
        Process a natural language command.
        Returns the parsed intent and proposed config changes.
        """
        self.logger.info(f"Processing command: {text}")

        # Parse intent using LLM
        parsed = await self._parse_intent(text)

        if not parsed or parsed.confidence < 0.5:
            return {
                "status": "unclear",
                "message": "I couldn't understand that command. Try rephrasing.",
                "suggestions": self._get_suggestions(),
            }

        # Generate config changes
        changes = await self._generate_changes(parsed)

        # Check if approval required
        requires_approval = self._requires_approval(parsed, changes)

        # Log to audit
        await self.audit.log(
            plugin="nl_config",
            action="command_received",
            user_initiated=True,
            input_data={"command": text, "user": user_id},
            output_data={
                "intent": parsed.intent,
                "parameters": parsed.parameters,
                "confidence": parsed.confidence,
                "changes": changes,
                "requires_approval": requires_approval,
            },
            decision_reasoning=f"Parsed intent: {parsed.intent} (confidence: {parsed.confidence:.0%})",
            risk_level="high" if requires_approval else "low",
            approved_by=user_id if not requires_approval else None,
        )

        if requires_approval:
            return {
                "status": "pending_approval",
                "intent": parsed.intent,
                "confidence": parsed.confidence,
                "proposed_changes": changes,
                "message": self._format_changes_message(parsed, changes),
                "approval_required": True,
            }
        else:
            # Auto-apply safe changes
            result = await self._apply_changes(changes)
            return {
                "status": "applied",
                "intent": parsed.intent,
                "changes": changes,
                "result": result,
            }

    async def _parse_intent(self, text: str) -> Optional[NLCommand]:
        """Parse natural language into structured intent."""

        prompt = f"""Parse this trading bot command into a structured intent.

COMMAND: "{text}"

CONTEXT:
- Bot: Freqtrade on Kraken Canada (CAD markets)
- Pairs: BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD
- Current: Dry-run mode, $1000 CAD, moderate risk
- Strategy: ModerateMultiPairStrategy (EMA/RSI/MACD/BB trend + mean reversion)

AVAILABLE INTENTS:
1. change_risk - Adjust risk level (conservative/moderate/aggressive)
2. change_whitelist - Add/remove trading pairs
3. change_stoploss - Adjust stoploss percentage
4. change_position_size - Adjust stake amount / max open trades
5. pause_resume - Pause or resume trading
6. change_strategy - Switch strategy
7. show_status - Show bot status/performance
8. explain_trade - Explain a specific trade decision
9. optimize_params - Trigger parameter optimization
10. generate_strategy - Request new strategy generation
11. market_analysis - Request market analysis

Return JSON with:
- intent: string (from above)
- parameters: object (extracted parameters)
- confidence: float (0-1)
- original_text: string

Examples:
"make it more conservative" -> {{"intent": "change_risk", "parameters": {{"risk_level": "conservative"}}, "confidence": 0.9}}
"add DOGE/CAD to whitelist" -> {{"intent": "change_whitelist", "parameters": {{"action": "add", "pairs": ["DOGE/CAD"]}}, "confidence": 0.95}}
"why did it sell ETH?" -> {{"intent": "explain_trade", "parameters": {{"pair": "ETH/CAD", "side": "sell"}}, "confidence": 0.9}}"""

        messages = [
            {"role": "system", "content": "You are a trading bot command parser. Extract intent and parameters accurately."},
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
                parameters=result.get("parameters", {}),
                confidence=result.get("confidence", 0.0),
                original_text=text,
            )

        except Exception as e:
            self.logger.error(f"LLM parsing failed, using pattern fallback: {e}")
            return self._fallback_parse(text)

    def _fallback_parse(self, text: str) -> Optional[NLCommand]:
        """Fallback pattern-based parsing."""
        text_lower = text.lower()

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    # Extract basic parameters
                    params = {}
                    if intent == "change_risk":
                        for level in ["conservative", "moderate", "aggressive"]:
                            if level in text_lower:
                                params["risk_level"] = level
                                break
                    elif intent == "change_whitelist":
                        if any(w in text_lower for w in ["add", "include"]):
                            params["action"] = "add"
                        else:
                            params["action"] = "remove"
                        # Extract pair mentions
                        pairs = re.findall(r'([A-Z]{2,5}/CAD)', text.upper())
                        if pairs:
                            params["pairs"] = pairs
                    elif intent == "pause_resume":
                        if any(w in text_lower for w in ["pause", "stop", "halt"]):
                            params["action"] = "pause"
                        else:
                            params["action"] = "resume"

                    return NLCommand(
                        intent=intent,
                        parameters=params,
                        confidence=0.7,
                        original_text=text,
                    )

        return None

    async def _generate_changes(self, parsed: NLCommand) -> List[Dict[str, Any]]:
        """Generate config changes from parsed intent."""
        changes = []

        if parsed.intent == "change_risk":
            risk_level = parsed.parameters.get("risk_level", "moderate")
            changes.extend(self._get_risk_config(risk_level))

        elif parsed.intent == "change_whitelist":
            action = parsed.parameters.get("action", "add")
            pairs = parsed.parameters.get("pairs", [])
            if pairs:
                changes.append({
                    "type": "whitelist",
                    "action": action,
                    "pairs": pairs,
                    "description": f"{action.capitalize()} {', '.join(pairs)} to/from whitelist",
                })

        elif parsed.intent == "change_stoploss":
            # Would need specific value from user
            changes.append({
                "type": "stoploss",
                "action": "modify",
                "description": "Stoploss adjustment requested (needs specific value)",
            })

        elif parsed.intent == "change_position_size":
            changes.append({
                "type": "position_size",
                "action": "modify",
                "description": "Position size adjustment requested (needs specific value)",
            })

        elif parsed.intent == "pause_resume":
            action = parsed.parameters.get("action", "pause")
            changes.append({
                "type": "bot_control",
                "action": action,
                "description": f"{action.capitalize()} trading bot",
            })

        elif parsed.intent == "change_strategy":
            changes.append({
                "type": "strategy",
                "action": "change",
                "description": "Strategy change requested (needs strategy name)",
            })

        elif parsed.intent == "show_status":
            changes.append({
                "type": "query",
                "action": "status",
                "description": "Show bot status and performance",
            })

        elif parsed.intent == "explain_trade":
            pair = parsed.parameters.get("pair")
            side = parsed.parameters.get("side")
            changes.append({
                "type": "query",
                "action": "explain_trade",
                "pair": pair,
                "side": side,
                "description": f"Explain {side} decision for {pair}",
            })

        elif parsed.intent == "optimize_params":
            changes.append({
                "type": "trigger",
                "action": "optimize_params",
                "description": "Trigger parameter optimization",
            })

        elif parsed.intent == "generate_strategy":
            changes.append({
                "type": "trigger",
                "action": "generate_strategy",
                "description": "Trigger strategy generation",
            })

        elif parsed.intent == "market_analysis":
            changes.append({
                "type": "trigger",
                "action": "market_analysis",
                "description": "Trigger market analysis",
            })

        return changes

    def _get_risk_config(self, risk_level: str) -> List[Dict[str, Any]]:
        """Get configuration for risk level."""
        configs = {
            "conservative": [
                {"type": "config", "key": "max_open_trades", "value": 2, "description": "Reduce max open trades to 2"},
                {"type": "config", "key": "stoploss", "value": -0.05, "description": "Tighten stoploss to 5%"},
                {"type": "config", "key": "trailing_stop_positive", "value": 0.015, "description": "Trail at 1.5% profit"},
                {"type": "config", "key": "minimal_roi", "value": {"0": 0.03, "30": 0.015, "60": 0.005, "120": 0}, "description": "Lower profit targets"},
                {"type": "config", "key": "tradable_balance_ratio", "value": 0.80, "description": "Reduce capital at risk to 80%"},
            ],
            "moderate": [
                {"type": "config", "key": "max_open_trades", "value": 3, "description": "Set max open trades to 3"},
                {"type": "config", "key": "stoploss", "value": -0.08, "description": "Set stoploss to 8%"},
                {"type": "config", "key": "trailing_stop_positive", "value": 0.02, "description": "Trail at 2% profit"},
                {"type": "config", "key": "minimal_roi", "value": {"0": 0.04, "30": 0.02, "60": 0.01, "120": 0}, "description": "Standard profit targets"},
                {"type": "config", "key": "tradable_balance_ratio", "value": 0.90, "description": "90% capital at risk"},
            ],
            "aggressive": [
                {"type": "config", "key": "max_open_trades", "value": 4, "description": "Increase max open trades to 4"},
                {"type": "config", "key": "stoploss", "value": -0.12, "description": "Widen stoploss to 12%"},
                {"type": "config", "key": "trailing_stop_positive", "value": 0.03, "description": "Trail at 3% profit"},
                {"type": "config", "key": "minimal_roi", "value": {"0": 0.06, "30": 0.03, "60": 0.015, "120": 0}, "description": "Higher profit targets"},
                {"type": "config", "key": "tradable_balance_ratio", "value": 0.95, "description": "95% capital at risk"},
            ],
        }
        return configs.get(risk_level, configs["moderate"])

    def _requires_approval(self, parsed: NLCommand, changes: List[Dict]) -> bool:
        """Check if changes require approval."""
        if not changes:
            return False

        # Queries don't require approval
        if all(c["type"] == "query" for c in changes):
            return False

        # Check specific change types
        for change in changes:
            change_type = change["type"]
            if change_type in self.require_approval_for:
                return True
            if change_type == "config" and change["key"] in ["stoploss", "max_open_trades", "stake_amount"]:
                return True
            if change_type == "bot_control":
                return True

        return False

    def _format_changes_message(self, parsed: NLCommand, changes: List[Dict]) -> str:
        """Format changes for user approval."""
        lines = [
            f"🤖 **Command**: \"{parsed.original_text}\"",
            f"🎯 **Intent**: {parsed.intent} (confidence: {parsed.confidence:.0%})",
            "",
            "**Proposed Changes:**",
        ]

        for i, change in enumerate(changes, 1):
            lines.append(f"{i}. {change['description']}")

        lines.extend([
            "",
            "⚠️ **Approval required** - Reply 'approve' to apply or 'reject' to cancel.",
        ])

        return "\n".join(lines)

    def _get_suggestions(self) -> List[str]:
        """Get example commands."""
        return [
            '"Switch to conservative mode"',
            '"Add DOGE/CAD to whitelist"',
            '"Why did the bot sell ETH/CAD?"',
            '"Show me the last 10 trades"',
            '"Pause trading for 2 hours"',
            '"Optimize parameters for current market"',
            '"Generate a new strategy for SOL/CAD"',
            '"What\'s the current market regime?"',
        ]

    async def _apply_changes(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply configuration changes to Freqtrade."""
        results = []

        for change in changes:
            try:
                if change["type"] == "config":
                    # Update single config value
                    config_update = {change["key"]: change["value"]}
                    result = await self.freqtrade.update_config(config_update)
                    results.append({"change": change, "result": result, "status": "success"})

                elif change["type"] == "whitelist":
                    if change["action"] == "add":
                        result = await self.freqtrade.add_to_whitelist(change["pairs"])
                    else:
                        result = await self.freqtrade.remove_from_whitelist(change["pairs"])
                    results.append({"change": change, "result": result, "status": "success"})

                elif change["type"] == "bot_control":
                    if change["action"] == "pause":
                        result = await self.freqtrade.pause()
                    else:
                        result = await self.freqtrade.resume()
                    results.append({"change": change, "result": result, "status": "success"})

                elif change["type"] == "trigger":
                    # Trigger plugin runs
                    plugin_name = change["action"].replace("generate_strategy", "strategy_generator")\
                                                   .replace("optimize_params", "param_optimizer")\
                                                   .replace("market_analysis", "market_analyst")
                    await self.orchestrator.run_plugin_now(plugin_name)
                    results.append({"change": change, "status": "triggered"})

                elif change["type"] == "query":
                    # Handle queries
                    if change["action"] == "status":
                        status = await self.freqtrade.status()
                        trades = await self.freqtrade.get_closed_trades(limit=10)
                        results.append({"change": change, "data": {"status": status, "recent_trades": len(trades)}, "status": "success"})
                    elif change["action"] == "explain_trade":
                        # Would need trade lookup
                        results.append({"change": change, "data": {"message": "Trade explanation requires trade ID"}, "status": "partial"})

            except Exception as e:
                results.append({"change": change, "error": str(e), "status": "failed"})

        return {"applied": len([r for r in results if r.get("status") == "success"]), "details": results}

    async def approve_and_apply(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply pre-approved changes."""
        result = await self._apply_changes(changes)

        await self.audit.log(
            plugin="nl_config",
            action="command_approved",
            user_initiated=True,
            input_data={"changes": changes},
            output_data=result,
            decision_reasoning="User approved pending changes",
            risk_level="high",
            approved_by="user",
        )

        return result

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Natural Language Config Plugin shut down")