"""On-demand analytics over the tracker sheet: resume track/variant
conversion rates, referral impact, funnel counts, and average days-in-stage.
Always reads live from the Sheet (NFR1) — there is no caching.

Usage:
    python stats_report.py             # print a text summary
    python stats_report.py --chart     # also write stats_chart.html
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sheets_client import SheetsClient  # noqa: E402

RESPONSE_STAGES = {"OA", "Phone Screen", "Onsite", "Offer", "Rejected"}
INTERVIEW_STAGES = {"Phone Screen", "Onsite", "Offer"}
FUNNEL_STAGES = ["Applied", "OA", "Phone Screen", "Onsite", "Offer", "Rejected", "Ghosted"]


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _stage_history_by_app(stage_events: list[dict]) -> dict[str, set[str]]:
    history: dict[str, set[str]] = defaultdict(set)
    for event in stage_events:
        if event.get("app_id"):
            history[event["app_id"]].add(event.get("stage", ""))
    return history


def compute_rates_by_group(applications: list[dict], stage_history: dict[str, set[str]], group_key) -> dict:
    groups: dict = defaultdict(lambda: {"total": 0, "responded": 0, "interviewed": 0})
    for app in applications:
        key = group_key(app)
        if key is None:
            continue
        stages = stage_history.get(app.get("app_id", ""), set())
        groups[key]["total"] += 1
        if stages & RESPONSE_STAGES:
            groups[key]["responded"] += 1
        if stages & INTERVIEW_STAGES:
            groups[key]["interviewed"] += 1

    result = {}
    for key, counts in groups.items():
        result[key] = {
            "total": counts["total"],
            "response_rate": _safe_rate(counts["responded"], counts["total"]),
            "interview_rate": _safe_rate(counts["interviewed"], counts["total"]),
        }
    return result


def compute_funnel_counts(applications: list[dict], stage_history: dict[str, set[str]]) -> dict[str, int]:
    counts = {stage: 0 for stage in FUNNEL_STAGES}
    for app in applications:
        stages = stage_history.get(app.get("app_id", ""), set()) | {app.get("current_stage", "")}
        for stage in FUNNEL_STAGES:
            if stage in stages:
                counts[stage] += 1
    return counts


def compute_avg_days_in_stage(stage_events: list[dict]) -> dict[str, float]:
    by_app: dict[str, list[dict]] = defaultdict(list)
    for event in stage_events:
        if event.get("app_id"):
            by_app[event["app_id"]].append(event)

    durations: dict[str, list[int]] = defaultdict(list)
    for events in by_app.values():
        events_sorted = sorted(events, key=lambda e: e.get("date", ""))
        for i in range(len(events_sorted) - 1):
            stage = events_sorted[i].get("stage", "")
            try:
                d1 = datetime.strptime(events_sorted[i]["date"], "%Y-%m-%d").date()
                d2 = datetime.strptime(events_sorted[i + 1]["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                continue
            durations[stage].append((d2 - d1).days)

    return {stage: (sum(days) / len(days)) for stage, days in durations.items() if days}


def load_stats(sheets: SheetsClient | None = None) -> dict:
    sheets = sheets or SheetsClient()
    applications = sheets.read_tab("Applications")
    resumes = {row["resume_id"]: row for row in sheets.read_tab("Resumes")}
    stage_events = sheets.read_tab("StageEvents")
    stage_history = _stage_history_by_app(stage_events)

    def resume_group(app):
        resume = resumes.get(app.get("resume_id"))
        if not resume:
            return None
        return f"{resume.get('track', '?')} / {resume.get('variant', '?')}"

    def referral_group(app):
        return "Referral" if app.get("referral") == "Y" else "No referral"

    def overall_group(app):
        return "Overall"

    return {
        "by_resume": compute_rates_by_group(applications, stage_history, resume_group),
        "by_referral": compute_rates_by_group(applications, stage_history, referral_group),
        "overall": compute_rates_by_group(applications, stage_history, overall_group),
        "funnel": compute_funnel_counts(applications, stage_history),
        "avg_days_in_stage": compute_avg_days_in_stage(stage_events),
        "total_applications": len(applications),
    }


def print_text_report(stats: dict) -> None:
    print(f"Total applications: {stats['total_applications']}\n")

    print("By resume (track / variant):")
    for key, vals in sorted(stats["by_resume"].items()):
        print(f"  {key}: n={vals['total']}, response={vals['response_rate']:.0%}, interview={vals['interview_rate']:.0%}")

    print("\nBy referral:")
    for key, vals in sorted(stats["by_referral"].items()):
        print(f"  {key}: n={vals['total']}, response={vals['response_rate']:.0%}, interview={vals['interview_rate']:.0%}")

    print("\nFunnel counts:")
    for stage in FUNNEL_STAGES:
        print(f"  {stage}: {stats['funnel'].get(stage, 0)}")

    print("\nAvg days in stage:")
    for stage in FUNNEL_STAGES:
        if stage in stats["avg_days_in_stage"]:
            print(f"  {stage}: {stats['avg_days_in_stage'][stage]:.1f}d")


# --- Chart rendering ---------------------------------------------------
# Colors are the pre-validated categorical/sequential slots from the
# dataviz skill's reference palette (references/palette.md) — not re-run
# through the validator here since the doc already states these orderings
# pass every hard gate in both light and dark mode.

_SERIES_1_LIGHT, _SERIES_1_DARK = "#2a78d6", "#3987e5"  # response rate
_SERIES_2_LIGHT, _SERIES_2_DARK = "#eb6834", "#d95926"  # interview rate
_FUNNEL_LIGHT = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab"]
_FUNNEL_DARK = ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec"]


def _bar_group_html(title: str, groups: dict) -> str:
    if not groups:
        return f"<section class='chart-block'><h3>{escape(title)}</h3><p class='empty'>No data yet.</p></section>"

    rows = []
    for key, vals in sorted(groups.items()):
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{escape(str(key))} <span class="n">(n={vals['total']})</span></div>
              <div class="bar-track">
                <div class="bar bar-series-1" style="width:{vals['response_rate']*100:.1f}%">
                  <span class="bar-value">{vals['response_rate']:.0%}</span>
                </div>
              </div>
              <div class="bar-track">
                <div class="bar bar-series-2" style="width:{vals['interview_rate']*100:.1f}%">
                  <span class="bar-value">{vals['interview_rate']:.0%}</span>
                </div>
              </div>
            </div>
            """
        )
    legend = (
        '<div class="legend">'
        '<span class="legend-item"><span class="swatch swatch-1"></span>Response rate</span>'
        '<span class="legend-item"><span class="swatch swatch-2"></span>Interview rate</span>'
        "</div>"
    )
    return f"<section class='chart-block'><h3>{escape(title)}</h3>{legend}{''.join(rows)}</section>"


def _funnel_html(funnel: dict[str, int]) -> str:
    max_count = max(funnel.values(), default=0) or 1
    rows = []
    for i, stage in enumerate(FUNNEL_STAGES):
        count = funnel.get(stage, 0)
        pct = count / max_count * 100
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{escape(stage)}</div>
              <div class="bar-track">
                <div class="bar bar-funnel-{i}" style="width:{pct:.1f}%">
                  <span class="bar-value">{count}</span>
                </div>
              </div>
            </div>
            """
        )
    return f"<section class='chart-block'><h3>Funnel (applications reaching each stage)</h3>{''.join(rows)}</section>"


def render_chart_html(stats: dict) -> str:
    funnel_css_light = "\n".join(f"      --funnel-{i}: {c};" for i, c in enumerate(_FUNNEL_LIGHT))
    funnel_css_dark = "\n".join(f"      --funnel-{i}: {c};" for i, c in enumerate(_FUNNEL_DARK))
    funnel_bar_css = "\n".join(f"    .bar-funnel-{i} {{ background: var(--funnel-{i}); }}" for i in range(len(FUNNEL_STAGES)))

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Internship Tracker — Stats</title>
<style>
  .viz-root {{
    color-scheme: light;
    --surface-1: #fcfcfb;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --track-bg: #eeece7;
    --series-1: {_SERIES_1_LIGHT};
    --series-2: {_SERIES_2_LIGHT};
{funnel_css_light}
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--surface-1);
    color: var(--text-primary);
    padding: 24px;
    max-width: 720px;
    margin: 0 auto;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) .viz-root {{
      color-scheme: dark;
      --surface-1: #1a1a19;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --track-bg: #2c2c29;
      --series-1: {_SERIES_1_DARK};
      --series-2: {_SERIES_2_DARK};
{funnel_css_dark}
    }}
  }}
  :root[data-theme="dark"] .viz-root {{
    color-scheme: dark;
    --surface-1: #1a1a19;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --track-bg: #2c2c29;
    --series-1: {_SERIES_1_DARK};
    --series-2: {_SERIES_2_DARK};
{funnel_css_dark}
  }}
  h2 {{ margin-bottom: 4px; }}
  .subtitle {{ color: var(--text-secondary); margin-top: 0; margin-bottom: 24px; }}
  .chart-block {{ margin-bottom: 32px; }}
  h3 {{ margin-bottom: 12px; }}
  .empty {{ color: var(--text-secondary); }}
  .legend {{ margin-bottom: 12px; font-size: 13px; color: var(--text-secondary); }}
  .legend-item {{ margin-right: 16px; }}
  .swatch {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }}
  .swatch-1 {{ background: var(--series-1); }}
  .swatch-2 {{ background: var(--series-2); }}
  .bar-row {{ margin-bottom: 10px; }}
  .bar-label {{ font-size: 13px; margin-bottom: 3px; }}
  .bar-label .n {{ color: var(--text-secondary); }}
  .bar-track {{ background: var(--track-bg); border-radius: 4px; height: 20px; margin-bottom: 3px; position: relative; }}
  .bar {{ height: 100%; border-radius: 4px; min-width: 2px; display: flex; align-items: center; }}
  .bar-series-1 {{ background: var(--series-1); }}
  .bar-series-2 {{ background: var(--series-2); }}
{funnel_bar_css}
  .bar-value {{ color: #fff; font-size: 11px; padding-left: 6px; white-space: nowrap; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }}
  th, td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--track-bg); }}
</style>
</head>
<body>
<div class="viz-root">
  <h2>Internship Tracker — Stats</h2>
  <p class="subtitle">{stats['total_applications']} total application(s), live as of generation time</p>

  {_bar_group_html("By resume (track / variant)", stats['by_resume'])}
  {_bar_group_html("By referral", stats['by_referral'])}
  {_funnel_html(stats['funnel'])}

  <section class="chart-block">
    <h3>Avg days in stage (table view)</h3>
    <table>
      <tr><th>Stage</th><th>Avg days before next transition</th></tr>
      {''.join(f"<tr><td>{escape(stage)}</td><td>{stats['avg_days_in_stage'][stage]:.1f}d</td></tr>" for stage in FUNNEL_STAGES if stage in stats['avg_days_in_stage'])}
    </table>
  </section>
</div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", action="store_true", help="Also write stats_chart.html")
    args = parser.parse_args()

    stats = load_stats()
    print_text_report(stats)

    if args.chart:
        out_path = Path(__file__).resolve().parent / "stats_chart.html"
        out_path.write_text(render_chart_html(stats))
        print(f"\nWrote chart to {out_path}")


if __name__ == "__main__":
    main()
