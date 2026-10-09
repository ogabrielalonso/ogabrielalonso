"""Render the profile card (assets/card-light.svg, assets/card-dark.svg) from live GitHub data.

The card is an 80-column punched card: the halftone portrait printed on the left,
the profile fields printed on the right, and the last 52 weeks of contributions
punched through the stock (one hole per day with at least one contribution).

Usage: GITHUB_TOKEN=... python scripts/build_card.py [--data snapshot.json]
Standard library only, so the scheduled Action needs no dependencies.
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
LOGIN = "ogabrielalonso"

# Card geometry follows a real 7 3/8 x 3 1/4 in card at 162.7 units per inch.
W, H = 1200, 528
COL0, COL_PITCH = 40.8, 14.15      # centre of column 1, column pitch
ROW0, ROW_PITCH = 40.7, 40.7       # centre of row 12, row pitch (12, 11, 0..9)
HOLE_W, HOLE_H = 9, 20
CORNER = 40                        # clipped top-left corner

STOCK = "#b5d2ff"
INK = "#101014"
INK_SOFT = "#2b3d63"
PRINT = "#7d9ed6"

PROFILE = {
    "name": "Gabriel Alonso",
    "builds": "I build AI tools and frameworks that make AI actually useful.",
    "fields": [
        ("Role", "CTO, Focus AI", 27),
        ("Based in", "Luxembourg", 39),
        ("Speaks", "PT, EN, FR", 49),
        ("Works with", "Claude Code, Codex", 58),
    ],
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      nodes { name stargazerCount }
    }
  }
}
"""

# 5x7 dot-matrix glyphs for the interpreted line along the top edge.
GLYPHS = {
    "A": "01110100011000111111100011000110001", "B": "11110100011000111110100011000111110",
    "C": "01110100011000010000100001000101110", "D": "11110100011000110001100011000111110",
    "E": "11111100001000011110100001000011111", "F": "11111100001000011110100001000010000",
    "G": "01110100011000010111100011000101111", "H": "10001100011000111111100011000110001",
    "I": "01110001000010000100001000010001110", "J": "00111000100001000010000101001001100",
    "K": "10001100101010011000101001001010001", "L": "10000100001000010000100001000011111",
    "M": "10001110111010110101100011000110001", "N": "10001100011100110101100111000110001",
    "O": "01110100011000110001100011000101110", "P": "11110100011000111110100001000010000",
    "Q": "01110100011000110001101011001001101", "R": "11110100011000111110101001001010001",
    "S": "01111100001000001110000010000111110", "T": "11111001000010000100001000010000100",
    "U": "10001100011000110001100011000101110", "V": "10001100011000110001100010101000100",
    "W": "10001100011000110101101011010101010", "X": "10001100010101000100010101000110001",
    "Y": "10001100010101000100001000010000100", "Z": "11111000010001000100010001000011111",
    "0": "01110100011001110101110011000101110", "1": "00100011000010000100001000010001110",
    "2": "01110100010000100010001000100011111", "3": "11111000100010000010000011000101110",
    "4": "00010001100101010010111110001000010", "5": "11111100001111000001000011000101110",
    "6": "00110010001000011110100011000101110", "7": "11111000010001000100010000100001000",
    "8": "01110100011000101110100011000101110", "9": "01110100011000101111000010001001100",
    ".": "00000000000000000000000000110001100", "/": "00000000010001000100010001000000000",
    "-": "00000000000000011111000000000000000", ":": "00000011000110000000011000110000000",
    " ": "0" * 35,
}


def col_x(c):
    return COL0 + (c - 1) * COL_PITCH


def row_y(i):
    return ROW0 + i * ROW_PITCH


def fetch(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    user = body["data"]["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    # the profile README repo is not a project
    repos = [n for n in user["repositories"]["nodes"] if n["name"] != LOGIN]
    return {
        "total": cal["totalContributions"],
        "weeks": [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]],
        "repos": len(repos),
        "stars": sum(n["stargazerCount"] for n in repos),
        "updated": dt.date.today().isoformat(),
    }


def font_face(family, file):
    data = base64.b64encode((ASSETS / "fonts" / file).read_bytes()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) format('woff2');}}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dot_matrix(text, x, y, dot, color):
    out = []
    for i, ch in enumerate(text.upper()):
        bits = GLYPHS.get(ch, GLYPHS[" "])
        cx = col_x(x + i) - 2 * dot
        for k, b in enumerate(bits):
            if b == "1":
                out.append(f'<rect x="{cx + (k % 5) * dot:.2f}" y="{y + (k // 5) * dot:.2f}" width="{dot * .8:.2f}" height="{dot * .8:.2f}"/>')
    return f'<g fill="{color}">{"".join(out)}</g>'


def render(data, theme, motion=True):
    weeks = data["weeks"][-52:]
    first_heat_col = 27
    holes, digits, months = [], [], []
    active = 0
    prev_month, last_label = None, -9
    for wi, week in enumerate(weeks):
        c = first_heat_col + wi
        month = week[0][0][:7]
        if month != prev_month:
            if wi - last_label >= 3 and wi <= 49:
                label = dt.date.fromisoformat(week[0][0]).strftime("%b")
                months.append(f'<text x="{col_x(c) - 4:.1f}" y="226">{label}</text>')
                last_label = wi
            prev_month = month
        days = {dt.date.fromisoformat(d).weekday(): n for d, n in week}
        for day in range(7):  # rows 3..9, Sunday first like GitHub
            wd = (day - 1) % 7
            i = 5 + day
            if days.get(wd, 0) > 0:
                active += 1
                holes.append(
                    f'<rect class="h c{wi}" x="{col_x(c) - HOLE_W / 2:.2f}" y="{row_y(i) - HOLE_H / 2:.2f}" '
                    f'width="{HOLE_W}" height="{HOLE_H}" rx="1"/>'
                )
            else:
                digits.append(f'<text x="{col_x(c):.2f}" y="{row_y(i) + 3.6:.2f}">{3 + day}</text>')

    for c in range(first_heat_col + len(weeks), 81):  # columns past the last week stay unpunched
        for day in range(7):
            digits.append(f'<text x="{col_x(c):.2f}" y="{row_y(5 + day) + 3.6:.2f}">{3 + day}</text>')
    colnums = "".join(f'<text x="{col_x(c):.2f}" y="518">{c}</text>' for c in range(first_heat_col, 81))

    delays = "".join(f".c{i}{{animation-delay:{120 + i * 30}ms}}" for i in range(52))
    total = f"{data['total']:,} contributions"
    stars = f"{data['stars']} star" + ("" if data["stars"] == 1 else "s")
    record = f"{total}  {active} active days  {data['repos']} public projects  {stars}"
    stamp = f"REC {data['updated']}"
    fields = []
    for label, value, c1 in PROFILE["fields"]:
        x = col_x(c1) - 3
        fields.append(
            f'<text class="lbl" x="{x:.1f}" y="160">{esc(label.upper())}</text>'
            f'<text class="val" x="{x:.1f}" y="185">{esc(value)}</text>'
        )
        if c1 != 27:
            fields.append(f'<line x1="{x - 9:.1f}" y1="145" x2="{x - 9:.1f}" y2="192"/>')

    card_path = f"M{CORNER},0H{W}V{H}H0V{CORNER}Z"
    shadow = (
        '<filter id="lift" x="-5%" y="-5%" width="110%" height="120%">'
        '<feDropShadow dx="0" dy="6" stdDeviation="9" flood-color="#1f2a44" flood-opacity=".18"/></filter>'
        if theme == "light" else ""
    )
    pad = 24
    portrait = base64.b64encode((ASSETS / "portrait-ink.png").read_bytes()).decode()

    motion_css = (
        "@keyframes punch{0%{fill:#fff}100%{fill:#000}}"
        ".h{animation:punch 1ms steps(1) backwards}" + delays
    ) if motion else ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {W + 2 * pad} {H + 2 * pad}" width="{W + 2 * pad}" height="{H + 2 * pad}" role="img" aria-labelledby="t d">
<title id="t">Gabriel Alonso</title>
<desc id="d">{esc(PROFILE['builds'])} CTO at Focus AI, based in Luxembourg. {esc(total)} in the last 12 months over {active} active days, each active day punched as a hole in an 80-column card.</desc>
<style>
{font_face('ArchivoDisplay', 'archivo-display.woff2')}
{font_face('ArchivoText', 'archivo-text.woff2')}
{font_face('ArchivoLabel', 'archivo-label.woff2')}
.name{{font:800 64px ArchivoDisplay,sans-serif;fill:{INK};letter-spacing:-1.5px}}
.builds{{font:500 22px ArchivoText,sans-serif;fill:{INK}}}
.lbl{{font:600 13px ArchivoLabel,sans-serif;fill:{INK_SOFT};letter-spacing:1.2px}}
.val{{font:500 19px ArchivoText,sans-serif;fill:{INK}}}
.dg text{{font:600 8.5px ArchivoLabel,sans-serif;fill:{PRINT};text-anchor:middle}}
.mo text{{font:600 13px ArchivoLabel,sans-serif;fill:{INK_SOFT};letter-spacing:.6px}}
.cn text{{font:600 7px ArchivoLabel,sans-serif;fill:{PRINT};text-anchor:middle}}
.rules line{{stroke:{INK_SOFT};stroke-width:1;opacity:.55}}
.h{{fill:#000}}
{motion_css}
@media (prefers-reduced-motion:reduce){{.h{{animation:none}}}}
</style>
<defs>
{shadow}
<mask id="punched" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">
<rect width="{W}" height="{H}" fill="#fff"/>
{''.join(holes)}
</mask>
<clipPath id="card"><path d="{card_path}"/></clipPath>
</defs>
<g {'filter="url(#lift)"' if shadow else ''}>
<g mask="url(#punched)">
<path d="{card_path}" fill="{STOCK}"/>
<g clip-path="url(#card)">
<image href="data:image/png;base64,{portrait}" x="16" y="24" width="372" height="480" preserveAspectRatio="none"/>
{dot_matrix(record, 4, 10, 1.75, INK)}
{dot_matrix(stamp, 81 - len(stamp), 10, 1.75, INK)}
<text class="name" x="{col_x(27) - 5:.1f}" y="92">{esc(PROFILE['name'])}</text>
<text class="builds" x="{col_x(27) - 3:.1f}" y="127">{esc(PROFILE['builds'])}</text>
<g class="rules">{''.join(f for f in fields if f.startswith('<line'))}</g>
{''.join(f for f in fields if not f.startswith('<line'))}
<g class="dg">{''.join(digits)}</g>
<g class="cn">{colnums}</g>
<g class="mo">{''.join(months)}</g>
</g>
</g>
</g>
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="read a JSON snapshot instead of calling the API")
    ap.add_argument("--save-data", help="write the fetched data to this JSON file")
    ap.add_argument("--still", action="store_true", help="omit the punch animation (review captures)")
    args = ap.parse_args()
    if args.data:
        data = json.loads(pathlib.Path(args.data).read_text())
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN is not set")
        data = fetch(token)
    if args.save_data:
        pathlib.Path(args.save_data).write_text(json.dumps(data))
    for theme in ("light", "dark"):
        (ASSETS / f"card-{theme}.svg").write_text(render(data, theme, motion=not args.still))
    print(f"card rendered: {data['total']} contributions, {data['repos']} repos, {data['stars']} stars")


if __name__ == "__main__":
    main()
