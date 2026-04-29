#!/usr/bin/env python3
"""Quick smoke test for the /api/d3block Flask endpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_get_json(url: str) -> tuple[int, object]:
    req = Request(url, method="GET")
    with urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)


def http_post_json(url: str, payload: dict) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as resp:
        return resp.status, resp.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick test for D3Blocks API")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Flask base URL")
    parser.add_argument("--dataset", default="participants", help="SQLite table name")
    parser.add_argument(
        "--columns",
        nargs="+",
        default=["participantId", "age"],
        help="Columns for analysis",
    )
    parser.add_argument("--chart", default="scatter", choices=["scatter", "heatmap", "sankey", "pair"])
    parser.add_argument("--x", help="X column for pair/scatter")
    parser.add_argument("--y", help="Y column for pair/scatter")
    parser.add_argument("--bins", type=int, default=20, help="Bins per axis for heatmap in pair view")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument(
        "--output",
        default="d3block_test_output.html",
        help="Output HTML file path",
    )
    parser.add_argument("--source-col", help="Source column (for d3graph/sankey)")
    parser.add_argument("--target-col", help="Target column (for d3graph/sankey)")
    parser.add_argument("--value-col", help="Value/weight column (for d3graph/sankey)")
    args = parser.parse_args()

    datasets_url = f"{args.base_url}/api/datasets"
    d3block_url = f"{args.base_url}/api/d3block"
    sankey_url = f"{args.base_url}/api/d3block-sankey"

    print(f"Checking datasets endpoint: {datasets_url}")
    try:
        status, data = http_get_json(datasets_url)
        print(f"GET /api/datasets -> {status}")
        datasets = data.get("datasets", []) if isinstance(data, dict) else []
        print(f"Found {len(datasets)} dataset(s)")
        if datasets:
            print("Sample:", ", ".join(datasets[:10]))
    except HTTPError as exc:
        print(f"GET /api/datasets failed: {exc.code} {exc.reason}")
        print(exc.read().decode("utf-8", errors="replace"))
        return 1
    except URLError as exc:
        print(f"Cannot connect to server: {exc}")
        return 1

    # Route based on chart type
    if args.chart in {"scatter", "heatmap"}:
        payload = {
            "dataset": args.dataset,
            "columns": args.columns,
            "chart": args.chart,
            "limit": args.limit,
        }
        url = d3block_url
    elif args.chart == "sankey":
        payload = {
            "dataset": args.dataset,
            "source_col": args.source_col or "participantId",
            "target_col": args.target_col or "employerId",
            "value_col": args.value_col or "duration",
            "limit": args.limit,
        }
        url = sankey_url
    elif args.chart == "pair":
        # pair view: scatter + heatmap synchronized
        # choose sensible defaults for common tables
        xcol = args.x
        ycol = args.y
        if not xcol and args.dataset == "participants":
            xcol = "age"
        if not ycol and args.dataset == "participants":
            ycol = "joviality"
        if not xcol:
            xcol = args.columns[0] if args.columns else None
        if not ycol:
            ycol = args.columns[1] if len(args.columns) > 1 else None
        if not xcol or not ycol:
            print("Pair view requires --x and --y (or two --columns), or use dataset-specific defaults.")
            return 1
        payload = {
            "dataset": args.dataset,
            "x": xcol,
            "y": ycol,
            "bins": args.bins,
            "limit": args.limit,
        }
        url = f"{args.base_url}/api/d3block-pair"
    else:
        print(f"Unknown chart type: {args.chart}")
        return 1

    print("\nPosting to", url.split("/api/")[1], "with payload:")
    print(json.dumps(payload, indent=2))

    try:
        status, html_or_error = http_post_json(url, payload)
        print(f"POST /api/d3block -> {status}")
        output_path = Path(args.output).resolve()
        output_path.write_text(html_or_error, encoding="utf-8")
        print(f"Saved response to: {output_path}")

        # Very lightweight sanity check
        if "<html" in html_or_error.lower() or "<!doctype html" in html_or_error.lower():
            print("Looks like valid HTML output.")
            return 0

        print("Response was not HTML. Inspect output file for details.")
        return 2

    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"POST /api/d3block failed: {exc.code} {exc.reason}")
        print(body)
        return 1
    except URLError as exc:
        print(f"Cannot connect to server: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
