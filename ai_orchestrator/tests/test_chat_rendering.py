#!/usr/bin/env python3
"""Check that the chat actually displays the answers the server sends back.

The bug this exists to prevent, reported from a running deployment:

    operator: how's things going?
    chat:     I understood that as: show_status.

    operator: what are the market conditions?
    chat:     I understood that as: show_status.

The server was answering correctly the whole time. A status query returns

    {"status": "applied", "intent": "show_status", "changes": [...],
     "result": {"executed": [{"change": {...}, "status": "success",
                              "data": {"state": "running", "dry_run": true,
                                       "current_balance": 1000.0, ...}}]}}

and the UI read only ``message`` and ``proposed_changes``. Neither is present on
a query response, so it fell through to its placeholder branch and told the
operator it had "understood" the request. Every answer was computed, returned,
and discarded at the last step.

Two independent defects made that placeholder the only thing ever shown:

  1. nothing rendered ``result.executed[].data`` - the field holding the answer;
  2. the branch reporting success tested ``status === "executed"``, but the
     server sends ``"applied"``, so even a change that really happened was
     reported as "I understood that as: ...".

**Why this test drives ``send()`` rather than the renderer.**

The first version of this file extracted ``renderQueryResults`` and called it
directly. It passed - and it also passed with the fix reverted, because
reverting the fix removed the *call site*, not the function. A test that calls
the renderer itself can never notice that nothing else does. That is the same
mistake as the bug: the answer existed and nothing reached it.

So this executes the real entry point, ``send()``, with ``api()`` stubbed to
return the recorded response, and then inspects the chat log the operator would
actually be looking at. Reverting the fix must fail this test; that is checked
explicitly in the commit that introduced it.

Requires node. Skips with a clear message rather than failing if it is absent.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

UI = pathlib.Path(__file__).resolve().parents[1] / "ui" / "index.html"

#: The response body from the deployment, reconstructed from the server's own
#: return statements in nl_config.process_command and _apply_changes.
STATUS_RESPONSE = {
    "status": "applied",
    "intent": "show_status",
    "changes": [{"type": "query", "action": "status", "description": "Show current status"}],
    "result": {
        "executed": [
            {
                "change": {"type": "query", "action": "status"},
                "status": "success",
                "data": {
                    "state": "running",
                    "dry_run": True,
                    "open_trades": 0,
                    "max_open_trades": 3,
                    "current_balance": 1000.0,
                    "profit_pct": -1.23,
                },
            }
        ],
        "proposals": [],
        "proposals_applied": False,
        "status": "completed",
        "summary": {"failed": 0},
    },
}

HARNESS_TEMPLATE = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const cases = JSON.parse(process.argv[3]);

function extract(name) {
  const start = src.search(new RegExp("(?:async\\s+)?function\\s+" + name + "\\s*\\("));
  if (start < 0) throw new Error("function not found in the page: " + name);
  const open = src.indexOf("{", start);
  let depth = 0, i = open;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) break; }
  }
  return src.slice(start, i + 1);
}

function makeEl(tag, cls, text) {
  const node = {
    tag, className: cls || "",
    _text: text === undefined || text === null ? "" : String(text),
    children: [], onclick: null, disabled: false, value: "", scrollTop: 0,
    scrollHeight: 0,
    focus() {}, blur() {}, remove() { this.removed = true; },
    addEventListener() {}, removeEventListener() {},
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); },
  };
  Object.defineProperty(node, "textContent", {
    get() { return this.children.length ? this.children.map(c => c.textContent).join(" ") : this._text; },
    set(v) { this._text = v === undefined || v === null ? "" : String(v); this.children = []; },
  });
  Object.defineProperty(node, "firstChild", { get() { return this.children[0] || null; } });
  return node;
}

const nodes = {};
global.document = {
  getElementById: (id) => nodes[id] || (nodes[id] = makeEl("div")),
  createElement: (t) => makeEl(t),
};
global.$ = (id) => global.document.getElementById(id);

// send() touches these; none of them are what is under test.
let busy = false;
global.toast = function () {};
global.decide = function () {};
global.loadApprovals = async function () {};
global.loadStatus = async function () {};
global.signOut = function () {};
global.runPlugin = function () {};
global.PLUGIN_LABELS = {
  market_analyst: "Market analysis",
  param_optimizer: "Parameter optimization",
  strategy_generator: "Strategy generation",
};
let apiResponse = null;
global.api = async function () { return apiResponse; };

eval(["el", "money", "pct", "addMsg", "addTyping", "renderQueryResults",
      "renderRefusedPluginActions", "send"].map(extract).join("\n\n"));

function allText(n, out) {
  if (!n) return out;
  if (!(n.children || []).length) out.push(n.textContent);
  (n.children || []).forEach(c => allText(c, out));
  return out;
}
function buttons(n, out) {
  if (!n) return out;
  if (n.tag === "button") out.push(n.textContent);
  (n.children || []).forEach(c => buttons(c, out));
  return out;
}

(async () => {
  let bad = 0;
  for (const c of cases) {
    // Fresh chat log per case.
    nodes["chat-log"] = makeEl("div");
    nodes["chat-in"] = makeEl("input");
    nodes["send-btn"] = makeEl("button");
    busy = false;
    apiResponse = c.response;

    try {
      await send(c.prompt);
    } catch (e) {
      console.log(`  FAIL ${c.name}: send() threw ${e.message}`);
      bad++;
      continue;
    }

    const text = allText(nodes["chat-log"], []).join(" | ");
    const btns = buttons(nodes["chat-log"], []);
    const problems = [];

    for (const want of (c.mustContain || []))
      if (!text.includes(want)) problems.push("missing " + JSON.stringify(want));
    for (const want of (c.mustNotContain || []))
      if (text.includes(want)) problems.push("should not contain " + JSON.stringify(want));
    for (const want of (c.mustButton || []))
      if (!btns.includes(want)) problems.push("missing button " + JSON.stringify(want)
        + " (got " + JSON.stringify(btns) + ")");
    for (const want of (c.mustNotButton || []))
      if (btns.includes(want)) problems.push("unexpected button " + JSON.stringify(want));

    if (!c.mustContain && !c.mustNotContain && !c.mustButton && !c.mustNotButton) {
      problems.push("case asserts nothing");
    }

    if (problems.length) {
      bad += problems.length;
      problems.forEach(p => console.log(`  FAIL ${c.name}: ${p}`));
      console.log(`        chat log was: ${text}`);
    } else {
      console.log(`  ok   ${c.name.padEnd(36)} [${text.slice(0, 76)}]`);
    }
  }
  console.log("");
  if (bad) { console.log("FAILED - " + bad + " problem(s)"); process.exit(1); }
  console.log("PASSED - the chat displays what the server returns");
})();
"""


def main() -> int:
    if not shutil.which("node"):
        print("SKIPPED - node is not installed, so the chat cannot be executed.")
        print("          This is a skip, not a pass: nothing was verified.")
        return 0

    cases = [
        {
            "name": "a status question shows the data",
            "prompt": "how's things going?",
            "response": STATUS_RESPONSE,
            # The operator asked a plain question and must see the answer.
            "mustContain": ["Trading", "Dry run", "Balance", "1,000.00", "Profit", "-1.23%"],
            "mustNotContain": ["I understood that as"],
        },
        {
            "name": "live mode is called out",
            "prompt": "status",
            "response": {
                "status": "applied", "intent": "show_status",
                "result": {"executed": [{"status": "success",
                           "data": {"state": "running", "dry_run": False,
                                    "current_balance": 500.0}}]},
            },
            "mustContain": ["LIVE", "real money"],
        },
        {
            "name": "a failed query shows its error",
            "prompt": "status",
            "response": {
                "status": "applied", "intent": "show_status",
                "result": {"executed": [{"status": "failed",
                           "error": "trader is not running"}]},
            },
            "mustContain": ["trader is not running"],
        },
        {
            "name": "an applied change is not called comprehension",
            "prompt": "pause trading",
            "response": {"status": "applied", "intent": "pause_resume"},
            "mustContain": ["Done"],
            "mustNotContain": ["I understood that as"],
        },
        {
            "name": "an unclear reply is reported honestly",
            "prompt": "blah",
            "response": {"status": "unclear", "intent": "unknown",
                         "message": "I could not understand that."},
            "mustContain": ["could not understand"],
        },
        {
            # A refusal must not be dressed up as comprehension either.
            "name": "a refusal shows the refusal text",
            "prompt": "what are the market conditions?",
            "response": {
                "status": "refused", "intent": "market_analysis",
                "message": "I did not make that change. Here is why:",
                "refused_changes": [{"type": "trigger", "action": "market_analyst",
                                     "description": "Run the market_analyst plugin now"}],
            },
            "mustContain": ["I did not make that change"],
            "mustButton": ["Run Market analysis now"],
        },
        {
            "name": "a plain refusal adds no button",
            "prompt": "do something odd",
            "response": {"status": "refused", "intent": "unknown",
                         "message": "Refused.", "refused_changes": []},
            "mustContain": ["Refused."],
            "mustNotButton": ["Run Market analysis now"],
        },
    ]

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(HARNESS_TEMPLATE)
        harness = fh.name

    try:
        proc = subprocess.run(
            ["node", harness, str(UI), json.dumps(cases)],
            capture_output=True, text=True, timeout=120,
        )
    finally:
        pathlib.Path(harness).unlink(missing_ok=True)

    print(proc.stdout.rstrip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.rstrip())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
