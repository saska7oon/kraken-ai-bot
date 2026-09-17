#!/usr/bin/env python3
"""Check every Freqtrade API call our client makes against a real source tree.

The orchestrator talks to Freqtrade over its REST API. Nothing in our own test
suite can tell whether ``/api/v1/locks/{id}`` is a real route, whether it takes
DELETE or POST, or whether it was renamed between releases - the tests exercise
our code, and our code would happily call a route that does not exist. The only
authority on what exists is Freqtrade's own source.

This matters more than it looks. A wrong route is not a crash: the call returns
404, our client raises FreqtradeAPIError, and a feature quietly reports "could
not reach the bot". For an operator who cannot read the logs, a feature that
never works looks identical to a feature that is simply idle.

What it checks
--------------
  * every path the client calls exists in the given Freqtrade source
  * the HTTP method matches - a GET against a POST-only route is a bug that a
    path-only check would miss entirely
  * path parameters are compared by shape, so ``/trades/{id}`` matches
    ``/trades/{tradeid}`` (the parameter name is ours, not theirs)

Routes built with f-strings are included. They are easy to overlook in review,
and one of them (the lock release) is part of the dry-run reset.

Usage
-----
    python3 tools/audit_api_routes.py --freqtrade-src /path/to/freqtrade

Exit codes:
    0  every call matches a real route
    1  at least one call does not, or the source could not be read
    2  the source tree is not a Freqtrade checkout
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO = Path(__file__).resolve().parents[1]
CLIENT = REPO / "ai_orchestrator" / "core" / "freqtrade_api.py"

# Freqtrade mounts every API router under this prefix. Read from webserver.py
# rather than assumed, so a future release that changes it is reported instead of
# silently mismatching every route.
DEFAULT_PREFIX = "/api/v1"


def _read_ft_prefixes(src: Path) -> Set[str]:
    """Prefixes Freqtrade mounts its routers under.

    Taken from the ``include_router`` calls, because that is where the prefix
    actually lives - the routers themselves are declared bare, so reading
    ``APIRouter(...)`` finds nothing and every route then looks missing.
    """
    webserver = src / "freqtrade" / "rpc" / "api_server" / "webserver.py"
    if not webserver.is_file():
        return {DEFAULT_PREFIX}
    try:
        text = webserver.read_text(encoding="utf-8")
    except OSError:
        return {DEFAULT_PREFIX}
    found = set(re.findall(r'include_router\((?:.|\n)*?prefix\s*=\s*["\']([^"\']+)["\']', text))
    return found or {DEFAULT_PREFIX}


def _ft_routes(src: Path, prefixes: Set[str]) -> Set[Tuple[str, str]]:
    """Every (METHOD, path) the Freqtrade API server exposes."""
    api_dir = src / "freqtrade" / "rpc" / "api_server"
    routes: Set[Tuple[str, str]] = set()
    for path in sorted(api_dir.glob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in re.finditer(
            r'@(\w+)\.(get|post|delete|patch|head)\(\s*["\']([^"\']*)["\']', text
        ):
            method, route = match.group(2).upper(), match.group(3)
            for prefix in prefixes:
                routes.add((method, prefix + route))
    return routes


def _client_routes() -> List[Tuple[str, str, int]]:
    """Every (METHOD, path, line) our client requests.

    Reads the AST rather than grepping, so a path is attributed to the method it
    is actually called with. A regex over the file cannot tell which method goes
    with which path when the call spans lines, and a mismatched method is exactly
    the class of bug this is looking for.
    """
    tree = ast.parse(CLIENT.read_text(encoding="utf-8"))
    out: List[Tuple[str, str, int]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "_request"):
            continue
        if len(node.args) < 2:
            continue
        method_node, path_node = node.args[0], node.args[1]
        if not isinstance(method_node, ast.Constant) or not isinstance(method_node.value, str):
            continue
        method = method_node.value.upper()

        if isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
            out.append((method, path_node.value, node.lineno))
        elif isinstance(path_node, ast.JoinedStr):
            # An f-string: keep the literal parts, mark the interpolations. This
            # is how the parameterised routes are built.
            parts = []
            for value in path_node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                else:
                    parts.append("{param}")
            out.append((method, "".join(parts), node.lineno))
        else:
            out.append((method, ast.unparse(path_node), node.lineno))

    return out


def _shape(path: str) -> str:
    """Compare paths by shape, not by parameter name.

    ``/api/v1/trades/{trade_id}`` and ``/api/v1/trades/{tradeid}`` are the same
    route; the name in braces is ours to choose. Comparing literally would report
    a mismatch that does not exist.
    """
    return re.sub(r"\{[^}]*\}", "{}", path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freqtrade-src",
        required=True,
        type=Path,
        help="Path to a Freqtrade source checkout",
    )
    parser.add_argument("--quiet", action="store_true", help="Only report problems")
    args = parser.parse_args()

    src = args.freqtrade_src.resolve()
    if not (src / "freqtrade" / "rpc" / "api_server").is_dir():
        print("ERROR: %s is not a Freqtrade source checkout" % src)
        return 2

    version = "unknown"
    try:
        init = (src / "freqtrade" / "__init__.py").read_text(encoding="utf-8")
        found = re.search(r'__version__\s*=\s*"([^"]+)"', init)
        if found:
            version = found.group(1)
    except OSError:
        pass

    prefixes = _read_ft_prefixes(src)
    real = _ft_routes(src, prefixes)
    if not real:
        print("ERROR: found no routes in %s - is this a Freqtrade checkout?" % src)
        return 2

    calls = _client_routes()
    if not calls:
        print("ERROR: found no API calls in %s" % CLIENT)
        return 2

    exact = {(method, _shape(path)) for method, path in real}
    by_shape: Dict[str, Set[str]] = {}
    for method, path in real:
        by_shape.setdefault(_shape(path), set()).add(method)

    problems: List[str] = []
    if not args.quiet:
        print("Freqtrade %s, %d route(s) mounted under %s"
              % (version, len(real), ", ".join(sorted(prefixes))))
        print("Our client makes %d call(s).\n" % len(calls))

    for method, path, line in sorted(calls, key=lambda c: c[1]):
        shape = _shape(path)
        if (method, shape) in exact:
            if not args.quiet:
                print("  ok    %-6s %s" % (method, path))
            continue
        if shape in by_shape:
            available = ", ".join(sorted(by_shape[shape]))
            message = (
                "%s:%d calls %s %s, but Freqtrade %s serves that path with %s"
                % (CLIENT.name, line, method, path, version, available)
            )
        else:
            message = (
                "%s:%d calls %s %s, which does not exist in Freqtrade %s"
                % (CLIENT.name, line, method, path, version)
            )
        problems.append(message)
        print("  FAIL  %s" % message)

    print()
    if problems:
        print("FAILED: %d of %d call(s) do not match Freqtrade %s"
              % (len(problems), len(calls), version))
        return 1

    print("PASSED: all %d call(s) match a real Freqtrade %s route and method" % (len(calls), version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
