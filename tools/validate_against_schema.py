#!/usr/bin/env python3
"""
Validate a freqtrade config against freqtrade's OWN JSON schema.

Freqtrade builds a JSON schema in freqtrade/config_schema/config_schema.py and
validates the merged configuration against it during startup. If the config
fails, the bot refuses to start.

This script imports that exact schema from a freqtrade source checkout and runs
the same validation locally, so a bad config is caught before a deploy instead
of after.

The schema only uses a small subset of JSON Schema: type, properties, required,
enum, minimum, maximum, exclusiveMaximum, items, uniqueItems, $ref, pattern,
patternProperties, additionalProperties, minItems, minLength, const, format.
There is no oneOf/anyOf/allOf/if-then-else, so a small validator is sufficient
and no third-party package is needed.

Usage:
    python3 tools/validate_against_schema.py \
        --freqtrade-src /path/to/freqtrade-2026.8 \
        --config-dir config
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight_config import deep_merge, load_config  # noqa: E402


# --------------------------------------------------------------------------
# Minimal JSON Schema validator covering the keywords freqtrade's schema uses.
# --------------------------------------------------------------------------

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
    "null": type(None),
}


def type_name(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def check_type(value, expected) -> bool:
    """JSON Schema `type`. Booleans are NOT integers here, which matters for
    keys like dry_run if someone writes 1 instead of true."""
    types = expected if isinstance(expected, list) else [expected]
    for t in types:
        if t == "integer":
            if isinstance(value, int) and not isinstance(value, bool):
                return True
        elif t == "number":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return True
        elif t == "boolean":
            if isinstance(value, bool):
                return True
        elif t == "object":
            if isinstance(value, dict):
                return True
        elif t == "array":
            if isinstance(value, list):
                return True
        elif t == "string":
            if isinstance(value, str):
                return True
        elif t == "null":
            if value is None:
                return True
    return False


class Validator:
    def __init__(self, root_schema: dict):
        self.root = root_schema
        self.errors: list[str] = []

    def resolve(self, schema: dict) -> dict:
        """Resolve a local $ref against #/definitions/..."""
        seen = 0
        while isinstance(schema, dict) and "$ref" in schema:
            ref = schema["$ref"]
            if not ref.startswith("#/"):
                return schema
            node = self.root
            for part in ref[2:].split("/"):
                node = node.get(part, {})
            schema = node
            seen += 1
            if seen > 10:
                return schema
        return schema

    def validate(self, value, schema: dict, path: str = "") -> None:
        schema = self.resolve(schema)
        if not isinstance(schema, dict):
            return
        where = path or "<root>"

        # const
        if "const" in schema and value != schema["const"]:
            self.errors.append(
                "%s: must be %r, got %r" % (where, schema["const"], value)
            )

        # type
        if "type" in schema and not check_type(value, schema["type"]):
            self.errors.append(
                "%s: expected type %s, got %s (%r)"
                % (where, schema["type"], type_name(value), value)
            )
            return  # further checks are meaningless

        # enum
        if "enum" in schema and value not in schema["enum"]:
            self.errors.append(
                "%s: %r is not one of %s" % (where, value, schema["enum"])
            )

        # numeric bounds
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                self.errors.append(
                    "%s: %r is below minimum %r" % (where, value, schema["minimum"])
                )
            if "maximum" in schema:
                # In JSON Schema draft-04 (which freqtrade uses), exclusiveMaximum
                # is a BOOLEAN modifier on maximum, not a bound of its own.
                # freqtrade uses both forms: stoploss has maximum=0 with
                # exclusiveMaximum=True (strictly below 0), while price_last_balance
                # has maximum=1 with exclusiveMaximum=False (1 is allowed).
                limit = schema["maximum"]
                if schema.get("exclusiveMaximum"):
                    if value >= limit:
                        self.errors.append(
                            "%s: %r must be below %r (exclusiveMaximum)"
                            % (where, value, limit)
                        )
                elif value > limit:
                    self.errors.append(
                        "%s: %r is above maximum %r" % (where, value, limit)
                    )
            if "exclusiveMinimum" in schema and isinstance(
                schema["exclusiveMinimum"], (int, float)
            ):
                if value <= schema["exclusiveMinimum"]:
                    self.errors.append(
                        "%s: %r must be above %r"
                        % (where, value, schema["exclusiveMinimum"])
                    )

        # strings
        if isinstance(value, str):
            if "pattern" in schema:
                if re.search(schema["pattern"], value) is None:
                    self.errors.append(
                        "%s: %r does not match pattern %r"
                        % (where, value, schema["pattern"])
                    )
            if "minLength" in schema and len(value) < schema["minLength"]:
                self.errors.append(
                    "%s: %r is shorter than minLength %d"
                    % (where, value, schema["minLength"])
                )

        # objects
        if isinstance(value, dict):
            for key in schema.get("required", []):
                if key not in value:
                    self.errors.append("%s: missing required property %r" % (where, key))
            props = schema.get("properties", {})
            pattern_props = schema.get("patternProperties", {})
            additional = schema.get("additionalProperties", True)
            for key, sub in value.items():
                child = "%s.%s" % (where, key) if where != "<root>" else key
                matched = False
                if key in props:
                    self.validate(sub, props[key], child)
                    matched = True
                for pat, pschema in pattern_props.items():
                    if re.search(pat, key):
                        self.validate(sub, pschema, child)
                        matched = True
                if not matched:
                    if additional is False:
                        self.errors.append("%s: unexpected property %r" % (where, key))
                    elif isinstance(additional, dict):
                        self.validate(sub, additional, child)

        # arrays
        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                self.errors.append(
                    "%s: needs at least %d items, got %d"
                    % (where, schema["minItems"], len(value))
                )
            if schema.get("uniqueItems"):
                seen = []
                for item in value:
                    if item in seen:
                        self.errors.append("%s: duplicate item %r" % (where, item))
                    seen.append(item)
            if "items" in schema:
                for i, item in enumerate(value):
                    self.validate(item, schema["items"], "%s[%d]" % (where, i))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freqtrade-src", required=True, type=Path)
    parser.add_argument("--config-dir", default="config", type=Path)
    args = parser.parse_args()

    src = args.freqtrade_src.resolve()
    if not (src / "freqtrade" / "config_schema").is_dir():
        print("ERROR: %s is not a freqtrade source checkout" % src)
        return 2

    sys.path.insert(0, str(src))
    try:
        from freqtrade.config_schema import CONF_SCHEMA  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        print("ERROR: could not import CONF_SCHEMA from %s: %s" % (src, exc))
        return 2

    version = "unknown"
    try:
        init = (src / "freqtrade" / "__init__.py").read_text()
        match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
        if match:
            version = match.group(1)
    except Exception:  # noqa: BLE001
        pass

    config: dict = {}
    for name in ("base.json", "canada_kraken.json"):
        path = args.config_dir / name
        if not path.exists():
            print("ERROR: missing %s" % path)
            return 2
        deep_merge(load_config(path), config)

    # Stand in for the runtime-generated private config. This MUST mirror what
    # config/freqtrade-entrypoint.sh actually writes, or the validation proves
    # nothing: jwt_secret_key and ws_token belong inside api_server, and
    # jwt_secret_key must satisfy the schema's minLength of 32.
    deep_merge(
        {
            "exchange": {"key": "x" * 32, "secret": "x" * 32},
            "api_server": {
                "username": "freqtrade",
                "password": "x" * 32,
                "jwt_secret_key": "x" * 47,
                "ws_token": "x" * 32,
            },
            "discord": {"webhook_url": "https://example.invalid/x"},
        },
        config,
    )

    # freqtrade stores the merged file list here; the schema expects it.
    config.setdefault("config_files", ["base.json", "canada_kraken.json"])

    validator = Validator(CONF_SCHEMA)
    validator.validate(config, CONF_SCHEMA)

    print("Validating against freqtrade %s CONF_SCHEMA" % version)
    print("  schema properties: %d" % len(CONF_SCHEMA.get("properties", {})))
    print()

    if validator.errors:
        for error in validator.errors:
            print("  ERROR %s" % error)
        print()
        print("FAILED: %d schema violation(s)" % len(validator.errors))
        return 1

    print("PASSED: config satisfies freqtrade's own JSON schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())