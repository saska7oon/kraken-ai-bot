#!/usr/bin/env python3
"""
Preflight check for the freqtrade configuration.

WHY THIS EXISTS
---------------
Freqtrade reads several config keys with direct subscription rather than
``.get()``:

    self.validate_pricing(config["exit_pricing"])          # exchange.py
    pos_adjust = "On" if config["position_adjustment_enable"] else "Off"

A missing key is therefore not a warning, it is a ``KeyError`` that aborts
startup. Worse, these failures happen at different points: ``exit_pricing`` is
read while constructing the exchange, ``position_adjustment_enable`` while the
RPC manager sends its startup message. Each one costs a full deploy-and-redeploy
cycle on real hardware to discover.

This script merges the config files exactly the way freqtrade does and checks
every key that is known to be read directly during ``freqtrade trade``.

It is a MIRROR of freqtrade's rules, not the rules themselves, so it can drift
when freqtrade changes. It is a fast local guard, not a substitute for the real
thing. The authoritative sources are:

  freqtrade/config_schema/config_schema.py   SCHEMA_TRADE_REQUIRED
  freqtrade/configuration/deprecated_settings.py
  freqtrade/configuration/config_validation.py

Usage:
    python3 tools/preflight_config.py [--config-dir config]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- Required for `freqtrade trade` ---------------------------------------
# Source: SCHEMA_TRADE_REQUIRED, freqtrade/config_schema/config_schema.py
SCHEMA_TRADE_REQUIRED = [
    "exchange",
    "timeframe",
    "max_open_trades",
    "stake_currency",
    "stake_amount",
    "tradable_balance_ratio",
    "last_stake_amount_min_ratio",
    "dry_run",
    "dry_run_wallet",
    "exit_pricing",
    "entry_pricing",
    "stoploss",
    "minimal_roi",
    "pairlists",
    "internals",
    "dataformat_ohlcv",
    "dataformat_trades",
]

# --- Keys read with direct subscription on the trade startup path ----------
# Each of these is a KeyError if absent. The file and reason are recorded so
# the failure mode is obvious if this list is ever questioned.
UNGUARDED_STARTUP_KEYS = {
    "dry_run": "exchange.py / rpc_manager.py",
    "stake_currency": "exchange.py validate_config, rpc_manager.py",
    "stake_amount": "rpc_manager.py startup_messages",
    "minimal_roi": "rpc_manager.py startup_messages",
    "stoploss": "rpc_manager.py startup_messages",
    "trailing_stop": "rpc_manager.py startup_messages",
    "timeframe": "worker.py, rpc_manager.py",
    "position_adjustment_enable": "rpc_manager.py startup_messages",
    "db_url": "freqtradebot.py",
    "max_open_trades": "freqtradebot.py",
    "exchange": "exchange.py validate_config",
}

# --- Sub-keys the schema marks as required inside their section ------------
NESTED_REQUIRED = {
    "entry_pricing": ["price_side"],
    "exit_pricing": ["price_side"],
}

# --- Settings freqtrade rejects outright -----------------------------------
# Source: deprecated_settings.py — these RAISE, they do not warn.
FORBIDDEN_TOP_LEVEL = {
    "protections": "protections belong in the strategy as a @property",
    "ticker_interval": "use 'timeframe' instead",
}
FORBIDDEN_IN_SECTION = {
    ("experimental", "use_sell_signal"): "use 'use_exit_signal'",
    ("experimental", "sell_profit_only"): "use 'exit_profit_only'",
    ("experimental", "ignore_roi_if_buy_signal"): "use 'ignore_roi_if_entry_signal'",
    ("ask_strategy", "use_sell_signal"): "use 'use_exit_signal'",
    ("ask_strategy", "sell_profit_only"): "use 'exit_profit_only'",
    ("ask_strategy", "sell_profit_offset"): "use 'exit_profit_offset'",
    ("ask_strategy", "ignore_roi_if_buy_signal"): "use 'ignore_roi_if_entry_signal'",
}
# Edge was removed in 2025.6; any ENABLED edge block is a hard error.
REMOVED_FEATURES = ["edge"]


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas.

    Mirrors rapidjson with PM_COMMENTS | PM_TRAILING_COMMAS, which is how
    freqtrade parses config files. Comment detection is string-aware, so a //
    inside a quoted value is left alone.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_config(path: Path) -> dict:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return json.loads(strip_jsonc(raw.decode("utf-8")))


def deep_merge(source: dict, destination: dict) -> dict:
    """Faithful reimplementation of freqtrade.misc.deep_merge_dicts.

    Non-dict values (including lists) REPLACE, they do not concatenate. This is
    why the Canada whitelist of four pairs fully overrides the base whitelist
    rather than appending to it.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            deep_merge(value, destination.setdefault(key, {}))
        else:
            destination[key] = value
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", default="config", type=Path)
    args = parser.parse_args()

    base = args.config_dir / "base.json"
    canada = args.config_dir / "canada_kraken.json"

    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    for path in (base, canada):
        if not path.exists():
            print("ERROR: missing config file: %s" % path)
            return 1

    config: dict = {}
    try:
        for path in (base, canada):
            deep_merge(load_config(path), config)
    except Exception as exc:  # noqa: BLE001 - report any parse failure plainly
        print("ERROR: could not parse config: %s" % exc)
        return 1

    # The private config is generated at runtime; merge a stand-in so the
    # credential-dependent keys are present, exactly as freqtrade will see them.
    # Must mirror config/freqtrade-entrypoint.sh exactly, or this proves nothing.
    deep_merge(
        {
            "exchange": {"key": "x" * 32, "secret": "x" * 32},
            "api_server": {
                "username": "freqtrade",
                "password": "x" * 32,
                "jwt_secret_key": "x" * 47,   # schema requires minLength 32
                "ws_token": "x" * 32,
            },
            "discord": {"webhook_url": "https://example.invalid/x"},
        },
        config,
    )

    # --- required keys ----------------------------------------------------
    for key in SCHEMA_TRADE_REQUIRED:
        if key not in config:
            errors.append(
                "missing required key %r (SCHEMA_TRADE_REQUIRED)" % key
            )

    # --- unguarded startup reads -----------------------------------------
    for key, where in UNGUARDED_STARTUP_KEYS.items():
        if key not in config:
            errors.append(
                "missing key %r - read directly in %s, so this is a KeyError"
                % (key, where)
            )

    # --- nested required --------------------------------------------------
    for section, keys in NESTED_REQUIRED.items():
        for key in keys:
            if key not in config.get(section, {}):
                errors.append("missing %s.%s (required by schema)" % (section, key))

    # --- forbidden settings ----------------------------------------------
    for key, reason in FORBIDDEN_TOP_LEVEL.items():
        if key in config:
            errors.append(
                "forbidden key %r in config - freqtrade raises on this: %s"
                % (key, reason)
            )

    for (section, key), reason in FORBIDDEN_IN_SECTION.items():
        if key in config.get(section, {}):
            errors.append(
                "removed setting %s.%s still present - %s" % (section, key, reason)
            )

    for feature in REMOVED_FEATURES:
        if config.get(feature, {}).get("enabled"):
            errors.append(
                "%r is enabled but the feature was removed from freqtrade" % feature
            )

    # --- api_server shape -------------------------------------------------
    # jwt_secret_key and ws_token belong INSIDE api_server. freqtrade reads them
    # from there (api_auth.py) and the schema requires jwt_secret_key there.
    api = config.get("api_server", {})
    for key in ("jwt_secret_key", "ws_token"):
        if key not in api:
            errors.append(
                "api_server.%s missing - the entrypoint must write it inside "
                "api_server, not at the top level" % key
            )
    if len(api.get("jwt_secret_key", "")) < 32:
        errors.append(
            "api_server.jwt_secret_key is shorter than 32 characters - the schema "
            "sets minLength 32, so startup would fail"
        )

    # --- telegram ---------------------------------------------------------
    # A telegram block is only valid WITH token and chat_id. Including one just
    # to say "disabled" fails validation.
    if "telegram" in config:
        for key in ("enabled", "token", "chat_id"):
            if key not in config["telegram"]:
                errors.append(
                    "telegram block is missing %r - the schema requires enabled, "
                    "token and chat_id together, so omit the block entirely to "
                    "disable Telegram" % key
                )

    # --- discord message types must be lists of field templates -----------
    # freqtrade does `for f in fields: for k, v in f.items()`, and the schema
    # declares these as arrays, so a boolean is both a validation failure and a
    # TypeError at runtime.
    MESSAGE_TYPES = {
        "status", "warning", "exception", "startup", "entry", "entry_fill",
        "entry_cancel", "exit", "exit_fill", "exit_cancel", "protection_trigger",
        "protection_trigger_global", "strategy_msg", "whitelist", "analyzed_df",
        "new_candle",
    }
    for key, value in config.get("discord", {}).items():
        if key in ("enabled", "webhook_url"):
            continue
        if key in MESSAGE_TYPES and not isinstance(value, list):
            errors.append(
                "discord.%s must be a list of field templates, not %s - freqtrade "
                "iterates it and the schema requires an array"
                % (key, type(value).__name__)
            )
        elif key not in MESSAGE_TYPES:
            warnings.append(
                "discord.%s is not a known RPCMessageType, so it will never fire"
                % key
            )

    # --- safety sanity checks --------------------------------------------
    if config.get("dry_run") is not True:
        warnings.append("dry_run is not true - this would place real orders")

    if not config.get("exchange", {}).get("pair_whitelist"):
        errors.append("exchange.pair_whitelist is empty")

    # discord.* is injected by the entrypoint from the Swarm secret, so it is
    # absent from the config files by design. Only note it; do not alarm.
    if config.get("discord", {}).get("enabled") and not config["discord"].get(
        "webhook_url"
    ):
        infos.append(
            "discord.enabled is true; webhook_url comes from the discord_webhook "
            "Swarm secret at runtime, and the entrypoint disables Discord if that "
            "secret is absent (Discord.__init__ reads it unguarded)"
        )

    if "protections" in config:
        errors.append("protections must be a @property on the strategy, not config")
    else:
        infos.append("protections are defined in the strategy (expected)")

    # --- report -----------------------------------------------------------
    print("freqtrade config preflight")
    print("  merged %s + %s" % (base.name, canada.name))
    print("  dry_run:          %s" % config.get("dry_run"))
    print("  stake_currency:   %s" % config.get("stake_currency"))
    print(
        "  whitelist:        %s"
        % ", ".join(config.get("exchange", {}).get("pair_whitelist", []))
    )
    print("  timeframe:        %s" % config.get("timeframe"))
    print(
        "  entry/exit price: %s / %s"
        % (
            config.get("entry_pricing", {}).get("price_side"),
            config.get("exit_pricing", {}).get("price_side"),
        )
    )
    print()

    for info in infos:
        print("  info  %s" % info)
    for warning in warnings:
        print("  WARN  %s" % warning)
    for error in errors:
        print("  ERROR %s" % error)

    print()
    if errors:
        print("FAILED: %d error(s) - freqtrade would not start" % len(errors))
        return 1
    print("PASSED: no blocking config errors found")
    return 0


if __name__ == "__main__":
    sys.exit(main())