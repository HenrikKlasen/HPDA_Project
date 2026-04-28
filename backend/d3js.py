import re
import sqlite3
from pathlib import Path

import pandas as pd
from d3blocks import D3Blocks
from flask import Flask, jsonify, request

app = Flask(__name__)


def _resolve_db_path() -> Path:
    """Resolve the SQLite file location with a small fallback chain."""
    backend_db = Path(__file__).resolve().parent / "vast_challenge.db"
    root_db = Path(__file__).resolve().parent.parent / "vast_challenge.db"
    return backend_db if backend_db.exists() else root_db


DB_PATH = _resolve_db_path()
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_valid_identifier(value: str) -> bool:
    return bool(value and IDENTIFIER_PATTERN.match(value))


def _get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


@app.route("/api/datasets", methods=["GET"])
def list_datasets():
    """List all available tables from vast_challenge.db."""
    if not DB_PATH.exists():
        return jsonify({"error": f"Database file not found: {DB_PATH}"}), 404

    conn = _get_db_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return jsonify({"datasets": [row[0] for row in rows]})
    finally:
        conn.close()


@app.route("/api/d3block", methods=["POST"])
def generate_d3block_html():
    """
    Generate a D3Blocks chart from SQLite data and return the HTML.

    Request JSON:
    {
      "dataset": "participants",
      "columns": ["participantId", "age"],
            "chart": "scatter",  # optional: scatter | heatmap
      "limit": 5000          # optional
    }
    """
    if not DB_PATH.exists():
        return jsonify({"error": f"Database file not found: {DB_PATH}"}), 404

    payload = request.get_json(silent=True) or {}
    dataset = payload.get("dataset")
    columns = payload.get("columns", [])
    chart = (payload.get("chart") or "scatter").lower()
    limit = payload.get("limit", 5000)

    if not isinstance(dataset, str) or not _is_valid_identifier(dataset):
        return jsonify({"error": "Invalid dataset name."}), 400

    if not isinstance(columns, list) or not columns:
        return jsonify({"error": "'columns' must be a non-empty list."}), 400

    if any(not isinstance(col, str) or not _is_valid_identifier(col) for col in columns):
        return jsonify({"error": "One or more column names are invalid."}), 400

    if chart not in {"scatter", "heatmap"}:
        return jsonify({"error": "Unsupported chart type."}), 400

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return jsonify({"error": "'limit' must be an integer."}), 400

    if limit <= 0:
        return jsonify({"error": "'limit' must be greater than 0."}), 400

    conn = _get_db_connection()
    try:
        if not _table_exists(conn, dataset):
            return jsonify({"error": f"Dataset '{dataset}' does not exist."}), 404

        available_columns = _get_table_columns(conn, dataset)
        missing = [col for col in columns if col not in available_columns]
        if missing:
            return jsonify({"error": f"Columns not found in '{dataset}': {missing}"}), 400

        selected_columns = ", ".join(columns)
        query = f"SELECT {selected_columns} FROM {dataset} LIMIT ?"
        df = pd.read_sql_query(query, conn, params=(limit,))
    finally:
        conn.close()

    if df.empty:
        return jsonify({"error": "No rows returned for this request."}), 404

    d3 = D3Blocks()

    try:
        html = ""
        if chart == "scatter":
            if len(columns) < 2:
                return jsonify({"error": "Scatter chart requires at least 2 columns."}), 400

            # d3blocks.scatter expects x and y arrays of equal length.
            scatter_df = df[[columns[0], columns[1]]].copy()
            scatter_df[columns[0]] = pd.to_numeric(scatter_df[columns[0]], errors="coerce")
            scatter_df[columns[1]] = pd.to_numeric(scatter_df[columns[1]], errors="coerce")
            scatter_df = scatter_df.dropna(subset=[columns[0], columns[1]])

            if scatter_df.shape[0] < 2:
                return jsonify({"error": "Not enough data points for scatter chart."}), 400

            html = d3.scatter(
                scatter_df[columns[0]].to_numpy(),
                scatter_df[columns[1]].to_numpy(),
                showfig=False,
                return_html=True,
                title=f"Scatter: {dataset} ({columns[0]} vs {columns[1]})",
            )

        elif chart == "heatmap":
            if len(columns) < 2:
                return jsonify({"error": "Heatmap requires at least 2 columns."}), 400
            pivot = (
                df.groupby([columns[0], columns[1]])
                .size()
                .reset_index(name="count")
                .pivot(index=columns[0], columns=columns[1], values="count")
                .fillna(0)
            )
            html = d3.heatmap(
                pivot,
                color=None,
                showfig=False,
                return_html=True,
                title=f"Heatmap: {dataset} ({columns[0]} x {columns[1]})",
            )

        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    except Exception as exc:
        return jsonify({"error": f"Failed to build D3Blocks chart: {exc}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)