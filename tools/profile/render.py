#!/usr/bin/env python3
"""Draws the profile SVGs (header, contribution forest, project cards) from tools/profile/data/.

Standard library only. Every random choice is seeded, so the same data gives the same SVG,
and each day's tree is seeded by its date, so trees keep their look as the year rolls on.
"""
import datetime as dt
import html
import json
import math
import random
import re
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
ASSETS = HERE.parent.parent / "assets"
CONFIG = json.loads((HERE / "config.json").read_text())

MONO = "'JetBrains Mono','SF Mono',SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
INK, BODY, MUTED, GREEN, GOLD = "#ece6f5", "#cfc8dc", "#8f87a0", "#9be08a", "#ffd29a"
SKY = ('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
       '<stop offset="0" stop-color="#141329"/><stop offset="1" stop-color="#2b2140"/></linearGradient>')

SEASON = ["winter", "winter", "spring", "spring", "spring", "summer",
          "summer", "summer", "autumn", "autumn", "autumn", "winter"]
SEASONS = {  # ground, crowns
    "winter": ("#dfe6ee", ["#2f5d50", "#3a6b5c"]),
    "spring": ("#93cf7f", ["#f5a8c9", "#f7c4da", "#8fd174"]),
    "summer": ("#5fae5a", ["#3d8b45", "#2f6f3c", "#4f9d4a"]),
    "autumn": ("#b9a35c", ["#e08a3c", "#c9483a", "#e8b84a"]),
}
TREE_SCALE = [0, .7, .95, 1.2, 1.55]


# ---------------------------------------------------------------- data

def load():
    cal = json.loads((DATA / "calendar.json").read_text())
    days = sorted((dt.date.fromisoformat(d), c) for d, c in cal.items())
    return days, json.loads((DATA / "pulls.json").read_text())


def summarize(days, pulls):
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    best_day, best = max(days, key=lambda x: x[1])
    return {
        "total": sum(c for _, c in days),
        "active": sum(1 for _, c in days if c),
        "best_day": best_day.isoformat(),
        "best": best,
        "longest": longest,
        "pulls": len(pulls),
        "merged": sum(p["merged"] for p in pulls),
    }


def weeks(days):
    """Columns of GitHub's calendar: weeks starting on Sunday."""
    cols = []
    for d, c in days:
        if not cols or d.weekday() == 6:
            cols.append([])
        cols[-1].append((d, c))
    return cols


def months(days):
    rows = {}
    for d, c in days:
        rows.setdefault((d.year, d.month), []).append((d, c))
    return list(rows.items())


def level(c, top):
    return 0 if not c else min(4, 1 + int(3.999 * math.sqrt(c / top)))


def fmt_day(d):
    return f"{d:%b} {d.day}"


def esc(text):
    return html.escape(text, quote=False)


def svg(w, h, body, style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f"<style>{style}</style>{body}</svg>\n")


def shade(hex_, f):
    r, g, b = (int(hex_[k:k + 2], 16) for k in (1, 3, 5))
    cl = lambda v: max(0, min(255, round(v * f)))
    return f"#{cl(r):02x}{cl(g):02x}{cl(b):02x}"


def stars(rnd, w, h, n):
    return "".join(f'<circle cx="{rnd.uniform(0, w):.0f}" cy="{rnd.uniform(0, h):.0f}" r="{rnd.uniform(.4, 1.1):.1f}" '
                   f'fill="#fff" opacity="{rnd.uniform(.15, .55):.2f}"/>' for _ in range(n))


# ---------------------------------------------------------------- trees and isometric tiles

def tree_pine(x, y, s, col, snow):
    o = [f'<rect x="{x - 1.5 * s:.1f}" y="{y - 6 * s:.1f}" width="{3 * s:.1f}" height="{6 * s:.1f}" fill="#5b3d2b"/>']
    for k in range(3):
        w = 20 * s * (1 - .24 * k)
        by = y - 4 * s - k * 8.5 * s
        ay = by - 15 * s
        o.append(f'<path d="M{x:.1f},{ay:.1f}L{x - w / 2:.1f},{by:.1f}L{x:.1f},{by:.1f}Z" fill="{shade(col, .78)}"/>'
                 f'<path d="M{x:.1f},{ay:.1f}L{x:.1f},{by:.1f}L{x + w / 2:.1f},{by:.1f}Z" fill="{col}"/>')
        if snow:
            o.append(f'<path d="M{x:.1f},{ay:.1f}L{x - w * .18:.1f},{ay + 5.5 * s:.1f}'
                     f'L{x + w * .18:.1f},{ay + 5.5 * s:.1f}Z" fill="#f4f8fc"/>')
    return "".join(o)


def tree_round(x, y, s, col):
    r = 9 * s
    cy = y - 11 * s - r * .75
    return (f'<rect x="{x - 1.6 * s:.1f}" y="{y - 12 * s:.1f}" width="{3.2 * s:.1f}" height="{12 * s:.1f}" fill="#5b3d2b"/>'
            f'<circle cx="{x:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{shade(col, .8)}"/>'
            f'<circle cx="{x + r * .22:.1f}" cy="{cy - r * .22:.1f}" r="{r * .72:.1f}" fill="{col}"/>'
            f'<circle cx="{x + r * .38:.1f}" cy="{cy - r * .42:.1f}" r="{r * .26:.1f}" fill="{shade(col, 1.18)}"/>')


def tree_for(d, rnd):
    """The tree of one day: kind and colour follow the season."""
    name = SEASON[d.month - 1]
    col = rnd.choice(SEASONS[name][1])
    pine = name == "winter" or (name == "summer" and rnd.random() < .4)
    return tree_pine if pine else tree_round, col, name == "winter"


def iso(i, j, z, o):
    ox, oy, tw, th = o
    return ox + (i - j) * tw / 2, oy + (i + j) * th / 2 - z


def prism(i, j, z0, z1, top, left, right, o):
    P = lambda a, b, z: "%.1f,%.1f" % iso(a, b, z, o)
    N, E, S, W = (i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)
    return (f'<polygon points="{P(*W, z1)} {P(*S, z1)} {P(*S, z0)} {P(*W, z0)}" fill="{left}"/>'
            f'<polygon points="{P(*S, z1)} {P(*E, z1)} {P(*E, z0)} {P(*S, z0)}" fill="{right}"/>'
            f'<polygon points="{P(*N, z1)} {P(*E, z1)} {P(*S, z1)} {P(*W, z1)}" fill="{top}"/>')


# ---------------------------------------------------------------- the forest

def render_forest(days, s):
    W, H = 1200, 700
    o = (232, 170, 32, 16)
    top = s["best"]
    best_day = dt.date.fromisoformat(s["best_day"])
    # (week, weekday with Sunday = 0, date, count), back to front
    cells = sorted(((i, (d.weekday() + 1) % 7, d, c) for i, col in enumerate(weeks(days)) for d, c in col),
                   key=lambda t: (t[0] + t[1], t[0]))

    out = [f'<defs>{SKY}<radialGradient id="sun"><stop offset="0" stop-color="#ff9e7a" stop-opacity=".45"/>'
           '<stop offset="1" stop-color="#ff9e7a" stop-opacity="0"/></radialGradient></defs>',
           f'<rect width="{W}" height="{H}" rx="16" fill="url(#sky)"/>',
           '<circle cx="1040" cy="560" r="260" fill="url(#sun)"/>',
           stars(random.Random(3), W, 260, 60)]

    for i, j, d, c in cells:
        g = shade(SEASONS[SEASON[d.month - 1]][0], 1.04 if (i + j) % 2 else .96)
        out.append(prism(i, j, -8, 0, g, shade(g, .72), shade(g, .56), o))

    prev = None
    for i, col in enumerate(weeks(days)):
        name = SEASON[col[len(col) // 2][0].month - 1]
        if name != prev:
            x, y = iso(i + .4, 7, -8, o)
            out.append(f'<text x="{x:.1f}" y="{y + 18:.1f}" transform="rotate(26.57 {x:.1f} {y + 18:.1f})" '
                       f'font-family="{MONO}" font-size="13" letter-spacing="2" fill="{MUTED}">{name}</text>')
        prev = name

    particles = []
    for i, j, d, c in cells:
        rnd = random.Random(d.toordinal())
        x, y = iso(i + .5, j + .5, 0, o)
        if c:
            sc = TREE_SCALE[level(c, top)]
            draw, col, snow = tree_for(d, rnd)
            out.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{8 * sc:.1f}" ry="{4 * sc:.1f}" fill="#000" opacity=".18"/>')
            out.append(draw(x, y, sc, col, snow) if draw is tree_pine else draw(x, y, sc, col))
            if d == best_day:
                ty = y - 62 * sc
                sign, anchor = (1, "start") if x < 900 else (-1, "end")
                out.append(f'<path d="M{x:.1f},{ty - 4:.1f} L{x + sign * 40:.1f},{ty - 40:.1f} H{x + sign * 220:.1f}" '
                           f'fill="none" stroke="{GOLD}" stroke-width="1"/>'
                           f'<text x="{x + sign * 44:.1f}" y="{ty - 47:.1f}" text-anchor="{anchor}" font-family="{MONO}" '
                           f'font-size="14" fill="{GOLD}">tallest tree · {fmt_day(d)} · {c}</text>')
        season = SEASON[d.month - 1]
        if season == "winter" and rnd.random() < .22:
            particles.append(f'<circle class="sn" cx="{x + rnd.uniform(-10, 10):.1f}" cy="{y - rnd.uniform(30, 70):.1f}" '
                             f'r="{rnd.uniform(1, 1.8):.1f}" fill="#fff" style="animation-delay:-{rnd.uniform(0, 7):.1f}s"/>')
        if season == "autumn" and rnd.random() < .1:
            particles.append(f'<ellipse class="lf" cx="{x + rnd.uniform(-10, 10):.1f}" cy="{y - rnd.uniform(30, 60):.1f}" '
                             f'rx="2.6" ry="1.3" fill="{rnd.choice(SEASONS["autumn"][1])}" '
                             f'style="animation-delay:-{rnd.uniform(0, 5):.1f}s"/>')
    out += particles

    lines = [f'<tspan fill="{GREEN}" font-weight="700">{s["total"]:,}</tspan> contributions · last 365 days',
             f'{s["active"]} trees planted · four seasons',
             f'longest grove: {s["longest"]} days in a row']
    out.append(f'<g font-family="{MONO}" font-size="21" fill="{BODY}" text-anchor="end">'
               f'<text x="1150" y="78" font-size="14" letter-spacing="3" fill="{MUTED}">THE CONTRIBUTION FOREST</text>'
               + "".join(f'<text x="1150" y="{122 + k * 36}">{ln}</text>' for k, ln in enumerate(lines)) + "</g>")
    out.append(f'<text x="40" y="662" font-family="{MONO}" font-size="15" fill="{MUTED}">seedling</text>')
    out += [tree_round(140 + k * 28, 668, TREE_SCALE[k], "#4f9d4a") for k in range(1, 5)]
    out.append(f'<text x="286" y="662" font-family="{MONO}" font-size="15" fill="{MUTED}">old oak</text>')
    style = ("@keyframes fall{0%{transform:translate(0,-26px);opacity:0}20%{opacity:.95}"
             "100%{transform:translate(9px,42px);opacity:0}}"
             ".sn{animation:fall 7s linear infinite}.lf{animation:fall 5s ease-in infinite}")
    return svg(W, H, "".join(out), style)


# ---------------------------------------------------------------- header

def render_header(days, s):
    W, H = 1200, 330
    out = [f'<defs>{SKY}<radialGradient id="sun"><stop offset="0" stop-color="#ff9e7a" stop-opacity=".4"/>'
           '<stop offset="1" stop-color="#ff9e7a" stop-opacity="0"/></radialGradient></defs>',
           f'<rect width="{W}" height="{H}" rx="16" fill="url(#sky)"/>',
           '<circle cx="960" cy="330" r="300" fill="url(#sun)"/>',
           stars(random.Random(1), W, 200, 45),
           f'<text x="64" y="94" font-family="{MONO}" font-size="16" letter-spacing="4" fill="{MUTED}">HI, I\'M</text>',
           f'<text x="60" y="164" font-family="{SANS}" font-size="64" font-weight="800" fill="{INK}">'
           f'{esc(CONFIG["name"])}</text>',
           f'<text x="64" y="212" font-family="{MONO}" font-size="22" fill="{BODY}">{esc(CONFIG["role"])}</text>',
           f'<text x="64" y="258" font-family="{MONO}" font-size="16" font-style="italic" fill="{MUTED}">'
           f'“{esc(CONFIG["tagline"])}”</text>']

    # one tree per month of the last year, sized by that month's contributions
    rows = months(days)[-12:]
    peak = max(sum(c for _, c in r) for _, r in rows)
    out.append('<ellipse cx="960" cy="336" rx="250" ry="44" fill="#243a2f"/>')
    for k, ((y, mo), r) in enumerate(rows):
        total = sum(c for _, c in r)
        x = 780 + k * 34
        base = 300 - 14 * math.sin(math.pi * (k + .5) / len(rows))
        sc = .55 + 1.25 * math.sqrt(total / peak)
        draw, col, snow = tree_for(dt.date(y, mo, 15), random.Random(y * 12 + mo))
        out.append(draw(x, base, sc, col, snow) if draw is tree_pine else draw(x, base, sc, col))
        out.append(f'<text x="{x}" y="{base + 18:.1f}" text-anchor="middle" font-family="{MONO}" font-size="11" '
                   f'fill="{MUTED}">{dt.date(y, mo, 1):%b}</text>')
    return svg(W, H, "".join(out))


# ---------------------------------------------------------------- project cards

def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return lines + [cur] if cur else lines


def repo_facts(repo, pulls):
    mine = [p for p in pulls if p["repo"] == repo]
    mods, versions = [], set()
    for p in reversed(mine):  # oldest first, so the modules read in the order they were built
        m = re.search(r"\]\s*([a-z][a-z0-9_]+)\s*(?::|$)", p["title"])
        if m and m.group(1) not in mods:
            mods.append(m.group(1))
        versions.update(re.findall(r"\[(\d+\.0)\]", p["title"]))
    return mine, mods, sorted(versions, key=float)


def card_layout(item, pulls, W, f):
    """Everything but the frame and the footer. Returns the parts and the y where content ends."""
    org, name = item["repo"].split("/")
    mine, mods, _ = repo_facts(item["repo"], pulls)
    pad, cw = 36, f * .6
    stat = f"{len(mine)} PRs · {sum(p['merged'] for p in mine)} merged"
    parts = [f'<text x="{pad}" y="{pad + f * 1.5:.0f}" font-family="{MONO}" font-size="{f * 1.5:.0f}">'
             f'<tspan fill="{MUTED}">{esc(org)} / </tspan><tspan fill="{INK}" font-weight="800">{esc(name)}</tspan></text>']
    y = pad + f * 1.5 + f * 1.9
    # the PR count sits right of the title when both fit, otherwise on its own line below
    if (len(f"{org} / {name}") * 1.5 + len(stat) * .85) * cw + 24 < W - 2 * pad:
        parts.append(f'<text x="{W - pad}" y="{pad + f * 1.3:.0f}" text-anchor="end" font-family="{MONO}" '
                     f'font-size="{f * .85:.0f}" fill="{GREEN}">{stat}</text>')
    else:
        parts.append(f'<text x="{pad}" y="{y - f * .3:.0f}" font-family="{MONO}" font-size="{f * .85:.0f}" '
                     f'fill="{GREEN}">{stat}</text>')
        y += f * 1.5
    for line in wrap(item["text"], int((W - 2 * pad) / cw)):
        parts.append(f'<text x="{pad}" y="{y:.0f}" font-family="{MONO}" font-size="{f}" fill="{BODY}">{esc(line)}</text>')
        y += f * 1.45
    y += f * .9
    x, cf = pad, f * .8
    for mod in mods:
        w = len(mod) * cf * .6 + 22
        if x + w > W - pad:
            x, y = pad, y + cf * 2.1
        parts.append(f'<rect x="{x:.0f}" y="{y - cf * 1.15:.0f}" width="{w:.0f}" height="{cf * 1.6:.0f}" rx="8" fill="#2c2548"/>'
                     f'<text x="{x + 11:.0f}" y="{y:.0f}" font-family="{MONO}" font-size="{cf:.0f}" fill="#cdbdff">'
                     f'{esc(mod)}</text>')
        x += w + 9
    return parts, y + cf * .6


def card_svg(item, pulls, W, H, f, parts):
    pad = 36
    _, _, versions = repo_facts(item["repo"], pulls)
    odoo = [f"Odoo {versions[0]}" + (f" → {versions[-1]}" if len(versions) > 1 else "")] if versions else []
    footer = " · ".join(odoo + item.get("tags", []))
    return svg(W, H, "".join([
        f"<defs>{SKY}</defs>",
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="url(#sky)" stroke="#3a3354"/>',
        *parts,
        f'<text x="{pad}" y="{H - pad + 6}" font-family="{MONO}" font-size="{f * .8:.0f}" fill="{MUTED}">{esc(footer)}</text>',
        tree_round(W - pad - 8, H - pad + 8, f / 15, "#4f9d4a"),
        tree_pine(W - pad - 32, H - pad + 8, f / 20, "#2f6f3c", False),
    ]))


def render_cards(pulls):
    """The first featured project gets a full-width card, the rest go in pairs at half width."""
    feat = CONFIG["featured"]
    cards = {}
    hero = feat[0]
    parts, end = card_layout(hero, pulls, 1200, 22)
    cards[hero["repo"]] = card_svg(hero, pulls, 1200, int(end + 70), 22, parts)
    rest = feat[1:]
    for k in range(0, len(rest), 2):
        pair = rest[k:k + 2]
        laid = [card_layout(item, pulls, 600, 19) for item in pair]
        h = int(max(end for _, end in laid) + 70)
        for item, (parts, _) in zip(pair, laid):
            cards[item["repo"]] = card_svg(item, pulls, 600, h, 19, parts)
    return cards


def main():
    days, pulls = load()
    s = summarize(days, pulls)
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "header.svg").write_text(render_header(days, s))
    (ASSETS / "forest.svg").write_text(render_forest(days, s))
    for repo, doc in render_cards(pulls).items():
        (ASSETS / f"card-{repo.split('/')[1]}.svg").write_text(doc)
    (DATA / "stats.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps(s))


if __name__ == "__main__":
    main()
