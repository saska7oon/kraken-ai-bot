"""
Static safety gate for LLM-generated Freqtrade strategy code.
=============================================================

Threat model
------------
An LLM (reached through OpenRouter) writes a complete Freqtrade strategy as
Python source text.  That text is then shown to a human operator who -- by
their own account -- does not know crypto trading and cannot read Python.
They can only answer "yes, trade my money with this" or "no".

Everything between the model and that person's money is therefore a security
boundary, and this module is the last automated line of defence before the
code is presented for approval.  The realistic bad outcomes we defend
against are:

1. **Financial ruin through plausible-looking numbers.**  The code compiles
   and imports cleanly, but sets ``stoploss = -0.9`` (a single trade can lose
   90% of its stake), an absurd ``minimal_roi``, or ``can_short = True`` /
   ``leverage()`` returning 20 on a Canadian spot-only Kraken account, where
   leverage simply is not available and the resulting behaviour is
   unpredictable.
2. **Silent account destruction (martingale / averaging down).**  Setting
   ``position_adjustment_enable = True`` makes the bot buy *more* of a losing
   position, doubling down again and again.  It looks profitable on history
   and blows up the account in one trend.  A novice reader cannot spot it.
3. **Code that is not a trading strategy at all.**  Prompt-injected or
   simply misbehaving output that imports ``os``/``subprocess``/``socket``,
   calls ``eval``/``exec``/``open(..., "w")``, or reaches the network.  The
   bot process holds exchange API keys and lives inside a container with the
   operator's configuration, so arbitrary code execution is a real risk, not
   a theoretical one.
4. **Operator lock-up.**  ``while True:`` with no exit inside a strategy
   callback freezes the trading loop -- no entries, no exits, an open
   position with nobody watching it.

Design rules
------------
* Structure is inspected with :mod:`ast` (never with regex).  Regex is used
  only to scan already-extracted string literals for URLs and pair names.
* This module **never raises**.  Any unexpected failure is converted into an
  error-severity ``internal_validator_error`` issue, which blocks approval --
  failing closed, never open.
* Verdicts are deliberately conservative: when the code cannot be understood
  with certainty, we report an ``error`` rather than assume the safe reading.
  A false rejection costs the operator one retry; a false approval can cost
  them their account.

The module has no third-party dependencies and no side effects: it reads a
string and returns a result.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import FrozenSet, Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ValidationIssue",
    "ValidationResult",
    "validate_strategy_code",
    "REQUIRED_METHODS",
    "FORBIDDEN_IMPORTS",
    "FORBIDDEN_CALLS",
    "DEFAULT_ALLOWED_TIMEFRAMES",
    "DEFAULT_FORBIDDEN_PAIR_SUFFIXES",
]


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

REQUIRED_INTERFACE_VERSION = 3

#: Circuit breakers every generated strategy must define.
#:
#: Freqtrade 2026.x moved protections out of the config (it now rejects a
#: 'protections' key there entirely) and onto the strategy as a @property. That
#: change created a silent hole in exactly the place a novice is most exposed:
#: a strategy could pass every other check, backtest well, and have NO safety
#: net at all, because nothing required one. These three are what stop a losing
#: streak from compounding:
#:
#:   MaxDrawdown    - halts trading when equity falls too far from its peak
#:   StoplossGuard  - halts a pair after repeated stop-loss hits
#:   CooldownPeriod - forces a pause after a stop loss
REQUIRED_PROTECTIONS: Tuple[str, ...] = (
    "MaxDrawdown",
    "StoplossGuard",
    "CooldownPeriod",
)

REQUIRED_METHODS: Tuple[str, ...] = (
    "populate_indicators",
    "populate_entry_trend",
    "populate_exit_trend",
)

#: Importing any of these means the generated code is doing something a
#: trading strategy has no business doing.  ``threading`` is handled
#: separately: it is suspicious but not automatically disqualifying.
FORBIDDEN_IMPORTS: Tuple[str, ...] = (
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "ctypes",
    "importlib",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "telnetlib",
    "smtplib",
    "pickle",
    "marshal",
    "multiprocessing",
    "pty",
    "signal",
)

#: Unlike the others, a threading import is only a warning -- some innocent
#: strategies mention it in a comment-level sense, and it cannot by itself
#: escape the sandbox.
WARN_ONLY_IMPORTS: Tuple[str, ...] = ("threading",)

FORBIDDEN_CALLS: Tuple[str, ...] = (
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "breakpoint",
    "input",
)

#: ---------------------------------------------------------------------------
#: ALLOWLIST - the actual security boundary.
#: ---------------------------------------------------------------------------
#: Everything above this point is a BLACKLIST, and blacklists lose. The
#: following four payloads were verified to pass this validator with zero
#: errors, because each one computes a forbidden name at runtime so it never
#: appears literally in the source:
#:
#:     getattr(__builtins__, "ev" + "al")                # eval, never spelled
#:     builtins.__dict__["__imp" + "ort__"]("os")        # __import__, never spelled
#:     open("".join(chr(c) for c in [47, 114, 117, 110]))
#:     getattr(object, "__subcl" + "asses__")()
#:
#: Pair that with the fact that a generated strategy is written into the very
#: directory Freqtrade imports from, and a validator bypass is remote code
#: execution inside the container holding the Kraken API key.
#:
#: So the rule is inverted here: rather than enumerating what is forbidden, we
#: enumerate what a trading strategy may legitimately use and reject the rest.
#: That is a far stronger guarantee, and for this domain it is affordable - the
#: deployed strategy needs only the five roots below.
ALLOWED_IMPORT_ROOTS: FrozenSet[str] = frozenset(
    {
        # The strategy API itself, including freqtrade.vendor.
        "freqtrade",
        # Dataframe and numerical work, which is what indicators are built from.
        "pandas",
        "numpy",
        # Indicator libraries.
        "talib",
        "technical",
        # Standard-library types and helpers with no capability to escape.
        "typing",
        "datetime",
        "math",
        "statistics",
        "decimal",
        "functools",
        "itertools",
        "collections",
        "dataclasses",
        "enum",
        "warnings",
        "logging",
    }
)

#: Bare names that must never be *referenced*, even as a value.
#: ``getattr`` is the important one: it is the runtime name-resolution primitive
#: that turns any string into a callable, which is how every one of the four
#: payloads above reaches forbidden functionality without naming it.
#: ``open`` is here rather than relying on the mode check in ``_check_open_call``,
#: because that check only inspects the mode argument and never the path.
FORBIDDEN_NAMES: Tuple[str, ...] = (
    "getattr",
    "setattr",
    "delattr",
    "vars",
    "globals",
    "locals",
    "eval",
    "exec",
    "compile",
    "open",
    "chr",
    "ord",
    "input",
    "breakpoint",
    "memoryview",
    "builtins",
    "importlib",
    "__import__",
    "__builtins__",
    "exit",
    "quit",
    "help",
)

#: Modules whose mere *use* (e.g. ``requests.get``) indicates network access.
NETWORK_MODULES: Tuple[str, ...] = ("socket", "requests", "urllib", "http")

#: Attribute names that are the classic route out of a Python sandbox.
DANGEROUS_DUNDER_READS: Tuple[str, ...] = (
    "__globals__",
    "__builtins__",
    "__subclasses__",
    "__bases__",
    "__base__",
    "__mro__",
    "__code__",
    "__closure__",
    "__func__",
    "__self__",
    "__reduce__",
    "__reduce_ex__",
)

#: Reading these is common in harmless code (logging, repr), so warn.
MILD_DUNDER_READS: Tuple[str, ...] = ("__class__", "__dict__", "__module__", "__qualname__")

DEFAULT_ALLOWED_TIMEFRAMES: Tuple[str, ...] = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "1d",
)

DEFAULT_FORBIDDEN_PAIR_SUFFIXES: Tuple[str, ...] = (
    "UP",
    "DOWN",
    "BULL",
    "BEAR",
    "LONG",
    "SHORT",
    "3L",
    "3S",
    "5L",
    "5S",
)

#: A ROI target this small is eaten alive by trading fees.
MIN_SENSIBLE_ROI_ZERO = 0.005

#: Above this many distinct pair-looking strings we assume hardcoded pair
#: lists, which do not belong inside a strategy body.
MAX_SUSPICIOUS_PAIRS = 20

#: Paths and names that indicate an attempt to read credentials.
#:
#: This matters specifically because a generated strategy is executed inside the
#: **freqtrade** container, which is exactly where the Kraken API key and secret
#: are mounted. ``os``/``socket``/``requests`` are already forbidden imports, but
#: ``open()`` is a builtin, so a literal path was a route around every one of
#: those checks. The shared strategies volume makes it worse: a strategy could
#: write what it read to a path the AI orchestrator can see.
SENSITIVE_PATH_PATTERNS: Tuple[str, ...] = (
    "/run/secrets",
    "/proc/self/environ",
    "/proc/1/environ",
    "/dev/shm",
    "freqtrade-private",
    "kraken_api_key",
    "kraken_api_secret",
    "freqtrade_api_password",
    "orchestrator_api_token",
    "openrouter_api_key",
    "nextcloud_pass",
    "backup_encrypt_key",
    ".env",
)

#: Class-level attribute names that hold a collection of trading pairs.
PAIR_CONTAINER_ATTRS: Tuple[str, ...] = (
    "pairs",
    "pair_whitelist",
    "pairlist",
    "whitelist",
    "allowed_pairs",
    "pairs_to_trade",
)

#: Class-level attributes that decide how a strategy may trade. A second
#: assignment to any of these is treated as suspicious, because Python keeps
#: only the last one and the first is then pure misdirection.
SECURITY_RELEVANT_ATTRS: Tuple[str, ...] = (
    "stoploss",
    "minimal_roi",
    "leverage",
    "can_short",
    "timeframe",
    "INTERFACE_VERSION",
    "trading_mode",
    "margin_mode",
    "position_adjustment_enable",
    "max_entry_position_adjustment",
    "use_custom_stoploss",
    "trailing_stop",
    "protections",
)

_QUOTE_CURRENCIES: Tuple[str, ...] = ("USDT", "USDC", "USD", "EUR", "GBP", "BTC", "ETH")

#: Matches a web address anywhere inside a string literal. The spec's rule is
#: "literals *starting with* http(s)://", but a URL buried in a longer literal
#: is at least as suspicious, so we search rather than anchor.
_URL_RE = re.compile(r"(https?|ftp)://\S*", re.IGNORECASE)
_PAIR_WITH_SLASH_RE = re.compile(r"^[A-Z0-9]{2,15}/[A-Z0-9]{2,15}$")
_PAIR_NO_SLASH_RE = re.compile(r"^[A-Z0-9]{5,24}$")


# --------------------------------------------------------------------------
# Public result types
# --------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single problem found in generated strategy code.

    ``severity`` is ``"error"`` (blocks approval) or ``"warning"`` (must be
    shown to the operator but does not block).  ``code`` is a short stable
    machine-readable identifier so callers can react to specific problems
    without parsing prose.  ``message`` is written for somebody who does not
    know trading or programming.
    """

    severity: str
    code: str
    message: str
    line: Optional[int] = None

    def __post_init__(self) -> None:
        if self.severity not in ("error", "warning"):
            self.severity = "error"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "line": self.line,
        }


@dataclass
class ValidationResult:
    """Outcome of validating one generated strategy.

    ``ok`` is True only when there are zero error-severity issues.
    """

    ok: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)

    def errors(self) -> List[ValidationIssue]:
        """Only the blocking problems."""
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> List[ValidationIssue]:
        """Only the non-blocking things the operator should still read."""
        return [i for i in self.issues if i.severity == "warning"]

    def summary(self) -> str:
        """Multi-line, jargon-free explanation suitable for a novice."""
        try:
            return _build_summary(self)
        except Exception:  # pragma: no cover - defensive, must never raise
            verdict = "PASSED" if self.ok else "FAILED"
            return (
                f"Automatic safety check: {verdict}.\n"
                "The detailed report could not be formatted, so please treat "
                "this strategy with caution and ask a developer to look at it."
            )


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _fmt_pct(value: float) -> str:
    """Format a ratio as a friendly percentage: -0.08 -> '8%'."""
    try:
        text = f"{abs(float(value)) * 100:.4f}".rstrip("0").rstrip(".")
    except Exception:
        return "an unknown amount"
    if not text:
        text = "0"
    return text + "%"


def _fmt_money_ratio(value: float) -> str:
    try:
        return f"{float(value) * 100:.4f}".rstrip("0").rstrip(".") + "%"
    except Exception:
        return "unknown"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _module_root(name: str) -> str:
    """'os.path' -> 'os'."""
    return (name or "").split(".", 1)[0].strip()


def _strip_relative(name: str) -> str:
    return (name or "").lstrip(".")


def _annotate_explanation(code_name: str, line: Optional[int]) -> str:
    if line:
        return f"{code_name} (line {line})"
    return code_name


# --------------------------------------------------------------------------
# AST helpers
# --------------------------------------------------------------------------


def _assignments_in_body(body: Sequence[ast.stmt]) -> Dict[str, ast.AST]:
    """Class- or module-level simple assignments: name -> value node.

    **Last binding wins**, matching Python's own semantics: in

        stoploss = -0.08
        stoploss = -0.30

    the effective value is -0.30. An earlier version of this function used
    ``setdefault``, so it reported the *first* value. That was a real bypass:
    a generated strategy could state a safe stop loss and then quietly redefine
    it to an unsafe one, and the validator would check the safe value while
    Python used the unsafe one. ``_check_duplicate_attributes`` now also flags
    the redefinition itself.
    """
    found: Dict[str, ast.AST] = {}
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.value is not None:
                found[stmt.target.id] = stmt.value
    return found


def _all_assignments_in_body(body: Sequence[ast.stmt]) -> Dict[str, List[ast.AST]]:
    """Every assignment to each name, in source order (for duplicate detection)."""
    found: Dict[str, List[ast.AST]] = {}
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    found.setdefault(target.id, []).append(stmt.value)
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.value is not None:
                found.setdefault(stmt.target.id, []).append(stmt.value)
    return found


def _plain_positions_in_body(body: Sequence[ast.stmt]) -> Dict[str, ast.stmt]:
    """Class-level assignments including valueless annotations (for presence)."""
    found: Dict[str, ast.stmt] = {}
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    found.setdefault(target.id, stmt)
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name):
                found.setdefault(stmt.target.id, stmt)
    return found


def _method_names(cls: ast.ClassDef) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for stmt in cls.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(stmt.name, stmt)
    return out


def _docstring_node_ids(tree: ast.AST) -> set:
    """ids of Constant strings that are inert, i.e. never read as a value.

    Two cases: real module/class/function docstrings, and any string that is a
    bare expression statement. Both are dead text at runtime, so a word or path
    inside one cannot read a file. Checks that look for *used* strings (secret
    paths, URLs) should skip these to avoid rejecting a strategy over prose.
    """
    ids = set()
    for node in ast.walk(tree):
        # Only statement containers have a list-valued .body. ast.Lambda has a
        # .body too, but it is an expression, so the isinstance guard matters.
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            ids.add(id(body[0].value))
        # Bare string statements anywhere ("this is really a comment").
        for stmt in body:
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                ids.add(id(stmt.value))
    return ids


def _loop_has_exit(body: Sequence[ast.stmt]) -> bool:
    """True if the loop body can leave the loop (break/return/raise).

    Nested function bodies are skipped: a ``return`` inside a nested ``def``
    does not leave the enclosing loop, so counting it would hide a real
    freeze.
    """
    stack: List[Any] = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, (ast.Break, ast.Return, ast.Raise)):
            return True
        for child in ast.iter_child_nodes(node):
            stack.append(child)
    return False


def _is_true_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _looks_like_pair(text: str) -> bool:
    """Heuristic: does this string literal look like a trading pair?"""
    if not text or text != text.upper():
        return False
    if "/" in text:
        return bool(_PAIR_WITH_SLASH_RE.match(text))
    if not _PAIR_NO_SLASH_RE.match(text):
        return False
    if not any(ch.isalpha() for ch in text):
        return False
    for quote in _QUOTE_CURRENCIES:
        if text.endswith(quote) and len(text) > len(quote) + 1:
            return True
    return False


def _pair_base(pair: str) -> str:
    if "/" in pair:
        return pair.split("/", 1)[0]
    for quote in _QUOTE_CURRENCIES:
        if pair.endswith(quote):
            return pair[: -len(quote)]
    return pair


def _forbidden_suffix(pair: str, suffixes: Sequence[str]) -> Optional[str]:
    base = _pair_base(pair).upper()
    for suffix in suffixes:
        suffix = suffix.upper()
        if base != suffix and base.endswith(suffix):
            return suffix
    return None


# --------------------------------------------------------------------------
# Analyzer
# --------------------------------------------------------------------------


class _Analyzer:
    """Runs every check against one parsed strategy.

    The analyzer never raises outward: helpers catch their own failures and
    record issues instead.
    """

    def __init__(
        self,
        code: str,
        profile: str,
        max_stoploss: float,
        min_stoploss: float,
        allowed_timeframes: Sequence[str],
        forbidden_pair_suffixes: Sequence[str],
    ) -> None:
        self.code = code
        self.profile = profile or "moderate"
        self.max_stoploss = float(max_stoploss)
        self.min_stoploss = float(min_stoploss)
        self.allowed_timeframes = tuple(str(t) for t in allowed_timeframes)
        self.forbidden_pair_suffixes = tuple(str(s).upper() for s in forbidden_pair_suffixes)

        self.issues: List[ValidationIssue] = []
        self.facts: Dict[str, Any] = {
            "class_name": None,
            "timeframe": None,
            "stoploss": None,
            "minimal_roi": None,
            "max_open_trades_in_strategy": None,
            "uses_position_adjustment": False,
            "can_short": False,
            "imports": [],
            "has_custom_stoploss": False,
            "leverage": None,
            # Extras (allowed; the spec requires "at least" the keys above).
            "profile": self.profile,
            "trailing_stop": None,
            "trailing_stop_positive": None,
            "process_only_new_candles": None,
            "startup_candle_count": None,
            "interface_version": None,
            "methods": [],
            "pairs": [],
            "line_count": len(code.splitlines()) if isinstance(code, str) else 0,
        }

        self.tree: Optional[ast.Module] = None
        self.module_consts: Dict[str, ast.AST] = {}
        self.import_aliases: Dict[str, str] = {}  # local name -> root module
        self.import_names: List[str] = []
        self.docstring_ids: set = set()
        self.classes: List[ast.ClassDef] = []
        self.strategy_class: Optional[ast.ClassDef] = None
        #: Local names that are bound to the IStrategy base class, including
        #: aliases such as ``from freqtrade.strategy import IStrategy as Base``.
        self.istrategy_names: set = {"IStrategy"}

    # -- infrastructure ---------------------------------------------------

    def add(self, severity: str, code: str, message: str, line: Optional[int] = None) -> None:
        self.issues.append(ValidationIssue(severity=severity, code=code, message=message, line=line))

    def error(self, code: str, message: str, line: Optional[int] = None) -> None:
        self.add("error", code, message, line)

    def warn(self, code: str, message: str, line: Optional[int] = None) -> None:
        self.add("warning", code, message, line)

    @staticmethod
    def _line_of(node: Any) -> Optional[int]:
        return getattr(node, "lineno", None) or None

    def resolve(self, node: ast.AST) -> Tuple[Any, bool]:
        """Best-effort literal value for an AST node.

        Returns ``(value, True)`` on success.  Falls back to module-level
        constants so ``MAX_LOSS = -0.1`` / ``stoploss = MAX_LOSS`` still
        resolves.  Never raises.
        """
        try:
            return ast.literal_eval(node), True
        except Exception:
            pass
        if isinstance(node, ast.Name):
            target = self.module_consts.get(node.id)
            if target is not None and target is not node:
                try:
                    return ast.literal_eval(target), True
                except Exception:
                    pass
        return None, False

    # -- entry point ------------------------------------------------------

    def run(self) -> ValidationResult:
        if not isinstance(self.code, str):
            self.error(
                "internal_validator_error",
                "The generated strategy was not delivered as readable text, so it "
                "could not be checked at all. Nothing should be approved until this "
                "is fixed.",
            )
            return self._finish()

        try:
            self.tree = ast.parse(self.code)
        except SyntaxError as exc:
            line = exc.lineno or None
            detail = (exc.msg or "invalid syntax").strip()
            self.error(
                "syntax_error",
                f"This strategy is not valid Python, so it cannot run at all. "
                f"The problem is on line {line or '?'}: {detail}. This usually means "
                f"the generated code was cut off or garbled.",
                line,
            )
            return self._finish()
        except Exception as exc:  # e.g. MemoryError on absurd input
            self.error(
                "syntax_error",
                f"This strategy could not be read as Python code ({type(exc).__name__}), "
                f"so nothing about it can be trusted.",
            )
            return self._finish()

        try:
            self.docstring_ids = _docstring_node_ids(self.tree)
            self.module_consts = _assignments_in_body(self.tree.body)
            self._collect_imports()
            self._find_strategy_classes()
            self._check_interface_version()
            self._check_required_methods()
            self._check_timeframe()
            self._check_stoploss()
            self._check_minimal_roi()
            self._check_position_adjustment()
            self._check_can_short()
            self._check_leverage()
            self._check_protections()
            self._check_custom_stoploss()
            self._check_trailing_stop()
            self._check_process_only_new_candles()
            self._check_startup_candle_count()
            self._check_max_open_trades()
            self._check_duplicate_attributes()
            self._check_margin()
            self._check_pair_attributes()
            self._check_import_allowlist()
            self._check_no_double_underscores()
            self._check_forbidden_names()
            self._scan_calls_and_attributes()
            self._scan_string_literals()
            self._check_secret_access()
            self._check_infinite_loops()
            self._check_dunder_usage()
        except Exception as exc:  # pragma: no cover - fail closed
            self.error(
                "internal_validator_error",
                "The safety checker itself hit an unexpected problem while reading "
                f"this strategy ({type(exc).__name__}: {exc}). Because the code could "
                "not be fully checked, it must not be approved.",
            )

        return self._finish()

    def _finish(self) -> ValidationResult:
        try:
            # Deduplicate identical issues, then show blocking problems first.
            seen = set()
            unique: List[ValidationIssue] = []
            for issue in self.issues:
                key = (issue.severity, issue.code, issue.message, issue.line)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(issue)
            unique.sort(key=lambda i: (0 if i.severity == "error" else 1))
            errors = [i for i in unique if i.severity == "error"]
            return ValidationResult(ok=not errors, issues=unique, facts=dict(self.facts))
        except Exception:  # pragma: no cover - fail closed
            fallback = ValidationIssue(
                severity="error",
                code="internal_validator_error",
                message="The safety checker could not produce a report. Treat this "
                "strategy as unverified and do not approve it.",
            )
            return ValidationResult(ok=False, issues=[fallback], facts=dict(self.facts))

    # -- structure --------------------------------------------------------

    def _collect_imports(self) -> None:
        assert self.tree is not None
        names: List[str] = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    names.append(module)
                    local = alias.asname or _module_root(module)
                    self.import_aliases[local] = _module_root(module)
                    self._flag_import(module, self._line_of(node))
            elif isinstance(node, ast.ImportFrom):
                module = ("." * (node.level or 0)) + (node.module or "")
                names.append(module)
                for alias in node.names:
                    local = alias.asname or alias.name
                    if node.module:
                        self.import_aliases[local] = _module_root(node.module)
                    if alias.name == "IStrategy":
                        self.istrategy_names.add(local)
                self._flag_import(module, self._line_of(node))
        # Preserve order, drop duplicates.
        seen = set()
        ordered = []
        for name in names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        self.import_names = ordered
        self.facts["imports"] = ordered

    def _flag_import(self, module: str, line: Optional[int]) -> None:
        root = _module_root(_strip_relative(module))
        if not root:
            return
        if root in FORBIDDEN_IMPORTS:
            self.error(
                "forbidden_import",
                f"This strategy tries to use the '{root}' tool, which is part of the "
                f"computer's operating system rather than anything to do with trading. "
                f"A trading strategy has no reason to touch files, run commands or "
                f"open network connections. Bot-generated code doing this can damage "
                f"the machine or leak your exchange keys.",
                line,
            )
        elif root in WARN_ONLY_IMPORTS:
            self.warn(
                "forbidden_import_warning",
                f"This strategy imports '{root}' (background threads). That is not "
                f"automatically unsafe, but it is unusual in a strategy and makes the "
                f"behaviour harder to predict.",
                line,
            )

    def _find_strategy_classes(self) -> None:
        assert self.tree is not None
        all_classes = [n for n in ast.walk(self.tree) if isinstance(n, ast.ClassDef)]

        direct: List[ast.ClassDef] = []
        for cls in all_classes:
            if self._class_inherits_istrategy(cls, all_classes):
                direct.append(cls)

        self.classes = direct
        if not direct:
            self.error(
                "no_strategy_class",
                "This code does not contain a trading strategy at all. Freqtrade "
                "strategies must define a class that builds on the built-in "
                "'IStrategy' template, and this file has nothing of the kind. It "
                "cannot be used for trading.",
            )
            return
        if len(direct) > 1:
            names = ", ".join(c.name for c in direct)
            self.error(
                "multiple_strategy_classes",
                f"This file defines {len(direct)} different trading strategies "
                f"({names}) instead of one. It is impossible to tell which one would "
                f"actually run, so this cannot be approved as it stands.",
                self._line_of(direct[1]),
            )
        self.strategy_class = direct[0]
        self.facts["class_name"] = self.strategy_class.name

    def _class_inherits_istrategy(self, cls: ast.ClassDef, all_classes: Sequence[ast.ClassDef]) -> bool:
        """Direct, aliased or in-module-transitive IStrategy subclass?"""
        local_names = {c.name for c in all_classes}
        seen: set = set()

        def check(node: ast.ClassDef) -> bool:
            if node.name in seen:
                return False
            seen.add(node.name)
            for base in node.bases:
                if isinstance(base, ast.Name):
                    if base.id in self.istrategy_names:
                        return True
                    if base.id.endswith("IStrategy"):
                        return True
                    if base.id in local_names:
                        for parent in all_classes:
                            if parent.name == base.id and check(parent):
                                return True
                elif isinstance(base, ast.Attribute):
                    if base.attr == "IStrategy" or base.attr.endswith("IStrategy"):
                        return True
                    if base.attr in local_names:
                        for parent in all_classes:
                            if parent.name == base.attr and check(parent):
                                return True
            return False

        return check(cls)

    def _class_attrs(self) -> Dict[str, ast.AST]:
        if self.strategy_class is None:
            return {}
        return _assignments_in_body(self.strategy_class.body)

    def _class_methods(self) -> Dict[str, ast.AST]:
        if self.strategy_class is None:
            return {}
        return _method_names(self.strategy_class)

    # -- checks added after adversarial review ----------------------------

    def _check_duplicate_attributes(self) -> None:
        """Flag a security-relevant attribute that is assigned more than once.

        Python keeps only the last assignment, so a duplicated attribute means
        the earlier value is misdirection. ``_assignments_in_body`` now resolves
        last-wins, which closes the resulting bypass; this check exists so the
        duplicate is surfaced rather than silently resolved.
        """
        if self.strategy_class is None:
            return
        for container_name, body in (
            ("class", self.strategy_class.body),
            ("module", self.tree.body if self.tree is not None else []),
        ):
            for name, values in _all_assignments_in_body(body).items():
                if len(values) < 2:
                    continue
                if name not in SECURITY_RELEVANT_ATTRS:
                    continue
                first, last = values[0], values[-1]
                first_val, first_ok = self.resolve(first)
                last_val, last_ok = self.resolve(last)
                rendered = (
                    f"{first_val!r} earlier, but {last_val!r} is what actually takes "
                    f"effect"
                    if first_ok and last_ok
                    else f"set {len(values)} times"
                )
                self.warn(
                    "duplicate_attribute",
                    f"This strategy sets '{name}' more than once ({rendered}). "
                    f"When the same setting is given twice, only the last one counts, "
                    f"which is an easy way for a mistake - or something worse - to "
                    f"hide behind the first. Only one value should be present.",
                    self._line_of(last),
                )

    def _check_secret_access(self) -> None:
        """Block any reference to credential files, paths or secret names.

        A generated strategy runs inside the container that holds the Kraken API
        key. ``open()`` is a builtin, so it needs no import and slips past the
        forbidden-import checks; a literal path was therefore a route to read the
        credentials. Any string that names a secret path or secret name is
        treated as a blocking error.

        Docstrings are excluded: they are inert, and blocking a URL or a word in
        prose would reject legitimate strategies.
        """
        if self.tree is None:
            return
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in self.docstring_ids:
                continue
            lowered = node.value.lower()
            for pattern in SENSITIVE_PATH_PATTERNS:
                if pattern.lower() in lowered:
                    self.error(
                        "secret_access",
                        f"This strategy refers to '{node.value}', which is the "
                        f"location or name of a credential. A trading strategy has no "
                        f"legitimate reason to touch your API keys or passwords, and "
                        f"reading them is how they get stolen. This must be removed "
                        f"before approval.",
                        self._line_of(node),
                    )
                    break

    def _check_margin(self) -> None:
        """Reject margin, leverage or non-spot trading configuration.

        Kraken Canada operates as a restricted dealer: no margin, no futures, no
        derivatives and no short selling. A strategy that requests them cannot
        work here and indicates the model misunderstood the venue.
        """
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()

        if "margin_mode" in attrs:
            node = attrs["margin_mode"]
            value, ok = self.resolve(node)
            self.error(
                "margin_mode_set",
                f"This strategy configures margin trading "
                f"({'margin_mode = ' + repr(value) if ok else 'margin_mode is set'}). "
                f"Margin trading borrows money to trade with, which magnifies both "
                f"gains and losses, and Kraken Canada does not offer it at all. "
                f"This must be removed before approval.",
                self._line_of(node),
            )

        if "trading_mode" in attrs:
            node = attrs["trading_mode"]
            value, ok = self.resolve(node)
            if not ok or (isinstance(value, str) and value.strip().lower() != "spot"):
                self.error(
                    "trading_mode_not_spot",
                    f"This strategy sets the trading mode to "
                    f"{repr(value) if ok else 'something that cannot be read'}. Only "
                    f"'spot' is available on Kraken Canada - spot means buying and "
                    f"selling coins you actually own, with no borrowing and no "
                    f"contracts. This must be set to spot or removed.",
                    self._line_of(node),
                )

    def _check_pair_attributes(self) -> None:
        """Apply the pair rules to class-level pair lists.

        ``forbidden_pair_suffixes`` was previously only applied to pair-looking
        strings found loose in the body, so a leveraged-token pair sitting in a
        class attribute escaped the check entirely.
        """
        if self.strategy_class is None:
            return
        for name, node in self._class_attrs().items():
            is_pair_attr = name in PAIR_CONTAINER_ATTRS or name.endswith("_pairs")
            if not is_pair_attr:
                continue

            for literal in self._iter_string_literals(node):
                if not _looks_like_pair(literal):
                    continue

                suffix = _forbidden_suffix(literal, self.forbidden_pair_suffixes)
                if suffix:
                    self.error(
                        "leveraged_pair",
                        f"This strategy names the pair '{literal}'. Tokens ending in "
                        f"'{suffix}' are leveraged or inverse products that multiply "
                        f"gains and losses, and Kraken Canada does not offer them. "
                        f"These pairs would simply fail to trade.",
                        self._line_of(node),
                    )
                    continue

                quote = literal.rsplit("/", 1)[-1].upper()
                if quote != "CAD" and quote in _QUOTE_CURRENCIES:
                    self.warn(
                        "non_cad_pair",
                        f"This strategy names the pair '{literal}', which is not "
                        f"priced in Canadian dollars. This bot trades CAD pairs on "
                        f"Kraken Canada, so a {quote} pair is likely a mistake and "
                        f"probably will not be available.",
                        self._line_of(node),
                    )

    def _iter_string_literals(self, node: ast.AST) -> List[str]:
        """Every string literal reachable inside a node (lists, dicts, calls)."""
        out: List[str] = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                out.append(sub.value)
        return out

    def _check_interface_version(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        positions = _plain_positions_in_body(self.strategy_class.body)
        if "INTERFACE_VERSION" not in positions:
            self.error(
                "interface_version_missing",
                "This strategy does not say which version of the Freqtrade rules it "
                "was written for. Without that label the bot cannot safely load it, "
                "and it may run the wrong instructions.",
                self._line_of(self.strategy_class),
            )
            return
        node = attrs.get("INTERFACE_VERSION")
        value, ok = (None, False) if node is None else self.resolve(node)
        self.facts["interface_version"] = value if ok else "unreadable"
        if not ok or value != REQUIRED_INTERFACE_VERSION:
            shown = repr(value) if ok else "a value that cannot be read"
            self.error(
                "interface_version_unsupported",
                f"This strategy is labelled as version {shown} of the Freqtrade "
                f"rules, but this bot only supports version "
                f"{REQUIRED_INTERFACE_VERSION}. Running the wrong version can make "
                f"the bot misread instructions and place unintended trades.",
                self._line_of(node if node is not None else positions["INTERFACE_VERSION"]),
            )

    def _check_required_methods(self) -> None:
        if self.strategy_class is None:
            return
        methods = self._class_methods()
        self.facts["methods"] = sorted(methods.keys())
        missing = [name for name in REQUIRED_METHODS if name not in methods]
        if missing:
            friendly = {
                "populate_indicators": "work out the market measurements (the maths it looks at)",
                "populate_entry_trend": "decide when to buy",
                "populate_exit_trend": "decide when to sell",
            }
            described = "; ".join(f"'{m}' (used to {friendly.get(m, 'do its job')})" for m in missing)
            self.error(
                "missing_method",
                f"This strategy is missing {len(missing)} of the three required "
                f"building blocks: {described}. Without them the bot does not know "
                f"when to trade, so the strategy cannot work.",
                self._line_of(self.strategy_class),
            )

    def _check_timeframe(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        positions = _plain_positions_in_body(self.strategy_class.body)
        if "timeframe" not in positions:
            self.error(
                "timeframe_missing",
                "This strategy does not say how often it looks at the market (for "
                "example every 5 minutes). Without that, the bot cannot know when to "
                "check prices or place trades.",
                self._line_of(self.strategy_class),
            )
            return
        node = attrs.get("timeframe")
        value, ok = (None, False) if node is None else self.resolve(node)
        line = self._line_of(node if node is not None else positions["timeframe"])
        if not ok or not isinstance(value, str):
            self.error(
                "timeframe_invalid",
                "This strategy's setting for how often it checks the market is not a "
                "simple text value such as \"5m\", so it cannot be verified. Unreadable "
                "timing settings must not be approved.",
                line,
            )
            return
        self.facts["timeframe"] = value
        if value not in self.allowed_timeframes:
            allowed = ", ".join(self.allowed_timeframes)
            self.error(
                "timeframe_not_allowed",
                f"This strategy checks the market every '{value}', which is not one of "
                f"the timeframes allowed for your setup ({allowed}). Other timeframes "
                f"may not work with the market data this bot is allowed to download.",
                line,
            )

    def _check_stoploss(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        positions = _plain_positions_in_body(self.strategy_class.body)
        if "stoploss" not in positions:
            self.error(
                "stoploss_missing",
                "This strategy has no stop loss. A stop loss is the safety net that "
                "automatically closes a losing trade at a set loss, so without one a "
                "bad trade can keep losing money until almost nothing is left. This "
                "must be set before anything is approved.",
                self._line_of(self.strategy_class),
            )
            return
        node = attrs.get("stoploss")
        value, ok = (None, False) if node is None else self.resolve(node)
        line = self._line_of(node if node is not None else positions["stoploss"])
        if not ok or not _is_number(value):
            self.error(
                "stoploss_not_number",
                "The stop loss is not written as a plain number, so it cannot be "
                "checked. Because this is the setting that limits how much a single "
                "trade can lose, an unreadable value must not be approved.",
                line,
            )
            return
        value = float(value)
        self.facts["stoploss"] = value

        if value >= 0:
            self.error(
                "stoploss_not_negative",
                f"This strategy's stop loss is set to {_fmt_pct(value)}, which is not a "
                f"loss at all. A stop loss must be a negative number such as -0.08 "
                f"(meaning a loss of 8%). As written, the safety net would never "
                f"trigger and a bad trade could run all the way to zero.",
                line,
            )
            return

        if value < self.max_stoploss - 1e-12:
            self.error(
                "stoploss_too_wide",
                f"This strategy sets a stop loss of {_fmt_pct(value)}. That means a "
                f"single bad trade could lose {_fmt_pct(value)} of the money in that "
                f"trade. The widest allowed for your '{self.profile}' profile is "
                f"{_fmt_pct(self.max_stoploss)}. This is far too risky: a handful of "
                f"bad trades in a row could take most of the account.",
                line,
            )
        elif value > self.min_stoploss + 1e-12:
            self.error(
                "stoploss_too_tight",
                f"This strategy sets a stop loss of only {_fmt_pct(value)}. That is "
                f"tighter than the {_fmt_pct(self.min_stoploss)} minimum for your "
                f"'{self.profile}' profile. Such a small cushion is usually hit by "
                f"ordinary market noise, so the bot would sell at a loss again and "
                f"again while paying fees every time.",
                line,
            )

    def _check_minimal_roi(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        positions = _plain_positions_in_body(self.strategy_class.body)
        if "minimal_roi" not in positions:
            self.error(
                "minimal_roi_missing",
                "This strategy does not say at what profit level to take the money "
                "off the table. Without that target the bot has no exit plan for "
                "winning trades, so profits can turn back into losses.",
                self._line_of(self.strategy_class),
            )
            return
        node = attrs.get("minimal_roi")
        value, ok = (None, False) if node is None else self.resolve(node)
        line = self._line_of(node if node is not None else positions["minimal_roi"])
        if not ok or not isinstance(value, dict):
            self.error(
                "minimal_roi_not_dict",
                "This strategy's profit targets are not written in the expected "
                "table form, so they cannot be checked. The take-profit plan is what "
                "decides when your money is banked, so an unreadable one must not be "
                "approved.",
                line,
            )
            return

        self.facts["minimal_roi"] = {
            str(k): v for k, v in value.items() if isinstance(k, (str, int, float))
        }

        zero_key = None
        if "0" in value:
            zero_key = "0"
        elif 0 in value:
            zero_key = 0
        if zero_key is None:
            self.error(
                "minimal_roi_no_zero_key",
                "This strategy's profit target table has no entry for the very first "
                "moment ('0'). In Freqtrade that first entry is the fallback target: "
                "without it the bot has no instruction for when to sell at the end of "
                "the plan, and trades may be held indefinitely.",
                line,
            )
            return

        zero_value = value[zero_key]
        if not _is_number(zero_value):
            self.error(
                "minimal_roi_bad_value",
                "The main profit target in this strategy is not a plain number, so it "
                "cannot be checked. Unreadable profit targets must not be approved.",
                line,
            )
            return
        zero_value = float(zero_value)

        if zero_value < 0:
            self.error(
                "minimal_roi_zero_negative",
                f"This strategy is set to close trades at a loss of "
                f"{_fmt_money_ratio(zero_value)} as soon as they open. In plain terms "
                f"it plans to lose money on purpose, which is the opposite of what you "
                f"want. This looks like a mistake in the generated code.",
                line,
            )
            return

        if zero_value > 1.0:
            self.error(
                "minimal_roi_zero_too_large",
                f"This strategy waits for a profit of {_fmt_money_ratio(zero_value)} "
                f"before selling. That means it wants to more than double the money in "
                f"a single trade. Targets like that essentially never happen and are a "
                f"sign the numbers were invented rather than tested.",
                line,
            )
            return

        for key, raw in value.items():
            if not _is_number(raw):
                self.error(
                    "minimal_roi_bad_value",
                    f"One of the profit targets in this strategy (for '{key}') is not "
                    f"a plain number, so the whole take-profit plan cannot be checked.",
                    line,
                )
                return

        if zero_value < MIN_SENSIBLE_ROI_ZERO:
            self.warn(
                "roi_below_fee_threshold",
                f"The basic profit target is only {_fmt_money_ratio(zero_value)}. "
                f"Kraken charges a fee on every buy and every sell, and those fees are "
                f"usually bigger than a target this small -- so the strategy could "
                f"book a 'winning' trade that actually loses money. It is allowed, but "
                f"you should know the fees may eat the gains.",
                line,
            )

    def _check_position_adjustment(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        positions = _plain_positions_in_body(self.strategy_class.body)
        methods = self._class_methods()

        pae_node = attrs.get("position_adjustment_enable")
        max_adj_node = attrs.get("max_entry_position_adjustment")
        has_adjust_method = "adjust_trade_position" in methods

        pae_value: Any = None
        pae_known = True
        if "position_adjustment_enable" in positions:
            node = pae_node if pae_node is not None else positions["position_adjustment_enable"]
            value, ok = self.resolve(pae_node) if pae_node is not None else (None, False)
            pae_value = value if ok else None
            pae_known = ok

        max_adj_value: Any = None
        max_adj_known = True
        adj_line = None
        if max_adj_node is not None:
            max_adj_value, max_adj_known = self.resolve(max_adj_node)
            adj_line = self._line_of(max_adj_node)
        elif "max_entry_position_adjustment" in positions:
            max_adj_known = False
            adj_line = self._line_of(positions["max_entry_position_adjustment"])

        self.facts["uses_position_adjustment"] = bool(
            pae_value is True
            or has_adjust_method
            or (max_adj_known and _is_number(max_adj_value) and float(max_adj_value) != 0.0)
            or not pae_known
        )

        danger = (
            "Put simply: this makes the bot buy MORE of a trade that is already "
            "losing, hoping the price comes back. It is called 'averaging down' or a "
            "'martingale'. Account statements of bots that did this look wonderful "
            "right up until one bad market move wipes out the whole account, because "
            "the losing position keeps being made bigger instead of being cut."
        )

        if "position_adjustment_enable" in positions:
            if not pae_known:
                self.error(
                    "position_adjustment_unknown",
                    "This strategy switches on the 'buy more when losing' feature, but "
                    "the switch is written in a way that cannot be read. " + danger,
                    self._line_of(positions["position_adjustment_enable"]),
                )
            elif pae_value is True or (pae_value is not False and bool(pae_value)):
                self.error(
                    "position_adjustment_enabled",
                    "This strategy is set to add money to positions that are already "
                    "losing. " + danger,
                    self._line_of(positions["position_adjustment_enable"]),
                )

        if has_adjust_method:
            self.error(
                "adjustment_logic_present",
                "This strategy contains code that deliberately changes the size of an "
                "open trade -- the machinery used to add money to losers. " + danger,
                self._line_of(methods.get("adjust_trade_position")),
            )

        if max_adj_node is not None or "max_entry_position_adjustment" in positions:
            if not max_adj_known or not _is_number(max_adj_value):
                self.error(
                    "max_entry_position_adjustment_unsafe",
                    "This strategy sets a limit on how many times it may add money to "
                    "an open trade, but the value is not a readable number. " + danger,
                    adj_line,
                )
            else:
                numeric = float(max_adj_value)
                if numeric == 0.0:
                    pass
                elif numeric == -1.0:
                    if has_adjust_method or pae_value is True:
                        self.error(
                            "max_entry_position_adjustment_unsafe",
                            "This strategy is set to keep adding money to an open trade "
                            "without any limit. " + danger,
                            adj_line,
                        )
                else:
                    self.error(
                        "max_entry_position_adjustment_unsafe",
                        f"This strategy is allowed to add money to the same losing "
                        f"trade up to {int(numeric)} extra times. " + danger,
                        adj_line,
                    )

    def _check_can_short(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        positions = _plain_positions_in_body(self.strategy_class.body)
        if "can_short" not in positions:
            self.facts["can_short"] = False
            return
        node = attrs.get("can_short")
        value, ok = (None, False) if node is None else self.resolve(node)
        line = self._line_of(node if node is not None else positions["can_short"])
        self.facts["can_short"] = bool(value) if ok else "unreadable"
        if not ok:
            self.error(
                "can_short_unknown",
                "This strategy tries to switch on 'short selling' (betting that a "
                "price will fall), but the setting cannot be read. Your Kraken "
                "account only trades the normal way -- buying and later selling what "
                "you own -- so anything unclear here must not be approved.",
                line,
            )
            return
        if value is True:
            self.error(
                "can_short_enabled",
                "This strategy wants to 'short sell' -- betting that prices will fall. "
                "That requires borrowing coins you do not own. Your Kraken account is "
                "a normal account that can only buy and then sell what it owns, so "
                "this strategy cannot work here and would fail or behave unpredictably "
                "the moment it tried.",
                line,
            )

    def _check_leverage(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        methods = self._class_methods()

        # Class-attribute style: leverage = 5
        if "leverage" in attrs:
            node = attrs["leverage"]  # type: ignore[index]
            value, ok = self.resolve(node)  # type: ignore[arg-type]
            if ok and _is_number(value):
                self.facts["leverage"] = float(value)
                if float(value) != 1.0:
                    self.error(
                        "leverage_not_one",
                        f"This strategy asks to borrow money to trade "
                        f"{float(value):g} times the amount you actually have "
                        f"('leverage'). Borrowed money multiplies losses as well as "
                        f"gains, and your Kraken account cannot borrow at all. This "
                        f"must be 1.0 (no borrowing).",
                        self._line_of(node),  # type: ignore[arg-type]
                    )
            else:
                self.error(
                    "leverage_unknown",
                    "This strategy sets a borrowing ('leverage') value that cannot be "
                    "read. Since borrowing multiplies losses and your Kraken account "
                    "cannot borrow at all, an unclear value here must not be approved.",
                    self._line_of(node),  # type: ignore[arg-type]
                )
            return

        method = methods.get("leverage")
        if method is None:
            self.facts["leverage"] = None
            return

        returns: List[Tuple[ast.Return, Any, bool]] = []
        for node in ast.walk(method):
            if isinstance(node, ast.Return):
                if node.value is None:
                    returns.append((node, None, False))
                else:
                    value, ok = self.resolve(node.value)
                    returns.append((node, value, ok))

        if not returns:
            self.facts["leverage"] = None
            self.error(
                "leverage_unknown",
                "This strategy includes a borrowing ('leverage') instruction but never "
                "says what value to use, so the amount of borrowed money is unknown. "
                "Borrowing multiplies losses, and your Kraken account cannot borrow at "
                "all, so this must be fixed.",
                self._line_of(method),
            )
            return

        bad: Optional[Tuple[ast.Return, Any, bool]] = None
        for entry in returns:
            _node, value, ok = entry
            if not ok or not _is_number(value) or float(value) != 1.0:
                bad = entry
                break

        if bad is None:
            self.facts["leverage"] = 1.0
            return

        node, value, ok = bad
        if ok and _is_number(value):
            self.facts["leverage"] = float(value)
            self.error(
                "leverage_not_one",
                f"This strategy asks to borrow money so it can trade {float(value):g} "
                f"times the amount you actually have ('leverage'). That works like a "
                f"loan on every trade: it multiplies your losses exactly as much as "
                f"your gains. Your Kraken account is a normal, non-borrowing account, "
                f"so this setting cannot be honoured -- it must be 1.0.",
                self._line_of(node),
            )
        else:
            self.facts["leverage"] = None
            self.error(
                "leverage_not_one",
                "This strategy contains a borrowing ('leverage') instruction whose "
                "value cannot be read or is not a plain number. Borrowing multiplies "
                "losses, and your Kraken account cannot borrow at all, so anything "
                "other than a clear 1.0 must not be approved.",
                self._line_of(node),
            )

    def _check_protections(self) -> None:
        """Require the strategy to define real trade protections.

        This closes a hole created by Freqtrade 2026.x moving protections from
        the config onto the strategy. Nothing checked for them, so a generated
        strategy could pass every other test, backtest well, and still have no
        circuit breaker of any kind - the operationally dangerous case, because
        it looks perfectly healthy right up until a bad streak empties the
        account.

        The property must be statically readable. A protections list that is
        computed at runtime cannot be verified here, and "cannot be verified"
        must never be treated as "fine".
        """
        if self.strategy_class is None:
            return

        prop: Optional[ast.FunctionDef] = None
        for node in self.strategy_class.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "protections":
                decorators = {ast.unparse(d).split(".")[-1] for d in node.decorator_list}
                if "property" in decorators:
                    prop = node  # type: ignore[assignment]
                break

        if prop is None:
            self.error(
                "protections_missing",
                "This strategy defines no trade protections. Protections are the "
                "automatic circuit breakers that pause trading when things go wrong "
                "- for example after a run of losses. Without them a bad streak can "
                "keep compounding with nothing to stop it. In Freqtrade these must be "
                "declared as a 'protections' property on the strategy class."
                f" At minimum, {', '.join(REQUIRED_PROTECTIONS)} should be present.",
                self._line_of(self.strategy_class),
            )
            return

        value: Any = None
        literal_ok = False
        for stmt in ast.walk(prop):
            if isinstance(stmt, ast.Return) and stmt.value is not None:
                try:
                    value = ast.literal_eval(stmt.value)
                    literal_ok = True
                except (ValueError, SyntaxError, TypeError):
                    literal_ok = False
                break

        if not literal_ok or not isinstance(value, list):
            self.error(
                "protections_not_readable",
                "This strategy's protections are built by code rather than written "
                "out as a plain list, so their contents cannot be checked. Because "
                "these are the settings that limit losses, an unreadable definition "
                "must not be approved - write them as a plain list of settings.",
                self._line_of(prop),
            )
            return

        methods = {
            str(entry.get("method"))
            for entry in value
            if isinstance(entry, dict) and entry.get("method")
        }
        self.facts["protections"] = sorted(methods)

        missing = [name for name in REQUIRED_PROTECTIONS if name not in methods]
        if missing:
            self.error(
                "protections_incomplete",
                f"This strategy is missing {', '.join(missing)} from its protections. "
                f"Those circuit breakers are what pause trading after losses pile up; "
                f"without them a losing streak has nothing to stop it. Found: "
                f"{', '.join(sorted(methods)) or 'none'}.",
                self._line_of(prop),
            )

    def _check_custom_stoploss(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        methods = self._class_methods()
        has_method = "custom_stoploss" in methods
        node = attrs.get("use_custom_stoploss")
        value, ok = (None, False) if node is None else self.resolve(node)
        uses = bool(value) if ok else bool(has_method)
        self.facts["has_custom_stoploss"] = bool(uses or has_method)

        if ok and value is True:
            self.error(
                "custom_stoploss_enabled",
                "This strategy replaces the normal stop loss with its own custom "
                "code. The simple stop loss number then no longer limits how much a "
                "trade can lose - a piece of code decides instead, and nothing here "
                "can say in advance what it will return. A custom stop loss can "
                "legitimately return a loss far larger than the configured limit. "
                "Because a generated strategy cannot be relied on to get this right, "
                "it must use a plain numeric stop loss instead.",
                self._line_of(node),  # type: ignore[arg-type]
            )
        if value is True and not has_method:
            self.warn(
                "custom_stoploss_method_missing",
                "This strategy says it uses a custom safety net but no custom safety "
                "net code was found. As written, the protection may not work at all.",
                self._line_of(node),  # type: ignore[arg-type]
            )

    def _check_trailing_stop(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        ts_node = attrs.get("trailing_stop")
        tsp_node = attrs.get("trailing_stop_positive")
        ts_value, ts_ok = (None, False) if ts_node is None else self.resolve(ts_node)
        tsp_value, tsp_ok = (None, False) if tsp_node is None else self.resolve(tsp_node)
        self.facts["trailing_stop"] = bool(ts_value) if ts_ok else None
        self.facts["trailing_stop_positive"] = tsp_value if tsp_ok else None

        if ts_ok and ts_value is True and not tsp_ok:
            self.warn(
                "trailing_stop_no_positive",
                "This strategy uses a 'trailing stop' (it follows a rising price up "
                "and sells when the price slips back a bit). But it never says how far "
                "the price may slip back before selling, so Freqtrade would have to "
                "guess. Setting that distance makes the behaviour predictable.",
                self._line_of(ts_node),  # type: ignore[arg-type]
            )
        if ts_ok and ts_value is True and tsp_ok and _is_number(tsp_value) and float(tsp_value) < 0:
            self.warn(
                "trailing_stop_positive_negative",
                "The trailing stop distance is a negative number. It should be a "
                "positive amount (for example 0.01 for 1%), or the sell trigger may "
                "not work as intended.",
                self._line_of(tsp_node),  # type: ignore[arg-type]
            )

    def _check_process_only_new_candles(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        node = attrs.get("process_only_new_candles")
        value, ok = (None, False) if node is None else self.resolve(node)
        self.facts["process_only_new_candles"] = value if ok else None
        if not ok or value is not True:
            self.warn(
                "process_only_new_candles_not_set",
                "This strategy does not switch on the option that tells the bot to "
                "make decisions only once per new price bar. Leaving it off makes the "
                "bot redo its work constantly, which is slow and wasteful and can "
                "occasionally make it act twice on the same information.",
                self._line_of(node) if node is not None else self._line_of(self.strategy_class),
            )

    def _check_startup_candle_count(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        positions = _plain_positions_in_body(self.strategy_class.body)
        if "startup_candle_count" not in positions:
            self.warn(
                "startup_candle_count_missing",
                "This strategy does not say how much past market history it needs "
                "before its maths becomes reliable. Without that, its first trades may "
                "be based on half-finished calculations, which are often wrong.",
                self._line_of(self.strategy_class),
            )
            return
        node = attrs.get("startup_candle_count")
        value, ok = (None, False) if node is None else self.resolve(node)
        self.facts["startup_candle_count"] = value if ok else None
        if not ok or not _is_number(value) or float(value) <= 0:
            self.warn(
                "startup_candle_count_suspicious",
                "The amount of past market history this strategy asks for is missing, "
                "zero or unreadable. It should be a sensible positive number of price "
                "bars, otherwise early signals may be based on incomplete maths.",
                self._line_of(node if node is not None else positions["startup_candle_count"]),
            )

    def _check_max_open_trades(self) -> None:
        if self.strategy_class is None:
            return
        attrs = self._class_attrs()
        node = attrs.get("max_open_trades")
        if node is None:
            return
        value, ok = self.resolve(node)
        if not ok:
            self.warn(
                "max_open_trades_unreadable",
                "This strategy tries to set how many trades may be open at once, but "
                "the value cannot be read. Your bot's own configuration should decide "
                "this; the strategy setting will be ignored or may behave oddly.",
                self._line_of(node),
            )
            return
        self.facts["max_open_trades_in_strategy"] = value
        if _is_number(value) and float(value) > 10:
            self.warn(
                "max_open_trades_high",
                f"This strategy asks to keep up to {int(float(value))} trades open at "
                f"the same time. Each open trade is money at risk, so a high number "
                f"multiplies how much of your account is exposed at once.",
                self._line_of(node),
            )

    # -- calls, attributes, strings, loops, dunders -----------------------

    def _scan_calls_and_attributes(self) -> None:
        assert self.tree is not None
        os_aliases = {name for name, root in self.import_aliases.items() if root == "os"}
        os_aliases.add("os")

        reported_os = False
        network_uses: set = set()

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                func = node.func
                name: Optional[str] = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    if func.attr in FORBIDDEN_CALLS:
                        name = func.attr
                    elif func.attr == "urlopen":
                        network_uses.add(("urlopen", self._line_of(node)))
                if name in FORBIDDEN_CALLS:
                    self.error(
                        "forbidden_call",
                        f"This strategy uses the '{name}' instruction. That is a "
                        f"general-purpose programming tool, not something a trading "
                        f"strategy needs, and it is a common way for harmful code to "
                        f"run on the machine. This must be removed before approval.",
                        self._line_of(node),
                    )
                if isinstance(func, ast.Name) and func.id == "open":
                    self._check_open_call(node)
                if isinstance(func, ast.Attribute) and func.attr == "open" and isinstance(func.value, ast.Name) and func.value.id in ("builtins", "io"):
                    # Catches builtins.open(...) / io.open(...), which would
                    # otherwise slip past the check above.
                    self._check_open_call(node)
                if isinstance(func, ast.Name) and func.id == "urlopen":
                    network_uses.add(("urlopen", self._line_of(node)))

            elif isinstance(node, ast.Attribute):
                base = node.value
                root = None
                if isinstance(base, ast.Name):
                    root = self.import_aliases.get(base.id, base.id)
                if root == "os" and not reported_os:
                    reported_os = True
                    self.error(
                        "os_usage",
                        "This strategy reaches into the computer's operating system "
                        "('os'), for example to run a command or touch a file. A "
                        "trading strategy never needs to do that, and code like this "
                        "can delete data or steal your exchange keys.",
                        self._line_of(node),
                    )
                if root in NETWORK_MODULES:
                    network_uses.add((f"{root}.{node.attr}", self._line_of(node)))
                if node.attr in ("urlopen",):
                    network_uses.add(("urlopen", self._line_of(node)))

            elif isinstance(node, ast.Name):
                if node.id in ("urlopen",) and not isinstance(getattr(node, "ctx", None), ast.Store):
                    network_uses.add(("urlopen", self._line_of(node)))

        for label, line in sorted(network_uses, key=lambda x: (x[1] or 0)):
            self.error(
                "network_access",
                f"This strategy tries to use '{label}', which means talking to the "
                f"internet directly. Your bot already has a safe, official connection "
                f"to Kraken for prices and orders; extra network code can leak your "
                f"API keys or send your information somewhere unknown.",
                line,
            )

    def _check_open_call(self, node: ast.Call) -> None:
        mode_node: Optional[ast.AST] = None
        if len(node.args) >= 2:
            mode_node = node.args[1]
        for kw in node.keywords:
            if kw.arg == "mode":
                mode_node = kw.value
        if mode_node is None:
            return  # fopen default is read-only text mode
        value, ok = self.resolve(mode_node)
        if not ok or not isinstance(value, str):
            self.warn(
                "open_mode_unknown",
                "This strategy opens a file using a setting that cannot be read. "
                "Opening a file to write to it is not something a trading strategy "
                "should ever do, so this needs a human to look at it.",
                self._line_of(node),
            )
            return
        if any(ch in value for ch in ("w", "a", "x", "+")):
            self.error(
                "open_write_mode",
                "This strategy opens a file so that it can write to or overwrite it. "
                "A trading strategy has no reason to create or change files on the "
                "computer, and doing so can destroy your settings, logs or saved data. "
                "This must be removed before approval.",
                self._line_of(node),
            )

    def _scan_string_literals(self) -> None:
        assert self.tree is not None
        pairs: List[str] = []
        pair_lines: Dict[str, Optional[int]] = {}
        url_hits: List[Tuple[bool, Optional[int]]] = []  # (in_docstring, line)

        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            text = node.value
            in_doc = id(node) in self.docstring_ids

            if _URL_RE.search(text):
                url_hits.append((in_doc, self._line_of(node)))
                continue
            if in_doc:
                continue

            if _looks_like_pair(text):
                if text not in pair_lines:
                    pair_lines[text] = self._line_of(node)
                    pairs.append(text)

        self.facts["pairs"] = pairs

        for in_doc, line in url_hits:
            if in_doc:
                self.warn(
                    "network_access_docstring",
                    "A web address appears in the description text of this strategy. "
                    "That is normally just a link to the Freqtrade documentation and is "
                    "harmless, because description text is not run. It is shown here "
                    "only so nothing is hidden from you.",
                    line,
                )
                continue
            self.error(
                "network_access",
                "This strategy contains a web address inside a piece of text that the "
                "code actually uses. That usually means the strategy intends to fetch "
                "something from the internet. Your bot's only safe connection is the "
                "official one to Kraken, so this must be removed.",
                line,
            )

        for pair in pairs:
            suffix = _forbidden_suffix(pair, self.forbidden_pair_suffixes)
            if suffix:
                self.warn(
                    "leveraged_pair",
                    f"This strategy mentions the trading pair '{pair}'. Names like this "
                    f"are not normal cryptocurrencies: tokens ending in '{suffix}' are "
                    f"leveraged products that are designed to magnify daily price "
                    f"movements, and they can lose almost all their value very quickly. "
                    f"Kraken also may not support them for your account.",
                    pair_lines.get(pair),
                )

        if len(pairs) > MAX_SUSPICIOUS_PAIRS:
            self.warn(
                "too_many_pairs",
                f"This strategy has {len(pairs)} different trading pair names written "
                f"directly into it (for example '{pairs[0]}'). Hard-coding a long list "
                f"of pairs inside a strategy is unusual; the bot's own settings are "
                f"supposed to choose what is traded, and a long list can quietly send "
                f"money into markets you never intended to touch.",
                pair_lines.get(pairs[0]) if pairs else None,
            )

    def _check_infinite_loops(self) -> None:
        assert self.tree is not None
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.While):
                continue
            test = node.test
            is_forever = isinstance(test, ast.Constant) and test.value is True
            is_forever = is_forever or (isinstance(test, ast.Constant) and test.value == 1 and not isinstance(test.value, bool))
            if not is_forever:
                continue
            if _loop_has_exit(node.body):
                continue
            self.error(
                "infinite_loop",
                "This strategy contains a loop that never ends. It repeats forever "
                "with no way out, which would freeze the trading bot completely: no "
                "new trades, and -- far more dangerous -- no stop loss would ever run "
                "on a position you already hold. This must be fixed.",
                self._line_of(node),
            )

    # ----------------------------------------------------------------- allowlist
    def _check_import_allowlist(self) -> None:
        """Reject every import whose root module is not on the allowlist.

        This is the load-bearing check. ``import builtins`` looked harmless to
        the old blacklist, yet it is enough to reach the import machinery:

            builtins.__dict__["__imp" + "ort__"]("os").system("...")

        Because we allow only what a strategy provably needs, every route like
        that is closed by construction rather than by enumeration.
        """
        assert self.tree is not None
        allowed = ", ".join(sorted(ALLOWED_IMPORT_ROOTS))

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = _module_root(alias.name)
                    if root not in ALLOWED_IMPORT_ROOTS:
                        self.error(
                            "import_not_allowed",
                            f"This strategy imports '{alias.name}', which is not on "
                            f"the list of libraries a trading strategy may use. "
                            f"Allowed libraries are: {allowed}. If a strategy needs "
                            f"something outside that list, it is doing work that "
                            f"belongs outside a strategy.",
                            self._line_of(node),
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    self.error(
                        "relative_import",
                        "This strategy uses a relative import, which means it is "
                        "reaching for another file on the computer rather than a "
                        "normal library. Strategies must be self-contained.",
                        self._line_of(node),
                    )
                    continue
                root = _module_root(_strip_relative(node.module or ""))
                if root not in ALLOWED_IMPORT_ROOTS:
                    self.error(
                        "import_not_allowed",
                        f"This strategy imports from '{node.module}', which is not on "
                        f"the list of libraries a trading strategy may use. "
                        f"Allowed libraries are: {allowed}.",
                        self._line_of(node),
                    )

    def _check_no_double_underscores(self) -> None:
        """Reject double underscores in names, attributes and string literals.

        Python's ``__x__`` names are the standard route out of any restricted
        environment: ``__builtins__`` gives the builtin namespace,
        ``__subclasses__`` enumerates every loaded class, ``__globals__`` leaks
        module state, ``__import__`` is the import machinery itself.

        The old checker only inspected ``ast.Attribute`` nodes, so the same names
        written as *strings* passed untouched - which is precisely how
        ``"__imp" + "ort__"`` and ``"__subcl" + "asses__"`` got through.

        A real trading strategy has no need for a double underscore anywhere.
        The deployed strategy contains zero of them, so this rule costs nothing
        legitimate and closes the whole family at once. Docstrings are exempt:
        prose is not executable.
        """
        assert self.tree is not None

        def reject(what: str, line: Optional[int]) -> None:
            self.error(
                "dunder_not_allowed",
                f"This strategy uses {what} containing a double underscore. In "
                f"Python, names like __builtins__ and __subclasses__ reach deep "
                f"into the interpreter and are the usual way code escapes its "
                f"sandbox. A trading strategy never needs one. This must be "
                f"removed before approval.",
                line,
            )

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Docstrings are documentation; only executable strings matter.
                if id(node) in self.docstring_ids:
                    continue
                if "__" in node.value:
                    reject("text", self._line_of(node))
            elif isinstance(node, ast.Attribute):
                if "__" in node.attr:
                    reject(f"'{node.attr}'", self._line_of(node))
            elif isinstance(node, ast.Name):
                if "__" in node.id:
                    reject(f"'{node.id}'", self._line_of(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if "__" in node.name:
                    reject(f"the definition '{node.name}'", self._line_of(node))
            elif isinstance(node, ast.arg):
                if "__" in node.arg:
                    reject(f"the parameter '{node.arg}'", self._line_of(node))

    def _check_forbidden_names(self) -> None:
        """Reject references to capability-bearing builtins such as getattr/open.

        ``getattr`` matters most: it converts any string into an attribute
        lookup, so it defeats every name-based check in this file. Banning the
        primitive is what makes the rest of the analysis meaningful.

        Deliberately *not* banned here: ``object``, ``type`` and ``super``. They
        are occasionally legitimate in strategy code, and the double-underscore
        rule above already closes the routes that made them dangerous
        (``getattr(object, "__subclasses__")`` needs both a forbidden name and a
        forbidden string).
        """
        assert self.tree is not None
        reported: set = set()

        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Name):
                continue
            # An assignment target is the strategy naming its own variable, which
            # is harmless; only *reading* the name reaches the builtin.
            if isinstance(getattr(node, "ctx", None), ast.Store):
                continue
            if node.id in FORBIDDEN_NAMES and node.id not in reported:
                reported.add(node.id)
                self.error(
                    "forbidden_name",
                    f"This strategy uses '{node.id}', which can run or reach parts "
                    f"of the computer that a trading strategy has no business "
                    f"touching. Tools like this are how harmful code hides - it is "
                    f"why the safety checker cannot simply look for the dangerous "
                    f"word itself. This must be removed before approval.",
                    self._line_of(node),
                )

    def _check_dunder_usage(self) -> None:
        assert self.tree is not None
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute):
                attr = node.attr
                if not (attr.startswith("__") and attr.endswith("__")):
                    continue
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    self.error(
                        "dunder_assignment",
                        f"This strategy rewrites the internal Python setting "
                        f"'{attr}'. Those double-underscore names control how Python "
                        f"itself works, and changing them is a recognised trick used "
                        f"to escape safety limits and run harmful code. A trading "
                        f"strategy should never need this.",
                        self._line_of(node),
                    )
                elif attr in DANGEROUS_DUNDER_READS:
                    self.error(
                        "dunder_access",
                        f"This strategy reads the internal Python value '{attr}'. That "
                        f"is the classic route used by harmful code to reach the rest "
                        f"of the computer from inside a plugin. A trading strategy "
                        f"never needs it.",
                        self._line_of(node),
                    )
                elif attr in MILD_DUNDER_READS:
                    self.warn(
                        "dunder_access_warning",
                        f"This strategy peeks at the internal Python value '{attr}' "
                        f"(often used just for printing a name). Usually harmless, but "
                        f"it is unusual in a trading strategy, so it is worth knowing.",
                        self._line_of(node),
                    )


# --------------------------------------------------------------------------
# Plain-English summary builder
# --------------------------------------------------------------------------


def _build_summary(result: ValidationResult) -> str:
    facts = result.facts or {}
    errors = result.errors()
    warnings = result.warnings()
    profile = facts.get("profile") or "moderate"

    lines: List[str] = []

    if result.ok:
        lines.append("AUTOMATIC SAFETY CHECK: PASSED.")
        lines.append(
            "Nothing in this strategy breaks the safety rules for your "
            f"'{profile}' settings."
        )
    else:
        lines.append("AUTOMATIC SAFETY CHECK: FAILED.")
        lines.append(
            f"This strategy breaks {len(errors)} safety rule"
            f"{'s' if len(errors) != 1 else ''}. Please do NOT approve it until the "
            f"problems below are fixed."
        )

    lines.append("")
    lines.append("What this strategy says about itself:")

    name = facts.get("class_name")
    lines.append(f"  - Name of the strategy: {name}" if name else "  - Name of the strategy: (not found)")

    timeframe = facts.get("timeframe")
    if isinstance(timeframe, str):
        lines.append(
            f"  - How often it looks at the market: every {timeframe} "
            f"(a 'timeframe' is just how frequently it checks prices)"
        )
    else:
        lines.append("  - How often it looks at the market: not stated properly")

    stoploss = facts.get("stoploss")
    if isinstance(stoploss, (int, float)) and not isinstance(stoploss, bool):
        lines.append(
            f"  - Stop loss: {_fmt_pct(stoploss)}. This is the automatic safety net: "
            f"if a trade goes against you by this much, it is closed. So one bad "
            f"trade could lose up to {_fmt_pct(stoploss)} of the money in that trade."
        )
    else:
        lines.append("  - Stop loss: MISSING or unreadable, so there is no known safety net")

    roi = facts.get("minimal_roi")
    if isinstance(roi, dict) and roi:
        first = roi.get("0")
        if isinstance(first, (int, float)) and not isinstance(first, bool):
            lines.append(
                f"  - Profit target: it aims to take profit once a trade is up about "
                f"{_fmt_money_ratio(first)} (its table of targets over time is: {roi})"
            )
        else:
            lines.append(f"  - Profit target: its table of targets is {roi}")
    else:
        lines.append("  - Profit target: MISSING or unreadable")

    lines.append(
        "  - Betting on prices to fall ('short selling'): "
        + ("YES" if facts.get("can_short") is True else "no" if facts.get("can_short") is False else "unclear")
    )
    lines.append(
        "  - Borrowing money to trade bigger ('leverage'): "
        + (
            "no (1x)"
            if facts.get("leverage") in (1, 1.0)
            else f"yes, {facts.get('leverage')}x" if isinstance(facts.get("leverage"), (int, float)) else "no borrowing requested (1x)"
        )
    )
    lines.append(
        "  - Buying more of a losing trade ('averaging down'): "
        + ("YES -- very dangerous" if facts.get("uses_position_adjustment") else "no")
    )

    if errors:
        lines.append("")
        lines.append(f"PROBLEMS THAT BLOCK APPROVAL ({len(errors)}):")
        for index, issue in enumerate(errors, start=1):
            where = f" (line {issue.line})" if issue.line else ""
            lines.append(f"  {index}. {issue.message}{where}")

    if warnings:
        lines.append("")
        lines.append(f"THINGS YOU SHOULD KNOW, BUT THAT DO NOT BLOCK ({len(warnings)}):")
        for index, issue in enumerate(warnings, start=1):
            where = f" (line {issue.line})" if issue.line else ""
            lines.append(f"  {index}. {issue.message}{where}")

    lines.append("")
    if result.ok:
        lines.append(
            "What this means for you: this code passed the automatic checks, so it "
            "does not do any of the obviously dangerous things. It does NOT mean the "
            "strategy will make money. An automatic check can only look for known "
            "problems, and it cannot judge whether the trading idea itself is any "
            "good."
        )
    else:
        lines.append(
            "What this means for you: do not let this strategy trade your money in "
            "its current form. You can ask for it to be fixed, or simply reject it. "
            "Nothing bad happens by saying no; approving it could lose real money."
        )

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def validate_strategy_code(
    code: str,
    *,
    profile: str = "moderate",
    max_stoploss: float = -0.15,
    min_stoploss: float = -0.02,
    allowed_timeframes: Tuple[str, ...] = DEFAULT_ALLOWED_TIMEFRAMES,
    forbidden_pair_suffixes: Tuple[str, ...] = DEFAULT_FORBIDDEN_PAIR_SUFFIXES,
) -> ValidationResult:
    """Check one generated Freqtrade strategy and decide whether it may be shown
    to a non-technical operator for approval.

    Args:
        code: The complete Python source of the generated strategy.
        profile: Risk profile name, used for the wording of messages.
        max_stoploss: Widest allowed stop loss (the most negative value), e.g.
            ``-0.15`` means a single trade may not risk more than 15%.
        min_stoploss: Tightest allowed stop loss (the least negative value),
            e.g. ``-0.02`` means a stop loss tighter than 2% is rejected as
            noise-triggered.
        allowed_timeframes: Timeframes the bot is configured to support.
        forbidden_pair_suffixes: Token name endings that indicate leveraged or
            short/inverse products.

    Returns:
        A :class:`ValidationResult`. ``ok`` is True only when no error-severity
        issue was found.

    This function never raises. Any unexpected internal failure becomes an
    ``internal_validator_error`` error issue, which blocks approval -- the
    validator fails closed, never open.
    """
    try:
        analyzer = _Analyzer(
            code=code,
            profile=profile,
            max_stoploss=max_stoploss,
            min_stoploss=min_stoploss,
            allowed_timeframes=allowed_timeframes,
            forbidden_pair_suffixes=forbidden_pair_suffixes,
        )
        return analyzer.run()
    except Exception as exc:  # pragma: no cover - absolute last resort
        issue = ValidationIssue(
            severity="error",
            code="internal_validator_error",
            message=(
                "The safety checker crashed while reading this strategy "
                f"({type(exc).__name__}: {exc}). Because the code could not be "
                "checked, it must not be approved."
            ),
        )
        return ValidationResult(
            ok=False,
            issues=[issue],
            facts={
                "class_name": None,
                "timeframe": None,
                "stoploss": None,
                "minimal_roi": None,
                "max_open_trades_in_strategy": None,
                "uses_position_adjustment": False,
                "can_short": False,
                "imports": [],
                "has_custom_stoploss": False,
                "leverage": None,
                "profile": profile,
            },
        )
