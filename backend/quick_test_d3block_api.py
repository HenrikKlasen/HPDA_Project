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
    parser.add_argument("--chart", default="scatter", choices=["scatter", "bar", "heatmap"])
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument(
        "--output",
        default="d3block_test_output.html",
        help="Output HTML file path",
    )
    args = parser.parse_args()

    datasets_url = f"{args.base_url}/api/datasets"
    d3block_url = f"{args.base_url}/api/d3block"

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

    payload = {
        "dataset": args.dataset,
        "columns": args.columns,
        "chart": args.chart,
        "limit": args.limit,
    }

    print("\nPosting to /api/d3block with payload:")
    print(json.dumps(payload, indent=2))

    try:
        status, html_or_error = http_post_json(d3block_url, payload)
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
