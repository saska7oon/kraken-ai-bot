"""
Operator UI regression tests.
=============================

Standalone (no pytest):

    python3 ai_orchestrator/tests/test_ui.py

Why this file exists
--------------------
The UI renders text that came from a language model - the daily digest is
model-written prose. If any of it reached the DOM through ``innerHTML``, a
confused or hostile model could inject script into the operator's browser, in a
page that holds a token which can pause trading and approve changes. The page
therefore writes every API string with ``textContent``, and that property is
asserted here rather than trusted.

Three other things are worth a test:

1. **No external resources.** The Pi may have no route to the internet. A page
   that pulls fonts or icons from a CDN renders as broken text when it does, and
   it leaks the operator's IP to a third party every time they open it.
2. **No invented endpoints.** The UI calls the API by path. A typo produces a
   button that silently does nothing, which is exactly the kind of failure a
   non-technical operator cannot diagnose. Every path the page calls is checked
   against the routes that actually exist in ``main.py``.
3. **The page is served, and served without auth.** The route must exist and
   must not require a token: the page contains no secrets, and demanding a token
   to fetch it would only mean pasting the token twice.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
from typing import List, Set, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
UI_FILE = REPO_ROOT / "ai_orchestrator" / "ui" / "index.html"
MAIN_PY = REPO_ROOT / "ai_orchestrator" / "main.py"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Remove HTML and JS comments, so prose about a danger is not mistaken for it."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # Line comments, but not the // inside "https://".
    text = re.sub(r"(?m)(?<![:\w])//[^\n]*$", "", text)
    return text


def _routes_in_main() -> Set[str]:
    """Every path declared with @app.<verb>("...").

    Parsed from source rather than imported: importing main.py would need
    FastAPI, which is not installed everywhere this test must run.
    """
    tree = ast.parse(_read(MAIN_PY))
    routes: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr in ("get", "post", "put", "delete", "patch")
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)
                ):
                    routes.add(dec.args[0].value)
    return routes


def _keys_returned_by(path: str) -> Set[str]:
    """Field names a route's handler returns.

    Collected from the handler's dict literals *and* from
    ``response["key"] = ...`` assignments, because several routes build their
    payload incrementally (``/api/v1/safety`` does exactly this). Only the
    handler bound to the requested path is inspected, so a variable name reused
    across handlers cannot leak another handler's fields into the result.
    """
    tree = ast.parse(_read(MAIN_PY))

    handler = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.args
                and isinstance(dec.args[0], ast.Constant)
                and dec.args[0].value == path
            ):
                handler = node
    if handler is None:
        return set()

    keys: Set[str] = set()
    for sub in ast.walk(handler):
        if isinstance(sub, ast.Dict):
            for k in sub.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
        # response["key"] = ...
        elif isinstance(sub, ast.Assign) and isinstance(sub.targets[0], ast.Subscript):
            sl = sub.targets[0].slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                keys.add(sl.value)
    return keys


#: DOM properties and JS builtins that share a variable's name but are not
#: response fields. Without this the check reports `t.append` and `d.get` as
#: missing API fields.
_NOT_RESPONSE_FIELDS = {
    "append", "appendChild", "classList", "className", "textContent", "style",
    "length", "push", "forEach", "map", "filter", "slice", "join", "get",
    "onclick", "value", "textContent", "remove", "then", "catch", "finally",
    "toLowerCase", "toUpperCase", "trim", "split", "includes", "indexOf",
    "toString", "keys", "values", "entries", "has", "add", "delete", "set",
}


def _ui_field_bindings(script: str) -> List[Tuple[str, str, int]]:
    """(variable, api_path, line) for each ``const X = await api("...")``.

    Ties a response variable to the route that produced it, so fields can be
    checked against the right handler. Guessing by variable name alone is what
    made an earlier version of this check report false positives - ``s`` is used
    for both the status and the safety response, and ``p`` for both a proposal
    and a protection.
    """
    out: List[Tuple[str, str, int]] = []
    pattern = re.compile(
        r"""(?:const|let|var)\s+(\w+)\s*=\s*await\s+api\(\s*["'](/api/[^"'`\s]*)["']"""
    )
    for m in pattern.finditer(script):
        out.append((m.group(1), m.group(2), script[: m.start()].count("\n") + 1))
    return out


def _js_functions(script: str) -> List[Tuple[str, str]]:
    """(name, body) for each top-level ``function`` / ``async function``.

    Field checking has to be function-scoped. The UI reuses short variable names
    across handlers - ``s`` for both the status and the safety response, ``d``
    for the digest, trades and proposals, ``r`` for both a command reply and an
    approve reply. A script-wide scan therefore attributes one handler's fields
    to another handler's response and reports mismatches that do not exist. That
    is precisely the false-positive trap this check exists to avoid, so it is
    scoped properly rather than loosened until it passes.
    """
    out: List[Tuple[str, str]] = []
    pattern = re.compile(r"(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{")
    for m in pattern.finditer(script):
        depth = 1
        i = m.end()
        while i < len(script) and depth:
            if script[i] == "{":
                depth += 1
            elif script[i] == "}":
                depth -= 1
            i += 1
        out.append((m.group(1), script[m.end(): i - 1]))
    return out


def _fields_read(script: str, var: str) -> Set[str]:
    """Response fields read off a variable: ``X.field``."""
    names = set(re.findall(r"\b%s\.([A-Za-z_]\w*)" % re.escape(var), script))
    return {n for n in names if n not in _NOT_RESPONSE_FIELDS}


def _paths_called_by_ui(script: str) -> List[Tuple[str, int]]:
    """Literal API paths the UI requests, with line numbers.

    Paths assembled by concatenation are resolved too. The plugin-control call is
    written as ``"/api/v1/plugins/" + encodeURIComponent(name) + "/control"``;
    matching only the leading literal would check ``/api/v1/plugins/`` against
    the *list* route, which exists - so a typo in ``control`` would pass. The
    literal segments are joined with a placeholder and the assembled path is
    what gets verified.
    """
    found: List[Tuple[str, int]] = []

    # Concatenated: "/api/v1/x/" + expr + "/y"
    concat = re.compile(
        r"""["'](/api/[^"'`\s]*)["']\s*(?:\+\s*[^"';]+\+\s*["']([^"']*)["']\s*)+"""
    )
    consumed: List[Tuple[int, int]] = []
    for match in concat.finditer(script):
        head = match.group(1)
        tail = "".join(match.groups()[1:])
        consumed.append(match.span())
        found.append((head + "*" + tail, script[: match.start()].count("\n") + 1))

    # Plain literals not already part of a concatenation.
    for match in re.finditer(r"""["'](/api/[^"'`\s]*)["']""", script):
        if any(start <= match.start() < end for start, end in consumed):
            continue
        found.append((match.group(1), script[: match.start()].count("\n") + 1))

    return found


def _endpoint_ok(called: str, routes: Set[str]) -> bool:
    """Does a called path correspond to a real route?

    Query strings are stripped, ``*`` stands for a concatenated segment, and a
    route declared with a path parameter
    (``/api/v1/plugins/{plugin_name}/control``) matches a concrete call.
    """
    path = called.split("?")[0].rstrip("/") or "/"
    if path in routes:
        return True
    for route in routes:
        if "{" not in route:
            continue
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", route) + "$"
        if re.match(pattern, path.replace("*", "x")):
            return True
    return False


def main() -> int:
    failures: List[str] = []

    if not UI_FILE.exists():
        print(f"FAIL - UI file missing: {UI_FILE}")
        return 1

    raw = _read(UI_FILE)
    code = _strip_comments(raw)
    routes = _routes_in_main()

    print(f"UI file: {UI_FILE.relative_to(REPO_ROOT)}  ({len(raw):,} bytes)")
    print(f"Routes found in main.py: {len(routes)}")
    print()

    # ---- 1. no HTML injection sinks -------------------------------------
    print("HTML injection sinks (model prose is rendered by this page):")
    sinks = [
        "innerHTML", "outerHTML", "insertAdjacentHTML",
        "document.write", "eval(", "new Function(", "srcdoc",
    ]
    bad_sinks = [s for s in sinks if s in code]
    if bad_sinks:
        for s in bad_sinks:
            failures.append(f"HTML sink {s!r} present in live code")
            print(f"  FAIL  {s} present in live code")
    else:
        print("  ok    none (all API strings go through textContent)")

    # ---- 2. no external resources ---------------------------------------
    print()
    print("External resources (the Pi may have no internet):")
    external = re.findall(r"""(?:src|href)\s*=\s*["'](https?:)?//[^"']+""", code)
    if external:
        for e in external:
            failures.append(f"external resource: {e}")
            print(f"  FAIL  {e}")
    else:
        print("  ok    none")

    # ---- 3. every called endpoint exists --------------------------------
    print()
    print("API paths the UI calls:")
    calls = _paths_called_by_ui(code)
    if not calls:
        failures.append("UI calls no API paths - did the script get stripped?")
        print("  FAIL  no API paths found")
    seen: Set[str] = set()
    for path, line in calls:
        if path in seen:
            continue
        seen.add(path)
        if _endpoint_ok(path, routes):
            print(f"  ok    {path}")
        else:
            failures.append(f"UI calls {path} (line {line}) which main.py does not define")
            print(f"  FAIL  {path}  (line {line}) - no such route")

    # ---- 4. the route exists and is unauthenticated ---------------------
    print()
    print("Serving route:")
    if "/" not in routes:
        failures.append("no '/' route in main.py")
        print("  FAIL  no '/' route")
    else:
        print("  ok    '/' is registered")

    tree = ast.parse(_read(MAIN_PY))
    ui_fn = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "operator_ui":
            ui_fn = node
    if ui_fn is None:
        failures.append("operator_ui handler not found")
        print("  FAIL  operator_ui handler not found")
    else:
        # The handler must not depend on the auth dependency.
        deps = [ast.unparse(d) for d in ui_fn.args.defaults]
        if any("require_api_token" in d for d in deps):
            failures.append("operator_ui requires a token; the page holds no secrets")
            print("  FAIL  operator_ui requires authentication")
        else:
            print("  ok    unauthenticated (the page contains no secrets)")

    # ---- 5. the page must ship in the image -----------------------------
    print()
    print("Packaging:")
    dockerfile = REPO_ROOT / "ai_orchestrator" / "Dockerfile"
    if dockerfile.exists():
        df = _read(dockerfile)
        if "COPY ai_orchestrator/ /app/ai_orchestrator/" in df:
            print("  ok    Dockerfile copies the whole package, so ui/ ships")
        else:
            failures.append("Dockerfile no longer copies the package wholesale; ui/ may not ship")
            print("  FAIL  ui/ may not be copied into the image")
    else:
        print("  --    Dockerfile not found, skipped")

    # ---- 6. it must not add capability ----------------------------------
    print()
    print("Capability (the UI is a display layer, not a new control surface):")
    writes = sorted({
        p for p, _ in calls
        if not p.startswith(("/api/v1/status", "/api/v1/balance", "/api/v1/performance",
                             "/api/v1/trades", "/api/v1/safety", "/api/v1/whitelist",
                             "/api/v1/explain", "/api/v1/proposals", "/api/v1/plugins",
                             "/api/v1/audit", "/api/v1/health"))
    })
    allowed_writes = {
        "/api/v1/command", "/api/v1/approve", "/api/v1/plugins/{plugin_name}/control",
    }
    unexpected = [w for w in writes if w not in allowed_writes]
    if unexpected:
        for w in unexpected:
            failures.append(f"UI calls {w}, which is not a known read or approved action")
            print(f"  FAIL  {w} is not a recognised endpoint")
    else:
        print("  ok    only existing reads plus command/approve/plugin-control")
        print(f"        write-capable paths: {', '.join(writes) if writes else 'none'}")

    # ---- 7. the fields it reads must exist in the response ---------------
    # A field-name mismatch is invisible at review time and shows the operator a
    # bare em-dash where a number should be - the exact failure a non-technical
    # user cannot diagnose. Bind each response variable to the route that
    # produced it and check the fields against that handler's returned keys.
    print()
    print("Response fields the UI reads (checked against each handler):")
    checked = 0
    for fname, body in _js_functions(code):
        bindings = _ui_field_bindings(body)
        for var, path, line in bindings:
            real_path = path.split("?")[0].rstrip("/") or "/"
            # Routes with a path parameter have no statically known shape.
            if any("{" in r and _endpoint_ok(real_path, {r}) for r in routes):
                continue
            known = _keys_returned_by(real_path)
            if not known:
                continue
            read = _fields_read(body, var)
            missing = sorted(f for f in read if f not in known)
            checked += 1
            if missing:
                failures.append(
                    f"{fname}() reads {var}.{missing} from {real_path}, "
                    f"but that handler returns {sorted(known)}"
                )
                print(f"  FAIL  {fname}() {real_path}: reads {missing}, not returned")
            else:
                print(f"  ok    {fname}() {real_path}  ({len(read)} field(s), all present)")
    if checked == 0:
        failures.append("no response bindings could be checked")
        print("  FAIL  nothing checked")

    print()
    print("=" * 68)
    if failures:
        print(f"FAILED - {len(failures)} problem(s)")
        for f in failures:
            print("   - " + f)
        return 1
    print("PASSED - UI is injection-safe, self-contained and uses only real endpoints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
