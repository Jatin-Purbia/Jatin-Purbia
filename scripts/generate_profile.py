#!/usr/bin/env python3
"""Generate assets/heatmap.svg and assets/stats.svg from public GitHub data.

No personal access token is needed: the contribution calendar comes from the
public contributions fragment, and repo/follower counts from the public API.
If anything fails, the existing SVGs are left untouched.
"""
import datetime as dt
import os
import re
import sys
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

import profile_card

USER = os.environ.get("PROFILE_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Jatin-Purbia"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"User-Agent": "profile-readme-generator"}

FONT_SANS = "'Segoe UI','Helvetica Neue',Arial,sans-serif"
FONT_MONO = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


# ------------------------------------------------------------------ data
def fetch_days(year=None):
    params = {"from": f"{year}-01-01", "to": f"{year}-12-31"} if year else None
    r = requests.get(f"https://github.com/users/{USER}/contributions", params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    tips = {}
    for tip in soup.find_all("tool-tip"):
        m = re.match(r"\s*(\d+)\s+contribution", tip.get_text())
        tips[tip.get("for")] = int(m.group(1)) if m else 0
    days = []
    for td in soup.select("td.ContributionCalendar-day"):
        date = td.get("data-date")
        if not date:
            continue
        level = int(td.get("data-level", 0))
        count = tips.get(td.get("id"))
        if count is None:
            m = re.search(r"(\d+)\s+contribution", td.get_text())
            count = int(m.group(1)) if m else 0
        days.append((date, count, level))
    days.sort()
    if year:  # keep only the requested calendar year
        days = [d for d in days if d[0].startswith(f"{year}-")]
    if not days:
        raise RuntimeError("no contribution days found")
    return days


def api(path):
    h = dict(HEADERS, Accept="application/vnd.github+json")
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    r = requests.get("https://api.github.com" + path, headers=h, timeout=30)
    r.raise_for_status()
    return r.json()


def streaks(days):
    counts = [c for _, c, _ in days]
    longest = cur = 0
    for c in counts:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:  # today may not have any activity yet
        i -= 1
    current = 0
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    return current, longest


# ------------------------------------------------------------------ heatmap
def heatmap_svg(days, total):
    cell, gap = 13, 3
    step = cell + gap
    x0, y0 = 44, 62
    first = dt.date.fromisoformat(days[0][0])
    first_row = (first.weekday() + 1) % 7  # Sunday = 0
    start = first - dt.timedelta(days=first_row)

    cells, cols = [], 0
    for date, count, level in days:
        d = dt.date.fromisoformat(date)
        col = (d - start).days // 7
        row = (d.weekday() + 1) % 7
        cols = max(cols, col + 1)
        cells.append(
            f'<rect x="{x0 + col * step}" y="{y0 + row * step}" width="{cell}" height="{cell}" rx="3" fill="{LEVELS[min(level, 4)]}"/>'
        )

    months, last_label_col, last_month = [], -10, None
    for col in range(cols):
        sunday = start + dt.timedelta(days=col * 7)
        if sunday.month != last_month and col - last_label_col >= 3:
            months.append(
                f'<text x="{x0 + col * step}" y="54" font-family="{FONT_SANS}" font-size="11" fill="#8b949e">{sunday.strftime("%b")}</text>'
            )
            last_label_col = col
        last_month = sunday.month

    width = 900
    grid_w = cols * step
    height = y0 + 7 * step + 34
    labels = "".join(
        f'<text x="12" y="{y0 + r * step + 11}" font-family="{FONT_SANS}" font-size="10" fill="#8b949e">{n}</text>'
        for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend_x = width - 24 - (5 * step + 70)
    legend = (
        f'<text x="{legend_x}" y="{height - 12}" font-family="{FONT_SANS}" font-size="11" fill="#8b949e">Less</text>'
        + "".join(
            f'<rect x="{legend_x + 32 + i * step}" y="{height - 22}" width="{cell}" height="{cell}" rx="3" fill="{c}"/>'
            for i, c in enumerate(LEVELS)
        )
        + f'<text x="{legend_x + 32 + 5 * step + 4}" y="{height - 12}" font-family="{FONT_SANS}" font-size="11" fill="#8b949e">More</text>'
    )

    T = 12.0
    cover_vals = f"{x0};{x0};{x0 + grid_w};{x0 + grid_w};{x0}"
    cover_keys = "0;0.04;0.30;0.94;1"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{total} contributions in the last year">
  <title>{total} contributions in the last year</title>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="#0d1117" stroke="#30363d"/>
  <text x="24" y="30" font-family="{FONT_SANS}" font-size="16" font-weight="600" fill="#e6edf3">{total} contributions in the last year</text>
  {"".join(months)}
  {labels}
  {"".join(cells)}
  <rect x="{x0}" y="{y0 - 4}" width="{grid_w + 8}" height="{7 * step + 4}" fill="#0d1117">
    <animate attributeName="x" values="{cover_vals}" keyTimes="{cover_keys}" dur="{T}s" repeatCount="indefinite"/>
  </rect>
  {legend}
</svg>
'''


# ------------------------------------------------------------------ stats
def countup(n, T, x, y, size, fill, start=0.5, dur=1.8, steps=18, anchor="middle"):
    """Stack text elements and switch between them to fake a counting number."""
    steps = max(1, min(steps, n)) if n > 0 else 1
    vals = [0] + [round(n * i / steps) for i in range(1, steps + 1)]
    times = [0.0] + [(start + dur * i / steps) / T for i in range(1, steps + 1)] + [1.0]
    out = []
    for i, v in enumerate(vals):
        t_on = times[i]
        t_off = times[i + 1]
        if i == 0:
            kt, ov = f"0;{t_off:.4f};1", "1;0;0"
        elif i == len(vals) - 1:
            kt, ov = f"0;{t_on:.4f};1", "0;1;1"
        else:
            kt, ov = f"0;{t_on:.4f};{t_off:.4f};1", "0;1;0;0"
        out.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT_SANS}" font-size="{size}" font-weight="800" fill="{fill}" opacity="0">{v}'
            f'<animate attributeName="opacity" values="{ov}" keyTimes="{kt}" dur="{T}s" calcMode="discrete" repeatCount="indefinite"/></text>'
        )
    return "".join(out)


def stats_svg(total, current, longest, repos, followers, stars):
    W, H, T = 900, 150, 12.0
    tw, gap = 210, 20
    tiles = [
        (total, "Contributions", "in the last year", "#38bdf8"),
        (current, "Current streak", "days in a row", "#7ee787"),
        (longest, "Longest streak", "days in a row", "#a78bfa"),
        (repos, "Public repos", f"{followers} followers  ·  {stars} stars", "#f472b6"),
    ]
    parts = []
    for i, (n, label, sub, color) in enumerate(tiles):
        x = i * (tw + gap)
        parts.append(
            f'<rect x="{x + 0.5}" y="0.5" width="{tw - 1}" height="{H - 1}" rx="12" fill="#0d1117" stroke="#30363d"/>'
            f'<rect x="{x + 12}" y="12" height="3" rx="1.5" fill="{color}" width="0">'
            f'<animate attributeName="width" values="0;0;{tw - 24};{tw - 24};0" keyTimes="0;0.02;0.2;0.95;1" dur="{T}s" repeatCount="indefinite"/></rect>'
            + countup(n, T, x + tw / 2, 78, 42, color)
            + f'<text x="{x + tw / 2}" y="108" text-anchor="middle" font-family="{FONT_SANS}" font-size="14" font-weight="600" fill="#e6edf3">{escape(label)}</text>'
            f'<text x="{x + tw / 2}" y="130" text-anchor="middle" font-family="{FONT_SANS}" font-size="12" fill="#8b949e">{escape(sub)}</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats">
  <title>GitHub stats for {escape(USER)}</title>
  {"".join(parts)}
</svg>
'''


# ------------------------------------------------------------------ main
def main():
    try:
        days = fetch_days()  # rolling last 365 days
        year = dt.date.today().year
        year_days = fetch_days(year)  # Jan 1 .. today of the current calendar year
        user = api(f"/users/{USER}")
        repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    except Exception as exc:  # leave existing files alone
        print(f"fetch failed, keeping existing SVGs: {exc}", file=sys.stderr)
        return 0

    total = sum(c for _, c, _ in days)
    current, longest = streaks(days)
    stars = sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork"))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "heatmap.svg"), "w", encoding="utf-8") as f:
        f.write(heatmap_svg(days, total))
    with open(os.path.join(OUT, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(total, current, longest, user.get("public_repos", 0), user.get("followers", 0), stars))
    with open(os.path.join(OUT, "profile.svg"), "w", encoding="utf-8") as f:
        f.write(profile_card.profile_svg(year_days, sum(c for _, c, _ in year_days), USER, year=year, streak_days=days))
    print(f"ok: total={total} current={current} longest={longest} repos={user.get('public_repos')} followers={user.get('followers')} stars={stars}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
