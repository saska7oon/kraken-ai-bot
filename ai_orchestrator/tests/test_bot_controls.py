#!/usr/bin/env python3
"""Check that the operator UI offers only the bot controls that make sense.

The Controls panel is rendered from the bot's real state rather than showing
every button at once. That is not cosmetic. Freqtrade has three states and the
difference between the last two costs money to get wrong:

    RUNNING  - looking for new trades, managing open ones
    PAUSED   - not looking for new trades, still managing open ones
    STOPPED  - neither; open positions are no longer watched

The specific risk this guards is a beginner reading "Stop" as "stop buying",
pressing it, and quietly ending the management of a position that is already
open. The exchange-side stoploss survives that, but the trailing stop and the
profit target do not, so the position can drift down to the stoploss instead of
being sold on the way up.

So the UI must:

  * offer Pause, not Stop, as the obvious way to stop buying while running;
  * never offer Start when the bot is already running;
  * never offer Pause when the bot is stopped, because that does nothing;
  * always keep Stop reachable from a running or paused bot;
  * default to Start for any state it does not recognise, which is the only
    safe action to offer when the current state is unknown.

The real function is executed, not pattern-matched. A regex over the source
would pass on a branch that is never reachable, which is exactly the failure
worth catching.

Requires node. Skips with a clear message rather than failing if it is absent,
so this never becomes a reason a build cannot run.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

UI = pathlib.Path(__file__).resolve().parents[1] / "ui" / "index.html"

#: The harness runs the extracted page function against a stub DOM. `clear` must
#: model firstChild/removeChild or buttons accumulate across renders and every
#: state appears to offer every button - a harness bug that looks exactly like
#: the product bug this test exists to find.
HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");

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
    tag, className: cls || "", textContent: text || "", children: [], onclick: null,
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); },
  };
  Object.defineProperty(node, "firstChild", { get() { return this.children[0] || null; } });
  return node;
}

const nodes = {};
global.window = { confirm: () => true };
global.document = {
  getElementById: (id) => nodes[id] || (nodes[id] = makeEl("div")),
  createElement: (tag) => makeEl(tag),
};
global.$ = (id) => global.document.getElementById(id);

eval(["el", "clear", "renderBotControls", "botControl"].map(extract).join("\n\n"));

const cases = [
  ["running", 0], ["running", 2], ["paused", 0], ["paused", 3],
  ["stopped", 0], ["stopped", 1], ["STOPPED", 0], ["weird-state", 0],
];
let bad = 0;
for (const [state, open] of cases) {
  renderBotControls({ state: state, open_trades: open });
  const labels = nodes["bot-controls"].children.map((c) => c.textContent);
  const s = String(state).toLowerCase();
  const where = `state=${state} open=${open}`;

  if (labels.length === 0) { console.log(`  FAIL ${where}: no buttons rendered`); bad++; }
  if (s === "running") {
    if (!labels.includes("Pause trading"))
      { console.log(`  FAIL ${where}: running must offer Pause`); bad++; }
    if (!labels.includes("Stop the bot"))
      { console.log(`  FAIL ${where}: running must keep Stop reachable`); bad++; }
    if (labels.includes("Start trading"))
      { console.log(`  FAIL ${where}: running must not offer Start`); bad++; }
  }
  if (s === "paused") {
    if (!labels.includes("Resume trading"))
      { console.log(`  FAIL ${where}: paused must offer Resume`); bad++; }
    if (!labels.includes("Stop the bot"))
      { console.log(`  FAIL ${where}: paused must keep Stop reachable`); bad++; }
    if (labels.includes("Start trading"))
      { console.log(`  FAIL ${where}: paused must offer Resume, not a second Start`); bad++; }
  }
  if (s !== "running" && s !== "paused") {
    if (!labels.includes("Start trading"))
      { console.log(`  FAIL ${where}: an unknown/stopped state must offer Start`); bad++; }
    if (labels.includes("Pause trading"))
      { console.log(`  FAIL ${where}: pausing a bot that is not running does nothing`); bad++; }
  }
  console.log(`  ${bad === 0 ? "ok  " : "    "} ${where.padEnd(24)} [${labels.join(" | ")}]`);
}
console.log();
console.log(bad === 0 ? "PASSED - control panel offers only sensible actions"
                      : `FAILED - ${bad} problem(s)`);
process.exit(bad ? 1 : 0);
"""


def main() -> int:
    if not UI.exists():
        print(f"FAIL - UI page not found at {UI}")
        return 1

    node = shutil.which("node")
    if node is None:
        print("SKIPPED - node is not installed, so the control panel was not executed")
        print("          (this is a skip, not a pass: the behaviour was not checked)")
        return 0

    html = UI.read_text(encoding="utf-8")

    # The function under test must actually exist; otherwise node would raise a
    # less obvious error.
    for name in ("renderBotControls", "botControl"):
        if not re.search(r"function\s+" + name + r"\s*\(", html):
            print(f"FAIL - the UI page defines no {name}()")
            return 1

    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    if not scripts:
        print("FAIL - the UI page has no <script> block")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        js = pathlib.Path(tmp) / "ui.js"
        js.write_text("\n".join(scripts), encoding="utf-8")
        harness = pathlib.Path(tmp) / "harness.js"
        harness.write_text(HARNESS, encoding="utf-8")

        print("Bot control panel (which actions are offered, per state):")
        proc = subprocess.run(
            [node, str(harness), str(js)],
            capture_output=True, text=True, timeout=60,
        )

    sys.stdout.write(proc.stdout)
    if proc.stderr.strip():
        sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
