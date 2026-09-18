#!/usr/bin/env python3
"""Check that a risk level means the same thing everywhere it can be chosen.

There are two ways to pick a risk level, and they used to disagree:

  * the settings panel - "Conservative / Moderate / Aggressive" buttons;
  * the assistant - "make it more conservative".

Each had its own table of numbers. They had drifted apart on seven values. The
one that matters most:

    conservative -> tradable_balance_ratio
        assistant said 0.80        ("Use at most 80% of the wallet")
        panel said     0.50

Same word, 60% more capital at risk, depending on whether the operator typed it
or clicked it. Nothing caught this because nothing compared the two tables.

This test compares them. Concretely it asserts:

  * there is exactly ONE definition of the presets, in settings_store;
  * every value in a preset is inside that setting's declared bounds - a preset
    that proposes a value the validator would reject fails at the worst moment,
    after the operator has said yes;
  * the assistant builds its proposal from that same definition rather than
    carrying a second copy;
  * the plain-language description is derived from the value, so it cannot
    describe a number other than the one being set;
  * conservative is genuinely no riskier than moderate, and moderate no riskier
    than aggressive, on each shared axis. Ordering is the entire meaning of these
    names: a "Conservative" that risks more than "Aggressive" would be worse than
    a broken number, because it would look correct.

nl_config imports aiohttp, which is absent in some environments, so the parts
that need it are read with ast rather than imported. No dependency is stubbed,
because a stub would let a broken import pass.
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

NL_CONFIG = REPO / "ai_orchestrator" / "plugins" / "nl_config.py"


def _load_settings_store():
    """Import settings_store by path, so a broken import is reported clearly."""
    from ai_orchestrator.core import settings_store
    return settings_store


def _bounds(store) -> dict:
    """Per-setting (min, max) from the EDITABLE allowlist."""
    out = {}
    for s in store.EDITABLE:
        out[s.key] = (getattr(s, "minimum", None), getattr(s, "maximum", None))
    return out


def _preset_literal_in_nl_config() -> bool:
    """Does nl_config still carry its own copy of the risk numbers?

    A second copy is the defect. If one reappears this fails, whatever its
    values happen to be - agreement by coincidence today is drift tomorrow.
    """
    tree = ast.parse(NL_CONFIG.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        # A dict literal with a key "conservative" whose value contains the
        # numbers a preset would hold.
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
        if "conservative" in keys and "aggressive" in keys:
            return True
    return False


def _uses_shared_presets() -> bool:
    """Is RISK_PRESETS referenced in nl_config?"""
    src = NL_CONFIG.read_text(encoding="utf-8")
    return "RISK_PRESETS" in src


def _describe_fn():
    """Extract and compile _describe_risk_value without importing the module."""
    tree = ast.parse(NL_CONFIG.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_describe_risk_value":
            mod = ast.Module(body=[node], type_ignores=[])
            ns: dict = {}
            exec(compile(ast.fix_missing_locations(mod), "<nl_config>", "exec"), ns)
            return ns["_describe_risk_value"]
    return None


def main() -> int:
    store = _load_settings_store()
    presets = store.RISK_PRESETS
    bounds = _bounds(store)
    describe = _describe_fn()
    failures = []

    print(f"Risk levels: {list(presets)}")
    print()

    # ---- 1. exactly one definition -------------------------------------
    print("Single definition:")
    if _preset_literal_in_nl_config():
        failures.append("nl_config carries its own copy of the risk presets again")
        print("  FAIL  nl_config.py contains a second risk-preset table")
    else:
        print("  ok    no second table in nl_config.py")
    if not _uses_shared_presets():
        failures.append("nl_config does not reference RISK_PRESETS")
        print("  FAIL  nl_config.py never references RISK_PRESETS")
    else:
        print("  ok    nl_config.py builds from settings_store.RISK_PRESETS")

    # ---- 2. the description helper exists ------------------------------
    print()
    print("Descriptions derived from values:")
    if describe is None:
        failures.append("_describe_risk_value not found in nl_config.py")
        print("  FAIL  _describe_risk_value missing")
    else:
        print("  ok    _describe_risk_value found")

    # ---- 3. every value is inside bounds -------------------------------
    print()
    print("Values inside their declared bounds:")
    for level, preset in sorted(presets.items()):
        for key, value in sorted(preset["values"].items()):
            lo, hi = bounds.get(key, (None, None))
            if lo is None and hi is None and key not in bounds:
                failures.append(f"{level}.{key} is not an editable setting")
                print(f"  FAIL  {level:13} {key:24} {value}   not an editable setting")
                continue
            bad = (lo is not None and value < lo) or (hi is not None and value > hi)
            if bad:
                failures.append(f"{level}.{key}={value} outside [{lo}, {hi}]")
                print(f"  FAIL  {level:13} {key:24} {value}   outside [{lo}, {hi}]")
            else:
                print(f"  ok    {level:13} {key:24} {value}   within [{lo}, {hi}]")

    # ---- 4. descriptions match the values ------------------------------
    if describe is not None:
        print()
        print("Descriptions say what the value is:")
        for level, preset in sorted(presets.items()):
            for key, value in sorted(preset["values"].items()):
                text = describe(key, value)
                # The number in the prose must be the number being set.
                if key == "stoploss":
                    want = f"{abs(value) * 100:.0f}%"
                elif key == "tradable_balance_ratio":
                    want = f"{value * 100:.0f}%"
                elif key == "trailing_stop_positive":
                    want = f"{value * 100:.1f}%"
                elif key == "max_open_trades":
                    want = str(value)
                else:
                    want = str(value)
                if want not in text:
                    failures.append(f"{level}.{key}={value} described as {text!r}")
                    print(f"  FAIL  {level:13} {key:24} {value} -> {text!r} (no {want})")
                else:
                    print(f"  ok    {level:13} {key:24} {value} -> {text!r}")

    # ---- 5. ordering: conservative must not risk more -------------------
    # Ordering IS the meaning of these names. A "Conservative" that uses more of
    # the wallet than "Aggressive" is worse than a wrong number, because it looks
    # right.
    print()
    print("Ordering (a more cautious name must not risk more):")
    order = ["conservative", "moderate", "aggressive"]
    present = [lvl for lvl in order if lvl in presets]
    for a, b in zip(present, present[1:]):
        for key in ("tradable_balance_ratio", "max_open_trades"):
            va = presets[a]["values"].get(key)
            vb = presets[b]["values"].get(key)
            if va is None or vb is None:
                continue
            if va > vb:
                failures.append(f"{a}.{key}={va} exceeds {b}.{key}={vb}")
                print(f"  FAIL  {a}({va}) > {b}({vb}) for {key}")
            else:
                print(f"  ok    {a}({va}) <= {b}({vb}) for {key}")
        # Stoploss is negative; a more cautious level must not lose MORE, so its
        # value must be the greater (closer to zero).
        sa = presets[a]["values"].get("stoploss")
        sb = presets[b]["values"].get("stoploss")
        if sa is not None and sb is not None:
            if sa < sb:
                failures.append(f"{a}.stoploss={sa} is looser than {b}.stoploss={sb}")
                print(f"  FAIL  {a}({sa}) loses more than {b}({sb})")
            else:
                print(f"  ok    {a}({sa}) no looser than {b}({sb})")

    print()
    print("=" * 68)
    if failures:
        print(f"FAILED - {len(failures)} problem(s)")
        for f in failures:
            print(f"   - {f}")
        return 1
    print("PASSED - a risk level means the same thing everywhere it can be chosen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
