"""
Plugin Manager for AI Orchestrator

Manages loading, enabling/disabling, and scheduling of AI plugins.
"""

import asyncio
import logging
import importlib
import inspect
from typing import Dict, List, Optional, Any, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin status."""
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    RUNNING = "running"


@dataclass
class PluginConfig:
    """Plugin configuration."""
    name: str
    enabled: bool = True
    schedule: Optional[str] = None  # Cron expression
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher priority runs first
    max_concurrent_runs: int = 1


@dataclass
class PluginInfo:
    """Plugin runtime information."""
    name: str
    status: PluginStatus
    config: PluginConfig
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    is_running: bool = False


class BasePlugin(ABC):
    """
    Base class for all AI plugins.
    """

    def __init__(self, config: PluginConfig, orchestrator: "PluginManager"):
        self.config = config
        self.orchestrator = orchestrator
        self.name = config.name
        self.logger = logging.getLogger(f"plugin.{self.name}")

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize plugin. Return True if successful."""
        pass

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the plugin's main logic."""
        pass

    @abstractmethod
    async def shutdown(self):
        """Cleanup on shutdown."""
        pass

    async def on_config_change(self, new_config: Dict[str, Any]):
        """Handle configuration changes."""
        self.config.config.update(new_config)
        self.logger.info(f"Configuration updated: {new_config}")

    def get_schedule(self) -> Optional[str]:
        """Get cron schedule."""
        return self.config.schedule

    def is_enabled(self) -> bool:
        return self.config.enabled


class PluginManager:
    """
    Manages plugin lifecycle, scheduling, and execution.
    """

    def __init__(
        self,
        openrouter_client,
        freqtrade_client,
        audit_logger,
        config: Dict[str, Any],
    ):
        self.openrouter_client = openrouter_client
        self.freqtrade_client = freqtrade_client
        self.audit_logger = audit_logger
        self.config = config

        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_info: Dict[str, PluginInfo] = {}
        self.plugin_classes: Dict[str, Type[BasePlugin]] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        self._plugin_lock = asyncio.Lock()

        # Built-in plugin mapping
        self._builtin_plugins = {
            "strategy_generator": "ai_orchestrator.plugins.strategy_generator.StrategyGeneratorPlugin",
            "market_analyst": "ai_orchestrator.plugins.market_analyst.MarketAnalystPlugin",
            "param_optimizer": "ai_orchestrator.plugins.param_optimizer.ParamOptimizerPlugin",
            "nl_config": "ai_orchestrator.plugins.nl_config.NLConfigPlugin",
            "autonomous_agent": "ai_orchestrator.plugins.autonomous_agent.AutonomousAgentPlugin",
        }

    async def initialize(self) -> bool:
        """Initialize all configured plugins."""
        plugin_configs = self.config.get("plugins", {})

        for plugin_name, plugin_config in plugin_configs.items():
            try:
                await self._load_plugin(plugin_name, plugin_config)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
                self.plugin_info[plugin_name] = PluginInfo(
                    name=plugin_name,
                    status=PluginStatus.ERROR,
                    config=PluginConfig(name=plugin_name),
                    last_error=str(e),
                )

        # Verify audit logger integrity
        integrity = self.audit_logger.verify_integrity()
        if not integrity["valid"]:
            logger.warning("Audit log integrity check failed!")

        return True

    async def _load_plugin(self, name: str, config_dict: Dict[str, Any]):
        """Load a single plugin."""
        plugin_config = PluginConfig(
            name=name,
            enabled=config_dict.get("enabled", True),
            schedule=config_dict.get("schedule"),
            config=config_dict.get("config", {}),
            priority=config_dict.get("priority", 0),
            max_concurrent_runs=config_dict.get("max_concurrent_runs", 1),
        )

        # Get plugin class
        if name in self._builtin_plugins:
            class_path = self._builtin_plugins[name]
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
        else:
            # Custom plugin - try to import from plugins directory
            raise ValueError(f"Unknown plugin: {name}")

        # Instantiate plugin
        plugin = plugin_class(plugin_config, self)
        success = await plugin.initialize()

        if success:
            self.plugins[name] = plugin
            self.plugin_info[name] = PluginInfo(
                name=name,
                status=PluginStatus.ENABLED if plugin_config.enabled else PluginStatus.DISABLED,
                config=plugin_config,
            )
            logger.info(f"Plugin {name} loaded successfully")
        else:
            self.plugin_info[name] = PluginInfo(
                name=name,
                status=PluginStatus.ERROR,
                config=plugin_config,
                last_error="Initialization failed",
            )
            logger.error(f"Plugin {name} initialization failed")

    async def start_scheduler(self):
        """Start the plugin scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Plugin scheduler started")

    async def stop_scheduler(self):
        """Stop the plugin scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Plugin scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(60)  # Check every minute

    async def _check_schedules(self):
        """Check and run scheduled plugins."""
        now = datetime.utcnow()

        for name, info in self.plugin_info.items():
            if info.status != PluginStatus.ENABLED:
                continue

            plugin = self.plugins.get(name)
            if not plugin:
                continue

            schedule = plugin.get_schedule()
            if not schedule:
                continue

            # Simple cron parsing (minute hour day month weekday)
            if self._should_run(schedule, now, info.last_run):
                if not info.is_running:
                    asyncio.create_task(self._run_plugin(name))

    def _should_run(self, schedule: str, now: datetime, last_run: Optional[datetime]) -> bool:
        """Check if plugin should run based on cron schedule."""
        # Simple cron: "minute hour * * *"
        parts = schedule.split()
        if len(parts) != 5:
            return False

        minute_spec, hour_spec = parts[0], parts[1]

        # Check minute
        if minute_spec != "*" and int(minute_spec) != now.minute:
            return False

        # Check hour
        if hour_spec != "*" and int(hour_spec) != now.hour:
            return False

        # Check if already run this minute
        if last_run and last_run.minute == now.minute and last_run.hour == now.hour:
            return False

        return True

    async def _run_plugin(self, name: str):
        """Run a plugin with error handling."""
        plugin = self.plugins.get(name)
        info = self.plugin_info.get(name)

        if not plugin or not info:
            return

        if info.is_running:
            logger.warning(f"Plugin {name} already running, skipping")
            return

        info.is_running = True
        info.status = PluginStatus.RUNNING
        start_time = datetime.utcnow()

        try:
            result = await plugin.run()
            info.last_run = start_time
            info.run_count += 1
            info.status = PluginStatus.ENABLED
            info.last_error = None
            logger.info(f"Plugin {name} completed successfully")

            # Log to audit
            await self.audit_logger.log(
                plugin=name,
                action="scheduled_run",
                user_initiated=False,
                input_data={"trigger": "scheduler"},
                output_data=result,
                decision_reasoning="Scheduled execution",
                risk_level="low",
            )

        except Exception as e:
            info.error_count += 1
            info.last_error = str(e)
            info.status = PluginStatus.ERROR
            logger.error(f"Plugin {name} failed: {e}")

            await self.audit_logger.log(
                plugin=name,
                action="scheduled_run_failed",
                user_initiated=False,
                input_data={"trigger": "scheduler"},
                output_data={"error": str(e)},
                decision_reasoning=f"Execution failed: {e}",
                risk_level="medium",
            )

        finally:
            info.is_running = False
            info.next_run = self._calculate_next_run(plugin.get_schedule())

    def _calculate_next_run(self, schedule: Optional[str]) -> Optional[datetime]:
        """Calculate next run time (simplified)."""
        if not schedule:
            return None
        # Simplified - just next hour
        now = datetime.utcnow()
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    async def run_plugin_now(self, name: str, **kwargs) -> Dict[str, Any]:
        """Manually trigger a plugin run."""
        plugin = self.plugins.get(name)
        info = self.plugin_info.get(name)

        if not plugin or not info:
            raise ValueError(f"Plugin {name} not found")

        if info.is_running:
            raise ValueError(f"Plugin {name} is already running")

        info.is_running = True
        info.status = PluginStatus.RUNNING

        try:
            result = await plugin.run(**kwargs)
            info.last_run = datetime.utcnow()
            info.run_count += 1
            info.status = PluginStatus.ENABLED
            info.last_error = None
            return result
        except Exception as e:
            info.error_count += 1
            info.last_error = str(e)
            info.status = PluginStatus.ERROR
            raise
        finally:
            info.is_running = False

    async def enable_plugin(self, name: str):
        """Enable a plugin."""
        info = self.plugin_info.get(name)
        if info:
            info.status = PluginStatus.ENABLED
            info.config.enabled = True
            logger.info(f"Plugin {name} enabled")

    async def disable_plugin(self, name: str):
        """Disable a plugin."""
        info = self.plugin_info.get(name)
        if info:
            info.status = PluginStatus.DISABLED
            info.config.enabled = False
            logger.info(f"Plugin {name} disabled")

    async def update_plugin_config(self, name: str, config: Dict[str, Any]):
        """Update plugin configuration."""
        plugin = self.plugins.get(name)
        info = self.plugin_info.get(name)

        if not plugin or not info:
            raise ValueError(f"Plugin {name} not found")

        # Log config change
        await self.audit_logger.log_config_change(
            plugin=name,
            config_changes=config,
            reasoning="Configuration updated via API",
            user_initiated=True,
        )

        # Update config
        info.config.config.update(config)
        await plugin.on_config_change(config)

    def get_plugin_status(self, name: str) -> Optional[PluginInfo]:
        """Get plugin status."""
        return self.plugin_info.get(name)

    def get_all_status(self) -> Dict[str, PluginInfo]:
        """Get all plugin statuses."""
        return self.plugin_info

    async def shutdown(self):
        """Shutdown all plugins."""
        await self.stop_scheduler()

        for name, plugin in self.plugins.items():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")

        logger.info("All plugins shut down")