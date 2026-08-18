#!/usr/bin/env python3
"""
Pulls contribution/language data from the GitHub GraphQL API and draws four
SVGs in the same visual language as the ASCII portrait. Standard library
only -- nothing to break in CI.

Env vars required:
    GITHUB_TOKEN  - provided automatically by Actions (contents: write is enough)
    GH_LOGIN      - ${{ github.repository_owner }}

Outputs (in cwd): stats.svg, streak.svg, langs.svg, year.svg
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

RAMP = " .`:-=+*cs#%@"  # same ramp as the portrait, for the year heatmap
FONT_FAMILY = "basic-mono, monospace"
FG = "#38bdf8"

API_URL = "https://api.github.com/graphql"


def gql(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-script",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if "errors" in data:
        raise RuntimeError(json.dumps(data["errors"]))
    return data["data"]


def utc_window():
    now = datetime.now(timezone.utc)
    to = now.replace(hour=23, minute=59, second=59, microsecond=0)
    frm = (to - timedelta(days=364)).replace(hour=0, minute=0, second=0)
    return frm, to


CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: [OWNER], privacy: PUBLIC, isFork: false) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch(login: str, token: str):
    frm, to = utc_window()
    data = gql(
        CONTRIB_QUERY,
        {"login": login, "from": frm.isoformat(), "to": to.isoformat()},
        token,
    )
    return data["user"]


def compute_streaks(days):
    """days: list of {date, contributionCount} in chronological order."""
    best_len = best_start = best_end = 0
    cur_len = 0
    cur_start = None
    run_start = None

    for d in days:
        if d["contributionCount"] > 0:
            if cur_len == 0:
                run_start = d["date"]
            cur_len += 1
            if cur_len > best_len:
                best_len = cur_len
                best_start = run_start
                best_end = d["date"]
        else:
            cur_len = 0

    # current streak = trailing run ending today (or yesterday, GitHub-style)
    current_len = 0
    current_start = None
    for d in reversed(days):
        if d["contributionCount"] > 0:
            current_len += 1
            current_start = d["date"]
        else:
            if current_len > 0:
                break
    return {
        "current": current_len,
        "current_start": current_start,
        "current_end": days[-1]["date"] if current_len else None,
        "longest": best_len,
        "longest_start": best_start,
        "longest_end": best_end,
    }


def weekly_totals(weeks):
    return [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]


def svg_open(width, height):
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="{FONT_FAMILY}">'
        '<defs><linearGradient id="accent" x1="0%" x2="100%" y1="0%" y2="100%">'
        '<stop offset="0%" stop-color="#38bdf8"/><stop offset="55%" stop-color="#818cf8"/>'
        '<stop offset="100%" stop-color="#2dd4bf"/></linearGradient></defs>'
        f'<style>text{{fill:#0f172a}} .dim{{fill:#64748b}} .accent{{fill:url(#accent)}}</style>'
    )


def render_stats_svg(total, weekly, out_path):
    w, h = 460, 140
    bars = weekly[-52:]
    max_v = max(bars) if bars and max(bars) else 1
    bar_w = (w - 20) / len(bars)
    parts = [svg_open(w, h)]
    parts.append(f'<text x="10" y="30" font-size="26" class="accent">{total}</text>')
    parts.append(f'<text x="10" y="50" font-size="12" class="dim">contributions, last 12 months</text>')
    base_y = h - 12
    max_bar_h = 55
    for i, v in enumerate(bars):
        bh = (v / max_v) * max_bar_h if max_v else 0
        x = 10 + i * bar_w
        parts.append(
            f'<rect x="{x:.2f}" y="{base_y - bh:.2f}" width="{max(bar_w - 1, 1):.2f}" '
            f'height="{bh:.2f}" fill="url(#accent)" opacity="0.9" />'
        )
    parts.append("</svg>")
    with open(out_path, "w") as f:
        f.write("\n".join(parts))


def render_streak_svg(streak, out_path):
    w, h = 460, 90
    parts = [svg_open(w, h)]
    parts.append(f'<text x="10" y="28" font-size="20" fill="#7c3aed">{streak["current"]} day streak</text>')
    if streak["current_start"] and streak["current_end"]:
        parts.append(
            f'<text x="10" y="46" font-size="12" class="dim">'
            f'{streak["current_start"]} to {streak["current_end"]}</text>'
        )
    parts.append(
        f'<text x="10" y="70" font-size="14" fill="#0f766e">longest: {streak["longest"]} days</text>'
    )
    if streak["longest_start"] and streak["longest_end"]:
        parts.append(
            f'<text x="10" y="86" font-size="12" class="dim">'
            f'{streak["longest_start"]} to {streak["longest_end"]}</text>'
        )
    parts.append("</svg>")
    with open(out_path, "w") as f:
        f.write("\n".join(parts))


def render_langs_svg(repos, out_path):
    totals = {}
    colors = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#38bdf8"

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    total_bytes = sum(v for _, v in ranked) or 1

    w, h = 460, 24 + len(ranked) * 22
    parts = [svg_open(w, h)]
    y = 26
    for name, size in ranked:
        pct = size / total_bytes * 100
        bar_w = pct / 100 * 240
        parts.append(f'<text x="10" y="{y}" font-size="13">{name}</text>')
        parts.append(
            f'<rect x="140" y="{y - 11}" width="{bar_w:.1f}" height="12" fill="{colors[name]}" opacity="0.9" />'
        )
        parts.append(f'<text x="390" y="{y}" font-size="12" class="dim">{pct:.1f}%</text>')
        y += 22
    parts.append("</svg>")
    with open(out_path, "w") as f:
        f.write("\n".join(parts))


def render_year_svg(weeks, out_path):
    cell = 11
    gap = 3
    w = len(weeks) * (cell + gap) + 20
    h = 7 * (cell + gap) + 20
    parts = [svg_open(w, h)]
    max_c = max(
        (d["contributionCount"] for wk in weeks for d in wk["contributionDays"]), default=0
    ) or 1
    for wi, wk in enumerate(weeks):
        for di, d in enumerate(wk["contributionDays"]):
            level = int((d["contributionCount"] / max_c) * (len(RAMP) - 1)) if max_c else 0
            level = max(0, min(level, len(RAMP) - 1))
            palette = ["#e2e8f0", "#bae6fd", "#7dd3fc", "#818cf8", "#8b5cf6", "#14b8a6"]
            color = palette[min(len(palette) - 1, round(level / (len(RAMP) - 1) * (len(palette) - 1)))]
            x = 10 + wi * (cell + gap)
            y = 10 + di * (cell + gap)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
                f'fill="{color}"><title>{d["date"]}: {d["contributionCount"]}</title></rect>'
            )
    parts.append("</svg>")
    with open(out_path, "w") as f:
        f.write("\n".join(parts))


def main():
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN")
    if not token or not login:
        print("GITHUB_TOKEN and GH_LOGIN must be set", file=sys.stderr)
        sys.exit(1)

    user = fetch(login, token)
    calendar = user["contributionsCollection"]["contributionCalendar"]
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    all_days = [d for wk in weeks for d in wk["contributionDays"]]
    streak = compute_streaks(all_days)
    weekly = weekly_totals(weeks)
    repos = user["repositories"]["nodes"]

    render_stats_svg(total, weekly, "stats.svg")
    render_streak_svg(streak, "streak.svg")
    render_langs_svg(repos, "langs.svg")
    render_year_svg(weeks, "year.svg")

    print(f"total={total} current_streak={streak['current']} longest_streak={streak['longest']}")


if __name__ == "__main__":
    main()
