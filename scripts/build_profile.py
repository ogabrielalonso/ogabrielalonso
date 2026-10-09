"""Render the profile README art: assets/contributions.svg and assets/whoami.svg.

Activity = GitHub contribution calendar + data/local-activity.json (commits that exist
only in local repositories, pushed daily from my server). Standard library only.

Usage: GITHUB_TOKEN=... python scripts/build_profile.py [--data snapshot.json] [--still]
"""
import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
LOCAL = ROOT / "data" / "local-activity.json"
LOGIN = "ogabrielalonso"

BG = "#0b0f17"
BAR = "#121a2b"
EDGE = "#24304a"
TEXT = "#d7e3f7"
DIM = "#7183a6"
BLUE = "#b5d2ff"
LEVELS = ["#161e2e", "#24406e", "#3f6aae", "#76a0e3", "#b5d2ff"]

WHOAMI = [
    ("Name", "Gabriel Alonso"),
    ("Role", "CTO @ Focus AI"),
    ("Based", "Luxembourg"),
    ("Now", "Building AI tools and frameworks that make AI actually useful"),
    ("Delivers", "AI agents & automation, custom software, knowledge systems, AI strategy"),
    ("Method", "Multi-model AI engineering: Codex, Claude Code and Grok as one team"),
    ("Quality", "Every change reviewed by a different model than the one that wrote it"),
    ("Stack", "Stack-agnostic, delivered through my own AI development framework"),
    ("Languages", "Portuguese, English"),
    ("Contact", "linkedin.com/in/ogabrielalonso"),
]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""

W = 900
FONT = None


def fonts():
    def face(weight, file):
        data = base64.b64encode((ASSETS / "fonts" / file).read_bytes()).decode()
        return (f"@font-face{{font-family:'JBM';font-weight:{weight};"
                f"src:url(data:font/woff2;base64,{data}) format('woff2');}}")
    return face(400, "jbm-regular.woff2") + face(700, "jbm-bold.woff2")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fetch_github(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def window(height, title, body, motion_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" role="img" aria-labelledby="t">
<title id="t">{esc(title)}</title>
<style>
{fonts()}
text{{font-family:JBM,monospace;fill:{TEXT}}}
.dim{{fill:{DIM}}} .key{{fill:{BLUE};font-weight:700}} .bold{{font-weight:700}}
{motion_css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<rect x=".5" y=".5" width="{W - 1}" height="{height - 1}" rx="10" fill="{BG}" stroke="{EDGE}"/>
<path d="M.5 34V10.5a10 10 0 0 1 10-10h{W - 21}a10 10 0 0 1 10 10V34z" fill="{BAR}"/>
<line x1="0" y1="34" x2="{W}" y2="34" stroke="{EDGE}"/>
<circle cx="20" cy="17" r="5.5" fill="#3a4a6b"/><circle cx="38" cy="17" r="5.5" fill="#3a4a6b"/><circle cx="56" cy="17" r="5.5" fill="#3a4a6b"/>
<text x="{W / 2}" y="22" text-anchor="middle" class="dim" font-size="13">{esc(title)}</text>
{body}
</svg>
"""


def contributions_svg(days, motion):
    today = dt.date.fromisoformat(max(days))
    start = today - dt.timedelta(days=today.isoweekday() % 7 + 52 * 7)  # Sunday, 53 columns
    cells, months = [], []
    cell, gap, x0, y0 = 12, 3, 62, 78
    nonzero = sorted(n for n in days.values() if n > 0)
    q = [nonzero[int(len(nonzero) * f)] for f in (.25, .5, .75)] if nonzero else [1, 2, 3]

    def level(n):
        return 0 if n == 0 else 1 + sum(n > t for t in q)

    prev_month = None
    d = start
    while d <= today:
        col = (d - start).days // 7
        row = (d - start).days % 7
        n = days.get(d.isoformat(), 0)
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        delay = (col + row) * 9
        cells.append(f'<rect class="c" style="animation-delay:{delay}ms" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{LEVELS[level(n)]}"><title>{n} on {d.isoformat()}</title></rect>')
        if row == 0 and d.month != prev_month:
            if col <= 50:
                months.append(f'<text x="{x}" y="{y0 - 10}" class="dim" font-size="12">{d.strftime("%b")}</text>')
            prev_month = d.month
        d += dt.timedelta(days=1)
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        months.append(f'<text x="18" y="{y0 + row * (cell + gap) + 11}" class="dim" font-size="11">{name}</text>')

    window_days = {k: v for k, v in days.items() if dt.date.fromisoformat(k) >= start}
    total = sum(window_days.values())
    active = sum(1 for v in window_days.values() if v > 0)
    longest = run = 0
    d = start
    while d <= today:
        run = run + 1 if days.get(d.isoformat(), 0) > 0 else 0
        longest = max(longest, run)
        d += dt.timedelta(days=1)
    current, d = 0, today if days.get(today.isoformat(), 0) > 0 else today - dt.timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        current += 1
        d -= dt.timedelta(days=1)

    gy = y0 + 7 * (cell + gap) + 30
    stats = (f'<text x="{x0}" y="{gy}" font-size="14"><tspan class="key">{total:,}</tspan> contributions'
             f'<tspan class="dim">  ·  </tspan><tspan class="key">{active}</tspan> active days'
             f'<tspan class="dim">  ·  </tspan>longest streak <tspan class="key">{longest}</tspan>'
             f'<tspan class="dim">  ·  </tspan>current <tspan class="key">{current}</tspan></text>')
    lx = W - 18 - 5 * (cell + 3) - 34
    legend = [f'<text x="{lx - 40}" y="{gy}" class="dim" font-size="12">Less</text>']
    legend += [f'<rect x="{lx + i * (cell + 3)}" y="{gy - 11}" width="{cell}" height="{cell}" rx="3" fill="{c}"/>' for i, c in enumerate(LEVELS)]
    legend.append(f'<text x="{lx + 5 * (cell + 3) + 4}" y="{gy}" class="dim" font-size="12">More</text>')
    note = (f'<text x="{x0}" y="{gy + 24}" class="dim" font-size="12">GitHub plus commits in my local repositories · '
            f'updated {today.isoformat()}</text>')

    css = ("@keyframes in{from{opacity:0;transform:translateY(-6px)}}"
           ".c{animation:in .5s cubic-bezier(.16,1,.3,1) backwards}") if motion else ""
    title = "contributions · last 12 months"
    body = "".join(cells) + "".join(months) + stats + "".join(legend) + note
    return window(gy + 44, title, body, css), {"total": total, "active": active, "longest": longest, "current": current}


def whoami_svg(motion):
    x0, y, lh = 28, 72, 27
    lines = [f'<text x="{x0}" y="{y}" font-size="16"><tspan class="key">gabriel</tspan><tspan class="dim">@</tspan><tspan class="key">github</tspan></text>',
             f'<text x="{x0}" y="{y + 18}" class="dim" font-size="16">{"─" * 14}</text>']
    y += 18 + lh
    for i, (k, v) in enumerate(WHOAMI):
        lines.append(f'<text class="l" style="animation-delay:{120 + i * 70}ms" x="{x0}" y="{y}" font-size="15">'
                     f'<tspan class="key">{esc(k)}</tspan><tspan class="dim">:</tspan>'
                     f'<tspan x="{x0 + 118}">{esc(v)}</tspan></text>')
        y += lh
    y += 8
    lines += [f'<rect x="{x0 + i * 34}" y="{y}" width="30" height="16" rx="2" fill="{c}"/>' for i, c in enumerate(LEVELS)]
    css = ("@keyframes in{from{opacity:0;transform:translateX(-8px)}}"
           ".l{animation:in .45s cubic-bezier(.16,1,.3,1) backwards}") if motion else ""
    return window(y + 42, "gabriel@github: ~", "".join(lines), css)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="GitHub calendar snapshot JSON ({date: count}) instead of the API")
    ap.add_argument("--save-data", help="write the fetched GitHub calendar to this file")
    ap.add_argument("--still", action="store_true", help="omit animation (review captures)")
    args = ap.parse_args()
    if args.data:
        github = json.loads(pathlib.Path(args.data).read_text())
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN is not set")
        github = fetch_github(token)
    if args.save_data:
        pathlib.Path(args.save_data).write_text(json.dumps(github))
    local = json.loads(LOCAL.read_text()) if LOCAL.exists() else {}
    days = dict(github)
    for k, v in local.items():
        if k in days:
            days[k] += v
    svg, stats = contributions_svg(days, motion=not args.still)
    (ASSETS / "contributions.svg").write_text(svg)
    (ASSETS / "whoami.svg").write_text(whoami_svg(motion=not args.still))
    print("rendered:", stats)


if __name__ == "__main__":
    main()
