"""Terminal-style profile card (contributions heatmap + whoami with ASCII portrait
and stat tiles), rendered as one animated SVG.

Used by generate_profile.py. Everything is computed from the `days` list of
(date_iso, count, level) tuples, so numbers refresh whenever the workflow runs.
"""
import base64
import datetime as dt
import os
from xml.sax.saxutils import escape

MONO = "'SFMono-Regular','Fira Code',Consolas,'Liberation Mono',Menlo,monospace"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
BG, PANEL, LINE = "#0d1117", "#161b22", "#30363d"
FG, MUTED, DIM = "#e6edf3", "#8b949e", "#6e7681"
GREEN = "#3fb950"
PAPER = "#f6f8fa"  # light panel behind the portrait (keeps dark hair dark)
T = 12.0  # seconds per animation loop

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTRAIT = os.path.join(ROOT, "assets", "portrait-src.png")


# ------------------------------------------------------------------ data
def _fmt_date(iso):
    d = dt.date.fromisoformat(iso)
    return d.strftime("%b ") + str(d.day)


def streak_info(days):
    """Return ((cur_len, cur_start, cur_end), (best_len, best_start, best_end))."""
    best = (0, None, None)
    run_start = None
    for i, (date, count, _) in enumerate(days):
        if count > 0:
            if run_start is None:
                run_start = i
            n = i - run_start + 1
            if n > best[0]:
                best = (n, days[run_start][0], date)
        else:
            run_start = None
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:  # today may not have any activity yet
        i -= 1
    end = i
    while i >= 0 and days[i][1] > 0:
        i -= 1
    cur = (end - i, days[i + 1][0], days[end][0]) if end - i > 0 else (0, None, None)
    return cur, best


def monthly(days, n=12, year=None):
    totals = {}
    for date, count, _ in days:
        d = dt.date.fromisoformat(date)
        totals[(d.year, d.month)] = totals.get((d.year, d.month), 0) + count
    if year:  # Jan..Dec of that year; months without data stay at zero
        return [(dt.date(year, m, 1).strftime("%b"), totals.get((year, m), 0)) for m in range(1, 13)]
    keys = sorted(totals)[-n:]
    return [(dt.date(y, m, 1).strftime("%b"), totals[(y, m)]) for y, m in keys]


# ------------------------------------------------------------------ pieces
def _prompt(y, cmd, cursor=False):
    s = (
        f'<text x="20" y="{y}" font-family="{MONO}" font-size="13" font-weight="600" xml:space="preserve">'
        f'<tspan fill="#7ee787">jatin@github</tspan><tspan fill="{MUTED}"> ~ </tspan>'
        f'<tspan fill="#7ee787">$</tspan><tspan fill="{FG}"> {escape(cmd)}</tspan></text>'
    )
    if cursor:
        x = 20 + 7.8 * (len("jatin@github ~ $ ") + len(cmd)) + 2
        s += (
            f'<rect x="{x:.1f}" y="{y - 11}" width="8" height="14" fill="{FG}">'
            f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5001;1" dur="1.1s" repeatCount="indefinite"/></rect>'
        )
    return s


def _countup(value, text_fn, x, y, size, fill, start=0.35, dur=1.6, steps=16):
    """Stack text elements and switch between them to fake a counting number."""
    steps = max(1, steps)
    vals = [0] + [value * i / steps for i in range(1, steps + 1)]
    vals[-1] = value
    s0 = start / T
    times = [0.0] + [(start + dur * i / steps) / T for i in range(1, steps + 1)] + [1.0]
    out = []
    for i, v in enumerate(vals):
        t_on, t_off = times[i], times[i + 1]
        if i == 0:
            kt, ov = f"0;{t_off:.4f};1", "1;0;0"
        elif i == len(vals) - 1:
            kt, ov = f"0;{t_on:.4f};1", "0;1;1"
        else:
            kt, ov = f"0;{t_on:.4f};{t_off:.4f};1", "0;1;0;0"
        out.append(
            f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" font-weight="700" fill="{fill}" opacity="0">'
            f"{escape(text_fn(v))}"
            f'<animate attributeName="opacity" values="{ov}" keyTimes="{kt}" dur="{T}s" calcMode="discrete" repeatCount="indefinite"/></text>'
        )
    return "".join(out)


def _heatmap(days, y_top, year=None):
    cell, gap = 12, 3
    step = cell + gap
    x0 = 56
    first = dt.date.fromisoformat(days[0][0])
    if year:
        first = dt.date(year, 1, 1)
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday

    cells, cols = [], 0
    if year:  # always reserve the full Jan..Dec width, even though the year isn't over yet
        cols = (dt.date(year, 12, 31) - start).days // 7 + 1
    for date, count, level in days:
        d = dt.date.fromisoformat(date)
        col = (d - start).days // 7
        row = (d.weekday() + 1) % 7
        cols = max(cols, col + 1)
        cells.append(
            f'<rect x="{x0 + col * step}" y="{y_top + row * step}" width="{cell}" height="{cell}" rx="2.5" fill="{LEVELS[min(level, 4)]}"/>'
        )
    months, last_col, last_month = [], -10, None
    for col in range(cols):
        sunday = start + dt.timedelta(days=col * 7)
        # in year view, name a week after the month most of it falls in (so a week starting Dec 28 reads "Jan")
        ref = sunday + dt.timedelta(days=6) if year else sunday
        if ref.month != last_month and (col - last_col >= 3 or last_col < 0) and (not year or ref.year == year):
            months.append(
                f'<text x="{x0 + col * step}" y="{y_top - 8}" font-family="{MONO}" font-size="10" fill="{MUTED}">{ref.strftime("%b")}</text>'
            )
            last_col = col
        last_month = ref.month
    labels = "".join(
        f'<text x="20" y="{y_top + r * step + 9}" font-family="{MONO}" font-size="10" fill="{MUTED}">{n}</text>'
        for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    grid_w = cols * step
    cover = (
        f'<rect x="{x0}" y="{y_top - 3}" width="{grid_w + 6}" height="{7 * step + 3}" fill="{BG}">'
        f'<animate attributeName="x" values="{x0};{x0};{x0 + grid_w + 6};{x0 + grid_w + 6};{x0}" keyTimes="0;0.04;0.30;0.94;1" dur="{T}s" repeatCount="indefinite"/></rect>'
    )
    return "".join(months) + labels + "".join(cells) + cover, x0 + grid_w, y_top + 7 * step


def _legend(x_right, y):
    cell, step = 11, 14
    x = x_right - (5 * step + 64)
    return (
        f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="10" fill="{MUTED}">Less</text>'
        + "".join(
            f'<rect x="{x + 30 + i * step}" y="{y - 10}" width="{cell}" height="{cell}" rx="2.5" fill="{c}"/>'
            for i, c in enumerate(LEVELS)
        )
        + f'<text x="{x + 30 + 5 * step + 4}" y="{y}" font-family="{MONO}" font-size="10" fill="{MUTED}">More</text>'
    )


def _tile(x, y, w, h, label, value, text_fn, sub, color, delay):
    digits = len(text_fn(value))
    unit_x = x + 16 + digits * 17.5 + 6
    return (
        f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="6" fill="{BG}" stroke="{LINE}"/>'
        f'<text x="{x + 16}" y="{y + 20}" font-family="{MONO}" font-size="10" letter-spacing="0.8" fill="{MUTED}">{escape(label)}</text>'
        + _countup(value, text_fn, x + 16, y + 47, 27, color, start=0.35 + delay)
        + f'<text x="{x + 16}" y="{y + 63}" font-family="{MONO}" font-size="10" fill="{DIM}">{escape(sub)}</text>'
    )


def _bars(x, y, w, h, series):
    top_pad, bottom_pad = 46, 26
    base = y + h - bottom_pad
    max_h = h - top_pad - bottom_pad
    peak = max((v for _, v in series), default=0) or 1
    slot = (w - 32) / max(1, len(series))
    bw = min(26, slot - 10)
    parts = [
        f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="6" fill="{BG}" stroke="{LINE}"/>',
        f'<text x="{x + 16}" y="{y + 20}" font-family="{MONO}" font-size="10" letter-spacing="0.8" fill="{MUTED}">CONTRIBUTIONS / MONTH</text>',
    ]
    for i, (name, v) in enumerate(series):
        bx = x + 16 + i * slot + (slot - bw) / 2
        bh = max(2.0, max_h * v / peak) if v else 2.0
        is_peak = v == peak and v > 0
        fill = "#39d353" if is_peak else ("#26a641" if v else "#21262d")
        t0 = 0.30 + i * 0.012
        t1 = t0 + 0.07
        parts.append(
            f'<rect x="{bx:.1f}" y="{base}" width="{bw:.1f}" height="0" rx="2" fill="{fill}">'
            f'<animate attributeName="height" values="0;0;{bh:.1f};{bh:.1f};0" keyTimes="0;{t0:.4f};{t1:.4f};0.94;1" dur="{T}s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{base};{base};{base - bh:.1f};{base - bh:.1f};{base}" keyTimes="0;{t0:.4f};{t1:.4f};0.94;1" dur="{T}s" repeatCount="indefinite"/></rect>'
            f'<text x="{bx + bw / 2:.1f}" y="{base + 15}" text-anchor="middle" font-family="{MONO}" font-size="9" fill="{DIM}">{name}</text>'
        )
        if is_peak:
            parts.append(
                f'<text x="{bx + bw / 2:.1f}" y="{base - bh - 6:.1f}" text-anchor="middle" font-family="{MONO}" font-size="10" font-weight="600" fill="{FG}" opacity="0">{v:,}'
                f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{t1:.4f};{t1 + 0.03:.4f};0.94;1" dur="{T}s" repeatCount="indefinite"/></text>'
            )
    return "".join(parts)


def _portrait(x, y, w, h):
    """ASCII portrait, light dots on the dark card, revealed by a scanning line."""
    with open(PORTRAIT, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode()
    iw, ih = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    pw = w - 24
    ph = round(pw * ih / iw)
    ix, iy = x + 12, y + 12
    box_h = ph + 12 + 30
    keys = "0;0.04;0.30;0.94;1"
    scan_y = f"{iy - 1};{iy - 1};{iy + ph - 1};{iy + ph - 1};{iy - 1}"
    svg = (
        f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{box_h - 1}" rx="6" fill="{BG}" stroke="{LINE}"/>'
        f'<g clip-path="url(#pclip)">'
        f'<rect x="{ix}" y="{iy}" width="{pw}" height="{ph}" fill="{PAPER}"/>'
        f'<image x="{ix}" y="{iy}" width="{pw}" height="{ph}" preserveAspectRatio="xMidYMid slice" href="data:image/png;base64,{b64}"/>'
        # cover wiped away top -> bottom, then pulled back up bottom -> top at the end of the loop
        f'<rect x="{ix}" y="{iy}" width="{pw}" height="{ph}" fill="{PAPER}">'
        f'<animate attributeName="y" values="{iy};{iy};{iy + ph};{iy + ph};{iy}" keyTimes="{keys}" dur="{T}s" repeatCount="indefinite"/>'
        f'<animate attributeName="height" values="{ph};{ph};0;0;{ph}" keyTimes="{keys}" dur="{T}s" repeatCount="indefinite"/></rect>'
        f'<g><animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.04;0.30;0.33;1" dur="{T}s" repeatCount="indefinite"/>'
        f'<rect x="{ix}" y="{iy - 50}" width="{pw}" height="50" fill="url(#trail)">'
        f'<animate attributeName="y" values="{iy - 50};{iy - 50};{iy + ph - 50};{iy + ph - 50};{iy - 50}" keyTimes="{keys}" dur="{T}s" repeatCount="indefinite"/></rect>'
        f'<rect x="{ix}" y="{iy - 1}" width="{pw}" height="2" fill="#39d353" filter="url(#glow)">'
        f'<animate attributeName="y" values="{scan_y}" keyTimes="{keys}" dur="{T}s" repeatCount="indefinite"/></rect></g>'
        f"</g>"
        f'<text x="{x + w / 2}" y="{y + box_h - 11}" text-anchor="middle" font-family="{MONO}" font-size="9" fill="{DIM}">image -&gt; ascii  .  jatin.png</text>'
    )
    return svg, box_h, (ix, iy, pw, ph)


# ------------------------------------------------------------------ card
def profile_svg(days, total, user="Jatin-Purbia", year=None, streak_days=None):
    W = 880
    period = str(year) if year else "the last year"
    (_, _, _), (best_n, best_s, best_e) = streak_info(days)
    # the *current* streak can run across New Year, so measure it on a rolling window when given
    (cur_n, cur_s, cur_e), _ = streak_info(streak_days or days)
    active = sum(1 for _, c, _ in days if c > 0)
    top = max(days, key=lambda d: d[1]) if days else (None, 0, 0)
    avg = total / active if active else 0.0
    series = monthly(days, year=year)

    # section 1: contributions.sh
    p1 = 62
    heat, heat_right, heat_bottom = _heatmap(days, y_top=p1 + 38, year=year)
    foot_y = heat_bottom + 24
    sec1 = (
        _prompt(p1, "./contributions.sh")
        + heat
        + f'<text x="20" y="{foot_y}" font-family="{MONO}" font-size="11" fill="{MUTED}">{total:,} contributions in {period}</text>'
        + _legend(W - 20, foot_y)
    )

    # section 2: whoami
    p2 = foot_y + 46
    top2 = p2 + 20
    portrait, box_h, pinfo = _portrait(20, top2, 300, 0)
    gx, gw = 340, W - 340 - 20
    tw, th, gap = (gw - 10) / 2, 70, 10
    tiles = [
        ("CURRENT STREAK", cur_n, lambda v: f"{round(v)}", f"{_fmt_date(cur_s)} - {_fmt_date(cur_e)}" if cur_n else "no active streak", GREEN),
        ("LONGEST STREAK", best_n, lambda v: f"{round(v)}", f"{_fmt_date(best_s)} - {_fmt_date(best_e)}" if best_n else "-", GREEN),
        ("CONTRIBUTIONS", total, lambda v: f"{round(v):,}", f"in {period}", FG),
        ("ACTIVE DAYS", active, lambda v: f"{round(v)}", "days with contributions", FG),
        ("BEST DAY", top[1], lambda v: f"{round(v)}", _fmt_date(top[0]) if top[0] and top[1] else "-", FG),
        ("AVG / ACTIVE DAY", avg, lambda v: f"{v:.1f}", "contributions per active day", FG),
    ]
    tile_svg = ""
    for i, (label, val, fn, sub, color) in enumerate(tiles):
        tx = gx + (i % 2) * (tw + gap)
        ty = top2 + (i // 2) * (th + gap)
        tile_svg += _tile(tx, ty, tw, th, label, val, fn, sub, color, delay=0.05 * (i % 3))
    grid_h = 3 * th + 2 * gap
    bars_y = top2 + grid_h + gap
    bars = _bars(gx, bars_y, gw, box_h - grid_h - gap, series)
    sec2 = _prompt(p2, "whoami") + portrait + tile_svg + bars

    # bottom prompt with a blinking cursor
    p3 = top2 + box_h + 34
    H = p3 + 22
    sec3 = _prompt(p3, "", cursor=True)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Terminal-style profile: {total} contributions in {period}, streaks and an ASCII portrait of Jatin">
  <title>{escape(user)} - README.md</title>
  <defs>
    <clipPath id="card"><rect width="{W}" height="{H}" rx="10"/></clipPath>
    <clipPath id="pclip"><rect x="{pinfo[0]}" y="{pinfo[1]}" width="{pinfo[2]}" height="{pinfo[3]}" rx="3"/></clipPath>
    <linearGradient id="trail" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" stop-color="#39d353" stop-opacity="0.28"/>
      <stop offset="1" stop-color="#39d353" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow" x="-5%" y="-400%" width="110%" height="900%">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="{BG}"/>
    <rect width="{W}" height="34" fill="{PANEL}"/>
    <line x1="0" y1="34.5" x2="{W}" y2="34.5" stroke="{LINE}"/>
    <text x="20" y="22" font-family="{MONO}" font-size="12" letter-spacing="0.6" fill="{MUTED}">{escape(user.upper())} / README.md</text>
    <path d="M{W - 34} 24 l1.2 -4.6 l7.6 -7.6 l3.4 3.4 l-7.6 7.6 z" fill="none" stroke="{MUTED}" stroke-width="1.2" stroke-linejoin="round"/>
    {sec1}
    {sec2}
    {sec3}
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{LINE}"/>
</svg>
'''
