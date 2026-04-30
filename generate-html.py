#!/usr/bin/env python3
"""Generate static HTML reports from dtoa-benchmark results.

Each result file under ``results/`` is rendered to a self-contained ``.html``
file alongside it: server-rendered SVG charts, no external dependencies,
a tiny inline script for table interactivity.

Two input formats are supported:

* ``*.json``  -- Google Benchmark's native JSON output, written by current
  builds. Carries a rich ``context`` block (CPU info, caches, library
  version, custom keys such as ``commit_hash``/``machine``/``os``/
  ``compiler``) plus per-benchmark ``real_time``/``iterations``/counters.
* ``*.csv``   -- legacy ``Type,Method,Digit,Time(ns)`` files committed
  before the JSON migration. Read but never produced.

Usage:
    python3 generate-html.py results/foo.json [results/bar.csv ...]
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

# Pseudo-method that does nothing; its time is the cost of the benchmark
# loop itself (data load, indirect call, buffer write). It's surfaced as a
# baseline footnote and a dashed reference line, not as a competing method.
BASELINE_METHOD = "null"

# Color palette for method series. Matches Google Charts' default
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

# Single bucket name for the rendered section. Originally the CSV's "Type"
# column distinguished different benchmark families; today there's only one,
# but the rendering pipeline still groups by type, so we keep a constant.
DEFAULT_TYPE = "randomdigit"


def load_csv(path: Path) -> list[tuple[str, str, int, float]]:
    """Read a legacy ``Type,Method,Digit,Time(ns)`` CSV.

    Returns rows of (type, method, digit, time_ns). Kept for backwards
    compatibility with CSV result files committed before the JSON switch."""
    with path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        rows: list[tuple[str, str, int, float]] = []
        for row in reader:
            if len(row) < 4:
                continue
            type_, method, digit, time = row[0], row[1], row[2], row[3]
            try:
                rows.append((type_, method, int(digit), float(time)))
            except ValueError:
                continue
    return rows


def load_json(path: Path) -> list[tuple[str, str, int, float]]:
    """Read Google Benchmark's native JSON output.

    Each ``benchmarks[]`` entry has a name like ``method`` (mixed pool) or
    ``method/d<N>`` (per-digit). Ns-per-double is derived from the
    ``Time/double`` user counter set in src/benchmark.cc, which is
    seconds-per-double after Google Benchmark's counter ``Finish()`` step
    (``kIsIterationInvariantRate | kInvert``)."""
    with path.open() as f:
        data = json.load(f)

    rows: list[tuple[str, str, int, float]] = []
    for r in data.get("benchmarks", []):
        # Skip aggregate rows (mean/median/stddev) when --benchmark_repetitions
        # is used; we want the raw per-iteration timings only.
        if r.get("run_type") and r["run_type"] != "iteration":
            continue
        if r.get("error_occurred"):
            continue
        name = r.get("run_name") or r.get("name") or ""
        sep = name.rfind("/d")
        if sep == -1:
            method = name
            digit = 0
        else:
            method = name[:sep]
            try:
                digit = int(name[sep + 2:])
            except ValueError:
                continue
        # Prefer the pre-computed counter; fall back to real_time/iterations
        # math if a future config drops the counter.
        if "Time/double" in r:
            time_ns = float(r["Time/double"]) * 1e9
        else:
            unit_to_ns = {"ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9}
            unit = r.get("time_unit", "ns")
            real_time = float(r["real_time"])
            items = 100_000 if digit > 0 else 100_000 * 17
            time_ns = real_time * unit_to_ns.get(unit, 1.0) / items
        rows.append((DEFAULT_TYPE, method, digit, time_ns))
    return rows


def load_results(path: Path) -> list[tuple[str, str, int, float]]:
    """Dispatch on file extension; supports .json (current) and .csv (legacy)."""
    if path.suffix == ".json":
        return load_json(path)
    if path.suffix == ".csv":
        return load_csv(path)
    raise ValueError(f"unsupported result file extension: {path.suffix}")


def aggregate(rows: Iterable[tuple[str, str, int, float]]) -> dict:
    """Group rows by Type. For each type compute per-method digit timings
    and a mean time matching the original PHP behaviour:

    - if a method has a row with digit==0, that single value is its time;
    - otherwise the mean is sum(time for digit>0) / max_digit_global.
    """
    by_type: dict[str, dict] = {}
    max_digit = 0
    for type_, _method, digit, _time in rows:
        if digit > max_digit:
            max_digit = digit
        by_type.setdefault(type_, {"methods": [], "times": defaultdict(dict),
                                   "fixed": {}, "digits": set()})

    for type_, method, digit, time in rows:
        bucket = by_type[type_]
        if method not in bucket["times"] and method not in bucket["fixed"]:
            bucket["methods"].append(method)
        if digit == 0:
            bucket["fixed"][method] = time
        else:
            bucket["times"][method][digit] = time
            bucket["digits"].add(digit)

    for bucket in by_type.values():
        bucket["digits"] = sorted(bucket["digits"])
        bucket["mean"] = {}
        denom = max_digit if max_digit > 0 else 1
        for method in bucket["methods"]:
            if method in bucket["fixed"]:
                bucket["mean"][method] = bucket["fixed"][method]
            else:
                vals = bucket["times"][method].values()
                bucket["mean"][method] = sum(vals) / denom if vals else 0.0
    return by_type


# ---------------------------------------------------------------------------
# SVG rendering helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _color_for(method: str, all_methods: list[str]) -> str:
    return PALETTE[all_methods.index(method) % len(PALETTE)]


def render_bar_chart(methods: list[str], means: dict[str, float],
                     all_methods: list[str]) -> str:
    items = [(m, means[m]) for m in methods if m not in BAR_CHART_EXCLUDED]
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

    max_v = max((v for _, v in items), default=1.0)

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {width} {height}" '
        f'class="chart bar-chart" role="img" '
        f'aria-label="Mean conversion time per method">'
    )
    parts.append('<g class="bars">')
    for i, (method, v) in enumerate(items):
        y = pad_t + i * (bar_h + gap)
        bw = (v / max_v) * plot_w if max_v > 0 else 0
        color = _color_for(method, all_methods)
        parts.append(
            f'<g class="bar" data-method="{_esc(method)}" data-value="{v:.4f}">'
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
            f'{_esc(method)}</text>'
        )
        parts.append(
            f'<rect class="fill" x="{label_w}" y="{y}" '
            f'width="{bw:.2f}" height="{bar_h}" '
            f'fill="{color}" rx="3" ry="3"/>'
        )
        parts.append(
            f'<text x="{label_w + bw + 8:.2f}" y="{y + bar_h / 2:.2f}" '
            f'dominant-baseline="middle" class="val">{v:,.2f} ns</text>'
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


def render_line_chart(methods: list[str], digits: list[int],
                      times: dict[str, dict[int, float]],
                      all_methods: list[str],
                      baseline_method: str | None = None) -> str:
    width, height = 820, 560
    margin = {"l": 64, "r": 24, "t": 16, "b": 56}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]
    # Reserve space at the bottom of the plot for a "0" baseline tick so
    # the lines don't visually start from the chart's bottom edge.
    zero_pad = 22
    data_h = plot_h - zero_pad

    all_vals = [v for m in methods for v in times[m].values() if v > 0]
    # Include the loop-overhead baseline in the y-axis range so that its
    # dashed reference line stays visible at the bottom of the plot.
    if baseline_method and baseline_method in times:
        all_vals += [v for v in times[baseline_method].values() if v > 0]
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
    for method in methods:
        pts = [(d, times[method].get(d, 0.0)) for d in digits
               if times[method].get(d, 0.0) > 0]
        if not pts:
            continue
        color = _color_for(method, all_methods)
        path = " ".join(f"{x_of(d):.2f},{y_of(t):.2f}" for d, t in pts)
        parts.append(
            f'<g class="ln" data-method="{_esc(method)}">'
            f'<polyline points="{path}" fill="none" '
            f'stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'</g>'
        )
        series_meta.append({
            "method": method,
            "color": color,
            "points": [
                {"d": d, "x": round(x_of(d), 2),
                 "y": round(y_of(t), 2), "v": t}
                for d, t in pts
            ],
        })
    parts.append('</g>')

    # Loop-overhead baseline as a dashed gray reference line. Not part of
    # `series_meta`, so it's invisible to the tooltip / legend hit-testing.
    if baseline_method and baseline_method in times:
        bpts = [(d, times[baseline_method].get(d, 0.0)) for d in digits
                if times[baseline_method].get(d, 0.0) > 0]
        if bpts:
            bpath = " ".join(f"{x_of(d):.2f},{y_of(t):.2f}" for d, t in bpts)
            avg = sum(t for _, t in bpts) / len(bpts)
            parts.append(
                f'<g class="baseline">'
                f'<polyline points="{bpath}" fill="none"/>'
                f'<text x="{plot_right - 6}" y="{y_of(avg) - 6:.2f}" '
                f'text-anchor="end" class="baseline-lbl">'
                f'loop overhead ({avg:,.2f} ns)</text>'
                f'</g>'
            )

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


def render_legend(methods: list[str], all_methods: list[str]) -> str:
    items = []
    for m in methods:
        c = _color_for(m, all_methods)
        items.append(
            f'<button type="button" class="lg" data-method="{_esc(m)}">'
            f'<span class="sw" style="background:{c}"></span>{_esc(m)}'
            f'</button>'
        )
    return f'<div class="legend">{"".join(items)}</div>'


def render_table(methods: list[str], means: dict[str, float]) -> str:
    items = sorted(methods, key=lambda m: means[m])
    body_rows = []
    for m in items:
        body_rows.append(
            f'<tr data-method="{_esc(m)}" data-mean="{means[m]}" tabindex="0">'
            f'<td class="f">{_esc(m)}</td>'
            f'<td class="t num">{means[m]:,.2f}</td>'
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
.line-chart .baseline polyline {
  fill: none;
  stroke: var(--fg-muted);
  stroke-width: 1.25;
  stroke-dasharray: 6 4;
  opacity: 0.55;
}
.line-chart .baseline-lbl {
  fill: var(--fg-muted);
  font-size: 11px;
  font-style: italic;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  opacity: 0.85;
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
.hint-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin: 8px 0 0;
}
.hint-row .hint { margin: 0; }
.copy-md {
  background: var(--bg);
  color: var(--fg-muted);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 10px;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: all 120ms ease;
  white-space: nowrap;
}
.copy-md:hover {
  border-color: var(--border-strong);
  color: var(--fg);
}
.copy-md.copied {
  border-color: var(--accent);
  color: var(--accent);
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
  // Table: click a row to make it the speedup baseline. The initial
  // baseline is `sprintf` (or the first row), but we don't highlight it
  // until the user actually picks one.
  document.querySelectorAll("table.results").forEach(function (tbl) {
    var rows = Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));
    function recompute(baseRow, highlight) {
      var base = parseFloat(baseRow.dataset.mean);
      rows.forEach(function (r) {
        var t = parseFloat(r.dataset.mean);
        var ratio = t > 0 ? base / t : 0;
        r.querySelector(".s").textContent = ratio.toFixed(3) + "x";
        r.classList.toggle("selected", highlight && r === baseRow);
      });
    }
    rows.forEach(function (r) {
      r.addEventListener("click", function () { recompute(r, true); });
      r.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          recompute(r, true);
        }
      });
    });
    var defaultRow = rows.find(function (r) {
      return r.dataset.method === "sprintf";
    }) || rows[0];
    if (defaultRow) recompute(defaultRow, false);
  });

  // Copy-as-Markdown button: serializes the adjacent results table to a
  // GitHub-flavored markdown table with right-aligned numeric columns.
  document.querySelectorAll(".copy-md").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var card = btn.closest(".card");
      var tbl = card && card.querySelector("table.results");
      if (!tbl) return;
      var ths = Array.prototype.slice.call(tbl.querySelectorAll("thead th"));
      var heads = ths.map(function (th) { return th.textContent.trim(); });
      var rights = ths.map(function (th) {
        return th.classList.contains("num");
      });
      var rows = Array.prototype.slice.call(
        tbl.querySelectorAll("tbody tr")
      ).map(function (tr) {
        return Array.prototype.slice.call(tr.cells).map(function (td) {
          return td.textContent.trim();
        });
      });
      var widths = heads.map(function (h, i) {
        var w = h.length;
        rows.forEach(function (r) {
          if (r[i] && r[i].length > w) w = r[i].length;
        });
        return w;
      });
      function pad(s, w, right) {
        while (s.length < w) s = right ? " " + s : s + " ";
        return s;
      }
      function fmtRow(cells) {
        return "| " + cells.map(function (c, i) {
          return pad(c, widths[i], rights[i]);
        }).join(" | ") + " |";
      }
      var sep = "|" + widths.map(function (w, i) {
        var len = w + 2;
        return rights[i]
          ? new Array(len).join("-") + ":"
          : new Array(len + 1).join("-");
      }).join("|") + "|";
      var md = [fmtRow(heads), sep]
        .concat(rows.map(fmtRow)).join("\n") + "\n";

      function done(ok) {
        var orig = btn.dataset.label || btn.textContent;
        btn.dataset.label = orig;
        btn.textContent = ok ? "Copied!" : "Copy failed";
        btn.classList.toggle("copied", ok);
        setTimeout(function () {
          btn.textContent = orig;
          btn.classList.remove("copied");
        }, 1500);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(md).then(
          function () { done(true); },
          function () { done(false); }
        );
      } else {
        // Fallback for non-secure contexts (e.g. file:// + old browsers).
        var ta = document.createElement("textarea");
        ta.value = md;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        var ok = false;
        try { ok = document.execCommand("copy"); } catch (e) {}
        document.body.removeChild(ta);
        done(ok);
      }
    });
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
    var pinnedMethod = null;
    var hoveredMethod = null;

    function applyHighlight() {
      var m = hoveredMethod || pinnedMethod;
      chart.classList.toggle("has-focus", !!m);
      lines.forEach(function (l) {
        l.classList.toggle("focused", l.dataset.method === m);
      });
      if (legend) {
        legend.querySelectorAll(".lg").forEach(function (b) {
          b.classList.toggle("active", b.dataset.method === m);
          b.classList.toggle("dim", !!m && b.dataset.method !== m);
        });
      }
    }

    function hideTooltip() {
      hoveredMethod = null;
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

      hoveredMethod = best.series.method;
      applyHighlight();

      // Render tooltip content + position.
      tooltip.innerHTML =
        '<div class="d">' + best.point.d + ' digits</div>' +
        '<div class="r"><span class="sw" style="background:' +
        best.series.color + '"></span><span class="f">' +
        escapeHtml(best.series.method) + '</span>:&nbsp;<span class="v">' +
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
          if (!pinnedMethod && !hoveredMethod) {
            hoveredMethod = btn.dataset.method;
            applyHighlight();
          }
        });
        btn.addEventListener("mouseleave", function () {
          if (hoveredMethod === btn.dataset.method) {
            hoveredMethod = null;
            applyHighlight();
          }
        });
        btn.addEventListener("click", function () {
          pinnedMethod = pinnedMethod === btn.dataset.method
            ? null : btn.dataset.method;
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
    methods = bucket["methods"]
    means = bucket["mean"]
    digits = bucket["digits"]
    times = bucket["times"]
    anchor = type_name.lower().replace(" ", "-")

    # `null` is a no-op pseudo-method that measures the benchmark loop's
    # overhead. Hide it from the table, bar chart and legend, and show it
    # as a footnote + dashed reference line in the line chart.
    has_baseline = BASELINE_METHOD in methods
    display_methods = [m for m in methods if m != BASELINE_METHOD]

    section = [
        f'<section data-type="{_esc(type_name)}" id="{_esc(anchor)}">',
        '<div class="card">',
        '<h3>Time per double (lower is better)</h3>',
        render_table(display_methods, means),
        '<div class="hint-row">'
        '<p class="hint">Click any row to use it as the speedup '
        'baseline.</p>'
        '<button type="button" class="copy-md">Copy as Markdown</button>'
        '</div>',
    ]
    if has_baseline:
        section.append(
            f'<p class="hint">Times include a fixed loop-overhead floor of '
            f'<strong>{means[BASELINE_METHOD]:,.2f} ns</strong> '
            f'(measured with a no-op stand-in for <code>dtoa</code>).</p>'
        )

    bar_methods = [m for m in display_methods if m not in BAR_CHART_EXCLUDED]
    if bar_methods:
        excluded_present = sorted(BAR_CHART_EXCLUDED & set(display_methods))
        if excluded_present:
            names = " and ".join(f"<code>{_esc(n)}</code>"
                                 for n in excluded_present)
            hint = (f'<p class="hint">{names} omitted; they are an order '
                    f'of magnitude slower than the rest.</p>')
        else:
            hint = '<p class="hint">All measured methods shown.</p>'
        section += [
            '<div class="card-divider"></div>',
            render_bar_chart(display_methods, means, methods),
            hint,
        ]
    section.append('</div>')

    if digits and times:
        section += [
            '<div class="card">',
            '<h3>Time vs. digit count (log scale)</h3>',
            render_line_chart(display_methods, digits, times, methods,
                              baseline_method=(BASELINE_METHOD if has_baseline
                                               else None)),
            render_legend(display_methods, methods),
            '<p class="hint">Hover or click a method to highlight its '
            'series.</p>',
            '</div>',
        ]

    section.append('</section>')
    return "".join(section)


def render_page(src_path: Path) -> str:
    name = src_path.stem
    rows = load_results(src_path)
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
  Generated from <code>{_esc(src_path.name)}</code> by
  <a href="https://github.com/fmtlib/dtoa-benchmark">fmtlib/dtoa-benchmark</a>.
</footer>
<script>{PAGE_JS}</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def process(src_path: Path) -> Path:
    out = src_path.with_suffix(".html")
    out.write_text(render_page(src_path), encoding="utf-8")
    return out


def is_stale(src_path: Path) -> bool:
    """True if the matching .html is missing or older than the source."""
    out = src_path.with_suffix(".html")
    if not out.exists():
        return True
    return src_path.stat().st_mtime > out.stat().st_mtime


def discover_all(results_dir: Path) -> list[Path]:
    """Return one source file per result base name, preferring .json over
    .csv when both exist for the same base (e.g. an old CSV next to a
    freshly-produced JSON for the same machine+commit)."""
    by_stem: dict[str, Path] = {}
    for path in sorted(results_dir.glob("*.json")):
        by_stem[path.stem] = path
    for path in sorted(results_dir.glob("*.csv")):
        by_stem.setdefault(path.stem, path)
    return [by_stem[stem] for stem in sorted(by_stem)]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*", type=Path,
                        help="Result files (.json or .csv) to convert.")
    parser.add_argument("--all", action="store_true",
                        help="Process every results/*.{json,csv} file.")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if the .html is up to date.")
    args = parser.parse_args(argv)

    if args.all:
        repo_root = Path(__file__).resolve().parent
        targets = discover_all(repo_root / "results")
    else:
        targets = list(args.inputs)

    if not targets:
        parser.error("no result files specified (use --all or pass paths).")

    for src_path in targets:
        if not src_path.exists():
            print(f"warning: {src_path} does not exist; skipping",
                  file=sys.stderr)
            continue
        if not args.force and not is_stale(src_path):
            continue
        out = process(src_path)
        print(f"  {src_path} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
