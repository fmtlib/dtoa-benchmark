#!/usr/bin/env python3
"""Generate static HTML reports from dtoa-benchmark CSV results.

Each CSV under ``results/*.csv`` is rendered to a self-contained ``.html``
file alongside it: server-rendered SVG charts, no external dependencies,
a tiny inline script for table interactivity.

Usage:
    python3 generate-html.py results/foo.csv [results/bar.csv ...]
    python3 generate-html.py --all
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


# Functions excluded from the bar chart because their times are large enough
# to flatten everyone else against the axis.
BAR_CHART_EXCLUDED = frozenset({"ostringstream", "sprintf"})

# Color palette for function series. Matches Google Charts' default
# palette (also what Google Sheets and the old chart used) so that
# previously published screenshots stay color-consistent.
PALETTE = [
    "#3366cc", "#dc3912", "#ff9900", "#109618",
    "#990099", "#0099c6", "#dd4477", "#66aa00",
    "#b82e2e", "#316395", "#994499", "#22aa99",
    "#aaaa11", "#6633cc", "#e67300", "#8b0707",
    "#651067", "#329262", "#5574a6", "#3b3eac",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> tuple[list[str], list[tuple[str, str, int, float]]]:
    """Returns (header, rows). Rows are (type, func, digit, time_ns)."""
    with path.open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows: list[tuple[str, str, int, float]] = []
        for row in reader:
            if len(row) < 4:
                continue
            type_, func, digit, time = row[0], row[1], row[2], row[3]
            try:
                rows.append((type_, func, int(digit), float(time)))
            except ValueError:
                continue
    return header, rows


def aggregate(rows: Iterable[tuple[str, str, int, float]]) -> dict:
    """Group rows by Type. For each type compute per-function digit timings
    and a mean time matching the original PHP behaviour:

    - if a function has a row with digit==0, that single value is its time;
    - otherwise the mean is sum(time for digit>0) / max_digit_global.
    """
    by_type: dict[str, dict] = {}
    max_digit = 0
    for type_, _func, digit, _time in rows:
        if digit > max_digit:
            max_digit = digit
        by_type.setdefault(type_, {"funcs": [], "times": defaultdict(dict),
                                   "fixed": {}, "digits": set()})

    for type_, func, digit, time in rows:
        bucket = by_type[type_]
        if func not in bucket["times"] and func not in bucket["fixed"]:
            bucket["funcs"].append(func)
        if digit == 0:
            bucket["fixed"][func] = time
        else:
            bucket["times"][func][digit] = time
            bucket["digits"].add(digit)

    for bucket in by_type.values():
        bucket["digits"] = sorted(bucket["digits"])
        bucket["mean"] = {}
        denom = max_digit if max_digit > 0 else 1
        for func in bucket["funcs"]:
            if func in bucket["fixed"]:
                bucket["mean"][func] = bucket["fixed"][func]
            else:
                vals = bucket["times"][func].values()
                bucket["mean"][func] = sum(vals) / denom if vals else 0.0
    return by_type


# ---------------------------------------------------------------------------
# SVG rendering helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _color_for(func: str, all_funcs: list[str]) -> str:
    return PALETTE[all_funcs.index(func) % len(PALETTE)]


def render_bar_chart(funcs: list[str], means: dict[str, float],
                     all_funcs: list[str]) -> str:
    items = [(f, means[f]) for f in funcs if f not in BAR_CHART_EXCLUDED]
    items.sort(key=lambda x: x[1])
    n = len(items)

    width = 820
    label_w = 150
    value_w = 80
    bar_h = 26
    gap = 10
    pad_t = 10
    pad_b = 10
    plot_w = width - label_w - value_w - 16
    height = pad_t + pad_b + n * bar_h + max(0, n - 1) * gap

    max_v = max((m for _, m in items), default=1.0)

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {width} {height}" '
        f'class="chart bar-chart" role="img" '
        f'aria-label="Mean conversion time per function">'
    )
    parts.append('<g class="bars">')
    for i, (func, m) in enumerate(items):
        y = pad_t + i * (bar_h + gap)
        bw = (m / max_v) * plot_w if max_v > 0 else 0
        color = _color_for(func, all_funcs)
        parts.append(
            f'<g class="bar" data-func="{_esc(func)}" data-value="{m:.4f}">'
        )
        # Transparent hit rect spanning the full row so the tooltip fires
        # anywhere in the row, not only over the visible bar.
        hit_y = y - gap / 2
        hit_h = bar_h + gap
        parts.append(
            f'<rect class="hit" x="0" y="{hit_y:.2f}" width="{width}" '
            f'height="{hit_h:.2f}" fill="transparent"/>'
        )
        parts.append(
            f'<text x="{label_w - 10}" y="{y + bar_h / 2:.2f}" '
            f'dominant-baseline="middle" text-anchor="end" class="lbl">'
            f'{_esc(func)}</text>'
        )
        parts.append(
            f'<rect class="fill" x="{label_w}" y="{y}" '
            f'width="{bw:.2f}" height="{bar_h}" '
            f'fill="{color}" rx="3" ry="3"/>'
        )
        parts.append(
            f'<text x="{label_w + bw + 8:.2f}" y="{y + bar_h / 2:.2f}" '
            f'dominant-baseline="middle" class="val">{m:,.2f} ns</text>'
        )
        parts.append('</g>')
    parts.append('</g>')
    parts.append('</svg>')
    return f'<div class="chart-wrap bar-wrap">{"".join(parts)}</div>'


def _nice_log_ticks(vmin: float, vmax: float) -> tuple[float, float, list[float], list[float]]:
    """Return (log_lo, log_hi, major_ticks, minor_ticks) for a log-scale Y
    axis. Majors land at 1*10^k and 5*10^k; minors at 2..4, 6..9 * 10^k.
    The log range is padded slightly so the data lines don't touch the
    plot edges."""
    if vmin <= 0:
        vmin = 1.0
    if vmax <= vmin:
        vmax = vmin * 10
    log_lo = math.log10(vmin)
    log_hi = math.log10(vmax)
    span = log_hi - log_lo
    pad = max(span * 0.04, 0.02)
    log_lo -= pad
    log_hi += pad

    lo_dec = math.floor(log_lo)
    hi_dec = math.ceil(log_hi)
    majors: list[float] = []
    minors: list[float] = []
    for k in range(lo_dec, hi_dec + 1):
        base = 10.0 ** k
        for m in (1, 5):
            v = m * base
            if log_lo <= math.log10(v) <= log_hi:
                majors.append(v)
        for m in (2, 3, 4, 6, 7, 8, 9):
            v = m * base
            if log_lo <= math.log10(v) <= log_hi:
                minors.append(v)
    return log_lo, log_hi, majors, minors


def render_line_chart(funcs: list[str], digits: list[int],
                      times: dict[str, dict[int, float]],
                      all_funcs: list[str]) -> str:
    width, height = 820, 560
    margin = {"l": 64, "r": 24, "t": 16, "b": 56}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]
    # Reserve space at the bottom of the plot for a "0" baseline tick so
    # the lines don't visually start from the chart's bottom edge.
    zero_pad = 22
    data_h = plot_h - zero_pad

    all_vals = [v for f in funcs for v in times[f].values() if v > 0]
    if not all_vals or not digits:
        return '<svg viewBox="0 0 100 20" class="chart"></svg>'
    vmin, vmax = min(all_vals), max(all_vals)
    log_lo, log_hi, majors, minors = _nice_log_ticks(vmin, vmax)

    def x_of(d: int) -> float:
        if len(digits) == 1:
            return margin["l"] + plot_w / 2
        i = digits.index(d)
        return margin["l"] + i * plot_w / (len(digits) - 1)

    def y_of(t: float) -> float:
        if t <= 0:
            return margin["t"] + plot_h
        v = (math.log10(t) - log_lo) / (log_hi - log_lo)
        return margin["t"] + (1 - v) * data_h

    y_zero = margin["t"] + plot_h
    plot_left = margin["l"]
    plot_right = margin["l"] + plot_w
    plot_top = margin["t"]
    plot_bot = margin["t"] + plot_h

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {width} {height}" '
        f'class="chart line-chart" role="img" '
        f'aria-label="Time vs digit count, log scale">'
    )

    # Plot background
    parts.append(
        f'<rect x="{plot_left}" y="{plot_top}" '
        f'width="{plot_w}" height="{plot_h}" class="plot-bg"/>'
    )

    # Vertical gridlines + X tick labels (one per digit)
    for d in digits:
        x = x_of(d)
        parts.append(
            f'<line x1="{x:.2f}" x2="{x:.2f}" '
            f'y1="{plot_top}" y2="{plot_bot}" class="grid"/>'
        )
        parts.append(
            f'<text x="{x:.2f}" y="{plot_bot + 18}" '
            f'text-anchor="middle" class="ax">{d}</text>'
        )

    # Minor horizontal gridlines (log)
    for v in minors:
        y = y_of(v)
        parts.append(
            f'<line x1="{plot_left}" x2="{plot_right}" '
            f'y1="{y:.2f}" y2="{y:.2f}" class="grid-minor"/>'
        )
    # Major horizontal gridlines + Y-axis labels
    for v in majors:
        y = y_of(v)
        parts.append(
            f'<line x1="{plot_left}" x2="{plot_right}" '
            f'y1="{y:.2f}" y2="{y:.2f}" class="grid-major"/>'
        )
        parts.append(
            f'<text x="{plot_left - 8}" y="{y:.2f}" '
            f'dominant-baseline="middle" text-anchor="end" class="ax">'
            f'{v:,g}</text>'
        )
    # "0" baseline at the bottom of the plot. The data lines never reach
    # here (log scale can't represent zero), but the tick mirrors what
    # Google Charts does and gives the chart a visual floor.
    parts.append(
        f'<line x1="{plot_left}" x2="{plot_right}" '
        f'y1="{y_zero:.2f}" y2="{y_zero:.2f}" class="grid-major"/>'
    )
    parts.append(
        f'<text x="{plot_left - 8}" y="{y_zero:.2f}" '
        f'dominant-baseline="middle" text-anchor="end" class="ax">0</text>'
    )

    # Axis titles
    parts.append(
        f'<text x="{plot_left + plot_w / 2:.2f}" y="{height - 8}" '
        f'text-anchor="middle" class="ax-title">Digits</text>'
    )
    parts.append(
        f'<text transform="translate(16 {plot_top + plot_h / 2:.2f}) '
        f'rotate(-90)" text-anchor="middle" class="ax-title">'
        f'Time (ns)</text>'
    )

    # Series. Also collect per-point coordinates for JS hit-testing.
    series_meta: list[dict] = []
    parts.append('<g class="series">')
    for func in funcs:
        pts = [(d, times[func].get(d, 0.0)) for d in digits
               if times[func].get(d, 0.0) > 0]
        if not pts:
            continue
        color = _color_for(func, all_funcs)
        path = " ".join(f"{x_of(d):.2f},{y_of(t):.2f}" for d, t in pts)
        parts.append(
            f'<g class="ln" data-func="{_esc(func)}">'
            f'<polyline points="{path}" fill="none" '
            f'stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'</g>'
        )
        series_meta.append({
            "func": func,
            "color": color,
            "points": [
                {"d": d, "x": round(x_of(d), 2),
                 "y": round(y_of(t), 2), "v": t}
                for d, t in pts
            ],
        })
    parts.append('</g>')

    # Focus elements, revealed by JS on hover.
    parts.append(
        '<g class="focus" pointer-events="none" style="display:none">'
        f'<line class="crosshair" y1="{plot_top}" y2="{plot_bot}"/>'
        '<circle class="dot" r="4.5" fill="currentColor" stroke="white"'
        ' stroke-width="2"/>'
        '</g>'
    )

    # Plot border
    parts.append(
        f'<rect x="{plot_left}" y="{plot_top}" '
        f'width="{plot_w}" height="{plot_h}" class="plot-border"/>'
    )

    parts.append('</svg>')

    meta = {
        "width": width,
        "height": height,
        "plot": {"l": plot_left, "r": plot_right,
                 "t": plot_top, "b": plot_bot},
        "series": series_meta,
    }
    # `<script>` content is raw text; escape any sequence that would close
    # the tag prematurely. HTML entity escaping must NOT be applied here.
    meta_json = (json.dumps(meta, separators=(",", ":"))
                 .replace("</", "<\\/"))
    return (
        '<div class="chart-wrap line-wrap">'
        f'{"".join(parts)}'
        f'<div class="tt" hidden></div>'
        f'<script type="application/json" class="chart-meta">{meta_json}'
        '</script>'
        '</div>'
    )


def render_legend(funcs: list[str], all_funcs: list[str]) -> str:
    items = []
    for f in funcs:
        c = _color_for(f, all_funcs)
        items.append(
            f'<button type="button" class="lg" data-func="{_esc(f)}">'
            f'<span class="sw" style="background:{c}"></span>{_esc(f)}'
            f'</button>'
        )
    return f'<div class="legend">{"".join(items)}</div>'


def render_table(funcs: list[str], means: dict[str, float]) -> str:
    items = sorted(funcs, key=lambda f: means[f])
    body_rows = []
    for f in items:
        body_rows.append(
            f'<tr data-func="{_esc(f)}" data-mean="{means[f]}" tabindex="0">'
            f'<td class="f">{_esc(f)}</td>'
            f'<td class="t num">{means[f]:,.2f}</td>'
            f'<td class="s num"></td>'
            f'</tr>'
        )
    return (
        '<table class="results">'
        '<thead><tr>'
        '<th scope="col">Method</th>'
        '<th scope="col" class="num">Time (ns)</th>'
        '<th scope="col" class="num">Speedup</th>'
        '</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        '</table>'
    )


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

PAGE_CSS = """
:root {
  --bg: #ffffff;
  --bg-soft: #f6f7f9;
  --fg: #0f172a;
  --fg-muted: #64748b;
  --border: #e2e8f0;
  --border-strong: #cbd5e1;
  --accent: #2563eb;
  --accent-soft: #dbeafe;
  --grid: #cccccc;
  --grid-major: #b8bcc4;
  --grid-minor: #e6e6e6;
  --selected: #fef3c7;
  --selected-fg: #78350f;
  --shadow: 0 1px 2px rgba(15, 23, 42, 0.04),
            0 4px 12px rgba(15, 23, 42, 0.04);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0b1220;
    --bg-soft: #111a2e;
    --fg: #e2e8f0;
    --fg-muted: #94a3b8;
    --border: #1e293b;
    --border-strong: #334155;
    --accent: #60a5fa;
    --accent-soft: #1e3a8a;
    --grid: #2f3641;
    --grid-major: #44505f;
    --grid-minor: #1a2230;
    --selected: #422006;
    --selected-fg: #fde68a;
    --shadow: 0 1px 2px rgba(0, 0, 0, 0.3),
              0 4px 12px rgba(0, 0, 0, 0.25);
  }
}
* { box-sizing: border-box; }
html { color-scheme: light dark; }
body {
  margin: 0;
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        "Helvetica Neue", Arial, sans-serif;
  color: var(--fg);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}
header.site {
  position: sticky;
  top: 0;
  z-index: 10;
  background: color-mix(in srgb, var(--bg) 92%, transparent);
  backdrop-filter: saturate(160%) blur(8px);
  border-bottom: 1px solid var(--border);
}
header.site .row {
  max-width: 920px;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
header.site a.brand {
  font-weight: 600;
  color: var(--fg);
  text-decoration: none;
}
header.site a.brand:hover { color: var(--accent); }
header.site nav {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: auto;
  flex-wrap: wrap;
}
header.site nav .picker {
  position: relative;
}
header.site nav .picker > summary {
  list-style: none;
  cursor: pointer;
  padding: 6px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  background: var(--bg-soft);
  user-select: none;
}
header.site nav .picker > summary::-webkit-details-marker { display: none; }
header.site nav .picker > summary::after {
  content: " ▾";
  color: var(--fg-muted);
}
header.site nav .picker[open] > summary {
  border-color: var(--accent);
}
header.site nav .picker .menu {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  min-width: 320px;
  max-height: 60vh;
  overflow: auto;
  background: var(--bg);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 4px;
}
header.site nav .picker .menu a {
  display: block;
  padding: 6px 10px;
  border-radius: 4px;
  color: var(--fg);
  text-decoration: none;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
               monospace;
  font-size: 13px;
}
header.site nav .picker .menu a:hover {
  background: var(--accent-soft);
  color: var(--accent);
}
header.site nav .picker .menu a.current {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
main {
  max-width: 920px;
  margin: 0 auto;
  padding: 24px;
}
h1 {
  font-size: 22px;
  margin: 8px 0 4px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
               monospace;
  word-break: break-all;
}
h3 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--fg-muted);
  margin: 0 0 12px;
  font-weight: 600;
}
.card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow);
}
.card .hint {
  color: var(--fg-muted);
  font-size: 12px;
  margin: 8px 0 0;
}
.card .card-divider {
  height: 1px;
  background: var(--border);
  margin: 24px -20px;
}
table.results {
  width: 100%;
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
}
table.results th,
table.results td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  text-align: left;
}
table.results th {
  font-weight: 600;
  color: var(--fg-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
table.results td.num,
table.results th.num { text-align: right; }
table.results tbody tr {
  cursor: pointer;
  transition: background-color 80ms ease;
}
table.results tbody tr:hover { background: var(--bg-soft); }
table.results tbody tr.selected {
  background: var(--selected);
  color: var(--selected-fg);
}
table.results tbody tr.selected td.f { font-weight: 600; }
table.results tbody tr:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.chart-wrap {
  position: relative;
}
.chart {
  width: 100%;
  height: auto;
  display: block;
}
.chart .lbl,
.chart .val,
.chart .ax {
  fill: var(--fg);
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.chart .ax,
.chart .val { fill: var(--fg-muted); }
.chart .ax-title {
  fill: var(--fg-muted);
  font-size: 12px;
  font-style: italic;
}
.line-chart .ax,
.line-chart .ax-title { fill: var(--fg); }
.chart .grid { stroke: var(--grid); stroke-width: 1; }
.chart .grid-major { stroke: var(--grid-major); stroke-width: 1; }
.chart .grid-minor { stroke: var(--grid-minor); stroke-width: 1; }
.chart .plot-bg { fill: var(--bg-soft); }
.line-chart .plot-bg { fill: var(--bg); }
.chart .plot-border {
  fill: none;
  stroke: var(--border-strong);
  stroke-width: 1;
}
.bar-chart .bar .fill { transition: filter 120ms ease; }
.bar-chart .bar.focused .fill {
  filter: drop-shadow(0 2px 4px rgba(15, 23, 42, 0.35));
}
@media (prefers-color-scheme: dark) {
  .bar-chart .bar.focused .fill {
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.75));
  }
}
.line-chart .ln {
  transition: opacity 120ms ease;
}
.line-chart.has-focus .ln { opacity: 0.2; }
.line-chart .ln.focused { opacity: 1; }
.line-chart .focus .crosshair {
  stroke: var(--border-strong);
  stroke-width: 1;
  stroke-dasharray: 2 3;
}
.tt {
  position: absolute;
  pointer-events: none;
  background: var(--bg);
  color: var(--fg);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  padding: 8px 10px;
  box-shadow: var(--shadow);
  font-size: 12px;
  line-height: 1.45;
  white-space: nowrap;
  z-index: 5;
  transition: opacity 80ms ease;
}
.tt[hidden] { display: none; }
.tt .d {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 2px;
  color: var(--fg);
}
.tt .r {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--fg-muted);
}
.tt .r .sw {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex: none;
}
.tt .r .f { color: var(--fg); }
.tt .r .v { color: var(--fg); font-weight: 600; }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}
.legend .lg {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg);
  color: var(--fg);
  font: inherit;
  cursor: pointer;
  transition: all 120ms ease;
}
.legend .lg:hover { border-color: var(--border-strong); }
.legend .lg.dim { opacity: 0.35; }
.legend .lg.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.legend .sw {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
footer {
  max-width: 920px;
  margin: 32px auto 48px;
  padding: 16px 24px;
  color: var(--fg-muted);
  font-size: 12px;
  border-top: 1px solid var(--border);
}
footer a { color: inherit; }
"""


PAGE_JS = r"""
(function () {
  // Table: click a row to make it the speedup baseline.
  document.querySelectorAll("table.results").forEach(function (tbl) {
    var rows = Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));
    function recompute(baseRow) {
      var base = parseFloat(baseRow.dataset.mean);
      rows.forEach(function (r) {
        var t = parseFloat(r.dataset.mean);
        var ratio = t > 0 ? base / t : 0;
        r.querySelector(".s").textContent = ratio.toFixed(3) + "x";
        r.classList.toggle("selected", r === baseRow);
      });
    }
    rows.forEach(function (r) {
      r.addEventListener("click", function () { recompute(r); });
      r.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          recompute(r);
        }
      });
    });
    var defaultRow = rows.find(function (r) {
      return r.dataset.func === "sprintf";
    }) || rows[0];
    if (defaultRow) recompute(defaultRow);
  });

  // Line chart: legend hover/click highlights a series; pointer movement
  // over the plot area shows a value tooltip and a focus dot.
  document.querySelectorAll(".line-wrap").forEach(function (wrap) {
    var chart = wrap.querySelector(".line-chart");
    var legend = wrap.parentElement.querySelector(".legend");
    var tooltip = wrap.querySelector(".tt");
    var meta;
    try {
      var script = wrap.querySelector("script.chart-meta");
      meta = JSON.parse(script.textContent);
    } catch (err) { return; }
    var focus = chart.querySelector(".focus");
    var crosshair = focus.querySelector(".crosshair");
    var dot = focus.querySelector(".dot");
    var lines = chart.querySelectorAll(".ln");
    var pinnedFunc = null;
    var hoveredFunc = null;

    function applyHighlight() {
      var f = hoveredFunc || pinnedFunc;
      chart.classList.toggle("has-focus", !!f);
      lines.forEach(function (l) {
        l.classList.toggle("focused", l.dataset.func === f);
      });
      if (legend) {
        legend.querySelectorAll(".lg").forEach(function (b) {
          b.classList.toggle("active", b.dataset.func === f);
          b.classList.toggle("dim", !!f && b.dataset.func !== f);
        });
      }
    }

    function hideTooltip() {
      hoveredFunc = null;
      focus.style.display = "none";
      tooltip.hidden = true;
      applyHighlight();
    }

    chart.addEventListener("pointermove", function (e) {
      var rect = chart.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      var sx = (e.clientX - rect.left) * meta.width / rect.width;
      var sy = (e.clientY - rect.top) * meta.height / rect.height;
      var p = meta.plot;
      if (sx < p.l || sx > p.r || sy < p.t || sy > p.b) {
        hideTooltip();
        return;
      }
      // Snap to the nearest digit column.
      var firstSeries = meta.series[0];
      if (!firstSeries) return;
      var nearestX = firstSeries.points[0].x;
      var minDX = Math.abs(sx - nearestX);
      for (var i = 0; i < firstSeries.points.length; i++) {
        var px = firstSeries.points[i].x;
        var dx = Math.abs(sx - px);
        if (dx < minDX) { minDX = dx; nearestX = px; }
      }
      // For that digit, find the series whose Y is closest to the pointer.
      var best = null, bestDist = Infinity;
      for (var s = 0; s < meta.series.length; s++) {
        var series = meta.series[s];
        for (var k = 0; k < series.points.length; k++) {
          var pt = series.points[k];
          if (pt.x !== nearestX) continue;
          var dist = Math.abs(sy - pt.y);
          if (dist < bestDist) {
            bestDist = dist;
            best = { series: series, point: pt };
          }
          break;
        }
      }
      if (!best) { hideTooltip(); return; }

      // Update focus elements.
      crosshair.setAttribute("x1", best.point.x);
      crosshair.setAttribute("x2", best.point.x);
      dot.setAttribute("cx", best.point.x);
      dot.setAttribute("cy", best.point.y);
      dot.setAttribute("fill", best.series.color);
      focus.style.display = "";

      hoveredFunc = best.series.func;
      applyHighlight();

      // Render tooltip content + position.
      tooltip.innerHTML =
        '<div class="d">' + best.point.d + ' digits</div>' +
        '<div class="r"><span class="sw" style="background:' +
        best.series.color + '"></span><span class="f">' +
        escapeHtml(best.series.func) + '</span>:&nbsp;<span class="v">' +
        formatNs(best.point.v) + ' ns</span></div>';
      tooltip.hidden = false;

      var sxScale = rect.width / meta.width;
      var syScale = rect.height / meta.height;
      var px = best.point.x * sxScale;
      var py = best.point.y * syScale;
      var ttRect = tooltip.getBoundingClientRect();
      var left = px + 14;
      var top = py - ttRect.height - 10;
      if (left + ttRect.width > rect.width - 4) {
        left = px - ttRect.width - 14;
      }
      if (top < 4) top = py + 14;
      if (left < 4) left = 4;
      if (top + ttRect.height > rect.height - 4) {
        top = rect.height - ttRect.height - 4;
      }
      tooltip.style.left = left + "px";
      tooltip.style.top = top + "px";
    });

    chart.addEventListener("pointerleave", hideTooltip);

    // Legend interactions (hover dim, click pin).
    if (legend) {
      legend.querySelectorAll(".lg").forEach(function (btn) {
        btn.addEventListener("mouseenter", function () {
          if (!pinnedFunc && !hoveredFunc) {
            hoveredFunc = btn.dataset.func;
            applyHighlight();
          }
        });
        btn.addEventListener("mouseleave", function () {
          if (hoveredFunc === btn.dataset.func) {
            hoveredFunc = null;
            applyHighlight();
          }
        });
        btn.addEventListener("click", function () {
          pinnedFunc = pinnedFunc === btn.dataset.func
            ? null : btn.dataset.func;
          applyHighlight();
        });
      });
    }
  });

  // Bar chart: highlight the hovered bar with a drop-shadow.
  document.querySelectorAll(".bar-wrap .bar-chart").forEach(function (chart) {
    var bars = chart.querySelectorAll(".bar");
    bars.forEach(function (g) {
      g.addEventListener("pointerenter", function () {
        bars.forEach(function (b) {
          b.classList.toggle("focused", b === g);
        });
      });
      g.addEventListener("pointerleave", function () {
        g.classList.remove("focused");
      });
    });
  });

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c];
    });
  }
  function formatNs(v) {
    return v.toFixed(2);
  }
})();
"""


def render_section(type_name: str, bucket: dict) -> str:
    funcs = bucket["funcs"]
    means = bucket["mean"]
    digits = bucket["digits"]
    times = bucket["times"]
    anchor = type_name.lower().replace(" ", "-")

    section = [
        f'<section data-type="{_esc(type_name)}" id="{_esc(anchor)}">',
        '<div class="card">',
        '<h3>Time per double (lower is better)</h3>',
        render_table(funcs, means),
        '<p class="hint">Click any row to use it as the speedup baseline.</p>',
    ]

    bar_funcs = [f for f in funcs if f not in BAR_CHART_EXCLUDED]
    if bar_funcs:
        excluded_present = sorted(BAR_CHART_EXCLUDED & set(funcs))
        if excluded_present:
            names = " and ".join(f"<code>{_esc(n)}</code>"
                                 for n in excluded_present)
            hint = (f'<p class="hint">{names} omitted; they are an order '
                    f'of magnitude slower than the rest.</p>')
        else:
            hint = '<p class="hint">All measured functions shown.</p>'
        section += [
            '<div class="card-divider"></div>',
            render_bar_chart(funcs, means, funcs),
            hint,
        ]
    section.append('</div>')

    if digits and times:
        section += [
            '<div class="card">',
            '<h3>Time vs. digit count (log scale)</h3>',
            render_line_chart(funcs, digits, times, funcs),
            render_legend(funcs, funcs),
            '<p class="hint">Hover or click a function to highlight its '
            'series.</p>',
            '</div>',
        ]

    section.append('</section>')
    return "".join(section)


def render_page(csv_path: Path) -> str:
    name = csv_path.stem
    _header, rows = load_csv(csv_path)
    by_type = aggregate(rows)
    types = sorted(by_type.keys())

    sections_html = "".join(render_section(t, by_type[t]) for t in types)

    section_links = "".join(
        f'<a href="#{_esc(t.lower().replace(" ", "-"))}">{_esc(t)}</a>'
        for t in types
    )
    section_menu = ""
    if len(types) > 1:
        section_menu = (
            '<details class="picker"><summary>Section</summary>'
            f'<div class="menu">{section_links}</div></details>'
        )

    nav_html = f'<nav>{section_menu}</nav>' if section_menu else ''

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(name)} — dtoa-benchmark</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="site">
  <div class="row">
    <a class="brand" href="https://github.com/fmtlib/dtoa-benchmark">dtoa-benchmark</a>
    {nav_html}
  </div>
</header>
<main>
  <h1 id="title">{_esc(name)}</h1>
  {sections_html}
</main>
<footer>
  Generated from <code>{_esc(csv_path.name)}</code> by
  <a href="https://github.com/fmtlib/dtoa-benchmark">fmtlib/dtoa-benchmark</a>.
</footer>
<script>{PAGE_JS}</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def process(csv_path: Path) -> Path:
    out = csv_path.with_suffix(".html")
    out.write_text(render_page(csv_path), encoding="utf-8")
    return out


def is_stale(csv_path: Path) -> bool:
    """True if the matching .html is missing or older than the CSV."""
    out = csv_path.with_suffix(".html")
    if not out.exists():
        return True
    return csv_path.stat().st_mtime > out.stat().st_mtime


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="*", type=Path,
                        help="CSV files to convert.")
    parser.add_argument("--all", action="store_true",
                        help="Process every results/*.csv file.")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if the .html is up to date.")
    args = parser.parse_args(argv)

    if args.all:
        repo_root = Path(__file__).resolve().parent
        targets = sorted((repo_root / "results").glob("*.csv"))
    else:
        targets = list(args.csv)

    if not targets:
        parser.error("no CSV files specified (use --all or pass paths).")

    for csv_path in targets:
        if not csv_path.exists():
            print(f"warning: {csv_path} does not exist; skipping",
                  file=sys.stderr)
            continue
        if not args.force and not is_stale(csv_path):
            continue
        out = process(csv_path)
        print(f"  {csv_path} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
