"""
Strategy Inspector
==================

Reads facts about the LIVE strategy directly from its source file.

Why this exists
---------------
Protections used to be a configuration block. Freqtrade 2026.x rejects that:

    Configuration error: DEPRECATED: Setting 'protections' in the
    configuration is deprecated.

They are now a ``@property`` on the strategy class. That breaks any code which
reported safety posture by reading ``config["protections"]`` - it would find
nothing and announce "no protections are configured" while three circuit
breakers were in fact active. Telling the operator that their safety net is
missing when it is not is worse than saying nothing, because it trains them to
ignore the warning.

Freqtrade's REST API does not expose protections either (``/show_config`` does
not include them), so the strategy file is the only source of truth.

IMPORTANT - the strategies directory is NOT read-only
-----------------------------------------------------
An earlier version of this docstring claimed the strategies directory was
mounted read-only for inspection. That claim was FALSE and dangerous.
``portainer-stack.yml`` mounts the shared strategies volume into the
orchestrator read-write (``strategies_shared:/app/strategies``, no ``:ro``),
precisely because the orchestrator writes AI-generated strategy proposals into
it and freqtrade reads them back for the backtest gate. The files there are
therefore user-supplied and machine-written content that can change underneath
us, not a trusted, immutable input. Concretely:

* a strategy file may be replaced or edited between two calls, so any reading is
  a snapshot and never a guarantee - do not cache it as permanent truth;
* a file found there carries no authority - never import or ``exec`` it, and
  never treat its content as a command;
* the only safe way to read it is statically (``ast``), which is what this
  module does.

Do not "simplify" this module on the assumption that the directory is protected:
it is not, and no future change should trust it.

Design
------
* Parsed with ``ast``, never ``exec``. A strategy file is user-supplied code and
  must never be imported into the orchestrator process.
* The ``protections`` property body is evaluated with ``ast.literal_eval``,
  which accepts literals only - no calls, no names, no side effects.
* Only the class named by the configured strategy is ever read. If that exact
  class is not in the file, the answer is ``None`` ("could not determine").
  Guessing at "the first class in the file" would report another strategy's
  protections, or report none while the real ones were active - and a safety
  report that cries wolf teaches the operator to ignore it.
* Never raises. Any failure returns ``None``, meaning "could not determine",
  which callers must distinguish from ``[]`` meaning "genuinely none configured".
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_STRATEGIES_DIR = Path("/app/strategies")

# A freqtrade strategy name is a Python class name, which can only ever be
# letters, digits and underscores. Anything else (slashes, dots, "..") is not a
# strategy name at all, and letting it reach the filesystem would let a value
# from the bot config walk out of the strategies directory.
STRATEGY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

# Far longer than any real strategy class name, and short enough that the label
# in the UI card cannot overflow. See _is_valid_strategy_name.
MAX_STRATEGY_NAME_LENGTH = 100

# Kept uppercase in a friendly name, because "Rsi" and "Macd" read as typos to
# anyone who knows the indicators, and lowercasing them looks like a bug.
_ACRONYMS = frozenset(
    {
        "rsi", "ema", "sma", "wma", "macd", "atr", "adx", "cci", "mfi", "obv",
        "vwap", "bb", "bollinger", "stoch", "kdj", "ichimoku", "roi", "sl", "tp",
        "api", "ai", "ui", "id", "cad", "usd", "eur", "btc", "eth", "sol", "xrp",
        "ada", "dot", "link", "matic", "doge", "ltc", "bch", "avax", "atom",
    }
)

# Protection methods freqtrade supports. Used to sanity-check what we read.
KNOWN_PROTECTION_METHODS = {
    "StoplossGuard",
    "MaxDrawdown",
    "LowProfitPairs",
    "CooldownPeriod",
}


def _is_valid_strategy_name(strategy_name: Any) -> bool:
    """True only for a plain Python-identifier-shaped strategy name.

    Why a whitelist rather than a blacklist: the name arrives from the bot
    configuration, and it is pasted straight into a filename. A value such as
    ``../../../etc/passwd`` would otherwise be used to build a path outside the
    strategies directory. Rejecting everything that is not ``[A-Za-z0-9_]+`` is
    the smallest rule that cannot be bypassed by an encoding trick the shell or
    ``pathlib`` might interpret differently.

    A length bound is included for a different reason. No real strategy class
    name is anywhere near this long, and the name is rendered in a fixed-width
    card in the UI - an unbounded value would be a label that overflows the
    layout. The limit is far above any plausible name so it cannot reject a real
    strategy.
    """
    return (
        isinstance(strategy_name, str)
        and len(strategy_name) <= MAX_STRATEGY_NAME_LENGTH
        and bool(STRATEGY_NAME_PATTERN.fullmatch(strategy_name))
    )


def _resolve_within(candidate: Path, base: Path) -> Optional[Path]:
    """Resolve ``candidate`` and return it only if it stays inside ``base``.

    Why this exists even though the name is validated: the whitelist stops
    ``..`` in the *name*, but a harmless-looking file inside the strategies
    directory can still be a symlink pointing at ``/etc/passwd``. Resolving the
    final path and checking containment catches both, and it is the check that
    has to hold if anyone later relaxes the name rule.
    """
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as exc:  # RuntimeError: symlink loops
        logger.warning("Could not resolve candidate strategy path %s: %s", candidate, exc)
        return None
    if not resolved.is_relative_to(base):
        logger.warning(
            "Refusing to read %s: it resolves to %s, outside the strategies "
            "directory %s.",
            candidate,
            resolved,
            base,
        )
        return None
    return resolved


def _find_strategy_file(strategy_name: str, strategies_dir: Path) -> Optional[Path]:
    """Locate the file that defines ``strategy_name``.

    Tries the snake_case filename freqtrade's resolver uses, then falls back to
    scanning every .py file for a matching class, so a rename cannot silently
    break protection reporting.

    Returns ``None`` when the name is not a legal strategy name, when the
    directory is missing, or when no file can be found. Callers must treat that
    as "unknown", never as "no protections configured".
    """
    if not _is_valid_strategy_name(strategy_name):
        # Not a name any freqtrade strategy can have - refuse to touch the
        # filesystem with it at all.
        logger.warning(
            "Refusing to inspect strategy %r: not a valid strategy class name.",
            strategy_name,
        )
        return None

    try:
        base = strategies_dir.resolve()
    except (OSError, RuntimeError) as exc:
        logger.warning("Could not resolve strategies directory %s: %s", strategies_dir, exc)
        return None

    if not base.is_dir():
        return None

    # Candidate filenames: the strategy name is a class, the file is snake_case.
    snake = []
    for i, ch in enumerate(strategy_name):
        if ch.isupper() and i > 0:
            snake.append("_")
        snake.append(ch.lower())
    candidates = [
        base / f"{''.join(snake)}.py",
        base / f"{strategy_name}.py",
    ]
    for candidate in candidates:
        resolved = _resolve_within(candidate, base)
        if resolved is not None and resolved.is_file():
            return resolved

    # Fall back to searching by class name. This only changes WHERE we look for
    # the class; the class name itself must still match exactly, so it cannot
    # make us report a different strategy's protections.
    for path in sorted(base.glob("*.py")):
        resolved = _resolve_within(path, base)
        if resolved is None:
            continue
        try:
            tree = ast.parse(resolved.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == strategy_name:
                return resolved
    return None


def _extract_protections_from_tree(tree: ast.AST, strategy_name: str) -> Optional[List[Dict[str, Any]]]:
    """Pull the protections list out of a parsed strategy module.

    The class must match ``strategy_name`` EXACTLY. There is deliberately no
    fallback to any other class: reporting class A's protections while the
    operator is running class B is a false safety claim, and reporting ``[]``
    ("nothing configured") when the truth is "I could not find the class" is
    worse still, because it tells the operator their safety net is gone when it
    is not. When the named class is absent the answer is ``None`` = unknown.

    Note also that "class found but no ``protections`` property" returns
    ``None`` rather than ``[]``: freqtrade resolves protections through the
    class hierarchy, so a base class in another file may be supplying them.
    Source-level inspection cannot see that, so it must not claim "none".
    """
    target_class: Optional[ast.ClassDef] = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == strategy_name:
            target_class = node
            break

    if target_class is None:
        logger.warning(
            "Strategy file does not define a class named %s, so its protections "
            "are UNKNOWN (not 'none configured').",
            strategy_name,
        )
        return None

    for node in target_class.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "protections":
            continue

        # Only accept a @property, which is how freqtrade reads it.
        decorators = {
            ast.unparse(d).split(".")[-1] for d in node.decorator_list
        }
        if "property" not in decorators:
            continue

        for stmt in node.body:
            if not isinstance(stmt, ast.Return) or stmt.value is None:
                continue
            try:
                value = ast.literal_eval(stmt.value)
            except (ValueError, SyntaxError, TypeError):
                logger.warning(
                    "Could not statically evaluate the protections property in "
                    "strategy %s; it uses expressions beyond literals.",
                    strategy_name,
                )
                return None
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            return None

    return None


def friendly_strategy_name(strategy_name: str) -> str:
    """Turn a strategy class name into something a person can read.

    ``ModerateMultiPairStrategy`` is an identifier, not a name. Someone who does
    not write code should not have to decode CamelCase to find out what their bot
    is running, and the stat card is the first thing they look at.

    The class name is the input because it is the only thing always available:
    every strategy has one, including ones downloaded from elsewhere. A written
    description is preferred when it exists, and
    :func:`read_strategy_description` supplies that - this is the fallback that
    guarantees a readable label regardless.

    Never raises, and never returns an empty string for a non-empty input: a
    strategy with an unusual name should look odd, not blank.
    """
    if not isinstance(strategy_name, str) or not strategy_name.strip():
        return ""

    name = strategy_name.strip()

    # "Strategy" on the end is a suffix, not information. Stripped only when
    # something is left, so a strategy literally called "Strategy" still shows.
    if name.endswith("Strategy") and len(name) > len("Strategy"):
        name = name[: -len("Strategy")]

    # Underscores are separators, not part of a word: "MyBot_v2" is "MyBot" and
    # "v2", not "MyBot" and "v" and "2".
    name = name.replace("_", " ")

    # Split CamelCase and acronym runs:
    #   ModerateMultiPair  -> Moderate, Multi, Pair
    #   RSIMeanReversion   -> RSI, Mean, Reversion
    #   MACDTrend          -> MACD, Trend
    #
    # Digits stay attached to the word they follow, so "v2" survives as one token
    # and "MultiPair2" does not become "multi pair 2".
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+\d*|[A-Z]+\d*|\d+", name)
    if not parts:
        return name

    # Digits belong to a single-letter word ("v2") but are a separate word after
    # a real one ("MultiPair2" is "Multi-pair 2", not "Multi-pair2"). Version
    # suffixes are common enough in strategy names to be worth reading properly.
    expanded: List[str] = []
    for part in parts:
        match = re.fullmatch(r"([A-Za-z]{2,})(\d+)", part)
        if match:
            expanded.extend([match.group(1), match.group(2)])
        else:
            expanded.append(part)
    parts = expanded

    words: List[str] = []
    for index, part in enumerate(parts):
        lowered = part.lower()
        if lowered in _ACRONYMS:
            words.append(part.upper())
        elif index == 0:
            words.append(part[:1].upper() + part[1:].lower())
        else:
            words.append(lowered)

    label = " ".join(words)

    # Hyphenate a few genuinely compound modifiers. English writes "multi-pair"
    # and "multi-timeframe", not "multi pair", and the hyphen is what makes the
    # phrase read as one idea rather than two.
    #
    # Case-insensitive, because the prefix can be the first word and therefore
    # capitalised: "MultiTimeframeTrend" is "Multi-timeframe trend". The
    # replacement preserves the original casing rather than forcing it.
    label = re.sub(
        r"\b(multi|cross|non) ([a-z]+)",
        lambda m: "%s-%s" % (m.group(1), m.group(2)),
        label,
        flags=re.IGNORECASE,
    )

    return label


def _extract_description_from_tree(tree: ast.AST, strategy_name: str) -> Optional[str]:
    """A ``DESCRIPTION`` class attribute, if the strategy defines one.

    Read with the AST and ``literal_eval`` rather than by importing the strategy:
    importing would execute arbitrary module-level code from a file that may have
    been written by the AI, which is exactly what this project refuses to do
    anywhere else.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != strategy_name:
            continue
        for statement in node.body:
            targets: List[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
                value_node = statement.value
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
                value_node = statement.value
            else:
                continue
            if value_node is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "DESCRIPTION":
                    try:
                        value = ast.literal_eval(value_node)
                    except (ValueError, SyntaxError):
                        return None
                    return value if isinstance(value, str) else None
    return None


def _module_docstring_summary(tree: ast.AST) -> Optional[str]:
    """The first meaningful line of the module docstring.

    A generated strategy's docstring opens with a summary line, so this is a
    decent description when no ``DESCRIPTION`` is set. Only the first line, and
    only if it looks like prose rather than a filename or an empty string.
    """
    docstring = ast.get_docstring(tree)
    if not docstring:
        return None
    for line in docstring.splitlines():
        candidate = line.strip()
        if len(candidate) >= 12:
            return candidate.rstrip(".")
    return None


def read_strategy_description(
    strategy_name: str,
    strategies_dir: Optional[str | Path] = None,
) -> Optional[str]:
    """A one-line plain description of a strategy, or ``None`` if unknown.

    ``None`` means "could not determine", never "there is none" - the same
    distinction :func:`read_strategy_protections` makes, and for the same reason:
    an empty string shown where a description belongs reads as a bug in the bot.
    """
    if not _is_valid_strategy_name(strategy_name):
        return None

    directory = Path(strategies_dir) if strategies_dir else DEFAULT_STRATEGIES_DIR
    try:
        path = _find_strategy_file(strategy_name, directory)
        if path is None:
            return None
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return _extract_description_from_tree(tree, strategy_name) or _module_docstring_summary(tree)
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        logger.debug("Could not read a description for %s: %s", strategy_name, exc)
        return None


def describe_strategy(
    strategy_name: Optional[str],
    strategies_dir: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Everything the UI needs to present a strategy to a non-expert.

    Returns ``friendly_name`` always (derived from the class name, so it is
    available even when the file cannot be read), plus ``description`` when the
    strategy provides one. ``description`` is ``None`` rather than empty when
    unknown, so the UI can omit the line instead of printing nothing.
    """
    # An invalid name is treated as "no strategy", so a junk value from the config
    # is never echoed back to the operator as though it were a real strategy.
    if not _is_valid_strategy_name(strategy_name):
        return {
            "class_name": None,
            "friendly_name": None,
            "description": None,
            "description_source": None,
        }

    description = read_strategy_description(strategy_name, strategies_dir)
    source = None
    if description:
        # Distinguish an authored DESCRIPTION from a docstring first line, so the
        # UI can prefer the former and a reviewer can tell which they are seeing.
        directory = Path(strategies_dir) if strategies_dir else DEFAULT_STRATEGIES_DIR
        try:
            path = _find_strategy_file(strategy_name, directory)
            tree = ast.parse(path.read_text(encoding="utf-8")) if path else None
        except (OSError, SyntaxError, UnicodeDecodeError):
            tree = None
        if tree is not None and _extract_description_from_tree(tree, strategy_name):
            source = "strategy:DESCRIPTION"
        else:
            source = "strategy:docstring"

    return {
        "class_name": strategy_name,
        "friendly_name": friendly_strategy_name(strategy_name),
        "description": description,
        "description_source": source,
    }


def read_strategy_protections(
    strategy_name: str,
    strategies_dir: Optional[str | Path] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Return the protections configured on a strategy.

    Args:
        strategy_name: the class name, e.g. ``ModerateMultiPairStrategy``.
        strategies_dir: directory holding strategy files.

    Returns:
        A list of protection dicts when they could be read, ``[]`` only when the
        named class was found and its ``protections`` property genuinely returns
        an empty list, or ``None`` when the answer could not be determined (bad
        or missing name, missing file, missing class, unreadable or
        non-literal property, any unexpected error).

        Callers MUST distinguish ``None`` (unknown) from ``[]`` (none
        configured): reporting "no protections" when the answer is merely
        "unknown" would be a lie, and the operator would learn to ignore the
        warning that is supposed to protect their money.

    This never raises. A failure to inspect a strategy is a reporting problem,
    not a reason to take the bot's explanations offline.
    """
    if not _is_valid_strategy_name(strategy_name):
        # Covers empty, None and any path-like value in one place, so no caller
        # has to remember to validate before calling.
        logger.debug("Not inspecting strategy %r: invalid strategy name.", strategy_name)
        return None

    directory = Path(strategies_dir) if strategies_dir else DEFAULT_STRATEGIES_DIR
    try:
        path = _find_strategy_file(strategy_name, directory)
        if path is None:
            logger.warning(
                "Strategy %s was not found in %s; protections are UNKNOWN "
                "(this is not a report that none are configured).",
                strategy_name,
                directory,
            )
            return None
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return _extract_protections_from_tree(tree, strategy_name)
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        logger.warning("Could not inspect strategy %s: %s", strategy_name, exc)
        return None
    except Exception:  # noqa: BLE001 - inspection must never break the caller
        logger.exception("Unexpected error inspecting strategy %s", strategy_name)
        return None


def summarise_protections(
    protections: Optional[List[Dict[str, Any]]],
) -> Optional[str]:
    """One-line human summary of protections, or None if unknown."""
    if protections is None:
        return None
    if not protections:
        return "none configured"
    return ", ".join(
        sorted({str(p.get("method", "unknown")) for p in protections})
    )