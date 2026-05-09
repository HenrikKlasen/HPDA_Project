import re
import sqlite3
from pathlib import Path

import pandas as pd
from d3blocks import D3Blocks
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


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


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _resolve_column_name(available_columns: set[str], requested: str) -> str | None:
    """Resolve a requested column name against real SQLite columns.

    Some VAST columns contain trailing spaces in the schema. We accept exact
    matches first, then a unique stripped match.
    """
    if requested in available_columns:
        return requested

    stripped = requested.strip()
    if stripped in available_columns:
        return stripped

    matches = [col for col in available_columns if col.strip() == stripped]
    if len(matches) == 1:
        return matches[0]
    return None


def _parse_table_ref(ref: str) -> tuple[str, str] | None:
    if not isinstance(ref, str) or "." not in ref:
        return None
    alias, col = ref.split(".", 1)
    alias = alias.strip()
    col = col.strip()
    if not _is_valid_identifier(alias) or not col:
        return None
    return alias, col


def _load_prefixed_table(
    conn: sqlite3.Connection,
    table_name: str,
    alias: str,
    columns: list[str],
    row_limit: int | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    available_columns = _get_table_columns(conn, table_name)
    resolved_columns: list[str] = []
    for col in columns:
        actual = _resolve_column_name(available_columns, col)
        if actual is None:
            raise ValueError(f"Column '{col}' not found in '{table_name}'")
        if actual not in resolved_columns:
            resolved_columns.append(actual)

    if not resolved_columns:
        raise ValueError(f"No columns selected for table '{table_name}'")

    select_sql = ", ".join(_quote_identifier(col) for col in resolved_columns)
    query = f"SELECT {select_sql} FROM {_quote_identifier(table_name)}"
    params: tuple[object, ...] = ()
    if row_limit is not None:
        query += " LIMIT ?"
        params = (int(row_limit),)
    df = pd.read_sql_query(query, conn, params=params)
    renamed = {col: f"{alias}__{col}" for col in resolved_columns}
    df = df.rename(columns=renamed)
    return df, renamed


class JoinRequestError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _build_joined_dataframe(
    payload: dict,
) -> tuple[pd.DataFrame, dict[str, dict], list[dict]]:
    """Build a joined DataFrame from a multi-table join request payload."""
    if not DB_PATH.exists():
        raise JoinRequestError(f"Database file not found: {DB_PATH}", 404)

    tables = payload.get("tables", [])
    joins = payload.get("joins", [])
    select_cols = payload.get("select", [])
    limit = payload.get("limit", 1000)

    if not isinstance(tables, list) or len(tables) < 2:
        raise JoinRequestError("'tables' must contain at least two table specs.")
    if not isinstance(joins, list) or not joins:
        raise JoinRequestError("'joins' must be a non-empty list.")

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise JoinRequestError("'limit' must be an integer.")
    if limit <= 0:
        raise JoinRequestError("'limit' must be greater than 0.")

    table_specs: dict[str, dict] = {}
    for table_spec in tables:
        if not isinstance(table_spec, dict):
            raise JoinRequestError("Each table spec must be an object.")
        table_name = table_spec.get("name")
        alias = table_spec.get("alias") or table_name
        if not isinstance(table_name, str) or not _is_valid_identifier(table_name):
            raise JoinRequestError(f"Invalid table name: {table_name}")
        if not isinstance(alias, str) or not _is_valid_identifier(alias):
            raise JoinRequestError(f"Invalid alias for table '{table_name}'.")
        if alias in table_specs:
            raise JoinRequestError(f"Duplicate table alias: {alias}")
        columns = table_spec.get("columns", [])
        if columns is not None and not isinstance(columns, list):
            raise JoinRequestError(
                f"'columns' must be a list for table '{table_name}'."
            )
        table_specs[alias] = {
            "name": table_name,
            "alias": alias,
            "columns": list(columns or []),
        }

    required_columns: dict[str, set[str]] = {
        alias: set(spec["columns"]) for alias, spec in table_specs.items()
    }
    validated_joins: list[dict] = []
    allowed_join_types = {"inner", "left", "right", "outer"}

    for join_spec in joins:
        if not isinstance(join_spec, dict):
            raise JoinRequestError("Each join spec must be an object.")
        left_ref = _parse_table_ref(join_spec.get("left", ""))
        right_ref = _parse_table_ref(join_spec.get("right", ""))
        if left_ref is None or right_ref is None:
            raise JoinRequestError("Join refs must use 'alias.column' syntax.")
        left_alias, left_col = left_ref
        right_alias, right_col = right_ref
        if left_alias not in table_specs or right_alias not in table_specs:
            raise JoinRequestError(
                f"Unknown table alias in join: {left_alias} -> {right_alias}"
            )
        how = (join_spec.get("how") or "inner").lower()
        if how not in allowed_join_types:
            raise JoinRequestError(f"Unsupported join type: {how}")
        required_columns[left_alias].add(left_col)
        required_columns[right_alias].add(right_col)
        validated_joins.append({"left": left_ref, "right": right_ref, "how": how})

    conn = _get_db_connection()
    try:
        loaded: dict[str, pd.DataFrame] = {}
        load_limit = max(int(limit), min(int(limit) * 10, 5000))
        for alias, spec in table_specs.items():
            if not _table_exists(conn, spec["name"]):
                raise JoinRequestError(f"Table '{spec['name']}' does not exist.", 404)
            df, _ = _load_prefixed_table(
                conn,
                spec["name"],
                alias,
                list(required_columns[alias]),
                row_limit=load_limit,
            )
            if df.empty:
                raise JoinRequestError(f"Table '{spec['name']}' returned no rows.", 404)
            loaded[alias] = df
    finally:
        conn.close()

    base_alias = next(iter(table_specs.keys()))
    joined = loaded[base_alias].copy()
    joined_aliases = {base_alias}

    def _prefixed_key(df: pd.DataFrame, alias: str, requested_col: str) -> str | None:
        available = {
            c.split("__", 1)[1] for c in df.columns if c.startswith(f"{alias}__")
        }
        actual_col = _resolve_column_name(available, requested_col)
        if actual_col is None:
            return None
        return f"{alias}__{actual_col}"

    for join_spec in validated_joins:
        (left_alias, left_col) = join_spec["left"]
        (right_alias, right_col) = join_spec["right"]
        if left_alias not in joined_aliases:
            raise JoinRequestError(
                f"Join order problem: '{left_alias}' is not present in the current joined data."
            )
        right_df = loaded[right_alias]
        left_key = _prefixed_key(joined, left_alias, left_col)
        right_key = _prefixed_key(right_df, right_alias, right_col)
        if left_key is None:
            raise JoinRequestError(
                f"Missing join key in current result: {join_spec['left'][0]}.{left_col}"
            )
        if right_key is None:
            raise JoinRequestError(
                f"Missing join key in table '{right_alias}': {join_spec['right'][0]}.{right_col}"
            )
        joined = pd.merge(
            joined, right_df, left_on=left_key, right_on=right_key, how=join_spec["how"]
        )
        joined_aliases.add(right_alias)

    if select_cols:
        if not isinstance(select_cols, list):
            raise JoinRequestError("'select' must be a list when provided.")
        resolved_select = []
        for item in select_cols:
            ref = _parse_table_ref(item)
            if ref is None:
                raise JoinRequestError(
                    f"Select columns must use 'alias.column' syntax: {item}"
                )
            alias, col = ref
            if alias not in table_specs:
                raise JoinRequestError(f"Unknown alias in select: {alias}")
            actual_col = _resolve_column_name(
                {
                    c.split("__", 1)[1]
                    for c in joined.columns
                    if c.startswith(f"{alias}__")
                },
                col,
            )
            if actual_col is None:
                raise JoinRequestError(f"Column not available in joined result: {item}")
            resolved_select.append(f"{alias}__{actual_col}")
        joined = joined[resolved_select]

    joined = joined.head(limit)
    if joined.empty:
        raise JoinRequestError("No rows after joining.", 404)

    return joined, table_specs, validated_joins


def _resolve_join_chart_column(joined: pd.DataFrame, ref: str) -> str | None:
    parsed = _parse_table_ref(ref)
    if parsed is None:
        return ref if ref in joined.columns else None
    alias, col = parsed
    available = {
        c.split("__", 1)[1] for c in joined.columns if c.startswith(f"{alias}__")
    }
    actual = _resolve_column_name(available, col)
    if actual is None:
        return None
    return f"{alias}__{actual}"


def _render_joined_chart_html(
    joined: pd.DataFrame, chart: str, columns: list[str], title: str
) -> str:
    chart = chart.lower()
    d3 = D3Blocks()
    if chart == "scatter":
        if len(columns) < 2:
            raise JoinRequestError("Scatter chart requires at least 2 chart columns.")
        x_col = _resolve_join_chart_column(joined, columns[0])
        y_col = _resolve_join_chart_column(joined, columns[1])
        if x_col is None or y_col is None:
            raise JoinRequestError("Chart columns not found in joined result.")
        scatter_df = joined[[x_col, y_col]].copy()
        scatter_df[x_col] = pd.to_numeric(scatter_df[x_col], errors="coerce")
        scatter_df[y_col] = pd.to_numeric(scatter_df[y_col], errors="coerce")
        scatter_df = scatter_df.dropna(subset=[x_col, y_col])
        if scatter_df.shape[0] < 2:
            raise JoinRequestError("Not enough numeric rows for scatter chart.")
        return d3.scatter(
            scatter_df[x_col].to_numpy(),
            scatter_df[y_col].to_numpy(),
            showfig=False,
            return_html=True,
            title=title,
        )

    if chart == "heatmap":
        if len(columns) < 2:
            raise JoinRequestError("Heatmap requires at least 2 chart columns.")
        x_col = _resolve_join_chart_column(joined, columns[0])
        y_col = _resolve_join_chart_column(joined, columns[1])
        if x_col is None or y_col is None:
            raise JoinRequestError("Chart columns not found in joined result.")
        pivot = (
            joined.groupby([x_col, y_col])
            .size()
            .reset_index(name="count")
            .pivot(index=x_col, columns=y_col, values="count")
            .fillna(0)
        )
        return d3.heatmap(
            pivot,
            color=None,
            showfig=False,
            return_html=True,
            title=title,
        )

    raise JoinRequestError(f"Unsupported chart type: {chart}")


def _render_synced_joined_views_html(
    joined: pd.DataFrame, views: list[dict], title: str
) -> str:
    """Render multiple synced charts from a joined DataFrame.

    Supported view types:
    - scatter: x/y numeric points
    - line: sorted x/y line with points
    - heatmap: binned x/y cells
    - histogram: one numeric x variable, binned counts
    - bar: categorical x variable, count or mean(y)
    """
    if not views or not isinstance(views, list):
        raise JoinRequestError("'views' must be a non-empty list.")

    joined = joined.reset_index(drop=True).copy()
    joined["__row_id"] = joined.index.astype(int)
    row_ids = joined["__row_id"].tolist()
    palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    chart_payloads = []
    for idx, view in enumerate(views):
        if not isinstance(view, dict):
            raise JoinRequestError("Each view must be an object.")

        view_type = (view.get("type") or "scatter").lower()
        title_text = view.get("title") or f"View {idx + 1}"
        x_ref = view.get("x")
        y_ref = view.get("y")

        if view_type in {"scatter", "line", "area", "step"}:
            if not x_ref or not y_ref:
                raise JoinRequestError(f"Each {view_type} view requires 'x' and 'y'.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            y_col = _resolve_join_chart_column(joined, y_ref)
            if x_col is None or y_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} columns not found in joined result."
                )
            chart_rows = joined[["__row_id", x_col, y_col]].copy()
            chart_rows[x_col] = pd.to_numeric(chart_rows[x_col], errors="coerce")
            chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
            chart_rows = chart_rows.dropna(subset=[x_col, y_col])
            if chart_rows.shape[0] < 2:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough numeric rows."
                )
            if view_type == "line":
                chart_rows = chart_rows.sort_values(by=x_col)
            chart_payloads.append(
                {
                    "type": view_type,
                    "title": title_text,
                    "xLabel": x_ref,
                    "yLabel": y_ref,
                    "points": [
                        {
                            "rowId": int(row["__row_id"]),
                            "x": float(row[x_col]),
                            "y": float(row[y_col]),
                        }
                        for _, row in chart_rows.iterrows()
                    ],
                }
            )

        elif view_type == "boxplot":
            if not x_ref or not y_ref:
                raise JoinRequestError("Each boxplot view requires 'x' and 'y'.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            y_col = _resolve_join_chart_column(joined, y_ref)
            if x_col is None or y_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} columns not found in joined result."
                )
            chart_rows = joined[["__row_id", x_col, y_col]].copy()
            chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
            chart_rows = chart_rows.dropna(subset=[y_col])
            if chart_rows.shape[0] < 2:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough numeric rows."
                )
            groups = []
            for category, group in chart_rows.groupby(x_col):
                values = group[y_col].astype(float).tolist()
                if len(values) < 2:
                    continue
                qs = group[y_col].quantile([0, 0.25, 0.5, 0.75, 1.0]).tolist()
                groups.append(
                    {
                        "category": str(category),
                        "rowIds": [int(v) for v in group["__row_id"].tolist()],
                        "values": values,
                        "min": float(qs[0]),
                        "q1": float(qs[1]),
                        "median": float(qs[2]),
                        "q3": float(qs[3]),
                        "max": float(qs[4]),
                    }
                )
            if not groups:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough grouped rows."
                )
            chart_payloads.append(
                {
                    "type": "boxplot",
                    "title": title_text,
                    "xLabel": x_ref,
                    "yLabel": y_ref,
                    "groups": groups,
                }
            )

        elif view_type == "circlepack":
            if not x_ref:
                raise JoinRequestError("Each circlepack view requires 'x'.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            if x_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} column not found in joined result."
                )
            chart_rows = joined[["__row_id", x_col]].copy()
            chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
            groups = (
                chart_rows.groupby(x_col)
                .agg(
                    count=("__row_id", "size"),
                    rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]),
                )
                .reset_index()
            )
            if groups.empty:
                raise JoinRequestError(f"View {idx + 1} does not have enough rows.")
            chart_payloads.append(
                {
                    "type": "circlepack",
                    "title": title_text,
                    "xLabel": x_ref,
                    "groups": [
                        {
                            "category": str(row[x_col]),
                            "count": int(row["count"]),
                            "rowIds": row["rowIds"],
                        }
                        for _, row in groups.iterrows()
                    ],
                }
            )

        elif view_type == "chord":
            if not x_ref or not y_ref:
                raise JoinRequestError("Each chord view requires 'x' and 'y'.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            y_col = _resolve_join_chart_column(joined, y_ref)
            if x_col is None or y_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} columns not found in joined result."
                )
            chart_rows = joined[["__row_id", x_col, y_col]].copy()
            chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
            chart_rows[y_col] = chart_rows[y_col].astype(str).fillna("(missing)")
            categories = sorted(
                set(chart_rows[x_col].unique()).union(set(chart_rows[y_col].unique()))
            )
            if len(categories) < 2:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough distinct categories."
                )
            index_map = {cat: i for i, cat in enumerate(categories)}
            matrix = [[0 for _ in categories] for _ in categories]
            row_ids_map: dict[str, list[int]] = {}
            for _, row in chart_rows.iterrows():
                i = index_map[str(row[x_col])]
                j = index_map[str(row[y_col])]
                matrix[i][j] += 1
                key = f"{i}-{j}"
                row_ids_map.setdefault(key, []).append(int(row["__row_id"]))
            chart_payloads.append(
                {
                    "type": "chord",
                    "title": title_text,
                    "xLabel": x_ref,
                    "yLabel": y_ref,
                    "categories": categories,
                    "matrix": matrix,
                    "rowIdsMap": row_ids_map,
                }
            )

        elif view_type == "violin":
            if not x_ref or not y_ref:
                raise JoinRequestError("Each violin view requires 'x' and 'y'.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            y_col = _resolve_join_chart_column(joined, y_ref)
            if x_col is None or y_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} columns not found in joined result."
                )
            chart_rows = joined[["__row_id", x_col, y_col]].copy()
            chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
            chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
            chart_rows = chart_rows.dropna(subset=[y_col])
            if chart_rows.shape[0] < 2:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough numeric rows."
                )
            groups = []
            for category, group in chart_rows.groupby(x_col):
                values = group[y_col].astype(float).tolist()
                if len(values) < 2:
                    continue
                min_v = float(min(values))
                max_v = float(max(values))
                groups.append(
                    {
                        "category": str(category),
                        "rowIds": [int(v) for v in group["__row_id"].tolist()],
                        "values": values,
                        "min": min_v,
                        "max": max_v,
                    }
                )
            if not groups:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough grouped rows."
                )
            chart_payloads.append(
                {
                    "type": "violin",
                    "title": title_text,
                    "xLabel": x_ref,
                    "yLabel": y_ref,
                    "groups": groups,
                }
            )

        elif view_type == "heatmap":
            if not x_ref or not y_ref:
                raise JoinRequestError("Each heatmap view requires 'x' and 'y'.")
            bins = int(view.get("bins", 8))
            if bins <= 0:
                raise JoinRequestError("Heatmap 'bins' must be greater than 0.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            y_col = _resolve_join_chart_column(joined, y_ref)
            if x_col is None or y_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} columns not found in joined result."
                )

            chart_rows = joined[["__row_id", x_col, y_col]].copy()
            chart_rows[x_col] = pd.to_numeric(chart_rows[x_col], errors="coerce")
            chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
            chart_rows = chart_rows.dropna(subset=[x_col, y_col])
            if chart_rows.shape[0] < 2:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough numeric rows."
                )

            chart_rows["__xb"] = pd.cut(
                chart_rows[x_col], bins=bins, labels=False, duplicates="drop"
            )
            chart_rows["__yb"] = pd.cut(
                chart_rows[y_col], bins=bins, labels=False, duplicates="drop"
            )
            chart_rows = chart_rows.dropna(subset=["__xb", "__yb"])
            if chart_rows.empty:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough binned rows."
                )

            chart_rows["__xb"] = chart_rows["__xb"].astype(int)
            chart_rows["__yb"] = chart_rows["__yb"].astype(int)
            pivot = (
                chart_rows.groupby(["__xb", "__yb"])
                .agg(
                    count=("__row_id", "size"),
                    rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]),
                )
                .reset_index()
            )

            chart_payloads.append(
                {
                    "type": "heatmap",
                    "title": title_text,
                    "xLabel": x_ref,
                    "yLabel": y_ref,
                    "bins": bins,
                    "xDomain": [
                        float(chart_rows[x_col].min()),
                        float(chart_rows[x_col].max()),
                    ],
                    "yDomain": [
                        float(chart_rows[y_col].min()),
                        float(chart_rows[y_col].max()),
                    ],
                    "cells": [
                        {
                            "xBin": int(row["__xb"]),
                            "yBin": int(row["__yb"]),
                            "count": int(row["count"]),
                            "rowIds": row["rowIds"],
                        }
                        for _, row in pivot.iterrows()
                    ],
                }
            )

        elif view_type == "histogram":
            if not x_ref:
                raise JoinRequestError("Each histogram view requires 'x'.")
            bins = int(view.get("bins", 10))
            if bins <= 0:
                raise JoinRequestError("Histogram 'bins' must be greater than 0.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            if x_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} column not found in joined result."
                )
            chart_rows = joined[["__row_id", x_col]].copy()
            chart_rows[x_col] = pd.to_numeric(chart_rows[x_col], errors="coerce")
            chart_rows = chart_rows.dropna(subset=[x_col])
            if chart_rows.shape[0] < 2:
                raise JoinRequestError(
                    f"View {idx + 1} does not have enough numeric rows."
                )
            chart_rows["__bin"] = pd.cut(
                chart_rows[x_col], bins=bins, labels=False, duplicates="drop"
            )
            chart_rows = chart_rows.dropna(subset=["__bin"])
            chart_rows["__bin"] = chart_rows["__bin"].astype(int)
            pivot = (
                chart_rows.groupby("__bin")
                .agg(
                    count=("__row_id", "size"),
                    rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]),
                )
                .reset_index()
            )
            chart_payloads.append(
                {
                    "type": "histogram",
                    "title": title_text,
                    "xLabel": x_ref,
                    "bins": bins,
                    "domain": [
                        float(chart_rows[x_col].min()),
                        float(chart_rows[x_col].max()),
                    ],
                    "bars": [
                        {
                            "bin": int(row["__bin"]),
                            "count": int(row["count"]),
                            "rowIds": row["rowIds"],
                        }
                        for _, row in pivot.iterrows()
                    ],
                }
            )

        elif view_type == "bar":
            if not x_ref:
                raise JoinRequestError("Each bar view requires 'x'.")
            x_col = _resolve_join_chart_column(joined, x_ref)
            if x_col is None:
                raise JoinRequestError(
                    f"View {idx + 1} column not found in joined result."
                )
            chart_rows = joined[
                ["__row_id", x_col]
                + ([_resolve_join_chart_column(joined, y_ref)] if y_ref else [])
            ].copy()
            chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
            if y_ref:
                y_col = _resolve_join_chart_column(joined, y_ref)
                if y_col is None:
                    raise JoinRequestError(
                        f"View {idx + 1} y column not found in joined result."
                    )
                chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
                pivot = (
                    chart_rows.dropna(subset=[y_col])
                    .groupby(x_col)
                    .agg(
                        value=(y_col, "mean"),
                        rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]),
                    )
                    .reset_index()
                )
                value_key = "value"
            else:
                pivot = (
                    chart_rows.groupby(x_col)
                    .agg(
                        value=("__row_id", "size"),
                        rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]),
                    )
                    .reset_index()
                )
                value_key = "value"
            if pivot.empty:
                raise JoinRequestError(f"View {idx + 1} does not have enough rows.")
            chart_payloads.append(
                {
                    "type": "bar",
                    "title": title_text,
                    "xLabel": x_ref,
                    "yLabel": y_ref,
                    "bars": [
                        {
                            "category": str(row[x_col]),
                            "value": float(row[value_key]),
                            "rowIds": row["rowIds"],
                        }
                        for _, row in pivot.iterrows()
                    ],
                }
            )

        else:
            raise JoinRequestError(f"Unsupported view type: {view_type}")

    import json

    page_template = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
	body { font-family: Arial, sans-serif; margin: 12px; background: #fafafa; }
	.header { margin-bottom: 12px; }
	.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 12px; align-items: start; }
	.card { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
	.card h3 { margin: 0 0 8px 0; font-size: 14px; }
	.chart { width: 100%; overflow: hidden; }
	.muted { opacity: 0.08; }
	.active { stroke: #111; stroke-width: 2px; opacity: 1 !important; }
	.axis text { font-size: 10px; }
	.axis path, .axis line { stroke: #bbb; }
	.tooltip { position: fixed; background: rgba(20, 20, 20, 0.92); color: #fff; padding: 8px 12px;
	  border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0;
	  transition: opacity 0.12s; line-height: 1.6; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
</style>
<script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
<div class="header">
	<h2>__TITLE__</h2>
	<div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
		<span>Brush a region in any chart to highlight the matching joined row(s) across all charts.</span>
		<button type="button" onclick="clearBrushedRows()">Clear brush</button>
	</div>
</div>

<div class="grid" id="chartGrid"></div>
<div class="tooltip" id="tip"></div>

<script>
const views = __VIEWS__;
const palette = __PALETTE__;

const grid = d3.select('#chartGrid');
const tip = d3.select('#tip');

function showTip(html, ev) {
  tip.html(html).style('opacity', 1)
     .style('left', (ev.clientX + 15) + 'px').style('top', (ev.clientY - 45) + 'px');
}
function hideTip() { tip.style('opacity', 0); }

const chartState = [];
const selectionState = {
	hoverRowIds: [],
	brushedRowIds: [],
};

function colorForRow(rowId) {
	return palette[rowId % palette.length];
}

function makeCard(view, index) {
	const card = grid.append('div').attr('class', 'card');
	card.append('h3').text(view.title);
	card.append('div').attr('class', 'chart').attr('id', `chart-${index}`);
	return card;
}

function normalizeRowIds(rowIds) {
	return Array.from(new Set((rowIds || []).map(v => +v).filter(v => Number.isFinite(v))));
}

function getActiveRowSet() {
	const source = selectionState.brushedRowIds.length ? selectionState.brushedRowIds : selectionState.hoverRowIds;
	return new Set(source.map(v => +v));
}

function updateHighlights() {
	const active = getActiveRowSet();
	if (!active.size) {
		chartState.forEach(({ svg }) => {
			svg.selectAll('[data-row-id], [data-row-ids]')
				.classed('muted', false)
				.classed('active', false);
		});
		return;
	}
	chartState.forEach(({ svg }) => {
		svg.selectAll('[data-row-id], [data-row-ids]')
			.classed('muted', true)
			.classed('active', false)
			.filter(function() {
				const single = this.getAttribute('data-row-id');
				if (single !== null) return active.has(+single);
				const multi = this.getAttribute('data-row-ids');
				if (!multi) return false;
				return multi.split(',').some(v => active.has(+v));
			})
			.classed('muted', false)
			.classed('active', true)
			.raise();
	});
}

function setHoverRows(rowIds) {
	if (selectionState.brushedRowIds.length) return;
	selectionState.hoverRowIds = normalizeRowIds(rowIds);
	updateHighlights();
}

function clearHoverRows() {
	if (selectionState.brushedRowIds.length) return;
	selectionState.hoverRowIds = [];
	updateHighlights();
}

function setBrushedRows(rowIds) {
	selectionState.brushedRowIds = normalizeRowIds(rowIds);
	selectionState.hoverRowIds = [];
	updateHighlights();
}

function clearBrushedRows() {
	selectionState.brushedRowIds = [];
	selectionState.hoverRowIds = [];
	updateHighlights();
}

function attachBrush(svg, extent, view, mode) {
	const brush = d3.brush().extent(extent)
		.on('brush end', (event) => {
			if (!event.selection) {
				if (event.type === 'end') clearBrushedRows();
				return;
			}
			const rowIds = brushSelectionToRowIds(view, event.selection, mode);
			setBrushedRows(rowIds);
		});
	svg.append('g').attr('class', 'brush').call(brush);
}

function brushSelectionToRowIds(view, brushExtent, mode) {
	const [[x0, y0], [x1, y1]] = brushExtent;
	if (mode === 'scatter' || mode === 'line' || mode === 'area' || mode === 'step') {
		return view.points.filter(d => d.__px >= x0 && d.__px <= x1 && d.__py >= y0 && d.__py <= y1).map(d => d.rowId);
	}
	if (mode === 'heatmap') {
		return view.cells.filter(d => d.__x0 < x1 && d.__x1 > x0 && d.__y0 < y1 && d.__y1 > y0).flatMap(d => d.rowIds);
	}
	if (mode === 'histogram' || mode === 'bar') {
		return view.bars.filter(d => d.__x0 < x1 && d.__x1 > x0 && d.__y0 < y1 && d.__y1 > y0).flatMap(d => d.rowIds);
	}
	if (mode === 'violin') {
		return view.groups.filter(d => d.__x0 < x1 && d.__x1 > x0).flatMap(d => d.rowIds);
	}
	if (mode === 'boxplot') {
		return view.groups.filter(d => d.__x0 < x1 && d.__x1 > x0).flatMap(d => d.rowIds);
	}
	return [];
}

function renderScatterLike(containerId, view) {
	const width = 420;
	const height = 320;
	const margin = { top: 20, right: 16, bottom: 42, left: 52 };
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const x = d3.scaleLinear().domain(d3.extent(view.points, d => d.x)).nice().range([margin.left, width - margin.right]);
	const y = d3.scaleLinear().domain(d3.extent(view.points, d => d.y)).nice().range([height - margin.bottom, margin.top]);

	svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x).ticks(5));
	svg.append('g').attr('class', 'axis').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5));

	svg.append('text')
		.attr('x', width / 2)
		.attr('y', height - 6)
		.attr('text-anchor', 'middle')
		.attr('font-size', 10)
		.attr('fill', '#444')
		.text(view.xLabel);
	svg.append('text')
		.attr('transform', 'rotate(-90)')
		.attr('x', -(height / 2))
		.attr('y', 14)
		.attr('text-anchor', 'middle')
		.attr('font-size', 10)
		.attr('fill', '#444')
		.text(view.yLabel);

	svg.append('g').selectAll('circle').data(view.points).join('circle')
		.attr('cx', d => x(d.x))
		.attr('cy', d => y(d.y))
		.attr('r', 3.5)
		.attr('fill', d => colorForRow(d.rowId))
		.attr('data-row-id', d => d.rowId)
		.on('mouseover', (event, d) => {
			setHoverRows([d.rowId]);
			showTip(`<strong>Row: ${d.rowId}</strong><br>${view.xLabel}: <strong>${d.x}</strong><br>${view.yLabel}: <strong>${d.y}</strong>`, event);
		})
		.on('mouseout', () => {
			clearHoverRows();
			hideTip();
		});

	view.points.forEach(d => {
		d.__px = x(d.x);
		d.__py = y(d.y);
	});
	attachBrush(svg, [[margin.left, margin.top], [width - margin.right, height - margin.bottom]], view, view.type);

	if (view.type === 'line') {
		svg.append('path')
			.datum(view.points)
			.attr('fill', 'none')
			.attr('stroke', '#444')
			.attr('stroke-width', 1.5)
			.attr('d', d3.line().x(d => x(d.x)).y(d => y(d.y)));
	} else if (view.type === 'area') {
		svg.append('path')
			.datum(view.points)
			.attr('fill', 'rgba(31, 119, 180, 0.22)')
			.attr('stroke', '#1f77b4')
			.attr('stroke-width', 1.3)
			.attr('d', d3.area().x(d => x(d.x)).y0(y(0)).y1(d => y(d.y)));
	} else if (view.type === 'step') {
		svg.append('path')
			.datum(view.points)
			.attr('fill', 'none')
			.attr('stroke', '#444')
			.attr('stroke-width', 1.5)
			.attr('d', d3.line().curve(d3.curveStep).x(d => x(d.x)).y(d => y(d.y)));
	}

	chartState.push({ svg });
}

function renderHistogram(containerId, view) {
	const width = 420;
	const height = 320;
	const margin = { top: 20, right: 16, bottom: 42, left: 52 };
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const bins = view.bins;
	const domain = view.domain;
	const xScale = d3.scaleLinear().domain(domain).range([margin.left, width - margin.right]);
	const yScale = d3.scaleLinear().domain([0, d3.max(view.bars, d => d.count) || 1]).nice().range([height - margin.bottom, margin.top]);
	const binWidth = (domain[1] - domain[0]) / bins;
	view.bars.forEach(d => {
		d.__x0_val = domain[0] + d.bin * binWidth;
		d.__x1_val = d.__x0_val + binWidth;
		d.__x0 = xScale(d.__x0_val);
		d.__x1 = d.__x0 + Math.max(1, (width - margin.left - margin.right) / bins - 1);
		d.__y0 = yScale(d.count);
		d.__y1 = yScale(0);
	});

	svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(xScale).ticks(5));
	svg.append('g').attr('class', 'axis').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(yScale).ticks(5));
	svg.append('text').attr('x', width / 2).attr('y', height - 6).attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#444').text(view.xLabel);

	svg.append('g').selectAll('rect').data(view.bars).join('rect')
		.attr('x', d => d.__x0)
		.attr('y', d => d.__y0)
		.attr('width', Math.max(1, (width - margin.left - margin.right) / bins - 1))
		.attr('height', d => d.__y1 - d.__y0)
		.attr('fill', d => colorForRow(d.rowIds[0] ?? 0))
		.attr('data-row-ids', d => d.rowIds.join(','))
		.on('mouseover', (event, d) => {
			setHoverRows(d.rowIds);
			showTip(`<strong>Range:</strong> ${d.__x0_val.toFixed(2)} - ${d.__x1_val.toFixed(2)}<br><strong>Count:</strong> ${d.count}`, event);
		})
		.on('mouseout', () => {
			clearHoverRows();
			hideTip();
		});
	attachBrush(svg, [[margin.left, margin.top], [width - margin.right, height - margin.bottom]], view, 'histogram');

	chartState.push({ svg });
}

function renderBar(containerId, view) {
	const width = 420;
	const height = 320;
	const margin = { top: 20, right: 16, bottom: 60, left: 52 };
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const x = d3.scaleBand().domain(view.bars.map(d => d.category)).range([margin.left, width - margin.right]).padding(0.2);
	const y = d3.scaleLinear().domain([0, d3.max(view.bars, d => d.value) || 1]).nice().range([height - margin.bottom, margin.top]);
	view.bars.forEach(d => {
		d.__x0 = x(d.category);
		d.__x1 = x(d.category) + x.bandwidth();
		d.__y0 = y(d.value);
		d.__y1 = y(0);
	});

	svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x)).selectAll('text').attr('transform', 'rotate(-35)').style('text-anchor', 'end');
	svg.append('g').attr('class', 'axis').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5));
	svg.append('text').attr('x', width / 2).attr('y', height - 6).attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#444').text(view.xLabel);

	svg.append('g').selectAll('rect').data(view.bars).join('rect')
		.attr('x', d => d.__x0)
		.attr('y', d => d.__y0)
		.attr('width', x.bandwidth())
		.attr('height', d => d.__y1 - d.__y0)
		.attr('fill', d => colorForRow(d.rowIds[0] ?? 0))
		.attr('data-row-ids', d => d.rowIds.join(','))
		.on('mouseover', (event, d) => {
			setHoverRows(d.rowIds);
			showTip(`<strong>Category:</strong> ${d.category}<br><strong>Value:</strong> ${d.value.toFixed(2)}`, event);
		})
		.on('mouseout', () => {
			clearHoverRows();
			hideTip();
		});
	attachBrush(svg, [[margin.left, margin.top], [width - margin.right, height - margin.bottom]], view, 'bar');

	chartState.push({ svg });
}

function renderBoxplot(containerId, view) {
	const width = 420;
	const height = 320;
	const margin = { top: 20, right: 16, bottom: 60, left: 52 };
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const x = d3.scaleBand().domain(view.groups.map(d => d.category)).range([margin.left, width - margin.right]).padding(0.2);
	const allValues = view.groups.flatMap(d => [d.min, d.q1, d.median, d.q3, d.max]);
	const y = d3.scaleLinear().domain(d3.extent(allValues)).nice().range([height - margin.bottom, margin.top]);
	view.groups.forEach(d => {
		d.__x0 = x(d.category);
		d.__x1 = x(d.category) + x.bandwidth();
	});

	svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x)).selectAll('text').attr('transform', 'rotate(-35)').style('text-anchor', 'end');
	svg.append('g').attr('class', 'axis').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5));
	svg.append('text').attr('x', width / 2).attr('y', height - 6).attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#444').text(view.xLabel);

	const g = svg.append('g');
	g.selectAll('line.whisker').data(view.groups).join('line')
		.attr('class', 'whisker')
		.attr('x1', d => x(d.category) + x.bandwidth() / 2)
		.attr('x2', d => x(d.category) + x.bandwidth() / 2)
		.attr('y1', d => y(d.min))
		.attr('y2', d => y(d.max))
		.attr('stroke', '#555');

	g.selectAll('rect.box').data(view.groups).join('rect')
		.attr('class', 'box')
		.attr('x', d => x(d.category))
		.attr('y', d => y(d.q3))
		.attr('width', x.bandwidth())
		.attr('height', d => Math.max(1, y(d.q1) - y(d.q3)))
		.attr('fill', d => colorForRow(d.rowIds[0] ?? 0))
		.attr('data-row-ids', d => d.rowIds.join(','))
		.on('mouseover', (event, d) => {
			setHoverRows(d.rowIds);
			showTip(`<strong>Category:</strong> ${d.category}<br>Median: <strong>${d.median.toFixed(2)}</strong><br>Q1: ${d.q1.toFixed(2)} | Q3: ${d.q3.toFixed(2)}<br>Min: ${d.min.toFixed(2)} | Max: ${d.max.toFixed(2)}`, event);
		})
		.on('mouseout', () => {
			clearHoverRows();
			hideTip();
		});

	g.selectAll('line.median').data(view.groups).join('line')
		.attr('class', 'median')
		.attr('x1', d => x(d.category))
		.attr('x2', d => x(d.category) + x.bandwidth())
		.attr('y1', d => y(d.median))
		.attr('y2', d => y(d.median))
		.attr('stroke', '#111');

	attachBrush(svg, [[margin.left, margin.top], [width - margin.right, height - margin.bottom]], view, 'boxplot');
	chartState.push({ svg });
}

function renderCirclePack(containerId, view) {
	const width = 420;
	const height = 320;
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const root = d3.hierarchy({ children: view.groups.map(d => ({ name: d.category, value: d.count, rowIds: d.rowIds })) })
		.sum(d => d.value || 0)
		.sort((a, b) => b.value - a.value);
	const pack = d3.pack().size([width - 16, height - 16]).padding(4);
	const leaves = pack(root).leaves();

	svg.append('g').attr('transform', 'translate(8,8)').selectAll('circle').data(leaves).join('circle')
		.attr('cx', d => d.x)
		.attr('cy', d => d.y)
		.attr('r', d => d.r)
		.attr('fill', d => colorForRow(d.data.rowIds[0] ?? 0))
		.attr('stroke', '#fff')
		.attr('data-row-ids', d => d.data.rowIds.join(','))
		.on('mouseover', (event, d) => setHoverRows(d.data.rowIds))
		.on('mouseout', clearHoverRows);

	svg.append('g').attr('transform', 'translate(8,8)').selectAll('text').data(leaves).join('text')
		.attr('x', d => d.x)
		.attr('y', d => d.y)
		.attr('text-anchor', 'middle')
		.attr('font-size', 10)
		.attr('pointer-events', 'none')
		.text(d => d.data.name.length > 14 ? `${d.data.name.slice(0, 11)}…` : d.data.name);

	chartState.push({ svg });
}

function renderChord(containerId, view) {
	const width = 420;
	const height = 320;
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const outerRadius = Math.min(width, height) * 0.38;
	const innerRadius = outerRadius - 20;
	const chord = d3.chord().padAngle(0.04).sortSubgroups(d3.descending);
	const arc = d3.arc().innerRadius(innerRadius).outerRadius(outerRadius);
	const ribbon = d3.ribbon().radius(innerRadius);
	const chords = chord(view.matrix);
	const g = svg.append('g').attr('transform', `translate(${width / 2},${height / 2})`);
	const color = d3.scaleOrdinal(d3.schemeTableau10).domain(view.categories);

	g.append('g').selectAll('path').data(chords.groups).join('path')
		.attr('d', arc)
		.attr('fill', d => color(view.categories[d.index]))
		.attr('stroke', '#fff')
		.attr('data-row-ids', d => chords.filter(c => c.source.index === d.index || c.target.index === d.index).flatMap(c => view.rowIdsMap[`${c.source.index}-${c.target.index}`] || []).join(','))
		.on('mouseover', (event, d) => {
			const ids = chords.filter(c => c.source.index === d.index || c.target.index === d.index).flatMap(c => view.rowIdsMap[`${c.source.index}-${c.target.index}`] || []);
			setHoverRows(ids);
		})
		.on('mouseout', clearHoverRows);

	g.append('g').attr('fill-opacity', 0.75).selectAll('path').data(chords).join('path')
		.attr('d', ribbon)
		.attr('fill', d => color(view.categories[d.source.index]))
		.attr('stroke', '#fff')
		.attr('data-row-ids', d => (view.rowIdsMap[`${d.source.index}-${d.target.index}`] || []).join(','))
		.on('mouseover', (event, d) => setHoverRows(view.rowIdsMap[`${d.source.index}-${d.target.index}`] || []))
		.on('mouseout', clearHoverRows);

	g.append('g').selectAll('text').data(chords.groups).join('text')
		.each(d => { d.angle = (d.startAngle + d.endAngle) / 2; })
		.attr('dy', '0.35em')
		.attr('transform', d => `rotate(${(d.angle * 180 / Math.PI - 90)}) translate(${outerRadius + 10}) ${d.angle > Math.PI ? 'rotate(180)' : ''}`)
		.attr('text-anchor', d => d.angle > Math.PI ? 'end' : 'start')
		.attr('font-size', 10)
		.text(d => view.categories[d.index]);

	chartState.push({ svg });
}

function renderViolin(containerId, view) {
	const width = 420;
	const height = 320;
	const margin = { top: 20, right: 16, bottom: 60, left: 52 };
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const x = d3.scaleBand().domain(view.groups.map(d => d.category)).range([margin.left, width - margin.right]).padding(0.2);
	const y = d3.scaleLinear().domain([
		d3.min(view.groups, d => d.min) ?? 0,
		d3.max(view.groups, d => d.max) ?? 1,
	]).nice().range([height - margin.bottom, margin.top]);
	const maxDensity = 1;
	const halfWidth = x.bandwidth() / 2;

	view.groups.forEach(group => {
		group.__x0 = x(group.category);
		group.__x1 = x(group.category) + x.bandwidth();
		const bins = d3.bin().domain(y.domain()).thresholds(16)(group.values);
		const maxCount = d3.max(bins, b => b.length) || 1;
		group.__density = bins.map(bin => ({
			y0: bin.x0,
			y1: bin.x1,
			density: bin.length / maxCount,
		}));
	});

	svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x)).selectAll('text').attr('transform', 'rotate(-35)').style('text-anchor', 'end');
	svg.append('g').attr('class', 'axis').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5));
	svg.append('text').attr('x', width / 2).attr('y', height - 6).attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#444').text(view.xLabel);
	svg.append('text').attr('transform', 'rotate(-90)').attr('x', -(height / 2)).attr('y', 14).attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#444').text(view.yLabel);

	const groupG = svg.append('g').attr('transform', `translate(0,0)`);
	groupG.selectAll('path').data(view.groups).join('path')
		.attr('transform', d => `translate(${x(d.category) + x.bandwidth() / 2},0)`)
		.attr('d', d => {
			const area = d3.area()
				.curve(d3.curveCatmullRom)
				.x0(v => -halfWidth * v.density)
				.x1(v => halfWidth * v.density)
				.y(v => y((v.y0 + v.y1) / 2));
			return area(d.__density);
		})
		.attr('fill', d => colorForRow(d.rowIds[0] ?? 0))
		.attr('opacity', 0.75)
		.attr('stroke', '#fff')
		.attr('data-row-ids', d => d.rowIds.join(','))
		.on('mouseover', (event, d) => setHoverRows(d.rowIds))
		.on('mouseout', clearHoverRows);

	groupG.selectAll('line.median').data(view.groups).join('line')
		.attr('x1', d => x(d.category) + x.bandwidth() / 2 - halfWidth * 0.5)
		.attr('x2', d => x(d.category) + x.bandwidth() / 2 + halfWidth * 0.5)
		.attr('y1', d => y(d3.median(d.values) ?? d.min))
		.attr('y2', d => y(d3.median(d.values) ?? d.min))
		.attr('stroke', '#111');

	attachBrush(svg, [[margin.left, margin.top], [width - margin.right, height - margin.bottom]], view, 'violin');
	chartState.push({ svg });
}

function renderHeatmap(containerId, view) {
	const width = 420;
	const height = 320;
	const margin = { top: 20, right: 16, bottom: 42, left: 52 };
	const svg = d3.select(`#${containerId}`).append('svg').attr('width', width).attr('height', height);
	const bins = view.bins;
	const cellW = (width - margin.left - margin.right) / bins;
	const cellH = (height - margin.top - margin.bottom) / bins;

	const xDomain = view.xDomain;
	const yDomain = view.yDomain;
	const xScale = d3.scaleLinear().domain(xDomain).range([margin.left, width - margin.right]);
	const yScale = d3.scaleLinear().domain(yDomain).range([height - margin.bottom, margin.top]);
	const color = d3.scaleSequential(d3.interpolateYlOrRd).domain([0, d3.max(view.cells, d => d.count) || 1]);

	svg.append('g').attr('class', 'axis').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(xScale).ticks(5));
	svg.append('g').attr('class', 'axis').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(yScale).ticks(5));

	svg.append('text')
		.attr('x', width / 2)
		.attr('y', height - 6)
		.attr('text-anchor', 'middle')
		.attr('font-size', 10)
		.attr('fill', '#444')
		.text(view.xLabel);
	svg.append('text')
		.attr('transform', 'rotate(-90)')
		.attr('x', -(height / 2))
		.attr('y', 14)
		.attr('text-anchor', 'middle')
		.attr('font-size', 10)
		.attr('fill', '#444')
		.text(view.yLabel);

	const xStep = (xDomain[1] - xDomain[0]) / bins;
	const yStep = (yDomain[1] - yDomain[0]) / bins;
	view.cells.forEach(d => {
		d.__x0 = xScale(xDomain[0] + d.xBin * xStep);
		d.__x1 = d.__x0 + Math.max(1, cellW);
		d.__y0 = yScale(yDomain[0] + (bins - d.yBin - 1) * yStep);
		d.__y1 = d.__y0 + Math.max(1, cellH);
	});

	svg.append('g').selectAll('rect').data(view.cells).join('rect')
		.attr('x', d => d.__x0)
		.attr('y', d => d.__y0)
		.attr('width', d => d.__x1 - d.__x0)
		.attr('height', d => d.__y1 - d.__y0)
		.attr('fill', d => color(d.count))
		.attr('stroke', '#fff').attr('stroke-width', 0.5)
		.attr('data-row-ids', d => d.rowIds.join(','))
		.on('mouseover', (event, d) => {
			setHoverRows(d.rowIds);
			showTip(`<strong>Count:</strong> ${d.count}<br>Rows: ${d.rowIds.length}`, event);
		})
		.on('mouseout', () => {
			clearHoverRows();
			hideTip();
		});

	attachBrush(svg, [[margin.left, margin.top], [width - margin.right, height - margin.bottom]], view, 'heatmap');

	chartState.push({ svg });
}

views.forEach((view, index) => {
	makeCard(view, index);
	if (view.type === 'heatmap') {
		renderHeatmap(`chart-${index}`, view);
	} else if (view.type === 'histogram') {
		renderHistogram(`chart-${index}`, view);
	} else if (view.type === 'bar') {
		renderBar(`chart-${index}`, view);
	} else if (view.type === 'boxplot') {
		renderBoxplot(`chart-${index}`, view);
	} else if (view.type === 'circlepack') {
		renderCirclePack(`chart-${index}`, view);
	} else if (view.type === 'chord') {
		renderChord(`chart-${index}`, view);
	} else if (view.type === 'violin') {
		renderViolin(`chart-${index}`, view);
	} else {
		renderScatterLike(`chart-${index}`, view);
	}
});

const legend = d3.select('.header').append('div').style('display', 'flex').style('gap', '8px').style('flex-wrap', 'wrap').style('margin-top', '8px');
rowIds.slice(0, Math.min(rowIds.length, 12)).forEach((rowId) => {
	const item = legend.append('div').style('display', 'inline-flex').style('align-items', 'center').style('gap', '4px').style('font-size', '11px');
	item.append('span').style('display', 'inline-block').style('width', '10px').style('height', '10px').style('border-radius', '50%').style('background', colorForRow(rowId));
	item.append('span').text(`row ${rowId}`);
});
</script>
</body>
</html>
"""

    return (
        page_template.replace("__TITLE__", title)
        .replace("__PALETTE__", json.dumps(palette))
        .replace("__VIEWS__", json.dumps(chart_payloads))
    )


@app.route("/api/join", methods=["POST"])
def join_tables():
    """Join multiple SQLite tables via a JSON request.

    Request JSON:
    {
      "tables": [
        {"name": "participantstatuslogs1", "alias": "log", "columns": ["participantId", "jobId", "availableBalance"]},
        {"name": "participants", "alias": "p", "columns": ["participantId", "age", "joviality"]},
        {"name": "jobs", "alias": "j", "columns": ["jobId", "employerId", "hourlyRate"]},
        {"name": "employers", "alias": "e", "columns": ["employerId", "buildingId", "location"]},
        {"name": "buildings", "alias": "b", "columns": ["buildingId", "buildingType", "location"]}
      ],
      "joins": [
        {"left": "log.participantId", "right": "p.participantId", "how": "inner"},
        {"left": "log.jobId", "right": "j.jobId", "how": "left"},
        {"left": "j.employerId", "right": "e.employerId", "how": "left"},
        {"left": "e.buildingId", "right": "b.buildingId", "how": "left"}
      ],
      "select": ["p.age", "p.joviality", "e.location", "b.buildingType"],
      "limit": 200,
      "format": "json"   # optional: json | html
    }
    """
    if not DB_PATH.exists():
        return jsonify({"error": f"Database file not found: {DB_PATH}"}), 404

    payload = request.get_json(silent=True) or {}
    tables = payload.get("tables", [])
    joins = payload.get("joins", [])
    select_cols = payload.get("select", [])
    output_format = (payload.get("format") or "json").lower()
    limit = payload.get("limit", 1000)

    if not isinstance(tables, list) or len(tables) < 2:
        return jsonify(
            {"error": "'tables' must contain at least two table specs."}
        ), 400
    if not isinstance(joins, list) or not joins:
        return jsonify({"error": "'joins' must be a non-empty list."}), 400
    if output_format not in {"json", "html"}:
        return jsonify({"error": "'format' must be 'json' or 'html'."}), 400

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return jsonify({"error": "'limit' must be an integer."}), 400
    if limit <= 0:
        return jsonify({"error": "'limit' must be greater than 0."}), 400

    table_specs: dict[str, dict] = {}
    for table_spec in tables:
        if not isinstance(table_spec, dict):
            return jsonify({"error": "Each table spec must be an object."}), 400
        table_name = table_spec.get("name")
        alias = table_spec.get("alias") or table_name
        if not isinstance(table_name, str) or not _is_valid_identifier(table_name):
            return jsonify({"error": f"Invalid table name: {table_name}"}), 400
        if not isinstance(alias, str) or not _is_valid_identifier(alias):
            return jsonify({"error": f"Invalid alias for table '{table_name}'."}), 400
        if alias in table_specs:
            return jsonify({"error": f"Duplicate table alias: {alias}"}), 400
        columns = table_spec.get("columns", [])
        if columns is not None and not isinstance(columns, list):
            return jsonify(
                {"error": f"'columns' must be a list for table '{table_name}'."}
            ), 400
        table_specs[alias] = {
            "name": table_name,
            "alias": alias,
            "columns": list(columns or []),
        }

    # Validate joins and collect required columns per table alias.
    required_columns: dict[str, set[str]] = {
        alias: set(spec["columns"]) for alias, spec in table_specs.items()
    }
    validated_joins: list[dict] = []
    allowed_join_types = {"inner", "left", "right", "outer"}

    for join_spec in joins:
        if not isinstance(join_spec, dict):
            return jsonify({"error": "Each join spec must be an object."}), 400
        left_ref = _parse_table_ref(join_spec.get("left", ""))
        right_ref = _parse_table_ref(join_spec.get("right", ""))
        if left_ref is None or right_ref is None:
            return jsonify({"error": "Join refs must use 'alias.column' syntax."}), 400
        left_alias, left_col = left_ref
        right_alias, right_col = right_ref
        if left_alias not in table_specs or right_alias not in table_specs:
            return jsonify(
                {"error": f"Unknown table alias in join: {left_alias} -> {right_alias}"}
            ), 400
        how = (join_spec.get("how") or "inner").lower()
        if how not in allowed_join_types:
            return jsonify({"error": f"Unsupported join type: {how}"}), 400
        required_columns[left_alias].add(left_col)
        required_columns[right_alias].add(right_col)
        validated_joins.append({"left": left_ref, "right": right_ref, "how": how})

    conn = _get_db_connection()
    try:
        loaded: dict[str, pd.DataFrame] = {}
        load_limit = max(int(limit), min(int(limit) * 10, 5000))
        for alias, spec in table_specs.items():
            if not _table_exists(conn, spec["name"]):
                return jsonify(
                    {"error": f"Table '{spec['name']}' does not exist."}
                ), 404
            df, _ = _load_prefixed_table(
                conn,
                spec["name"],
                alias,
                list(required_columns[alias]),
                row_limit=load_limit,
            )
            if df.empty:
                return jsonify(
                    {"error": f"Table '{spec['name']}' returned no rows."}
                ), 404
            loaded[alias] = df
    finally:
        conn.close()

    # Join in the requested order; the first table becomes the base frame.
    base_alias = next(iter(table_specs.keys()))
    joined = loaded[base_alias].copy()
    joined_aliases = {base_alias}

    def _prefixed_key(df: pd.DataFrame, alias: str, requested_col: str) -> str | None:
        available = {
            c.split("__", 1)[1] for c in df.columns if c.startswith(f"{alias}__")
        }
        actual_col = _resolve_column_name(available, requested_col)
        if actual_col is None:
            return None
        return f"{alias}__{actual_col}"

    for join_spec in validated_joins:
        (left_alias, left_col) = join_spec["left"]
        (right_alias, right_col) = join_spec["right"]
        if left_alias not in joined_aliases:
            return jsonify(
                {
                    "error": f"Join order problem: '{left_alias}' is not present in the current joined data."
                }
            ), 400
        right_df = loaded[right_alias]
        left_key = _prefixed_key(joined, left_alias, left_col)
        right_key = _prefixed_key(right_df, right_alias, right_col)
        if left_key is None:
            return jsonify(
                {
                    "error": f"Missing join key in current result: {join_spec['left'][0]}.{left_col}"
                }
            ), 400
        if right_key is None:
            return jsonify(
                {
                    "error": f"Missing join key in table '{right_alias}': {join_spec['right'][0]}.{right_col}"
                }
            ), 400
        if left_key not in joined.columns:
            return jsonify(
                {
                    "error": f"Missing join key in current result: {join_spec['left'][0]}.{left_col}"
                }
            ), 400
        if right_key not in right_df.columns:
            return jsonify(
                {
                    "error": f"Missing join key in table '{right_alias}': {join_spec['right'][0]}.{right_col}"
                }
            ), 400
        joined = pd.merge(
            joined, right_df, left_on=left_key, right_on=right_key, how=join_spec["how"]
        )
        joined_aliases.add(right_alias)

    if select_cols:
        if not isinstance(select_cols, list):
            return jsonify({"error": "'select' must be a list when provided."}), 400
        resolved_select = []
        for item in select_cols:
            ref = _parse_table_ref(item)
            if ref is None:
                return jsonify(
                    {"error": f"Select columns must use 'alias.column' syntax: {item}"}
                ), 400
            alias, col = ref
            if alias not in table_specs:
                return jsonify({"error": f"Unknown alias in select: {alias}"}), 400
            actual_col = _resolve_column_name(
                {
                    c.split("__", 1)[1]
                    for c in joined.columns
                    if c.startswith(f"{alias}__")
                },
                col,
            )
            if actual_col is None:
                return jsonify(
                    {"error": f"Column not available in joined result: {item}"}
                ), 400
            resolved_select.append(f"{alias}__{actual_col}")
        joined = joined[resolved_select]

    joined = joined.head(limit)
    if joined.empty:
        return jsonify({"error": "No rows after joining."}), 404

    if output_format == "html":
        title = "Multi-table join result"
        html = f"""<!doctype html>
<html>
<head>
	<meta charset=\"utf-8\">
	<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
	<title>{title}</title>
	<style>
		body {{ font-family: Arial, sans-serif; margin: 16px; }}
		code, pre {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
		table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
		th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
		th {{ background: #f2f2f2; position: sticky; top: 0; }}
		.meta {{ margin-bottom: 12px; color: #444; }}
	</style>
</head>
<body>
	<h2>{title}</h2>
	<div class=\"meta\">Rows: {len(joined)} | Columns: {len(joined.columns)} | Tables: {", ".join(table_specs.keys())}</div>
	{joined.to_html(index=False, escape=True)}
</body>
</html>"""
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    return jsonify(
        {
            "row_count": int(len(joined)),
            "column_count": int(len(joined.columns)),
            "columns": list(joined.columns),
            "rows": joined.to_dict(orient="records"),
            "tables": list(table_specs.keys()),
            "joins": [
                {
                    "left": f"{left_alias}.{left_col}",
                    "right": f"{right_alias}.{right_col}",
                    "how": join_spec["how"],
                }
                for join_spec in validated_joins
                for (left_alias, left_col), (right_alias, right_col) in [
                    (join_spec["left"], join_spec["right"])
                ]
            ],
        }
    )


@app.route("/api/join-chart", methods=["POST"])
def join_chart():
    """Join multiple tables and render a D3Blocks chart from the joined result."""
    payload = request.get_json(silent=True) or {}
    chart = (payload.get("chart") or "scatter").lower()
    chart_columns = payload.get("chart_columns", payload.get("columns", []))
    if not isinstance(chart_columns, list):
        return jsonify({"error": "'chart_columns' must be a list when provided."}), 400

    try:
        joined, table_specs, validated_joins = _build_joined_dataframe(payload)
        title = payload.get("title") or f"Joined {chart} chart"
        html = _render_joined_chart_html(joined, chart, chart_columns, title)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    except JoinRequestError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    except Exception as exc:
        return jsonify({"error": f"Failed to build join chart: {exc}"}), 500


@app.route("/api/join-sync", methods=["POST"])
def join_sync():
    """Join multiple tables and render multiple synced scatter charts."""
    payload = request.get_json(silent=True) or {}
    views = payload.get("views", [])
    if not isinstance(views, list) or not views:
        return jsonify({"error": "'views' must be a non-empty list."}), 400

    try:
        joined, _table_specs, _validated_joins = _build_joined_dataframe(payload)
        title = payload.get("title") or "Synced multi-view join"
        html = _render_synced_joined_views_html(joined, views, title)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    except JoinRequestError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    except Exception as exc:
        return jsonify({"error": f"Failed to build synced join view: {exc}"}), 500


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

    if any(
        not isinstance(col, str) or not _is_valid_identifier(col) for col in columns
    ):
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
            return jsonify(
                {"error": f"Columns not found in '{dataset}': {missing}"}
            ), 400

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
                return jsonify(
                    {"error": "Scatter chart requires at least 2 columns."}
                ), 400

            # d3blocks.scatter expects x and y arrays of equal length.
            scatter_df = df[[columns[0], columns[1]]].copy()
            scatter_df[columns[0]] = pd.to_numeric(
                scatter_df[columns[0]], errors="coerce"
            )
            scatter_df[columns[1]] = pd.to_numeric(
                scatter_df[columns[1]], errors="coerce"
            )
            scatter_df = scatter_df.dropna(subset=[columns[0], columns[1]])

            if scatter_df.shape[0] < 2:
                return jsonify(
                    {"error": "Not enough data points for scatter chart."}
                ), 400

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


@app.route("/api/d3block-sankey", methods=["POST"])
def generate_sankey_html():
    """
    Generate an interactive Sankey diagram from SQLite data.

    Request JSON:
    {
      "dataset": "participants",
      "source_col": "participantId",
      "target_col": "employerId",
      "value_col": "duration",        # required for Sankey; must be numeric
      "limit": 1000                   # optional
    }
    """
    if not DB_PATH.exists():
        return jsonify({"error": f"Database file not found: {DB_PATH}"}), 404

    payload = request.get_json(silent=True) or {}
    dataset = payload.get("dataset")
    source_col = payload.get("source_col")
    target_col = payload.get("target_col")
    value_col = payload.get("value_col")
    limit = payload.get("limit", 1000)

    if not isinstance(dataset, str) or not _is_valid_identifier(dataset):
        return jsonify({"error": "Invalid dataset name."}), 400

    if not source_col or not _is_valid_identifier(source_col):
        return jsonify({"error": "Invalid source_col."}), 400

    if not target_col or not _is_valid_identifier(target_col):
        return jsonify({"error": "Invalid target_col."}), 400

    if not value_col or not _is_valid_identifier(value_col):
        return jsonify({"error": "value_col is required for Sankey."}), 400

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
        missing = [
            c for c in [source_col, target_col, value_col] if c not in available_columns
        ]
        if missing:
            return jsonify({"error": f"Columns not found: {missing}"}), 400

        cols_to_select = ", ".join([source_col, target_col, value_col])
        query = f"SELECT {cols_to_select} FROM {dataset} LIMIT ?"
        df = pd.read_sql_query(query, conn, params=(limit,))
    finally:
        conn.close()

    if df.empty:
        return jsonify({"error": "No rows returned for this request."}), 404

    # Prepare for Sankey: requires 3-column DataFrame with source, target, value
    df_sankey = df[[source_col, target_col, value_col]].copy()
    df_sankey[value_col] = pd.to_numeric(df_sankey[value_col], errors="coerce")
    df_sankey = df_sankey.dropna(subset=[value_col])

    if df_sankey.empty:
        return jsonify(
            {"error": "No valid numeric values in value_col for Sankey."}
        ), 400

    # Sankey expects a DataFrame where the first two columns are source/target
    # and the third column is the value. Rename columns to match D3Blocks expectation.
    df_sankey.columns = ["source", "target", "value"]

    d3 = D3Blocks()
    try:
        html = d3.sankey(
            df=df_sankey,
            showfig=False,
            return_html=True,
            title=f"Sankey: {dataset} ({source_col} → {target_col})",
        )

        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    except Exception as exc:
        return jsonify({"error": f"Failed to build Sankey: {exc}"}), 500


def _parse_wkt_point(wkt: str) -> tuple[float, float] | tuple[None, None]:
    m = re.search(
        r"POINT\s*\(\s*([\d.eE+\-]+)\s+([\d.eE+\-]+)\s*\)", str(wkt), re.IGNORECASE
    )
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def _get_job_transitions(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (start_employers, end_employers) DataFrames with participantId → employerId.

    Uses the numerically-first and numerically-last participantstatuslogs table
    as proxies for the start and end of the study period.
    """
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'participantstatuslogs%'"
    ).fetchall()

    def _extract_number(name: str) -> int:
        match = re.search(r"(\d+)$", name)
        return int(match.group(1)) if match else 0

    tables = sorted([r[0] for r in rows], key=_extract_number)
    if len(tables) < 2:
        return pd.DataFrame(), pd.DataFrame()

    jobs_df = pd.read_sql_query("SELECT jobId, employerId FROM jobs", conn)

    def dominant_employer(table: str) -> pd.DataFrame:
        # Optimization: Move the "dominant" logic into SQL to avoid loading millions of rows into memory
        query = f"""
            SELECT participantId, jobId
            FROM (
                SELECT participantId, jobId, COUNT(*) AS cnt,
                        ROW_NUMBER() OVER (PARTITION BY participantId ORDER BY COUNT(*) DESC) as rn
                FROM {_quote_identifier(table)}
                WHERE jobId IS NOT NULL
                    AND jobId NOT IN ('', 'N/A', 'nan')
                GROUP BY participantId, jobId
            ) WHERE rn = 1
        """
        try:
            top = pd.read_sql_query(query, conn)
            if top.empty:
                return pd.DataFrame(columns=["participantId", "employerId"])

            top["jobId"] = pd.to_numeric(top["jobId"], errors="coerce")
            return top.merge(jobs_df, on="jobId", how="left")[
                ["participantId", "employerId"]
            ].dropna()
        except Exception as e:
            print(f"Error processing table {table}: {e}")
            return pd.DataFrame(columns=["participantId", "employerId"])

    return dominant_employer(tables[0]), dominant_employer(tables[-1])


def _compute_employer_health_scores(conn: sqlite3.Connection) -> pd.DataFrame:
    """Estimated health score per employer (derived — not an official measure).

    Score = normalized(job_count)*0.25 + normalized(avg_rate)*0.25
          + normalized(stable)*0.25 - normalized(turnover_rate)*0.25
    All components normalised 0–1 within the current dataset.
    """
    job_df = pd.read_sql_query(
        "SELECT employerId, COUNT(*) AS job_count, AVG(hourlyRate) AS avg_rate FROM jobs GROUP BY employerId",
        conn,
    )
    start_df, end_df = _get_job_transitions(conn)
    if start_df.empty or end_df.empty:
        return pd.DataFrame()

    all_employers = set(start_df["employerId"].dropna().astype(int)) | set(
        end_df["employerId"].dropna().astype(int)
    )
    rows = []
    for emp in all_employers:
        sp = set(start_df[start_df["employerId"] == emp]["participantId"])
        ep = set(end_df[end_df["employerId"] == emp]["participantId"])
        stable = len(sp & ep)
        departed = len(sp - ep)
        arrived = len(ep - sp)
        total_start = max(len(sp), 1)
        rows.append(
            {
                "employerId": emp,
                "stable": stable,
                "departed": departed,
                "arrived": arrived,
                "total_start": total_start,
                "turnover_rate": round((departed + arrived) / total_start, 3),
            }
        )
    trans_df = pd.DataFrame(rows)

    job_df["employerId"] = pd.to_numeric(job_df["employerId"], errors="coerce")
    trans_df["employerId"] = pd.to_numeric(trans_df["employerId"], errors="coerce")
    df = job_df.merge(trans_df, on="employerId", how="inner")
    if df.empty:
        return df

    def _norm(col: str) -> pd.Series:
        mn, mx = df[col].min(), df[col].max()
        if mx == mn:
            return pd.Series([0.5] * len(df), index=df.index)
        return (df[col] - mn) / (mx - mn)

    df["health_score"] = (
        _norm("job_count") * 0.25
        + _norm("avg_rate") * 0.25
        + _norm("stable") * 0.25
        - _norm("turnover_rate") * 0.25
    ).round(3)
    return df


@app.route("/api/business-health-page", methods=["GET"])
def business_health_page():
    """Combined Business Health dashboard: 4 linked charts in one page."""
    if not DB_PATH.exists():
        return jsonify({"error": f"Database not found: {DB_PATH}"}), 404

    conn = _get_db_connection()
    try:
        health_df = _compute_employer_health_scores(conn)
        activity_df = pd.read_sql_query(
            """
			SELECT CAST(venueId AS INTEGER) AS employerId,
			       strftime('%Y-%m', timestamp) AS month,
			       COUNT(*) AS checkins
			FROM checkinjournal
			WHERE venueType = 'Workplace'
			GROUP BY employerId, month
			ORDER BY month
			""",
            conn,
        )
    finally:
        conn.close()

    if health_df.empty:
        return jsonify({"error": "Not enough data to build business health page"}), 404

    months_list = (
        sorted(activity_df["month"].unique().tolist()) if not activity_df.empty else []
    )

    act_map: dict = {}
    for _, row in activity_df.iterrows():
        eid = int(row["employerId"])
        act_map.setdefault(eid, {})[row["month"]] = int(row["checkins"])

    def _cat(s: float) -> str:
        return "Prosperous" if s >= 0.6 else "Neutral" if s >= 0.35 else "Struggling"

    employers = [
        {
            "id": int(row["employerId"]),
            "avg_rate": round(float(row["avg_rate"]), 2),
            "job_count": int(row["job_count"]),
            "stable": int(row["stable"]),
            "departed": int(row["departed"]),
            "arrived": int(row["arrived"]),
            "turnover_rate": round(float(row["turnover_rate"]), 3),
            "score": float(row["health_score"]),
            "category": _cat(float(row["health_score"])),
            "activity": [
                act_map.get(int(row["employerId"]), {}).get(m, 0) for m in months_list
            ],
        }
        for _, row in health_df.sort_values("health_score", ascending=False).iterrows()
    ]

    html = _render_business_health_page_html(
        {"employers": employers, "months": months_list}
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def _render_business_health_page_html(data: dict) -> str:
    import json as _json

    page = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Business Health Dashboard</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, sans-serif; background: #f4f5f7; color: #222; }
.page { max-width: 1380px; margin: 0 auto; padding: 20px; }

/* header */
.dash-header { background: #fff; border-radius: 10px; padding: 16px 20px; margin-bottom: 14px;
  box-shadow: 0 1px 4px rgba(0,0,0,.1); }
.dash-header h2 { margin: 0 0 4px; font-size: 18px; }
.dash-sub { font-size: 12px; color: #888; margin: 0 0 8px; }
.dash-note { font-size: 10px; color: #b00; background: #fff8f0; border: 1px solid #f5c6a0;
  border-radius: 4px; padding: 4px 8px; display: inline-block; margin-bottom: 10px; }

/* category legend / filter */
.cat-legend { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; font-size: 11px; }
.cat-btn { display: flex; align-items: center; gap: 5px; cursor: pointer; padding: 3px 8px;
  border-radius: 12px; border: 1.5px solid transparent; user-select: none; transition: opacity .1s; }
.cat-btn:hover { opacity: .8; }
.cat-btn.off { opacity: .3; }
.cat-swatch { width: 10px; height: 10px; border-radius: 50%; }
.deselect-btn { margin-left: 8px; font-size: 10px; padding: 3px 10px; cursor: pointer;
  border: 1px solid #ccc; border-radius: 10px; background: #f5f5f5; }
.deselect-btn:hover { background: #e8e8e8; }

/* details bar */
.details-bar { background: #fff; border-radius: 10px; padding: 12px 16px; box-shadow: 0 1px 5px rgba(0,0,0,.1);
  margin-top: 14px; min-height: 64px; display: flex; align-items: center; justify-content: center; gap: 20px; flex-wrap: wrap; }
.detail-stat { display: flex; flex-direction: column; align-items: center; min-width: 70px; }
.detail-label { font-size: 10px; color: #777; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
.detail-value { font-size: 15px; font-weight: bold; color: #2f5d8c; }
.detail-val-cat { padding: 2px 8px; border-radius: 12px; color: #fff; font-size: 11px; font-weight: bold; }

/* chart grid */
.charts-top { display: grid; grid-template-columns: 3fr 2fr; gap: 14px; margin-bottom: 14px; }
.charts-bottom { display: grid; grid-template-columns: 2fr 3fr; gap: 14px; }

.panel { background: #fff; border-radius: 10px; padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,.1); overflow: hidden; }
.panel h3 { margin: 0 0 3px; font-size: 13px; color: #333; }
.panel-sub { font-size: 10px; color: #aaa; margin: 0 0 8px; }

/* ranking scroll */
.rank-scroll { overflow-y: auto; max-height: 420px; }
.rank-ctrl { font-size: 11px; margin-bottom: 8px; }
.rank-ctrl select { font-size: 11px; padding: 2px 4px; }

/* size scroll */
.size-scroll { overflow-y: auto; max-height: 380px; }

/* color legend bar */
.grad-legend { display: flex; align-items: center; gap: 6px; font-size: 10px;
  color: #888; margin-bottom: 6px; }

.info-icon { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px;
  background: #2f5d8c; color: #fff; border-radius: 50%; font-size: 9px; margin-left: 6px; cursor: help; vertical-align: middle; }

/* shared tooltip */
.tooltip { position: fixed; background: rgba(20, 20, 20, 0.92); color: #fff; padding: 8px 12px;
  border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0;
  transition: opacity 0.12s; line-height: 1.6; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

.axis text { font-size: 9px; fill: #666; }
.axis path, .axis line { stroke: #ddd; }

@media (max-width: 900px) {
  .charts-top, .charts-bottom { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="page">

  <div class="dash-header">
    <h2>Business Health Dashboard</h2>
    <p class="dash-sub">Focus: Which businesses appear prosperous or struggling?  Click any employer in any chart to highlight it across all views.</p>
    <div class="dash-note">&#9432; Health score is <strong>derived/estimated</strong>: 0.25×(jobs) + 0.25×(avg rate) + 0.25×(stable) &minus; 0.25×(turnover rate). Not an official economic measure.</div>
    <div class="cat-legend" id="cat-legend">
      <span style="font-size:11px;color:#666;margin-right:4px;">Filter:</span>
    </div>
    <div class="details-bar" id="details-bar">Click any employer in any chart to see details here.</div>
  </div>

  <div class="charts-top">
    <!-- SCATTER -->
    <div class="panel">
      <h3>Prosperity Scatter <span class="info-icon" onmouseover="showTip('<strong>Avg hourly rate vs job listings</strong><br>Dot size = stable workers.<br> Colour = health score.', event)" onmouseout="hideTip()">?</span></h3>
      <div class="grad-legend">
        <span>Low score</span>
        <canvas id="grad-canvas" width="120" height="9" style="border-radius:3px"></canvas>
        <span>High score</span>
        &nbsp;&nbsp;
        <svg width="56" height="14">
          <circle cx="7" cy="7" r="3" fill="#888"/>
          <circle cx="26" cy="7" r="6" fill="#888"/>
          <circle cx="48" cy="7" r="9" fill="#888"/>
        </svg>
        <span>= stable workers</span>
      </div>
      <svg id="scatter-svg"></svg>
    </div>

    <!-- RANKING -->
    <div class="panel">
      <h3>Health Ranking <span class="info-icon" onmouseover="showTip('<strong>Derived health score per employer</strong><br>Green=Prosperous <br> Yellow=Neutra <br> Red=Struggling', event)" onmouseout="hideTip()">?</span></h3>
      <div class="rank-ctrl">
        Sort:
        <select id="rank-sort" onchange="drawRanking()">
          <option value="score">Health Score</option>
          <option value="turnover_rate">Turnover Rate</option>
          <option value="avg_rate">Avg Rate</option>
          <option value="stable">Stable Workers</option>
        </select>
        <select id="rank-dir" onchange="drawRanking()">
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
        &nbsp;
        <label><input type="checkbox" id="rank-top" checked onchange="drawRanking()"> Top 40</label>
      </div>
      <div class="rank-scroll">
        <svg id="ranking-svg"></svg>
      </div>
    </div>
  </div>

  <div class="charts-bottom">
    <!-- SIZE & WAGE -->
    <div class="panel">
      <h3>Employer Size &amp; Wage <span class="info-icon" onmouseover="showTip('<strong>Employer size and wage levels</strong><br>Bar height = job count<br>Colour = avg hourly rate', event)" onmouseout="hideTip()">?</span></h3>
      <div class="size-scroll">
        <svg id="size-svg"></svg>
      </div>
    </div>

    <!-- ACTIVITY -->
    <div class="panel">
      <h3>Workplace Activity<span class="info-icon" onmouseover="showTip('<strong>Monthly workplace check-ins</strong><br>Lines show city-wide employer activity. Highlights the selected employer.', event)" onmouseout="hideTip()">?</span></h3>
      <svg id="activity-svg"></svg>
    </div>
  </div>

</div>
<div class="tooltip" id="tip"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const DATA = __DATA__;

// ── shared state ───────────────────────────────────────────
let selectedId = null;
const hiddenCats = new Set();
const CAT_COLORS = {Prosperous:'#1a9850', Neutral:'#e6ab02', Struggling:'#d73027'};
const scoreColor = d3.scaleSequential(d3.interpolateRdYlGn).domain([0, 1]);
const tip = d3.select('#tip');

function isVis(d) { return !hiddenCats.has(d.category); }

function showTip(html, ev) {
  tip.html(html).style('opacity', 1)
     .style('left', (ev.clientX + 15) + 'px').style('top', (ev.clientY - 45) + 'px');
}
function hideTip() { tip.style('opacity', 0); }

function selectEmployer(id) {
  selectedId = (selectedId === id) ? null : id;
  applySelection();
  updateDetailsBar();
}

function applySelection() {
  // scatter dots
  d3.selectAll('.s-dot')
    .attr('opacity', d => !isVis(d) ? 0 : selectedId == null ? 0.85 : d.id === selectedId ? 1 : 0.07)
    .attr('stroke', d => d.id === selectedId ? '#000' : '#fff')
    .attr('stroke-width', d => d.id === selectedId ? 2.5 : 0.7)
    .attr('r', d => d.id === selectedId ? sizeScale(d.stable) * 1.35 : sizeScale(d.stable));
  d3.selectAll('.s-dot').filter(d => d.id === selectedId).raise();

  // ranking bars
  d3.selectAll('.r-bar')
    .attr('opacity', d => !isVis(d) ? 0 : selectedId == null ? 0.9 : d.id === selectedId ? 1 : 0.1);
  d3.selectAll('.r-val')
    .attr('opacity', d => !isVis(d) ? 0 : selectedId == null ? 1 : d.id === selectedId ? 1 : 0.15);

  // size bars
  d3.selectAll('.sz-bar')
    .attr('opacity', d => !isVis(d) ? 0 : selectedId == null ? 0.85 : d.id === selectedId ? 1 : 0.08);
  d3.selectAll('.sz-val')
    .attr('opacity', d => !isVis(d) ? 0 : selectedId == null ? 0.7 : d.id === selectedId ? 1 : 0.1);

  // activity lines
  d3.selectAll('.act-line')
    .attr('stroke', d => selectedId == null ? (isVis(d) ? '#bbb' : '#eee') : d.id === selectedId ? CAT_COLORS[d.category] : '#ddd')
    .attr('stroke-width', d => d.id === selectedId ? 2.8 : 1)
    .attr('opacity', d => !isVis(d) ? 0 : selectedId == null ? 0.5 : d.id === selectedId ? 1 : 0.06);
  d3.selectAll('.act-line').filter(d => d.id === selectedId).raise();
}

function updateDetailsBar() {
  const el = document.getElementById('details-bar');
  if (selectedId == null) {
    el.style.justifyContent = 'center';
    el.innerHTML = '<span style="color:#aaa;font-style:italic">Click any employer in any chart to see deep-dive metrics here.</span>';
    return;
  }
  const d = DATA.employers.find(e => e.id === selectedId);
  if (!d) return;
  
  el.style.justifyContent = 'space-around';
  const peak = DATA.months.length ? Math.max(...d.activity) : '—';
  
  el.innerHTML = `
    <div class="detail-stat">
      <span class="detail-label">Employer</span>
      <span class="detail-value">#${d.id}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Status</span>
      <span class="detail-val-cat" style="background:${CAT_COLORS[d.category]}">${d.category}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Health Score</span>
      <span class="detail-value">${d.score.toFixed(3)}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Jobs</span>
      <span class="detail-value">${d.job_count}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Avg Rate</span>
      <span class="detail-value">$${d.avg_rate}/hr</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Turnover</span>
      <span class="detail-value">${(d.turnover_rate*100).toFixed(1)}%</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Stable</span>
      <span class="detail-value">${d.stable}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Departed</span>
      <span class="detail-value" style="color:#d62728">${d.departed}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Arrived</span>
      <span class="detail-value" style="color:#2ca02c">${d.arrived}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Peak Activity</span>
      <span class="detail-value">${peak}</span>
    </div>
    <div class="detail-stat" style="min-width:auto">
      <button class="deselect-btn" onclick="selectEmployer(${d.id})" style="margin:0">&#10005;</button>
    </div>
  `;
}

// ── category legend ────────────────────────────────────────
const catLegend = d3.select('#cat-legend');
['Prosperous','Neutral','Struggling'].forEach(cat => {
  const btn = catLegend.append('div').attr('class','cat-btn').attr('id',`cat-btn-${cat}`)
    .style('border-color', CAT_COLORS[cat])
    .on('click', () => {
      if (hiddenCats.has(cat)) hiddenCats.delete(cat); else hiddenCats.add(cat);
      d3.select(`#cat-btn-${cat}`).classed('off', hiddenCats.has(cat));
      applySelection();
    });
  btn.append('div').attr('class','cat-swatch').style('background', CAT_COLORS[cat]);
  btn.append('span').text(cat);
});
catLegend.append('button').attr('class','deselect-btn').text('Clear selection')
  .on('click', () => { selectedId = null; applySelection(); updateDetailsBar(); });

// ── gradient legend canvas ─────────────────────────────────
const canvas = document.getElementById('grad-canvas');
const ctx = canvas.getContext('2d');
const grd = ctx.createLinearGradient(0,0,120,0);
grd.addColorStop(0,'#d73027'); grd.addColorStop(0.5,'#ffffbf'); grd.addColorStop(1,'#1a9850');
ctx.fillStyle = grd; ctx.fillRect(0,0,120,9);

// ── SCATTER CHART ──────────────────────────────────────────
const scatterMargin = {top:16, right:16, bottom:52, left:52};
const scatterW = 540 - scatterMargin.left - scatterMargin.right;
const scatterH = 380 - scatterMargin.top  - scatterMargin.bottom;

const sizeScale = d3.scaleSqrt()
  .domain([0, d3.max(DATA.employers, d => d.stable) || 1]).range([3, 17]);

const sx = d3.scaleLinear().domain(d3.extent(DATA.employers, d => d.avg_rate)).nice().range([0, scatterW]);
const sy = d3.scaleLinear().domain([0, d3.max(DATA.employers, d => d.job_count)*1.12]).nice().range([scatterH, 0]);

const scatterSvg = d3.select('#scatter-svg')
  .attr('width',  scatterW + scatterMargin.left + scatterMargin.right)
  .attr('height', scatterH + scatterMargin.top  + scatterMargin.bottom)
  .append('g').attr('transform', `translate(${scatterMargin.left},${scatterMargin.top})`);

// grid
scatterSvg.append('g').call(d3.axisLeft(sy).tickSize(-scatterW).tickFormat(''))
  .call(g => { g.select('.domain').remove(); g.selectAll('.tick line').attr('stroke','#f0f0f0'); });
scatterSvg.append('g').attr('transform',`translate(0,${scatterH})`)
  .call(d3.axisBottom(sx).tickSize(-scatterH).tickFormat(''))
  .call(g => { g.select('.domain').remove(); g.selectAll('.tick line').attr('stroke','#f0f0f0'); });

scatterSvg.append('g').attr('class','axis').attr('transform',`translate(0,${scatterH})`).call(d3.axisBottom(sx).ticks(6));
scatterSvg.append('g').attr('class','axis').call(d3.axisLeft(sy).ticks(5));

scatterSvg.append('text').attr('x',scatterW/2).attr('y',scatterH+40)
  .attr('text-anchor','middle').attr('font-size',11).attr('fill','#666').text('Average Hourly Rate ($/hr)');
scatterSvg.append('text').attr('transform','rotate(-90)').attr('x',-scatterH/2).attr('y',-38)
  .attr('text-anchor','middle').attr('font-size',11).attr('fill','#666').text('Job Listings');

scatterSvg.selectAll('.s-dot').data(DATA.employers).join('circle')
  .attr('class','s-dot').attr('cx', d => sx(d.avg_rate)).attr('cy', d => sy(d.job_count))
  .attr('r', d => sizeScale(d.stable))
  .attr('fill', d => scoreColor(d.score))
  .attr('stroke','#fff').attr('stroke-width',0.7).attr('opacity',0.85).attr('cursor','pointer')
  .on('mouseover', (event,d) => {
    showTip(`<strong>Employer ${d.id}</strong><br>${d.category}<br>Score: <strong>${d.score.toFixed(3)}</strong><br>Rate: <strong>$${d.avg_rate}/hr</strong><br>Jobs: <strong>${d.job_count}</strong><br>Stable: <strong>${d.stable}</strong><br>Turnover: <strong>${(d.turnover_rate*100).toFixed(1)}%</strong>`, event);
  })
  .on('mouseout', () => tip.style('opacity',0))
  .on('click', (_,d) => selectEmployer(d.id));

// ── HEALTH RANKING ─────────────────────────────────────────
function drawRanking() {
  const key  = document.getElementById('rank-sort').value;
  const dir  = document.getElementById('rank-dir').value;
  const topN = document.getElementById('rank-top').checked;

  let recs = [...DATA.employers];
  recs.sort((a,b) => dir === 'desc' ? b[key] - a[key] : a[key] - b[key]);
  if (topN) recs = recs.slice(0, 40);

  const margin = {top:4, right:56, bottom:20, left:74};
  const W = 360 - margin.left - margin.right;
  const barH = 13, gap = 3;
  const H = recs.length * (barH + gap);

  d3.select('#ranking-svg').selectAll('*').remove();
  const svg = d3.select('#ranking-svg')
    .attr('width',  W + margin.left + margin.right)
    .attr('height', H + margin.top  + margin.bottom)
    .append('g').attr('transform',`translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0,1]).range([0,W]);
  const y = d3.scaleBand().domain(recs.map(d=>`E${d.id}`)).range([0,H]).padding(0.15);

  svg.append('g').attr('transform',`translate(0,${H})`).attr('class','axis')
    .call(d3.axisBottom(x).ticks(4).tickFormat(d3.format('.1f')));
  svg.append('g').attr('class','axis').call(d3.axisLeft(y).tickSize(0))
    .call(g => g.select('.domain').remove()).selectAll('text').attr('font-size','9px');

  svg.selectAll('.r-bar').data(recs).join('rect').attr('class','r-bar')
    .attr('x',0).attr('y', d=>y(`E${d.id}`))
    .attr('width', d=>x(d.score)).attr('height', y.bandwidth())
    .attr('fill', d=>CAT_COLORS[d.category]).attr('rx',2).attr('opacity',0.9).attr('cursor','pointer')
    .on('mouseover',(event,d) => {
      showTip(`<strong>Employer ${d.id}</strong><br>${d.category}<br>Score: <strong>${d.score.toFixed(3)}</strong><br>Rate: <strong>$${d.avg_rate}/hr</strong><br>Turnover: <strong>${(d.turnover_rate*100).toFixed(1)}%</strong>`, event);
    })
    .on('mouseout', () => tip.style('opacity',0))
    .on('click', (_,d) => selectEmployer(d.id));

  svg.selectAll('.r-val').data(recs).join('text').attr('class','r-val')
    .attr('x', d=>x(d.score)+3).attr('y', d=>y(`E${d.id}`)+y.bandwidth()/2)
    .attr('dy','0.35em').attr('font-size',8).attr('fill','#555').text(d=>d.score.toFixed(2));

  applySelection();
}

// ── SIZE & WAGE CHART ──────────────────────────────────────
(function initSizeChart() {
  const recs = [...DATA.employers].sort((a,b)=>b.job_count-a.job_count).slice(0,35);

  const rateColor = d3.scaleSequential(d3.interpolateYlOrRd)
    .domain([0, d3.max(DATA.employers, d=>d.avg_rate)]);

  const margin = {top:4, right:60, bottom:20, left:74};
  const W = 360 - margin.left - margin.right;
  const barH = 13, gap = 3;
  const H = recs.length * (barH + gap);

  const svg = d3.select('#size-svg')
    .attr('width',  W + margin.left + margin.right)
    .attr('height', H + margin.top  + margin.bottom)
    .append('g').attr('transform',`translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, d3.max(recs,d=>d.job_count)*1.05]).nice().range([0,W]);
  const y = d3.scaleBand().domain(recs.map(d=>`E${d.id}`)).range([0,H]).padding(0.15);

  svg.append('g').attr('transform',`translate(0,${H})`).attr('class','axis')
    .call(d3.axisBottom(x).ticks(5));
  svg.append('g').attr('class','axis').call(d3.axisLeft(y).tickSize(0))
    .call(g => g.select('.domain').remove()).selectAll('text').attr('font-size','9px');

  svg.selectAll('.sz-bar').data(recs).join('rect').attr('class','sz-bar')
    .attr('x',0).attr('y', d=>y(`E${d.id}`))
    .attr('width', d=>x(d.job_count)).attr('height', y.bandwidth())
    .attr('fill', d=>rateColor(d.avg_rate)).attr('rx',2).attr('opacity',0.85).attr('cursor','pointer')
    .on('mouseover',(event,d) => {
      showTip(`<strong>Employer ${d.id}</strong><br>Job listings: <strong>${d.job_count}</strong><br>Avg rate: <strong>$${d.avg_rate}/hr</strong><br>Score: <strong>${d.score.toFixed(3)}</strong>`, event);
    })
    .on('mouseout', () => tip.style('opacity',0))
    .on('click', (_,d) => selectEmployer(d.id));

  svg.selectAll('.sz-val').data(recs).join('text').attr('class','sz-val')
    .attr('x', d=>x(d.job_count)+3).attr('y', d=>y(`E${d.id}`)+y.bandwidth()/2)
    .attr('dy','0.35em').attr('font-size',8).attr('fill','#666').text(d=>`$${d.avg_rate}`);
})();

// ── ACTIVITY CHART ─────────────────────────────────────────
(function initActivity() {
  if (!DATA.months.length) {
    d3.select('#activity-svg').append('text').attr('x',20).attr('y',40)
      .attr('font-size',12).attr('fill','#aaa').text('No check-in data available.');
    return;
  }
  const parseM = d3.timeParse('%Y-%m');
  const fmtM   = d3.timeFormat('%b %Y');
  const months = DATA.months.map(parseM);

  const margin = {top:16, right:16, bottom:52, left:52};
  const W = 680 - margin.left - margin.right;
  const H = 280 - margin.top  - margin.bottom;

  const x = d3.scaleTime().domain(d3.extent(months)).range([0,W]);
  const maxAct = d3.max(DATA.employers, d => d3.max(d.activity) || 0) || 1;
  const y = d3.scaleLinear().domain([0, maxAct * 1.1]).nice().range([H, 0]);

  const actSvg = d3.select('#activity-svg')
    .attr('width',  W + margin.left + margin.right)
    .attr('height', H + margin.top  + margin.bottom)
    .append('g').attr('transform',`translate(${margin.left},${margin.top})`);

  actSvg.append('g').attr('class','axis').call(d3.axisLeft(y).ticks(4));
  actSvg.append('g').attr('class','axis').attr('transform',`translate(0,${H})`)
    .call(d3.axisBottom(x).ticks(d3.timeMonth.every(2)).tickFormat(fmtM))
    .selectAll('text').attr('transform','rotate(-30)').style('text-anchor','end');

  actSvg.append('text').attr('transform','rotate(-90)').attr('x',-H/2).attr('y',-38)
    .attr('text-anchor','middle').attr('font-size',10).attr('fill','#888').text('Workplace check-ins');

  const lineGen = d3.line().x((_,i)=>x(months[i])).y(v=>y(v)).defined(v=>v>=0);

  actSvg.selectAll('.act-line').data(DATA.employers).join('path')
    .attr('class','act-line').attr('fill','none')
    .attr('stroke','#bbb').attr('stroke-width',1).attr('opacity',0.5)
    .attr('d', d => lineGen(d.activity)).attr('cursor','pointer')
    .on('mouseover',(event,d) => {
      showTip(`<strong>Employer ${d.id}</strong><br>${d.category}<br>Peak: <strong>${d3.max(d.activity)}</strong> check-ins<br>Score: <strong>${d.score.toFixed(3)}</strong>`, event);
    })
    .on('mouseout', () => tip.style('opacity',0))
    .on('click', (_,d) => selectEmployer(d.id));
})();

// ── init ───────────────────────────────────────────────────
drawRanking();
updateDetailsBar();
</script>
</body>
</html>"""

    return page.replace("__DATA__", _json.dumps(data))


@app.route("/api/overall-view-page", methods=["GET"])
def overall_view_page():
    """Combined Overall View dashboard: KPIs + 4 linked charts in one page."""
    if not DB_PATH.exists():
        return jsonify({"error": f"Database not found: {DB_PATH}"}), 404

    conn = _get_db_connection()
    try:
        health_df = _compute_employer_health_scores(conn)

        fin_df = pd.read_sql_query(
            """
			SELECT strftime('%Y-%m', timestamp) AS month,
			       SUM(CASE WHEN category = 'Wage' THEN amount ELSE 0 END) AS wage,
			       SUM(CASE WHEN category IN ('Food','Shelter','Recreation','Education')
			                THEN ABS(amount) ELSE 0 END) AS cost_of_living
			FROM financialjournal
			GROUP BY month ORDER BY month
			""",
            conn,
        )

        net_df = pd.read_sql_query(
            """
			SELECT participantId,
			       SUM(CASE WHEN category='Wage' THEN amount ELSE 0 END) -
			       SUM(CASE WHEN category IN ('Food','Shelter','Recreation','Education')
			                THEN ABS(amount) ELSE 0 END) AS net_income
			FROM financialjournal GROUP BY participantId
			""",
            conn,
        )

        earners_row = pd.read_sql_query(
            "SELECT COUNT(DISTINCT participantId) AS n FROM financialjournal WHERE category='Wage'",
            conn,
        )

        emp_df = pd.read_sql_query("SELECT employerId, location FROM employers", conn)
        jobs_df = pd.read_sql_query(
            "SELECT employerId, COUNT(*) AS job_count, AVG(hourlyRate) AS avg_rate FROM jobs GROUP BY employerId",
            conn,
        )
        start_df, end_df = _get_job_transitions(conn)

        # ── Sector breakdown ───────────────────────────────────────────────
        sector_df = pd.read_sql_query(
            "SELECT educationRequirement as sector, AVG(hourlyRate) as avg_rate, COUNT(*) as job_count FROM jobs GROUP BY sector",
            conn,
        )
    finally:
        conn.close()

    # ── KPIs ──────────────────────────────────────────────────────────────
    total_wages = round(float(fin_df["wage"].sum()), 2) if not fin_df.empty else 0
    total_spending = (
        round(float(fin_df["cost_of_living"].sum()), 2) if not fin_df.empty else 0
    )
    median_net = (
        round(float(net_df["net_income"].median()), 2) if not net_df.empty else 0
    )
    active_emp = int(health_df["employerId"].nunique()) if not health_df.empty else 0
    avg_turnover = (
        round(float(health_df["turnover_rate"].mean()) * 100, 1)
        if not health_df.empty
        else 0
    )
    active_earners = int(earners_row["n"].iloc[0]) if not earners_row.empty else 0

    def _fmt(n):
        if abs(n) >= 1_000_000:
            return f"${n / 1_000_000:.1f}M"
        if abs(n) >= 1_000:
            return f"${n / 1_000:.0f}K"
        return f"${n:.0f}"

    kpis = {
        "total_wages": _fmt(total_wages),
        "total_spending": _fmt(total_spending),
        "median_net": _fmt(median_net),
        "turnover_rate": f"{avg_turnover}%",
        "active_employers": str(active_emp),
        "active_earners": str(active_earners),
    }

    # ── Line chart data ────────────────────────────────────────────────────
    if not fin_df.empty:
        fin_df["net_income"] = fin_df["wage"] - fin_df["cost_of_living"]
        line_data = {
            "months": fin_df["month"].tolist(),
            "series": [
                {
                    "name": "Wage",
                    "values": [round(v, 2) for v in fin_df["wage"].tolist()],
                    "color": "#2ca02c",
                },
                {
                    "name": "Cost of Living",
                    "values": [round(v, 2) for v in fin_df["cost_of_living"].tolist()],
                    "color": "#d62728",
                },
                {
                    "name": "Net Income",
                    "values": [round(v, 2) for v in fin_df["net_income"].tolist()],
                    "color": "#1f77b4",
                },
            ],
        }
    else:
        line_data = {"months": [], "series": []}

    # ── Employer data (scatter + ranking) ──────────────────────────────────
    def _cat(s):
        return "Prosperous" if s >= 0.6 else "Neutral" if s >= 0.35 else "Struggling"

    employers = []
    if not health_df.empty:
        employers = [
            {
                "id": int(row["employerId"]),
                "avg_rate": round(float(row["avg_rate"]), 2),
                "job_count": int(row["job_count"]),
                "stable": int(row["stable"]),
                "departed": int(row["departed"]),
                "arrived": int(row["arrived"]),
                "turnover_rate": round(float(row["turnover_rate"]), 3),
                "score": round(float(row["health_score"]), 3),
                "category": _cat(float(row["health_score"])),
            }
            for _, row in health_df.sort_values(
                "health_score", ascending=False
            ).iterrows()
        ]

    # ── Symbol map data ────────────────────────────────────────────────────
    health_by_id = {e["id"]: e for e in employers}
    emp_df = emp_df.merge(jobs_df, on="employerId", how="left").fillna(
        {"job_count": 1, "avg_rate": 0}
    )

    if not start_df.empty and not end_df.empty:
        all_emp = set(start_df["employerId"].dropna().astype(int)) | set(
            end_df["employerId"].dropna().astype(int)
        )
        turnover_map = {}
        for eid in all_emp:
            s = set(start_df[start_df["employerId"] == eid]["participantId"])
            e = set(end_df[end_df["employerId"] == eid]["participantId"])
            turnover_map[int(eid)] = len(s.symmetric_difference(e))
    else:
        turnover_map = {}

    symbols = []
    for _, row in emp_df.iterrows():
        px, py = _parse_wkt_point(str(row["location"]))
        if px is None:
            continue
        eid = int(row["employerId"])
        h = health_by_id.get(eid, {})
        symbols.append(
            {
                "id": eid,
                "x": px,
                "y": py,
                "job_count": int(row["job_count"]),
                "avg_rate": round(float(row["avg_rate"]), 2),
                "turnover": turnover_map.get(eid, 0),
                "score": h.get("score", 0.5),
                "category": h.get("category", "Neutral"),
            }
        )

    # ── Buildings for map background ───────────────────────────────────────
    buildings_path = Path(__file__).resolve().parent / "buildings.json"
    buildings = []
    if buildings_path.exists():
        import json as _jj

        raw = _jj.loads(buildings_path.read_text(encoding="utf-8"))
        buildings = [
            {"coords": b["coords"], "type": b.get("type", "")}
            for b in raw
            if b.get("coords")
        ]

    sector_data = sector_df.to_dict(orient="records") if not sector_df.empty else []

    data = {
        "kpis": kpis,
        "line": line_data,
        "employers": employers,
        "symbols": symbols,
        "buildings": buildings,
        "sectors": sector_data,
    }
    html = _render_overall_view_html(data)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def _render_overall_view_html(data: dict) -> str:
    import json as _json

    page = r"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Overall View</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#f4f5f7;color:#222;padding:16px}
.kpi-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:16px}
.kpi-card{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 5px rgba(0,0,0,.1)}
.kpi-label{font-size:11px;color:#777;margin-bottom:6px}
.kpi-value{font-size:18px;font-weight:bold}
.details-bar{background:#fff;border-radius:10px;padding:12px 16px;box-shadow:0 1px 5px rgba(0,0,0,.1);color:#aaa;
  margin-bottom:14px;min-height:64px;display:flex;align-items:center;justify-content:center;gap:20px;flex-wrap:wrap}
.detail-stat{display:flex;flex-direction:column;align-items:center;min-width:70px}
.detail-label{font-size:10px;color:#777;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:5px}
.detail-value{font-size:15px;font-weight:bold;color:#2f5d8c}
.detail-val-cat{padding:2px 8px;border-radius:12px;color:#fff;font-size:11px;font-weight:bold}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.chart-panel{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 5px rgba(0,0,0,.1)}
.chart-panel h3{font-size:14px;margin-bottom:3px}
.chart-note{font-size:11px;color:#777;margin-bottom:10px}
.info-icon{display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;
  background:#2f5d8c;color:#fff;border-radius:50%;font-size:9px;margin-left:6px;cursor:help;vertical-align:middle}
.ranking-wrap{overflow-y:auto;max-height:320px}
.tooltip { position: fixed; background: rgba(20, 20, 20, 0.92); color: #fff; padding: 8px 12px;
  border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0;
  transition: opacity 0.12s; line-height: 1.6; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
@media(max-width:800px){.kpi-grid{grid-template-columns:repeat(3,1fr)}.chart-grid{grid-template-columns:1fr}}
</style>
</head>
<body>

<div class="kpi-grid">
  <div class="kpi-card"><div class="kpi-label">Total Resident Wages</div><div class="kpi-value" id="kv-wages">—</div></div>
  <div class="kpi-card"><div class="kpi-label">Total Resident Spending</div><div class="kpi-value" id="kv-spending">—</div></div>
  <div class="kpi-card"><div class="kpi-label">Median Net Income</div><div class="kpi-value" id="kv-net">—</div></div>
  <div class="kpi-card"><div class="kpi-label">Avg Turnover Rate</div><div class="kpi-value" id="kv-turnover">—</div></div>
  <div class="kpi-card"><div class="kpi-label">Active Employers</div><div class="kpi-value" id="kv-employers">—</div></div>
  <div class="kpi-card"><div class="kpi-label">Active Wage Earners</div><div class="kpi-value" id="kv-earners">—</div></div>
</div>

<div class="details-bar" id="details-bar">Click any employer in the ranking, scatter, or map to see details here.</div>

<div class="chart-grid">
  <div class="chart-panel">
    <h3>Cost of Living Gap <span class="info-icon" onmouseover="showTip('<strong>Monthly city-wide totals</strong><br>Compares total wage income, cost of living expenses, and resulting net income.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-line"></div>
  </div>
  <div class="chart-panel">
    <h3>Employer Health Ranking <span class="info-icon" onmouseover="showTip('<strong>Employer prosperity ranking</strong><br>Sorted by derived health score.', event)" onmouseout="hideTip()">?</span></h3>
    <div class="ranking-wrap"><div id="ch-ranking"></div></div>
  </div>
  <div class="chart-panel">
    <h3>Business Prosperity / Stability <span class="info-icon" onmouseover="showTip('<strong>Wages vs Jobs</strong><br>X-axis: Avg hourly rate.<br>Y-axis: Job count.<br>Dot size: number of stable workers.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-scatter"></div>
  </div>
  <div class="chart-panel">
    <h3>Employer Map <span class="info-icon" onmouseover="showTip('<strong>Geographical distribution of employers.</strong><br>Position: building location.<br>Size: job count.<br>Color: prosperity health category.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-map"></div>
  </div>
</div>

<div class="chart-panel" style="margin-top:20px">
    <h3>Education Requirement & Wage Breakdown <span class="info-icon" onmouseover="showTip('<strong>Sector Demographics</strong><br>Compares average hourly wages and job availability by education requirement level.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-sectors" style="height:300px"></div>
</div>

</div>

<div class="tooltip" id="tip"></div>

<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
const DATA = __DATA__;
const K = DATA.kpis;
document.getElementById('kv-wages').textContent     = K.total_wages;
document.getElementById('kv-spending').textContent  = K.total_spending;
document.getElementById('kv-net').textContent       = K.median_net;
document.getElementById('kv-turnover').textContent  = K.turnover_rate;
document.getElementById('kv-employers').textContent = K.active_employers;
document.getElementById('kv-earners').textContent   = K.active_earners;

const CAT_COLOR = {Prosperous:'#2ca02c', Neutral:'#f59e0b', Struggling:'#d62728'};
const tip = d3.select('#tip');
let selectedId = null;
// Keep a persistent zoom behavior and transform for the employer map so
// redraws preserve the user's pan/zoom. `mapZoom` is the d3.zoom() behavior
// and `mapTransform` stores the last transform applied.
let mapZoom = null;
let mapTransform = d3.zoomIdentity;

function showTip(html, ev) {
  tip.html(html).style('opacity', 1)
     .style('left', (ev.clientX + 15) + 'px').style('top', (ev.clientY - 45) + 'px');
}
function hideTip(){ tip.style('opacity',0); }

function selectEmployer(id){
  selectedId = (selectedId === id) ? null : id;
  updateDetails();
  drawRanking();
  drawScatter();
  drawMap();
}

function updateDetails(){
  const bar = document.getElementById('details-bar');
  if(!selectedId){ 
    bar.style.justifyContent = 'center';
    bar.innerHTML = '<span style="color:#aaa;font-style:italic">Click any employer in the ranking, scatter, or map to see deep-dive metrics here.</span>'; 
    return; 
  }
  const e = DATA.employers.find(d=>d.id===selectedId);
  if(!e) return;
  
  bar.style.justifyContent = 'space-around';
  bar.innerHTML = `
    <div class="detail-stat">
      <span class="detail-label">Employer</span>
      <span class="detail-value">#${e.id}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Status</span>
      <span class="detail-val-cat" style="background:${CAT_COLOR[e.category]}">${e.category}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Health Score</span>
      <span class="detail-value">${e.score.toFixed(3)}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Jobs</span>
      <span class="detail-value">${e.job_count}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Avg Rate</span>
      <span class="detail-value">$${e.avg_rate}/hr</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Turnover</span>
      <span class="detail-value">${(e.turnover_rate*100).toFixed(1)}%</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Stable</span>
      <span class="detail-value">${e.stable}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Departed</span>
      <span class="detail-value" style="color:#d62728">${e.departed}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Arrived</span>
      <span class="detail-value" style="color:#2ca02c">${e.arrived}</span>
    </div>
  `;
}

// ── Line chart (standalone — no employer selection) ─────────────────────
(function drawLine(){
  const {months, series} = DATA.line;
  if(!months.length) return;
  const el = document.getElementById('ch-line');
  const W = el.clientWidth || 440, H = 270;
  const m = {top:10,right:70,bottom:38,left:56};
  const w = W-m.left-m.right, h = H-m.top-m.bottom;

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  const x = d3.scalePoint().domain(months).range([0,w]);
  const allV = series.flatMap(s=>s.values);
  const y = d3.scaleLinear().domain([d3.min(allV), d3.max(allV)]).nice().range([h,0]);

  g.append('g').attr('transform',`translate(0,${h})`)
    .call(d3.axisBottom(x).tickValues(months.filter((_,i)=>i%4===0)).tickSize(-h))
    .call(ax=>ax.selectAll('.tick line').attr('stroke','#eee'))
    .call(ax=>ax.select('.domain').remove())
    .selectAll('text').attr('transform','rotate(-30)').attr('text-anchor','end').attr('font-size',9);

  g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d=>'$'+d3.format('.2s')(d)));

  const line = d3.line().x((_,i)=>x(months[i])).y(d=>y(d)).curve(d3.curveMonotoneX);

  series.forEach(s=>{
    g.append('path').datum(s.values)
      .attr('fill','none').attr('stroke',s.color).attr('stroke-width',2).attr('d',line);
    const lx = x(months[months.length-1]);
    const ly = y(s.values[s.values.length-1]);
    g.append('text').attr('x',lx+4).attr('y',ly).attr('fill',s.color)
      .attr('font-size',9).attr('dominant-baseline','middle').text(s.name);
  });
})();

// ── Ranking (linked) ────────────────────────────────────────────────────
function drawRanking(){
  const el = document.getElementById('ch-ranking');
  d3.select(el).selectAll('*').remove();
  const emps = DATA.employers;
  const W = (el.clientWidth||440), barH = 16;
  const m = {top:4,right:50,bottom:20,left:60};
  const H = emps.length*barH+m.top+m.bottom;
  const w = W-m.left-m.right;

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  const x = d3.scaleLinear().domain([0,1]).range([0,w]);
  const y = d3.scaleBand().domain(emps.map(d=>d.id)).range([0,emps.length*barH]).padding(0.12);

  g.selectAll('rect').data(emps).join('rect')
    .attr('x',0).attr('y',d=>y(d.id))
    .attr('width',d=>x(d.score)).attr('height',y.bandwidth())
    .attr('fill',d=>CAT_COLOR[d.category])
    .attr('opacity',d=>!selectedId||selectedId===d.id ? 0.85 : 0.2)
    .attr('stroke',d=>selectedId===d.id?'#222':'none').attr('stroke-width',1.5)
    .style('cursor','pointer')
    .on('mouseover',(ev,d)=>showTip(`<strong>Employer ${d.id}</strong><br>${d.category}<br>Score: <strong>${d.score}</strong><br>Jobs: <strong>${d.job_count}</strong>`,ev))
    .on('mouseout',hideTip)
    .on('click',(_,d)=>selectEmployer(d.id));

  g.append('g').call(d3.axisLeft(y).tickFormat(d=>`Emp ${d}`).tickSize(0))
    .call(ax=>{ax.select('.domain').remove(); ax.selectAll('text').attr('font-size',9);});
  g.append('g').attr('transform',`translate(0,${emps.length*barH})`)
    .call(d3.axisBottom(x).ticks(4).tickFormat(d3.format('.2f')));
}

// ── Scatter (linked) ────────────────────────────────────────────────────
function drawScatter(){
  const el = document.getElementById('ch-scatter');
  d3.select(el).selectAll('*').remove();
  const emps = DATA.employers;
  const W = el.clientWidth||440, H = 480;
  const m = {top:14,right:16,bottom:40,left:48};
  const w = W-m.left-m.right, h = H-m.top-m.bottom;

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  const x = d3.scaleLinear().domain(d3.extent(emps,d=>d.avg_rate)).nice().range([0,w]);
  const y = d3.scaleLinear().domain(d3.extent(emps,d=>d.job_count)).nice().range([h,0]);
  const r = d3.scaleSqrt().domain([0,d3.max(emps,d=>d.stable)]).range([3,14]);

  g.append('g').attr('transform',`translate(0,${h})`)
    .call(d3.axisBottom(x).ticks(5).tickFormat(d=>'$'+d));
  g.append('g').call(d3.axisLeft(y).ticks(5));

  g.append('text').attr('x',w/2).attr('y',h+34).attr('text-anchor','middle')
    .attr('font-size',11).text('Avg Hourly Rate ($)');
  g.append('text').attr('transform','rotate(-90)').attr('x',-h/2).attr('y',-36)
    .attr('text-anchor','middle').attr('font-size',11).text('Job Count');

  g.selectAll('circle').data(emps).join('circle')
    .attr('cx',d=>x(d.avg_rate)).attr('cy',d=>y(d.job_count)).attr('r',d=>r(d.stable))
    .attr('fill',d=>CAT_COLOR[d.category])
    .attr('opacity',d=>!selectedId||selectedId===d.id ? 0.78 : 0.12)
    .attr('stroke',d=>selectedId===d.id?'#222':'#fff')
    .attr('stroke-width',d=>selectedId===d.id?2:0.5)
    .style('cursor','pointer')
    .on('mouseover',(ev,d)=>showTip(`<strong>Employer ${d.id}</strong><br>${d.category}<br>Rate: <strong>$${d.avg_rate}/hr</strong><br>Jobs: <strong>${d.job_count}</strong><br>Stable: <strong>${d.stable}</strong>`,ev))
    .on('mouseout',hideTip)
    .on('click',(_,d)=>selectEmployer(d.id));
}

// ── Symbol map (linked) ─────────────────────────────────────────────────
function drawMap(){
	const el = document.getElementById('ch-map');
	d3.select(el).selectAll('*').remove();
	const syms = DATA.symbols, blds = DATA.buildings;
	const W = el.clientWidth||440, H = 480;

	const TYPE_COLOR = {Commercial:'#0f0f0f', Residental:'#0f0f0f', School:'#0f0f0f'};

	const allX = [...blds.flatMap(b=>b.coords.map(c=>c[0])), ...syms.map(s=>s.x)];
	const allY = [...blds.flatMap(b=>b.coords.map(c=>c[1])), ...syms.map(s=>s.y)];
	const x = d3.scaleLinear().domain(d3.extent(allX)).range([8,W-8]);
	const y = d3.scaleLinear().domain(d3.extent(allY)).range([H-8,8]);
	// rPx maps job_count -> desired on-screen pixel radius (when zoom k===1)
	const rPx = d3.scaleSqrt().domain([0,d3.max(syms,s=>s.job_count)]).range([3,12]);

	const svg = d3.select(el).append('svg').attr('width',W).attr('height',H)
		.style('border','1px solid #e5e7eb').style('border-radius','6px');

	// container group that will be transformed by zoom/pan
	const container = svg.append('g').attr('class','map-container');

	// buildings layer (inside container so it pans/zooms)
	container.append('g').selectAll('path').data(blds).join('path')
		.attr('d',b=>b.coords.map((c,i)=>(i?'L':'M')+x(c[0])+','+y(c[1])).join('')+'Z')
		.attr('fill',b=>TYPE_COLOR[b.type]||'#aaa').attr('opacity',0.2)
		.attr('stroke','#ccc').attr('stroke-width',0.3);

	// symbols layer
	const symbols = container.append('g').attr('class','symbols');

	symbols.selectAll('circle').data(syms).join('circle')
		.attr('class','sym')
		.attr('cx',d=>x(d.x)).attr('cy',d=>y(d.y))
		// initial r for k === 1
		.attr('r',d=>rPx(d.job_count))
		.attr('fill',d=>CAT_COLOR[d.category])
		.attr('opacity',d=>!selectedId||selectedId===d.id ? 0.85 : 0.18)
		.attr('stroke',d=>selectedId===d.id?'#222':'#fff')
		.attr('stroke-width',d=>selectedId===d.id?2:0.5)
		.style('cursor','pointer')
		.on('mouseover',(ev,d)=>showTip(`<strong>Employer ${d.id}</strong><br>${d.category}<br>Jobs: <strong>${d.job_count}</strong><br>Rate: <strong>$${d.avg_rate}/hr</strong>`,ev))
		.on('mouseout',hideTip)
		.on('click',(_,d)=>selectEmployer(d.id));

	// Setup zoom behavior for this map. We keep the zoom instance and last
	// transform in outer-scope variables so redraws preserve the view.
	mapZoom = d3.zoom()
		.scaleExtent([0.5, 8])
		.on('zoom', (event) => {
			const t = event.transform;
			container.attr('transform', t);
			mapTransform = t;
			const k = t.k || 1;
			// adjust symbol radii and stroke widths to keep on-screen size constant
			symbols.selectAll('circle.sym')
				.attr('r', d => Math.max(1, rPx(d.job_count) / k))
				.attr('stroke-width', d => (selectedId===d.id ? 2 : 0.5) / Math.max(k, 0.0001));
			// thin building strokes visually as user zooms out/in
			container.selectAll('path').attr('stroke-width', 0.3 / Math.max(k, 0.0001));
		});

	svg.call(mapZoom);
	// restore previous transform if any
	if(mapTransform && mapTransform.k && mapTransform.k !== 1){
		svg.call(mapZoom.transform, mapTransform);
		// also trigger a manual update of radii based on that transform
		const k0 = mapTransform.k || 1;
		symbols.selectAll('circle.sym')
			.attr('r', d => Math.max(1, rPx(d.job_count) / k0))
			.attr('stroke-width', d => (selectedId===d.id ? 2 : 0.5) / Math.max(k0, 0.0001));
		container.selectAll('path').attr('stroke-width', 0.3 / Math.max(k0, 0.0001));
	}
}

// ── Sector Chart ────────────────────────────────────────────────────────
(function drawSectors(){
    const data = DATA.sectors;
    if(!data || !data.length) return;
    const el = document.getElementById('ch-sectors');
    const W = el.clientWidth, H = 300;
    const m = {top:20, right:60, bottom:40, left:60};
    const w = W - m.left - m.right, h = H - m.top - m.bottom;

    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);

    const x = d3.scaleBand().domain(data.map(d=>d.sector)).range([0, w]).padding(0.3);
    const yL = d3.scaleLinear().domain([0, d3.max(data, d=>d.avg_rate)*1.1]).nice().range([h, 0]);
    const yR = d3.scaleLinear().domain([0, d3.max(data, d=>d.job_count)*1.1]).nice().range([h, 0]);

    g.append('g').attr('transform', `translate(0, ${h})`).call(d3.axisBottom(x));
    g.append('g').call(d3.axisLeft(yL).ticks(5).tickFormat(d=>'$'+d));
    g.append('g').attr('transform', `translate(${w}, 0)`).call(d3.axisRight(yR).ticks(5));

    // Bars for job count
    g.selectAll('.bar-jobs').data(data).enter().append('rect')
     .attr('x', d => x(d.sector))
     .attr('y', d => yR(d.job_count))
     .attr('width', x.bandwidth() / 2)
     .attr('height', d => h - yR(d.job_count))
     .attr('fill', '#1f77b4').attr('opacity', 0.6)
     .on('mouseover', (ev, d) => showTip(`<strong>${d.sector}</strong><br>Total Jobs: <strong>${d.job_count.toLocaleString()}</strong>`, ev))
     .on('mouseout', hideTip);

    // Bars for avg wage
    g.selectAll('.bar-wage').data(data).enter().append('rect')
     .attr('x', d => x(d.sector) + x.bandwidth() / 2)
     .attr('y', d => yL(d.avg_rate))
     .attr('width', x.bandwidth() / 2)
     .attr('height', d => h - yL(d.avg_rate))
     .attr('fill', '#2ca02c').attr('opacity', 0.6)
     .on('mouseover', (ev, d) => showTip(`<strong>${d.sector}</strong><br>Avg Hourly Rate: <strong>$${d.avg_rate.toFixed(2)}/hr</strong>`, ev))
     .on('mouseout', hideTip);

    // Legend
    const leg = svg.append('g').attr('transform', `translate(${W-150}, 5)`);
    [['#1f77b4', 'Job Count'], ['#2ca02c', 'Avg Wage']].forEach(([c, n], i) => {
        const li = leg.append('g').attr('transform', `translate(0, ${i*15})`);
        li.append('rect').attr('width', 10).attr('height', 10).attr('fill', c);
        li.append('text').attr('x', 14).attr('y', 9).attr('font-size', 10).text(n);
    });
})();

drawRanking();
drawScatter();
drawMap();
</script>
</body></html>"""

    return page.replace("__DATA__", _json.dumps(data))


@app.route("/api/resident-financial-page", methods=["GET"])
def resident_financial_page():
    """Combined Resident Financial Health dashboard: 5 charts in one page."""
    if not DB_PATH.exists():
        return jsonify({"error": f"Database not found: {DB_PATH}"}), 404

    conn = _get_db_connection()
    try:
        cat_df = pd.read_sql_query(
            """SELECT strftime('%Y-%m', timestamp) AS month, category,
			          SUM(amount) AS total_amount
			   FROM financialjournal
			   GROUP BY month, category ORDER BY month, category""",
            conn,
        )
        wc_df = pd.read_sql_query(
            """SELECT strftime('%Y-%m', timestamp) AS month,
			          SUM(CASE WHEN category='Wage' THEN amount ELSE 0 END) AS wage,
			          SUM(CASE WHEN category IN ('Food','Shelter','Recreation','Education')
			                   THEN ABS(amount) ELSE 0 END) AS cost_of_living
			   FROM financialjournal GROUP BY month ORDER BY month""",
            conn,
        )
        ni_df = pd.read_sql_query(
            """SELECT participantId,
			          SUM(CASE WHEN category='Wage' THEN amount ELSE 0 END) AS total_wage,
			          SUM(CASE WHEN category IN ('Food','Shelter','Recreation','Education')
			                   THEN ABS(amount) ELSE 0 END) AS total_expenses,
			          SUM(amount) AS net_income
			   FROM financialjournal GROUP BY participantId""",
            conn,
        )
        p_df = pd.read_sql_query(
            "SELECT participantId, educationLevel, age, joviality, householdSize, interestGroup FROM participants",
            conn,
        )
    finally:
        conn.close()

    # ── Financial categories line ──────────────────────────────────────────
    if not cat_df.empty:
        months_cat = sorted(cat_df["month"].dropna().unique().tolist())
        cats = sorted(cat_df["category"].dropna().unique().tolist())
        pivot = (
            cat_df.pivot(index="month", columns="category", values="total_amount")
            .reindex(months_cat)
            .fillna(0)
        )
        cat_data = {
            "months": months_cat,
            "series": [
                {"name": c, "values": [round(float(v), 2) for v in pivot[c].tolist()]}
                for c in cats
                if c in pivot.columns
            ],
        }
    else:
        cat_data = {"months": [], "series": []}

    # ── Wages vs cost line ─────────────────────────────────────────────────
    if not wc_df.empty:
        wc_df["net_income"] = wc_df["wage"] - wc_df["cost_of_living"]
        wc_data = {
            "months": wc_df["month"].tolist(),
            "series": [
                {
                    "name": "Wage",
                    "values": [round(v, 2) for v in wc_df["wage"].tolist()],
                    "color": "#2ca02c",
                },
                {
                    "name": "Cost of Living",
                    "values": [round(v, 2) for v in wc_df["cost_of_living"].tolist()],
                    "color": "#d62728",
                },
                {
                    "name": "Net Income",
                    "values": [round(v, 2) for v in wc_df["net_income"].tolist()],
                    "color": "#1f77b4",
                },
            ],
        }
    else:
        wc_data = {"months": [], "series": []}

    # ── Per-participant net income ─────────────────────────────────────────
    ni_records = (
        [
            {
                "id": int(r["participantId"]),
                "net": round(float(r["net_income"]), 2),
                "wage": round(float(r["total_wage"]), 2),
                "exp": round(float(r["total_expenses"]), 2),
            }
            for _, r in ni_df.iterrows()
        ]
        if not ni_df.empty
        else []
    )

    # ── Group comparison + parallel coords ────────────────────────────────
    group_data = {"groups": [], "series": []}
    pc_data = {"records": [], "axes": [], "axis_labels": {}}

    if not p_df.empty and not ni_df.empty:
        p_df["participantId"] = pd.to_numeric(p_df["participantId"], errors="coerce")
        ni_df["participantId"] = pd.to_numeric(ni_df["participantId"], errors="coerce")
        merged = p_df.merge(ni_df, on="participantId", how="inner")

        ORDER = {"Low": 0, "HighSchoolOrCollege": 1, "Bachelors": 2, "Graduate": 3}
        grp = (
            merged.groupby("educationLevel")
            .agg(
                avg_wage=("total_wage", "mean"),
                avg_exp=("total_expenses", "mean"),
                avg_net=("net_income", "mean"),
            )
            .reset_index()
        )
        grp["_k"] = grp["educationLevel"].map(ORDER).fillna(99)
        grp = grp.sort_values("_k")

        group_data = {
            "groups": grp["educationLevel"].tolist(),
            "series": [
                {
                    "name": "Total Wage",
                    "values": [round(float(v), 0) for v in grp["avg_wage"].tolist()],
                    "color": "#2ca02c",
                },
                {
                    "name": "Total Expenses",
                    "values": [round(float(v), 0) for v in grp["avg_exp"].tolist()],
                    "color": "#d62728",
                },
                {
                    "name": "Net Income",
                    "values": [round(float(v), 0) for v in grp["avg_net"].tolist()],
                    "color": "#1f77b4",
                },
            ],
        }

        axes = [
            "total_wage",
            "total_expenses",
            "net_income",
            "joviality",
            "age",
            "householdSize",
        ]
        pc_data = {
            "records": [
                {
                    "edu": r["educationLevel"],
                    "ig": r["interestGroup"],
                    **{k: round(float(r[k]), 2) for k in axes if pd.notna(r[k])},
                }
                for _, r in merged.iterrows()
                if all(pd.notna(r[k]) for k in axes)
            ],
            "axes": axes,
            "axis_labels": {
                "total_wage": "Total Wage ($)",
                "total_expenses": "Total Expenses ($)",
                "net_income": "Net Income ($)",
                "joviality": "Joviality",
                "age": "Age",
                "householdSize": "Household Size",
            },
        }

    data = {
        "categories": cat_data,
        "wages_cost": wc_data,
        "net_income": ni_records,
        "groups": group_data,
        "parallel": pc_data,
    }
    html = _render_resident_financial_html(data)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/employer_summary", methods=["GET"])
def api_employer_summary():
    """Return precomputed employer summary JSON (if present).

    This serves `backend/employer_health_summary.json` for the frontend to
    enrich employer sidecards without requiring the full embedded HTML.
    """
    try:
        import json
        from pathlib import Path

        summary_path = Path(__file__).resolve().parent / "employer_health_summary.json"
        if not summary_path.exists():
            return jsonify({"error": "summary not available"}), 404
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/employers", methods=["GET"])
def api_employers():
    """Return a lightweight list of employers for the frontend.

    Prefer the precomputed `employer_health_summary.json` when present; if not,
    query the database for basic fields (employerId, job count, avg rate).
    """
    try:
        import json
        from pathlib import Path

        summary_path = Path(__file__).resolve().parent / "employer_health_summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            out = []
            for e in raw:
                eid = e.get("employerId")
                out.append(
                    {
                        "id": eid,
                        "employerId": eid,
                        "name": e.get("name") or f"Employer {eid}",
                        "job_count": e.get("JobCount") or e.get("JobCount", 0),
                        "avg_rate": e.get("AverageHourlyRate") or e.get("avg_rate"),
                        "sector": e.get("Sector") or e.get("sector"),
                    }
                )
            return jsonify(out)

        # fallback to DB
        conn = _get_db_connection()
        try:
            rows = conn.execute(
                "SELECT e.employerId AS employerId, COUNT(j.rowid) AS job_count, AVG(j.hourlyRate) AS avg_rate "
                "FROM employers e LEFT JOIN jobs j ON e.employerId = j.employerId "
                "GROUP BY e.employerId"
            ).fetchall()
            out = []
            for r in rows:
                eid = int(r["employerId"])
                out.append(
                    {
                        "id": eid,
                        "employerId": eid,
                        "name": f"Employer {eid}",
                        "job_count": int(r["job_count"])
                        if r["job_count"] is not None
                        else 0,
                        "avg_rate": float(r["avg_rate"])
                        if r["avg_rate"] is not None
                        else None,
                    }
                )
            return jsonify(out)
        finally:
            conn.close()

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _render_resident_financial_html(data: dict) -> str:
    import json as _json

    page = r"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Resident Financial Health</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#f4f5f7;color:#222;padding:16px}
.info-box { background: #fff; border-radius: 10px; padding: 12px 16px; box-shadow: 0 1px 5px rgba(0,0,0,.1);color:#aaa;
  margin-bottom: 14px; min-height: 64px; display: flex; align-items: center; justify-content: center; gap: 20px; flex-wrap: wrap; }
.detail-stat { display: flex; flex-direction: column; align-items: center; min-width: 80px; }
.detail-label { font-size: 10px; color: #777; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
.detail-value { font-size: 15px; font-weight: bold; color: #2f5d8c; }
.detail-val-edu { padding: 2px 10px; border-radius: 12px; color: #fff; font-size: 11px; font-weight: bold; }
.deselect-btn { font-size: 12px; padding: 4px 8px; cursor: pointer; border: 1px solid #ddd; border-radius: 4px; background: #fff; margin-left: 10px; }
.deselect-btn:hover { background: #f5f5f5; }
.info-icon{display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;
  background:#2f5d8c;color:#fff;border-radius:50%;font-size:9px;margin-left:6px;cursor:help;vertical-align:middle}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.chart-panel{background:#fff;border-radius:10px;padding:14px;
  box-shadow:0 1px 5px rgba(0,0,0,.1)}
.chart-panel.full{background:#fff;border-radius:10px;padding:14px;
  box-shadow:0 1px 5px rgba(0,0,0,.1);margin-bottom:14px}
.chart-panel h3{font-size:14px;margin-bottom:3px}
.chart-note{font-size:11px;color:#777;margin-bottom:10px}
.legend{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:8px;font-size:11px}
.leg-item{display:flex;align-items:center;gap:4px;cursor:pointer}
.leg-dot{width:10px;height:10px;border-radius:50%}
.tooltip { position: fixed; background: rgba(20, 20, 20, 0.92); color: #fff; padding: 8px 12px;
  border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0;
  transition: opacity 0.12s; line-height: 1.6; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
@media(max-width:800px){.chart-grid{grid-template-columns:1fr}}
</style>
</head>
<body>

<div class="info-box" id="info-box">
  Click an education level in the <strong>Net Income by Group</strong> chart to highlight
  matching participants in the <strong>Resident Financial Profiles</strong> below.
</div>

<div class="chart-grid">
  <div class="chart-panel">
    <h3>Financial Categories <span class="info-icon" onmouseover="showTip('<strong>Expense trends</strong><br>Monthly totals by category from FinancialJournal.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-cats"></div>
  </div>
  <div class="chart-panel">
    <h3>Wages vs Cost of Living <span class="info-icon" onmouseover="showTip('<strong>Income vs Spending</strong><br>Monthly wage income, living costs, and net income.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-wc"></div>
  </div>
  <div class="chart-panel">
    <h3>Net Income <span class="info-icon" onmouseover="showTip('<strong>Study period totals</strong><br>Histogram of per-participant net income over the study period.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-hist"></div>
  </div>
  <div class="chart-panel">
    <h3>Net Income by Education Group <span class="info-icon" onmouseover="showTip('<strong>Educational demographics</strong><br>Avg wage, expenses, net income per education level. <br>Click a group to highlight in parallel coords.', event)" onmouseout="hideTip()">?</span></h3>
    <div id="ch-groups"></div>
  </div>
</div>

<div class="chart-panel full">
  <h3>Resident Financial Profiles <span class="info-icon" onmouseover="showTip('<strong>Participant deep-dive</strong><br>Each line = one participant. <br>Color = education level.<br> Click a group above to highlight.', event)" onmouseout="hideTip()">?</span></h3>
  <div class="legend" id="pc-legend"></div>
  <div id="ch-pc"></div>
</div>

<div class="tooltip" id="tip"></div>

<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
const DATA = __DATA__;
const tip  = d3.select('#tip');
let selectedGroup = null;

const EDU_COLOR = {
  'Low':                 '#e41a1c',
  'HighSchoolOrCollege': '#ff7f00',
  'Bachelors':           '#4daf4a',
  'Graduate':            '#377eb8',
};
const CAT_COLORS = d3.schemeTableau10;

function showTip(html, ev) {
  tip.html(html).style('opacity', 1)
     .style('left', (ev.clientX + 15) + 'px').style('top', (ev.clientY - 45) + 'px');
}
function hideTip(){ tip.style('opacity',0); }

// ── helpers ─────────────────────────────────────────────────────────────
function drawLineChart(elId, months, series, tickStep){
  const el = document.getElementById(elId);
  const W = el.clientWidth||440, H = 260;
  const m = {top:10,right:80,bottom:38,left:58};
  const w = W-m.left-m.right, h = H-m.top-m.bottom;

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g   = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  const x  = d3.scalePoint().domain(months).range([0,w]);
  const allV = series.flatMap(s=>s.values);
  const y  = d3.scaleLinear().domain([d3.min(allV),d3.max(allV)]).nice().range([h,0]);
  const ln = d3.line().x((_,i)=>x(months[i])).y(d=>y(d)).curve(d3.curveMonotoneX);

  g.append('g').attr('transform',`translate(0,${h})`)
    .call(d3.axisBottom(x).tickValues(months.filter((_,i)=>i%(tickStep||4)===0)).tickSize(-h))
    .call(ax=>{ax.selectAll('.tick line').attr('stroke','#eee'); ax.select('.domain').remove();})
    .selectAll('text').attr('transform','rotate(-30)').attr('text-anchor','end').attr('font-size',9);
  g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d=>'$'+d3.format('.2s')(d)));

  series.forEach((s,i)=>{
    const col = s.color || CAT_COLORS[i % CAT_COLORS.length];
    g.append('path').datum(s.values).attr('fill','none')
      .attr('stroke',col).attr('stroke-width',1.8).attr('d',ln);
    const lx = x(months[months.length-1]);
    const ly = y(s.values[s.values.length-1]);
    g.append('text').attr('x',lx+4).attr('y',ly).attr('fill',col)
      .attr('font-size',9).attr('dominant-baseline','middle').text(s.name);
  });
}

// ── Financial categories line ────────────────────────────────────────────
(function(){
  const {months, series} = DATA.categories;
  if(months.length) drawLineChart('ch-cats', months, series, 4);
})();

// ── Wages vs cost line ───────────────────────────────────────────────────
(function(){
  const {months, series} = DATA.wages_cost;
  if(months.length) drawLineChart('ch-wc', months, series, 4);
})();

// ── Net income histogram ─────────────────────────────────────────────────
(function(){
  const records = DATA.net_income;
  if(!records.length) return;
  const el = document.getElementById('ch-hist');
  const W = el.clientWidth||440, H = 260;
  const m = {top:14,right:16,bottom:38,left:52};
  const w = W-m.left-m.right, h = H-m.top-m.bottom;

  const vals = records.map(d=>d.net);
  const x = d3.scaleLinear().domain(d3.extent(vals)).nice().range([0,w]);
  const bins = d3.bin().domain(x.domain()).thresholds(30)(vals);
  const y = d3.scaleLinear().domain([0,d3.max(bins,b=>b.length)]).nice().range([h,0]);
  const med = d3.median(vals);

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g   = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  g.selectAll('rect').data(bins).join('rect')
    .attr('x',b=>x(b.x0)+1).attr('width',b=>Math.max(0,x(b.x1)-x(b.x0)-1))
    .attr('y',b=>y(b.length)).attr('height',b=>h-y(b.length))
    .attr('fill','#1f77b4').attr('opacity',0.75)
    .on('mouseover',(ev,b)=>showTip(`Range: $${b.x0.toFixed(0)} – $${b.x1.toFixed(0)}<br>Count: ${b.length}`,ev))
    .on('mouseout',hideTip);

  g.append('line').attr('x1',x(med)).attr('x2',x(med)).attr('y1',0).attr('y2',h)
    .attr('stroke','#d62728').attr('stroke-width',1.5).attr('stroke-dasharray','4,3');
  g.append('text').attr('x',x(med)+4).attr('y',10).attr('fill','#d62728')
    .attr('font-size',10).text('median');

  g.append('g').attr('transform',`translate(0,${h})`)
    .call(d3.axisBottom(x).ticks(6).tickFormat(d=>'$'+d3.format('.2s')(d)));
  g.append('g').call(d3.axisLeft(y).ticks(5));
  g.append('text').attr('x',w/2).attr('y',h+34).attr('text-anchor','middle')
    .attr('font-size',11).text('Net Income ($)');
})();

// ── Group comparison bars (linked) ───────────────────────────────────────
function drawGroups(){
  const el = document.getElementById('ch-groups');
  d3.select(el).selectAll('*').remove();
  const {groups, series} = DATA.groups;
  if(!groups.length) return;

  const W = el.clientWidth||440, H = 260;
  const m = {top:10,right:10,bottom:60,left:62};
  const w = W-m.left-m.right, h = H-m.top-m.bottom;

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g   = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  const x0  = d3.scaleBand().domain(groups).range([0,w]).padding(0.2);
  const x1  = d3.scaleBand().domain(series.map(s=>s.name)).range([0,x0.bandwidth()]).padding(0.05);
  const allV = series.flatMap(s=>s.values);
  const y   = d3.scaleLinear().domain([0,d3.max(allV)]).nice().range([h,0]);

  series.forEach(s=>{
    g.selectAll(null).data(groups).join('rect')
      .attr('x',grp=>x0(grp)+x1(s.name))
      .attr('y',(_,i)=>y(s.values[i]))
      .attr('width',x1.bandwidth())
      .attr('height',(_,i)=>h-y(s.values[i]))
      .attr('fill',s.color)
      .attr('opacity',(_,i)=>!selectedGroup||selectedGroup===groups[i]?0.85:0.25)
      .style('cursor','pointer')
      .on('mouseover',(ev,grp,j)=>{
        const i=groups.indexOf(grp);
        showTip(`<strong>${grp}</strong><br>${s.name}: <strong>$${s.values[i].toLocaleString()}</strong>`,ev);
      })
      .on('mouseout',hideTip)
      .on('click',(_,grp)=>{
        selectedGroup = (selectedGroup===grp)?null:grp;
        updateGroupSelection();
      });
  });

  g.append('g').attr('transform',`translate(0,${h})`)
    .call(d3.axisBottom(x0))
    .selectAll('text').attr('transform','rotate(-20)').attr('text-anchor','end').attr('font-size',10)
    .style('cursor','pointer').on('click',(_,grp)=>{
      selectedGroup=(selectedGroup===grp)?null:grp;
      updateGroupSelection();
    });
  g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d=>'$'+d3.format('.2s')(d)));

  // legend
  const legEl = document.createElement('div');
  legEl.style.cssText='display:flex;gap:12px;font-size:11px;margin-bottom:6px;flex-wrap:wrap';
  series.forEach(s=>{
    const item = document.createElement('span');
    item.style.cssText='display:flex;align-items:center;gap:4px';
    item.innerHTML=`<span style="width:10px;height:10px;border-radius:50%;background:${s.color};display:inline-block"></span>${s.name}`;
    legEl.appendChild(item);
  });
  el.insertBefore(legEl, el.firstChild);
}

function updateGroupSelection(){
  const box = document.getElementById('info-box');
  if(!selectedGroup){
    box.style.justifyContent = 'center';
    box.innerHTML = '<span style="color:#aaa;font-style:italic">Click an education level in the <strong>Net Income by Group</strong> chart to deep-dive into demographic stats.</span>';
    drawGroups();
    drawParallelCoords();
    return;
  }
  
  const gIdx = DATA.groups.groups.indexOf(selectedGroup);
  const wage = DATA.groups.series[0].values[gIdx];
  const col  = DATA.groups.series[1].values[gIdx];
  const net  = DATA.groups.series[2].values[gIdx];
  
  box.style.justifyContent = 'space-around';
  box.innerHTML = `
    <div class="detail-stat">
      <span class="detail-label">Education Group</span>
      <span class="detail-val-edu" style="background:${EDU_COLOR[selectedGroup]}">${selectedGroup}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Avg Wage</span>
      <span class="detail-value" style="color:#2ca02c">$${wage.toLocaleString()}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Avg Expenses</span>
      <span class="detail-value" style="color:#d62728">$${col.toLocaleString()}</span>
    </div>
    <div class="detail-stat">
      <span class="detail-label">Avg Net Income</span>
      <span class="detail-value" style="color:#1f77b4">$${net.toLocaleString()}</span>
    </div>
    <div class="detail-stat" style="min-width:auto">
      <button class="deselect-btn" onclick="selectedGroup=null;updateGroupSelection()">&#10005;</button>
    </div>
  `;
  
  drawGroups();
  drawParallelCoords();
}

// ── Parallel coordinates (linked) ────────────────────────────────────────
function drawParallelCoords(){
  const el = document.getElementById('ch-pc');
  d3.select(el).selectAll('*').remove();
  const {records, axes, axis_labels} = DATA.parallel;
  if(!records.length) return;

  const W = el.clientWidth||860, H = 380;
  const m = {top:30,right:20,bottom:10,left:20};
  const w = W-m.left-m.right, h = H-m.top-m.bottom;

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g   = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  const x = d3.scalePoint().domain(axes).range([0,w]);
  const y = {};
  axes.forEach(ax=>{
    y[ax] = d3.scaleLinear().domain(d3.extent(records,d=>d[ax])).nice().range([h,0]);
  });

  function makePath(d){
    return d3.line()(axes.map(ax=>[x(ax), y[ax](d[ax])]));
  }

  // Draw lines
  g.selectAll('path.rec').data(records).join('path')
    .attr('class','rec')
    .attr('d',makePath)
    .attr('fill','none')
    .attr('stroke',d=>EDU_COLOR[d.edu]||'#999')
    .attr('stroke-width',0.7)
    .attr('opacity',d=>!selectedGroup||selectedGroup===d.edu?0.35:0.04)
    .on('mouseover',(ev,d)=>showTip(
      `<strong>Edu: ${d.edu}</strong><br>Wage: <strong>$${d.total_wage?.toLocaleString()}</strong><br>`+
      `Expenses: <strong>$${d.total_expenses?.toLocaleString()}</strong><br>Net: <strong>$${d.net_income?.toLocaleString()}</strong><br>`+
      `Age: <strong>${d.age}</strong> | Joviality: <strong>${d.joviality.toFixed(2)}</strong>`,ev))
    .on('mouseout',hideTip);

  // Axes
  axes.forEach(ax=>{
    const axG = g.append('g').attr('transform',`translate(${x(ax)},0)`);
    axG.call(d3.axisLeft(y[ax]).ticks(5));
    axG.append('text').attr('y',-14).attr('text-anchor','middle')
      .attr('fill','#333').attr('font-size',11).attr('font-weight','bold')
      .text(axis_labels[ax]||ax);
  });
}

// ── Parallel coords legend ───────────────────────────────────────────────
(function buildLegend(){
  const legEl = document.getElementById('pc-legend');
  Object.entries(EDU_COLOR).forEach(([edu, col])=>{
    const item = document.createElement('span');
    item.className='leg-item';
    item.style.cssText='display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px';
    item.innerHTML=`<span class="leg-dot" style="background:${col};width:10px;height:10px;border-radius:50%;display:inline-block"></span>${edu}`;
    item.addEventListener('click',()=>{
      selectedGroup=(selectedGroup===edu)?null:edu;
      updateGroupSelection();
    });
    legEl.appendChild(item);
  });
})();

// initial draw
drawGroups();
drawParallelCoords();
</script>
</body></html>"""

    return page.replace("__DATA__", _json.dumps(data))


@app.route("/api/employment-page", methods=["GET"])
def employment_page():
    """Combined Employment dashboard: Workforce participation, shifts, happiness, and hourly activity."""
    if not DB_PATH.exists():
        return jsonify({"error": f"Database not found: {DB_PATH}"}), 404

    conn = _get_db_connection()
    try:
        # 1. Workforce participation
        wf_df = pd.read_sql_query(
            """SELECT strftime('%Y-%m', timestamp) AS month,
                      COUNT(DISTINCT participantId) AS active_workers,
                      SUM(amount)/COUNT(DISTINCT participantId) AS avg_wage
               FROM financialjournal WHERE category='Wage'
               GROUP BY month ORDER BY month""",
            conn,
        )

        # 2. Shift starts (Jobs)
        shift_df = pd.read_sql_query(
            "SELECT startTime, COUNT(*) as count FROM jobs GROUP BY startTime ORDER BY startTime",
            conn,
        )

        # 3. Wage vs Joviality
        happiness_df = pd.read_sql_query(
            """SELECT p.joviality, SUM(f.amount)/12 as avg_wage
               FROM participants p
               JOIN financialjournal f ON p.participantId = f.participantId
               WHERE f.category = 'Wage'
               GROUP BY p.participantId LIMIT 2000""",
            conn,
        )

        # 4. Hourly Workplace Activity
        hourly_df = pd.read_sql_query(
            """SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
               FROM checkinjournal
               WHERE venueType = 'Workplace'
               GROUP BY hour ORDER BY hour""",
            conn,
        )
    finally:
        conn.close()

    # Build workforce data
    wf_data = {"months": wf_df["month"].tolist(), "series": [
        {"name": "Active Workers", "values": wf_df["active_workers"].tolist(), "color": "#2ca02c"},
        {"name": "Avg Monthly Wage", "values": [round(v, 2) for v in wf_df["avg_wage"].tolist()], "color": "#ff7f0e"}
    ]} if not wf_df.empty else {"months": [], "series": []}

    # Build shift data
    shift_data = {
        "labels": shift_df["startTime"].tolist(),
        "values": shift_df["count"].tolist()
    } if not shift_df.empty else {"labels": [], "values": []}

    # Build happiness data (scatter)
    happiness_points = happiness_df.dropna().to_dict(orient="records") if not happiness_df.empty else []

    # Build hourly activity
    hourly_data = {
        "labels": [f"{int(h):02d}:00" for h in hourly_df["hour"].tolist()],
        "values": hourly_df["count"].tolist()
    } if not hourly_df.empty else {"labels": [], "values": []}

    data = {
        "workforce": wf_data,
        "shifts": shift_data,
        "happiness": happiness_points,
        "hourly": hourly_data
    }
    html = _render_employment_html(data)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/job_transitions", methods=["GET"])
def get_job_transitions():
    """Get job transitions data for interactive map visualization."""
    try:
        import json
        from pathlib import Path

        # Load job_changes.json
        job_changes_path = Path(__file__).resolve().parent / "job_changes.json"
        if not job_changes_path.exists():
            return jsonify({"error": "job_changes.json not found"}), 404

        with open(job_changes_path, "r") as f:
            job_changes = json.load(f)

        # Load map_points.csv to get employers with coordinates
        map_points_path = Path(__file__).resolve().parent / "map_points.csv"
        employer_coords = {}
        if map_points_path.exists():
            with open(map_points_path, "r") as f:
                lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    parts = line.strip().split(",")
                    if len(parts) >= 5:
                        emp_id = int(parts[0])
                        name = parts[1]
                        category = parts[2]
                        x = float(parts[3])
                        y = float(parts[4])
                        if category == "Employer":
                            employer_coords[emp_id] = {"name": name, "x": x, "y": y}

        # Process job_changes.json to extract transitions only between employers in map
        links = []
        all_employers = set()

        for participant_id, transitions in job_changes.items():
            for transition in transitions:
                source = int(transition["source"])
                target = int(transition["target"])
                # Only include if both endpoints are in the map
                if source in employer_coords and target in employer_coords:
                    all_employers.add(source)
                    all_employers.add(target)
                    links.append({"source": source, "target": target, "value": 1})

        # Aggregate links by source and target
        link_dict = {}
        for link in links:
            key = (link["source"], link["target"])
            link_dict[key] = link_dict.get(key, 0) + 1

        # Convert to list of links with aggregated values
        aggregated_links = [
            {"source": src, "target": tgt, "value": count}
            for (src, tgt), count in link_dict.items()
        ]

        # Only keep employers that have at least one transition
        employers_with_transitions = set()
        for link in aggregated_links:
            employers_with_transitions.add(link["source"])
            employers_with_transitions.add(link["target"])

        # Create nodes list with coordinates
        nodes = [
            {
                "id": emp_id,
                "name": employer_coords[emp_id]["name"],
                "x": employer_coords[emp_id]["x"],
                "y": employer_coords[emp_id]["y"],
            }
            for emp_id in sorted(employers_with_transitions)
        ]

        # Keep links with original employer IDs
        links_with_ids = [
            {"source": link["source"], "target": link["target"], "value": link["value"]}
            for link in aggregated_links
        ]

        return jsonify({"nodes": nodes, "links": links_with_ids})

    except Exception as exc:
        return jsonify({"error": f"Failed to load job transitions: {exc}"}), 500


@app.route("/api/employer_financials_timeline/<int:employer_id>", methods=["GET"])
def api_employer_financials_timeline(employer_id: int):
    """Return revenue and profit over time for a specific employer."""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Get jobs for this employer
        cursor.execute(
            "SELECT jobId, hourlyRate FROM jobs WHERE employerId = ?", (employer_id,)
        )
        jobs = {row[0]: row[1] for row in cursor.fetchall()}

        if not jobs:
            conn.close()
            return jsonify({"error": f"No jobs found for employer {employer_id}"}), 404

        job_ids = tuple(jobs.keys())
        avg_hourly_rate = sum(jobs.values()) / len(jobs)

        # Query all participant logs for complete coverage
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'participantstatuslogs%' ORDER BY SUBSTR(name, 19)"
        )
        table_names = [row[0] for row in cursor.fetchall()]

        timeline_data = {}
        for table_name in table_names:
            placeholders = ",".join("?" * len(job_ids))
            query = f"SELECT DATE(timestamp) as d, COUNT(DISTINCT participantId) as c FROM {table_name} WHERE jobId IN ({placeholders}) GROUP BY d"
            try:
                cursor.execute(query, job_ids)
                for work_date, emp_count in cursor.fetchall():
                    if work_date:
                        timeline_data[work_date] = (
                            timeline_data.get(work_date, 0) + emp_count
                        )
            except:
                pass

        if not timeline_data:
            conn.close()
            return jsonify(
                {
                    "employer_id": employer_id,
                    "total_jobs": len(jobs),
                    "weekly": [],
                    "monthly": [],
                    "summary": {},
                }
            )

        # Calculate financials
        hours_per_day = 8
        weekly_data = {}
        monthly_data = {}

        for work_date in sorted(timeline_data.keys()):
            emp_count = timeline_data[work_date]
            daily_revenue = emp_count * avg_hourly_rate * hours_per_day
            payroll = daily_revenue * 0.6
            operating = daily_revenue * 0.3
            profit = daily_revenue - payroll - operating

            date_obj = pd.to_datetime(work_date)
            week_key = date_obj.strftime("%Y-W%U")
            month_key = date_obj.strftime("%Y-%m")

            # Weekly
            if week_key not in weekly_data:
                weekly_data[week_key] = {
                    "week": week_key,
                    "employees": [],
                    "revenue": 0,
                    "payroll": 0,
                    "operating": 0,
                    "profit": 0,
                }
            weekly_data[week_key]["employees"].append(emp_count)
            weekly_data[week_key]["revenue"] += daily_revenue
            weekly_data[week_key]["payroll"] += payroll
            weekly_data[week_key]["operating"] += operating
            weekly_data[week_key]["profit"] += profit

            # Monthly
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "month": month_key,
                    "employees": [],
                    "revenue": 0,
                    "payroll": 0,
                    "operating": 0,
                    "profit": 0,
                }
            monthly_data[month_key]["employees"].append(emp_count)
            monthly_data[month_key]["revenue"] += daily_revenue
            monthly_data[month_key]["payroll"] += payroll
            monthly_data[month_key]["operating"] += operating
            monthly_data[month_key]["profit"] += profit

        # Format results
        weekly_list = []
        for w in sorted(weekly_data.values(), key=lambda x: x["week"]):
            avg_emp = sum(w["employees"]) / len(w["employees"])
            weekly_list.append(
                {
                    "week": w["week"],
                    "avg_employees": round(avg_emp, 1),
                    "max_employees": max(w["employees"]),
                    "revenue": round(w["revenue"], 2),
                    "payroll": round(w["payroll"], 2),
                    "operating": round(w["operating"], 2),
                    "profit": round(w["profit"], 2),
                }
            )

        monthly_list = []
        for m in sorted(monthly_data.values(), key=lambda x: x["month"]):
            avg_emp = sum(m["employees"]) / len(m["employees"])
            monthly_list.append(
                {
                    "month": m["month"],
                    "avg_employees": round(avg_emp, 1),
                    "max_employees": max(m["employees"]),
                    "revenue": round(m["revenue"], 2),
                    "payroll": round(m["payroll"], 2),
                    "operating": round(m["operating"], 2),
                    "profit": round(m["profit"], 2),
                }
            )

        total_revenue = sum(w["revenue"] for w in weekly_list)
        total_profit = sum(w["profit"] for w in weekly_list)
        avg_employees = sum(timeline_data.values()) / len(timeline_data)

        conn.close()
        return jsonify(
            {
                "employer_id": employer_id,
                "employer_name": f"Employer {employer_id}",
                "avg_hourly_rate": round(avg_hourly_rate, 2),
                "total_jobs": len(jobs),
                "date_range": {
                    "start": min(timeline_data.keys()),
                    "end": max(timeline_data.keys()),
                    "days": len(timeline_data),
                },
                "summary": {
                    "avg_employees": round(avg_employees, 1),
                    "total_revenue": round(total_revenue, 2),
                    "total_profit": round(total_profit, 2),
                    "avg_daily_revenue": round(total_revenue / len(timeline_data), 2),
                    "avg_daily_profit": round(total_profit / len(timeline_data), 2),
                },
                "weekly": weekly_list,
                "monthly": monthly_list,
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _render_employment_html(data: dict) -> str:
    import json as _json

    page = r"""
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Employment Insights</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#f4f5f7;color:#222;padding:20px}
.header { margin-bottom: 20px; text-align: center; }
.header h2 { font-size: 24px; color: #2f5d8c; }
.dashboard-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.chart-panel{background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 5px rgba(0,0,0,.1); min-height: 400px; display: flex; flex-direction: column;}
.chart-panel h3{font-size:16px;margin-bottom:12px; display: flex; align-items: center;}
.chart-panel.full-width { grid-column: span 2; }
.tooltip { position: fixed; background: rgba(20, 20, 20, 0.92); color: #fff; padding: 8px 12px;
  border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0;
  transition: opacity 0.12s; line-height: 1.6; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.info-icon{display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;
  background:#2f5d8c;color:#fff;border-radius:50%;font-size:9px;margin-left:6px;cursor:help;vertical-align:middle}
.chart-container { flex-grow: 1; position: relative; }
@media(max-width: 900px) { .dashboard-grid { grid-template-columns: 1fr; } .chart-panel.full-width { grid-column: span 1; } }
</style>
</head>
<body>

<div class="header">
    <h2>Advanced Employment Analytics</h2>
</div>

<div class="dashboard-grid">
    <div class="chart-panel full-width">
        <h3>Workforce Participation & Wages <span class="info-icon" onmouseover="showTip('<strong>City-wide trends</strong><br>Tracks the volume of active workers and average monthly wage levels.', event)" onmouseout="hideTip()">?</span></h3>
        <div id="ch-workforce" class="chart-container"></div>
    </div>

    <div class="chart-panel">
        <h3>Shift Start Time Distribution <span class="info-icon" onmouseover="showTip('<strong>Workforce Timing</strong><br>Frequency of jobs starting at specific times of the day.', event)" onmouseout="hideTip()">?</span></h3>
        <div id="ch-shifts" class="chart-container"></div>
    </div>

    <div class="chart-panel">
        <h3>Workplace Activity by Hour <span class="info-icon" onmouseover="showTip('<strong>Daily Rythm</strong><br>Aggregated check-in volume at workplaces throughout the day.', event)" onmouseout="hideTip()">?</span></h3>
        <div id="ch-hourly" class="chart-container"></div>
    </div>

    <div class="chart-panel full-width">
        <h3>Wage vs. Happiness (Joviality) <span class="info-icon" onmouseover="showTip('<strong>Economic Psychology</strong><br>Scatter plot showing the relationship between average monthly wage and participant joviality.', event)" onmouseout="hideTip()">?</span></h3>
        <div id="ch-happiness" class="chart-container"></div>
    </div>
</div>

<div class="tooltip" id="tip"></div>

<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
const DATA = __DATA__;
const tip  = d3.select('#tip');

function showTip(html, ev) {
  tip.html(html).style('opacity', 1)
     .style('left', (ev.clientX + 15) + 'px').style('top', (ev.clientY - 45) + 'px');
}
function hideTip() { tip.style('opacity', 0); }

const colors = {
    wage: "#ff7f0e",
    workers: "#2ca02c",
    activity: "#1f77b4",
    shift: "#9467bd",
    scatter: "#e377c2"
};

// ── 1. Workforce participation ──────────────────────────────────
(function drawWorkforce(){
  const {months, series} = DATA.workforce;
  if(!months || !months.length) return;
  const el = document.getElementById('ch-workforce');
  const W = el.clientWidth, H = el.clientHeight || 350;
  const m = {top:20, right:60, bottom:50, left:60};
  const w = W - m.left - m.right, h = H - m.top - m.bottom;

  const svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  const g   = svg.append('g').attr('transform',`translate(${m.left},${m.top})`);

  const x   = d3.scalePoint().domain(months).range([0,w]);
  const yL  = d3.scaleLinear().domain([0, d3.max(series[0].values) * 1.1]).nice().range([h,0]);
  const yR  = d3.scaleLinear().domain([0, d3.max(series[1].values) * 1.1]).nice().range([h,0]);
  
  g.append('g').attr('transform',`translate(0,${h})`)
	.call(d3.axisBottom(x).tickValues(months.filter((_,i)=>i%4===0)).tickSize(-h))
	.call(ax=>{ax.selectAll('.tick line').attr('stroke','#eee');ax.select('.domain').remove();})
	.selectAll('text').attr('transform','rotate(-30)').attr('text-anchor','end').attr('font-size',10);

  g.append('g').call(d3.axisLeft(yL).ticks(6)).selectAll('text').attr('fill', series[0].color);
  g.append('g').attr('transform',`translate(${w},0)`)
	.call(d3.axisRight(yR).ticks(6).tickFormat(d=>'$'+d3.format(',.0s')(d)))
	.selectAll('text').attr('fill', series[1].color);

  series.forEach((s,i)=>{
	const ysc = i===0?yL:yR;
	g.append('path').datum(s.values).attr('fill','none')
	  .attr('stroke',s.color).attr('stroke-width',3)
      .attr('d', d3.line().x((_,idx)=>x(months[idx])).y(d=>ysc(d)).curve(d3.curveMonotoneX));
    
    g.selectAll(`.dot-${i}`).data(s.values).enter().append('circle')
      .attr('cx', (_, idx) => x(months[idx])).attr('cy', d => ysc(d)).attr('r', 4).attr('fill', s.color)
      .on('mouseover', (ev, d) => showTip(`<strong>${months[s.values.indexOf(d)]}</strong><br>${s.name}: <strong>${i===0?d.toLocaleString():'$'+d.toLocaleString()}</strong>`, ev))
      .on('mouseout', hideTip);
  });
})();

// ── 2. Shift Starts (Bar) ───────────────────────────────────────
(function drawShifts(){
    const {labels, values} = DATA.shifts;
    if(!labels.length) return;
    const el = document.getElementById('ch-shifts');
    const W = el.clientWidth, H = el.clientHeight || 350;
    const m = {top:20, right:30, bottom:60, left:60};
    const w = W - m.left - m.right, h = H - m.top - m.bottom;

    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);

    const x = d3.scaleBand().domain(labels).range([0, w]).padding(0.2);
    const y = d3.scaleLinear().domain([0, d3.max(values) * 1.1]).nice().range([h, 0]);

    g.append('g').attr('transform', `translate(0, ${h})`).call(d3.axisBottom(x))
     .selectAll('text').attr('transform', 'rotate(-45)').attr('text-anchor', 'end');
    g.append('g').call(d3.axisLeft(y).ticks(5));

    g.selectAll('.bar').data(values).enter().append('rect')
     .attr('x', (_, i) => x(labels[i])).attr('y', d => y(d))
     .attr('width', x.bandwidth()).attr('height', d => h - y(d))
     .attr('fill', colors.shift).attr('opacity', 0.8)
     .on('mouseover', (ev, d) => showTip(`Start Time: <strong>${labels[values.indexOf(d)]}</strong><br>Jobs: <strong>${d.toLocaleString()}</strong>`, ev))
     .on('mouseout', hideTip);
})();

// ── 3. Hourly Activity (Area) ──────────────────────────────────
(function drawHourly(){
    const {labels, values} = DATA.hourly;
    if(!labels.length) return;
    const el = document.getElementById('ch-hourly');
    const W = el.clientWidth, H = el.clientHeight || 350;
    const m = {top:20, right:30, bottom:40, left:60};
    const w = W - m.left - m.right, h = H - m.top - m.bottom;

    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);

    const x = d3.scalePoint().domain(labels).range([0, w]);
    const y = d3.scaleLinear().domain([0, d3.max(values) * 1.1]).nice().range([h, 0]);

    const area = d3.area().x((_,i)=>x(labels[i])).y0(h).y1(d=>y(d)).curve(d3.curveMonotoneX);

    g.append('path').datum(values).attr('fill', colors.activity).attr('opacity', 0.3).attr('d', area);
    g.append('path').datum(values).attr('fill', 'none').attr('stroke', colors.activity).attr('stroke-width', 2).attr('d', d3.line().x((_,i)=>x(labels[i])).y(d=>y(d)).curve(d3.curveMonotoneX));

    g.append('g').attr('transform', `translate(0, ${h})`).call(d3.axisBottom(x).tickValues(labels.filter((_,i)=>i%3===0)));
    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('.2s')));

    g.selectAll('.dot').data(values).enter().append('circle')
     .attr('cx', (_, i) => x(labels[i])).attr('cy', d => y(d)).attr('r', 4).attr('fill', colors.activity)
     .on('mouseover', (ev, d) => showTip(`Time: <strong>${labels[values.indexOf(d)]}</strong><br>Workplace Check-ins: <strong>${d.toLocaleString()}</strong>`, ev))
     .on('mouseout', hideTip);
})();

// ── 4. Happiness Scatter ──────────────────────────────────────
(function drawHappiness(){
    const data = DATA.happiness;
    if(!data.length) return;
    const el = document.getElementById('ch-happiness');
    const W = el.clientWidth, H = el.clientHeight || 350;
    const m = {top:20, right:40, bottom:50, left:60};
    const w = W - m.left - m.right, h = H - m.top - m.bottom;

    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H);
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);

    const x = d3.scaleLinear().domain([0, d3.max(data, d=>d.avg_wage)]).nice().range([0, w]);
    const y = d3.scaleLinear().domain([0, 1]).range([h, 0]);

    g.append('g').attr('transform', `translate(0, ${h})`).call(d3.axisBottom(x).tickFormat(d=>'$'+d3.format('.2s')(d)));
    g.append('g').call(d3.axisLeft(y).ticks(5));

    // Labels
    g.append('text').attr('x', w/2).attr('y', h+40).attr('text-anchor', 'middle').attr('font-size', 11).text('Estimated Monthly Wage ($)');
    g.append('text').attr('transform', 'rotate(-90)').attr('x', -h/2).attr('y', -45).attr('text-anchor', 'middle').attr('font-size', 11).text('Joviality (Happiness Score)');

    g.selectAll('.dot').data(data).enter().append('circle')
     .attr('cx', d => x(d.avg_wage)).attr('cy', d => y(d.joviality))
     .attr('r', 3).attr('fill', colors.scatter).attr('opacity', 0.5)
     .on('mouseover', (ev, d) => showTip(`Wage: <strong>$${d.avg_wage.toLocaleString()}</strong><br>Happiness: <strong>${d.joviality.toFixed(3)}</strong>`, ev))
     .on('mouseout', hideTip);
    
    // Regression line (simple linear)
    const x1 = d3.min(data, d=>d.avg_wage), x2 = d3.max(data, d=>d.avg_wage);
    const sumX = d3.sum(data, d=>d.avg_wage), sumY = d3.sum(data, d=>d.joviality);
    const sumXY = d3.sum(data, d=>d.avg_wage * d.joviality), sumX2 = d3.sum(data, d=>d.avg_wage * d.avg_wage);
    const n = data.length;
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    
    g.append('line').attr('x1', x(x1)).attr('y1', y(slope*x1+intercept)).attr('x2', x(x2)).attr('y2', y(slope*x2+intercept))
     .attr('stroke', '#333').attr('stroke-width', 2).attr('stroke-dasharray', '5,5');
})();
</script>
</body></html>"""

    return page.replace("__DATA__", _json.dumps(data))


    return page.replace("__DATA__", _json.dumps(data))

    return page.replace("__DATA__", _json.dumps(data))


@app.route("/api/export/employer-health-csv", methods=["GET"])
def export_employer_health_csv_endpoint():
    """Export employer health metrics as CSV and return as downloadable file."""
    try:
        output_path = export_employer_health_json()
        return send_file(
            output_path,
            mimetype="application/json",
            as_attachment=True,
            download_name="employer_health_summary.json",
        )
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Failed to export: {exc}"}), 500


def export_employer_health_json(output_path: str | Path | None = None) -> Path:
    """Export employer health metrics to a single JSON file."""
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "employer_health_summary.json"
    else:
        output_path = Path(output_path)

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database file not found: {DB_PATH}")

    conn = _get_db_connection()
    try:
        health_df = _compute_employer_health_scores(conn)
        if health_df.empty:
            raise ValueError("No employer health data available.")

        sector_df = pd.read_sql_query(
            """
			SELECT employerId, educationRequirement AS sector, COUNT(*) AS cnt
			FROM jobs
			WHERE educationRequirement IS NOT NULL
			GROUP BY employerId, educationRequirement
			ORDER BY employerId, cnt DESC
			""",
            conn,
        )
        if not sector_df.empty:
            sector_df = sector_df.sort_values(
                ["employerId", "cnt"], ascending=[True, False]
            )
            sector_df = sector_df.groupby("employerId", as_index=False).first()[
                ["employerId", "sector"]
            ]
        else:
            sector_df = pd.DataFrame(columns=["employerId", "sector"])

        health_df["employerId"] = pd.to_numeric(
            health_df["employerId"], errors="coerce"
        )
        health_df["job_count"] = (
            pd.to_numeric(health_df["job_count"], errors="coerce").fillna(0).astype(int)
        )
        health_df["avg_rate"] = pd.to_numeric(
            health_df["avg_rate"], errors="coerce"
        ).round(2)
        health_df["turnover_count"] = (
            pd.to_numeric(health_df["departed"], errors="coerce").fillna(0)
            + pd.to_numeric(health_df["arrived"], errors="coerce").fillna(0)
        ).astype(int)

        export_df = health_df.merge(sector_df, on="employerId", how="left")
        export_df["sector"] = export_df["sector"].fillna("Unknown")
        export_df["health_category"] = export_df["health_score"].apply(
            lambda s: (
                "Prosperous" if s >= 0.6 else "Neutral" if s >= 0.35 else "Struggling"
            )
        )

        result = export_df[
            [
                "employerId",
                "sector",
                "job_count",
                "avg_rate",
                "turnover_count",
                "turnover_rate",
                "health_category",
            ]
        ].rename(
            columns={
                "employerId": "employerId",
                "sector": "Sector",
                "job_count": "JobCount",
                "avg_rate": "AverageHourlyRate",
                "turnover_count": "TurnoverCount",
                "turnover_rate": "TurnoverRate",
                "health_category": "HealthCategory",
            }
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_json(output_path, orient="records", indent=2)
        return output_path
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True, threaded=True, host="0.0.0.0", port=5000)
