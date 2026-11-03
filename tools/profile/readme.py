#!/usr/bin/env python3
"""Rewrites the generated blocks of README.md (between <!-- name:start --> and <!-- name:end -->)."""
import datetime as dt
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
README = HERE.parent.parent / "README.md"
CONFIG = json.loads((HERE / "config.json").read_text())


def md(text):
    return re.sub(r"([\\`*\[\]<>])", r"\\\1", text)


def replace_block(text, name, content):
    pattern = re.compile(rf"(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README.md has no <!-- {name}:start/end --> markers")
    return pattern.sub(lambda m: m.group(1) + content + "\n" + m.group(2), text)


def forest(s):
    best = dt.date.fromisoformat(s["best_day"])
    alt = (f"Contribution forest: an isometric strip through the four seasons with one tree per active day "
           f"of the last year. {s['total']:,} contributions, {s['active']} trees, the tallest on "
           f"{best:%b} {best.day} with {s['best']}.")
    return f'<img src="./assets/forest.svg" width="100%" alt="{alt}">'


def pull_line(p):
    tags, rest = re.match(r"((?:\[[^\]]*\]\s*)*)(.*)", p["title"]).groups()
    module, _, what = rest.partition(": ")
    label = f"**{md(module)}**: {md(what)}" if what else md(rest)
    icon = "🟣" if p["merged"] else "🟢" if p["state"] == "open" else "⚪"
    day = dt.date.fromisoformat(p["created"])
    meta = " · ".join([p["repo"], *re.findall(r"\[([^\]]*)\]", tags), f"{day:%b} {day.day}"])
    return f"- {icon} [{label}]({p['url']}) <sub>{md(meta)}</sub>"


def main():
    stats = json.loads((HERE / "data/stats.json").read_text())
    pulls = json.loads((HERE / "data/pulls.json").read_text())[:CONFIG["latest_pulls"]]
    text = README.read_text()
    text = replace_block(text, "forest", forest(stats))
    text = replace_block(text, "pulls", "\n".join(map(pull_line, pulls)) + "\n\n<sub>🟣 merged · 🟢 open · ⚪ closed</sub>")
    README.write_text(text)


if __name__ == "__main__":
    main()
