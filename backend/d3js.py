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


def _build_joined_dataframe(payload: dict) -> tuple[pd.DataFrame, dict[str, dict], list[dict]]:
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
			raise JoinRequestError(f"'columns' must be a list for table '{table_name}'.")
		table_specs[alias] = {
			"name": table_name,
			"alias": alias,
			"columns": list(columns or []),
		}

	required_columns: dict[str, set[str]] = {alias: set(spec["columns"]) for alias, spec in table_specs.items()}
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
			raise JoinRequestError(f"Unknown table alias in join: {left_alias} -> {right_alias}")
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
		available = {c.split("__", 1)[1] for c in df.columns if c.startswith(f"{alias}__")}
		actual_col = _resolve_column_name(available, requested_col)
		if actual_col is None:
			return None
		return f"{alias}__{actual_col}"

	for join_spec in validated_joins:
		(left_alias, left_col) = join_spec["left"]
		(right_alias, right_col) = join_spec["right"]
		if left_alias not in joined_aliases:
			raise JoinRequestError(f"Join order problem: '{left_alias}' is not present in the current joined data.")
		right_df = loaded[right_alias]
		left_key = _prefixed_key(joined, left_alias, left_col)
		right_key = _prefixed_key(right_df, right_alias, right_col)
		if left_key is None:
			raise JoinRequestError(f"Missing join key in current result: {join_spec['left'][0]}.{left_col}")
		if right_key is None:
			raise JoinRequestError(f"Missing join key in table '{right_alias}': {join_spec['right'][0]}.{right_col}")
		joined = pd.merge(joined, right_df, left_on=left_key, right_on=right_key, how=join_spec["how"])
		joined_aliases.add(right_alias)

	if select_cols:
		if not isinstance(select_cols, list):
			raise JoinRequestError("'select' must be a list when provided.")
		resolved_select = []
		for item in select_cols:
			ref = _parse_table_ref(item)
			if ref is None:
				raise JoinRequestError(f"Select columns must use 'alias.column' syntax: {item}")
			alias, col = ref
			if alias not in table_specs:
				raise JoinRequestError(f"Unknown alias in select: {alias}")
			actual_col = _resolve_column_name(
				{c.split("__", 1)[1] for c in joined.columns if c.startswith(f"{alias}__")},
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
	available = {c.split("__", 1)[1] for c in joined.columns if c.startswith(f"{alias}__")}
	actual = _resolve_column_name(available, col)
	if actual is None:
		return None
	return f"{alias}__{actual}"


def _render_joined_chart_html(joined: pd.DataFrame, chart: str, columns: list[str], title: str) -> str:
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


def _render_synced_joined_views_html(joined: pd.DataFrame, views: list[dict], title: str) -> str:
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
		"#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
		"#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
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
				raise JoinRequestError(f"View {idx + 1} columns not found in joined result.")
			chart_rows = joined[["__row_id", x_col, y_col]].copy()
			chart_rows[x_col] = pd.to_numeric(chart_rows[x_col], errors="coerce")
			chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
			chart_rows = chart_rows.dropna(subset=[x_col, y_col])
			if chart_rows.shape[0] < 2:
				raise JoinRequestError(f"View {idx + 1} does not have enough numeric rows.")
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
				raise JoinRequestError(f"View {idx + 1} columns not found in joined result.")
			chart_rows = joined[["__row_id", x_col, y_col]].copy()
			chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
			chart_rows = chart_rows.dropna(subset=[y_col])
			if chart_rows.shape[0] < 2:
				raise JoinRequestError(f"View {idx + 1} does not have enough numeric rows.")
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
				raise JoinRequestError(f"View {idx + 1} does not have enough grouped rows.")
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
				raise JoinRequestError(f"View {idx + 1} column not found in joined result.")
			chart_rows = joined[["__row_id", x_col]].copy()
			chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
			groups = (
				chart_rows.groupby(x_col)
				.agg(count=("__row_id", "size"), rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]))
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
				raise JoinRequestError(f"View {idx + 1} columns not found in joined result.")
			chart_rows = joined[["__row_id", x_col, y_col]].copy()
			chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
			chart_rows[y_col] = chart_rows[y_col].astype(str).fillna("(missing)")
			categories = sorted(set(chart_rows[x_col].unique()).union(set(chart_rows[y_col].unique())))
			if len(categories) < 2:
				raise JoinRequestError(f"View {idx + 1} does not have enough distinct categories.")
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
				raise JoinRequestError(f"View {idx + 1} columns not found in joined result.")
			chart_rows = joined[["__row_id", x_col, y_col]].copy()
			chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
			chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
			chart_rows = chart_rows.dropna(subset=[y_col])
			if chart_rows.shape[0] < 2:
				raise JoinRequestError(f"View {idx + 1} does not have enough numeric rows.")
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
				raise JoinRequestError(f"View {idx + 1} does not have enough grouped rows.")
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
				raise JoinRequestError(f"View {idx + 1} columns not found in joined result.")

			chart_rows = joined[["__row_id", x_col, y_col]].copy()
			chart_rows[x_col] = pd.to_numeric(chart_rows[x_col], errors="coerce")
			chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
			chart_rows = chart_rows.dropna(subset=[x_col, y_col])
			if chart_rows.shape[0] < 2:
				raise JoinRequestError(f"View {idx + 1} does not have enough numeric rows.")

			chart_rows["__xb"] = pd.cut(chart_rows[x_col], bins=bins, labels=False, duplicates="drop")
			chart_rows["__yb"] = pd.cut(chart_rows[y_col], bins=bins, labels=False, duplicates="drop")
			chart_rows = chart_rows.dropna(subset=["__xb", "__yb"])
			if chart_rows.empty:
				raise JoinRequestError(f"View {idx + 1} does not have enough binned rows.")

			chart_rows["__xb"] = chart_rows["__xb"].astype(int)
			chart_rows["__yb"] = chart_rows["__yb"].astype(int)
			pivot = (
				chart_rows.groupby(["__xb", "__yb"])
				.agg(count=("__row_id", "size"), rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]))
				.reset_index()
			)

			chart_payloads.append(
				{
					"type": "heatmap",
					"title": title_text,
					"xLabel": x_ref,
					"yLabel": y_ref,
					"bins": bins,
					"xDomain": [float(chart_rows[x_col].min()), float(chart_rows[x_col].max())],
					"yDomain": [float(chart_rows[y_col].min()), float(chart_rows[y_col].max())],
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
				raise JoinRequestError(f"View {idx + 1} column not found in joined result.")
			chart_rows = joined[["__row_id", x_col]].copy()
			chart_rows[x_col] = pd.to_numeric(chart_rows[x_col], errors="coerce")
			chart_rows = chart_rows.dropna(subset=[x_col])
			if chart_rows.shape[0] < 2:
				raise JoinRequestError(f"View {idx + 1} does not have enough numeric rows.")
			chart_rows["__bin"] = pd.cut(chart_rows[x_col], bins=bins, labels=False, duplicates="drop")
			chart_rows = chart_rows.dropna(subset=["__bin"])
			chart_rows["__bin"] = chart_rows["__bin"].astype(int)
			pivot = (
				chart_rows.groupby("__bin")
				.agg(count=("__row_id", "size"), rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()]))
				.reset_index()
			)
			chart_payloads.append(
				{
					"type": "histogram",
					"title": title_text,
					"xLabel": x_ref,
					"bins": bins,
					"domain": [float(chart_rows[x_col].min()), float(chart_rows[x_col].max())],
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
				raise JoinRequestError(f"View {idx + 1} column not found in joined result.")
			chart_rows = joined[["__row_id", x_col] + ([ _resolve_join_chart_column(joined, y_ref) ] if y_ref else [])].copy()
			chart_rows[x_col] = chart_rows[x_col].astype(str).fillna("(missing)")
			if y_ref:
				y_col = _resolve_join_chart_column(joined, y_ref)
				if y_col is None:
					raise JoinRequestError(f"View {idx + 1} y column not found in joined result.")
				chart_rows[y_col] = pd.to_numeric(chart_rows[y_col], errors="coerce")
				pivot = chart_rows.dropna(subset=[y_col]).groupby(x_col).agg(value=(y_col, "mean"), rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()])).reset_index()
				value_key = "value"
			else:
				pivot = chart_rows.groupby(x_col).agg(value=("__row_id", "size"), rowIds=("__row_id", lambda s: [int(v) for v in s.tolist()])).reset_index()
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

<script>
const views = __VIEWS__;
const palette = __PALETTE__;

const grid = d3.select('#chartGrid');
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
		.on('mouseover', (event, d) => setHoverRows([d.rowId]))
		.on('mouseout', clearHoverRows);

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
		d.__x0 = xScale(domain[0] + d.bin * binWidth);
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
		.on('mouseover', (event, d) => setHoverRows(d.rowIds))
		.on('mouseout', clearHoverRows);
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
		.on('mouseover', (event, d) => setHoverRows(d.rowIds))
		.on('mouseout', clearHoverRows);
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
		.on('mouseover', (event, d) => setHoverRows(d.rowIds))
		.on('mouseout', clearHoverRows);

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
		.attr('width', Math.max(1, cellW))
		.attr('height', Math.max(1, cellH))
		.attr('fill', d => color(d.count))
		.attr('stroke', '#fff')
		.attr('data-row-ids', d => d.rowIds.join(','))
		.on('mouseover', (event, d) => setHoverRows(d.rowIds))
		.on('mouseout', clearHoverRows);
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
		page_template
		.replace("__TITLE__", title)
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
		return jsonify({"error": "'tables' must contain at least two table specs."}), 400
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
			return jsonify({"error": f"'columns' must be a list for table '{table_name}'."}), 400
		table_specs[alias] = {
			"name": table_name,
			"alias": alias,
			"columns": list(columns or []),
		}

	# Validate joins and collect required columns per table alias.
	required_columns: dict[str, set[str]] = {alias: set(spec["columns"]) for alias, spec in table_specs.items()}
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
			return jsonify({"error": f"Unknown table alias in join: {left_alias} -> {right_alias}"}), 400
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
				return jsonify({"error": f"Table '{spec['name']}' does not exist."}), 404
			df, _ = _load_prefixed_table(
				conn,
				spec["name"],
				alias,
				list(required_columns[alias]),
				row_limit=load_limit,
			)
			if df.empty:
				return jsonify({"error": f"Table '{spec['name']}' returned no rows."}), 404
			loaded[alias] = df
	finally:
		conn.close()

	# Join in the requested order; the first table becomes the base frame.
	base_alias = next(iter(table_specs.keys()))
	joined = loaded[base_alias].copy()
	joined_aliases = {base_alias}

	def _prefixed_key(df: pd.DataFrame, alias: str, requested_col: str) -> str | None:
		available = {c.split("__", 1)[1] for c in df.columns if c.startswith(f"{alias}__")}
		actual_col = _resolve_column_name(available, requested_col)
		if actual_col is None:
			return None
		return f"{alias}__{actual_col}"

	for join_spec in validated_joins:
		(left_alias, left_col) = join_spec["left"]
		(right_alias, right_col) = join_spec["right"]
		if left_alias not in joined_aliases:
			return jsonify({"error": f"Join order problem: '{left_alias}' is not present in the current joined data."}), 400
		right_df = loaded[right_alias]
		left_key = _prefixed_key(joined, left_alias, left_col)
		right_key = _prefixed_key(right_df, right_alias, right_col)
		if left_key is None:
			return jsonify({"error": f"Missing join key in current result: {join_spec['left'][0]}.{left_col}"}), 400
		if right_key is None:
			return jsonify({"error": f"Missing join key in table '{right_alias}': {join_spec['right'][0]}.{right_col}"}), 400
		if left_key not in joined.columns:
			return jsonify({"error": f"Missing join key in current result: {join_spec['left'][0]}.{left_col}"}), 400
		if right_key not in right_df.columns:
			return jsonify({"error": f"Missing join key in table '{right_alias}': {join_spec['right'][0]}.{right_col}"}), 400
		joined = pd.merge(joined, right_df, left_on=left_key, right_on=right_key, how=join_spec["how"])
		joined_aliases.add(right_alias)

	if select_cols:
		if not isinstance(select_cols, list):
			return jsonify({"error": "'select' must be a list when provided."}), 400
		resolved_select = []
		for item in select_cols:
			ref = _parse_table_ref(item)
			if ref is None:
				return jsonify({"error": f"Select columns must use 'alias.column' syntax: {item}"}), 400
			alias, col = ref
			if alias not in table_specs:
				return jsonify({"error": f"Unknown alias in select: {alias}"}), 400
			actual_col = _resolve_column_name(
				{c.split("__", 1)[1] for c in joined.columns if c.startswith(f"{alias}__")},
				col,
			)
			if actual_col is None:
				return jsonify({"error": f"Column not available in joined result: {item}"}), 400
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
				for (left_alias, left_col), (right_alias, right_col) in [(join_spec["left"], join_spec["right"])]
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
		missing = [c for c in [source_col, target_col, value_col] if c not in available_columns]
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
		return jsonify({"error": "No valid numeric values in value_col for Sankey."}), 400

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


@app.route("/api/d3block-pair", methods=["POST"])
def generate_pair_html():
	"""
	Generate a single HTML page with a scatter + heatmap that are data-driven
	and synchronized. Server-side binning is used for the heatmap; the raw
	points are embedded as JSON so client-side D3 can link elements reliably.

	Request JSON:
	{
		"dataset": "participants",
		"x": "longitude",
		"y": "latitude",
		"bins": 20,        # optional, bins per axis for heatmap
		"limit": 5000
	}
	"""
	payload = request.get_json(silent=True) or {}
	dataset = payload.get("dataset")
	x_col = payload.get("x")
	y_col = payload.get("y")
	bins = int(payload.get("bins", 20))
	limit = int(payload.get("limit", 5000))

	if not dataset or not _is_valid_identifier(dataset):
			return jsonify({"error": "Invalid dataset"}), 400
	if not x_col or not _is_valid_identifier(x_col):
			return jsonify({"error": "Invalid x column"}), 400
	if not y_col or not _is_valid_identifier(y_col):
			return jsonify({"error": "Invalid y column"}), 400

	conn = _get_db_connection()
	try:
			if not _table_exists(conn, dataset):
					return jsonify({"error": f"Dataset '{dataset}' not found"}), 404

			available_columns = _get_table_columns(conn, dataset)
			if x_col not in available_columns or y_col not in available_columns:
					return jsonify({"error": f"Columns not found in '{dataset}'"}), 400

			query = f"SELECT {x_col}, {y_col} FROM {dataset} LIMIT ?"
			df = pd.read_sql_query(query, conn, params=(limit,))
	finally:
			conn.close()

	if df.empty:
			return jsonify({"error": "No data returned"}), 404

	# Coerce numeric and drop NaNs
	df[x_col] = pd.to_numeric(df[x_col], errors="coerce")
	df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
	df = df.dropna(subset=[x_col, y_col])

	if df.empty:
			return jsonify({"error": "No valid numeric rows in the chosen columns"}), 400

	# Compute bins for heatmap
	df["_xb"] = pd.cut(df[x_col], bins=bins, labels=False)
	df["_yb"] = pd.cut(df[y_col], bins=bins, labels=False)

	# Get bin edges (left edges + final right edge)
	x_intervals = pd.cut(df[x_col], bins=bins).cat.categories
	x_bins = [float(interval.left) for interval in x_intervals] + [float(x_intervals[-1].right)]
	y_intervals = pd.cut(df[y_col], bins=bins).cat.categories
	y_bins = [float(interval.left) for interval in y_intervals] + [float(y_intervals[-1].right)]

	# pivot counts
	pivot = df.groupby(["_xb", "_yb"]).size().rename("count").reset_index()

	counts = [[0 for _ in range(bins)] for _ in range(bins)]
	for _, row in pivot.iterrows():
			i = int(row["_xb"]) if not pd.isna(row["_xb"]) else None
			j = int(row["_yb"]) if not pd.isna(row["_yb"]) else None
			if i is None or j is None:
					continue
			if 0 <= i < bins and 0 <= j < bins:
					counts[i][j] = int(row["count"])

	# scatter points with bin indices
	points = []
	for idx, r in df.reset_index().iterrows():
			points.append({
					"id": int(r["index"]),
					"x": float(r[x_col]),
					"y": float(r[y_col]),
					"xb": int(r["_xb"]),
					"yb": int(r["_yb"]),
			})

	import json

	page_template = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paired Scatter & Heatmap</title>
<style>
	body { font-family: Arial, sans-serif; margin: 8px; }
	.container { display:flex; gap:16px; align-items:flex-start; }
	.panel { border:1px solid #ddd; padding:8px; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
	.panel h3 { margin:4px 0 8px 0; font-size:14px; }
	.muted { opacity:0.1; }
	.highlight { stroke: #f00; stroke-width:2px; }
</style>
<script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
<div class="container">
	<div class="panel" id="scatterPanel" style="flex:1;">
		<h3>Scatter: __X_COL__ vs __Y_COL__</h3>
		<svg id="scatter" width="600" height="500"></svg>
	</div>
	<div class="panel" id="heatmapPanel" style="width:420px;">
		<h3>Heatmap (bins=__BINS__)</h3>
		<svg id="heatmap" width="420" height="420"></svg>
	</div>
</div>

<script>
	const points = __POINTS__;
	const counts = __COUNTS__;
	const xBins = __XBINS__;
	const yBins = __YBINS__;

	// Scatter
	const sWidth = 600, sHeight = 500, margin = {top:20,right:20,bottom:40,left:50};
	const sx = d3.scaleLinear().domain(d3.extent(points, d=>d.x)).nice().range([margin.left, sWidth - margin.right]);
	const sy = d3.scaleLinear().domain(d3.extent(points, d=>d.y)).nice().range([sHeight - margin.bottom, margin.top]);
	const sSvg = d3.select('#scatter');
	sSvg.selectAll('*').remove();
	sSvg.append('g').attr('transform', `translate(0,0)`);

	sSvg.selectAll('circle').data(points).join('circle')
		.attr('cx', d=>sx(d.x)).attr('cy', d=>sy(d.y)).attr('r', 3)
		.attr('fill', '#1f77b4')
		.attr('data-xb', d=>d.xb).attr('data-yb', d=>d.yb)
		.on('mouseover', (event,d)=>{ highlightBin(d.xb, d.yb); })
		.on('mouseout', ()=>{ clearHighlights(); });

	sSvg.append('g').attr('transform', `translate(0,${sHeight - margin.bottom})`)
		.call(d3.axisBottom(sx));
	sSvg.append('g').attr('transform', `translate(${margin.left},0)`)
		.call(d3.axisLeft(sy));

	// Heatmap
	const hSize = 420;
	const cellW = hSize / counts.length;
	const cellH = hSize / counts[0].length;
	const hSvg = d3.select('#heatmap');
	hSvg.selectAll('*').remove();

	const flat = counts.flat();
	const color = d3.scaleSequential(d3.interpolateYlOrRd).domain([0, d3.max(flat)]);

	const cells = [];
	for(let i=0;i<counts.length;i++){
		for(let j=0;j<counts[i].length;j++){
			cells.push({i:i,j:j,count:counts[i][j]});
		}
	}

	hSvg.selectAll('rect').data(cells).join('rect')
		.attr('x', d=>d.i*cellW)
		.attr('y', d=>hSize - (d.j+1)*cellH)
		.attr('width', cellW)
		.attr('height', cellH)
		.attr('fill', d=> color(d.count))
		.attr('stroke', '#eee')
		.attr('data-i', d=>d.i).attr('data-j', d=>d.j)
		.on('mouseover', (event,d)=>{ highlightBin(d.i,d.j); })
		.on('mouseout', ()=>{ clearHighlights(); });

	// Highlighting
	function highlightBin(i,j){
		// highlight heatmap cell
		hSvg.selectAll('rect').classed('muted', true).classed('highlight', false);
		hSvg.selectAll('rect').filter(function(){ return +this.getAttribute('data-i')===i && +this.getAttribute('data-j')===j; }).classed('muted', false).classed('highlight', true).raise();

		// highlight scatter points in that bin
		sSvg.selectAll('circle').classed('muted', true).classed('highlight', false);
		sSvg.selectAll('circle').filter(function(){ return +this.getAttribute('data-xb')===i && +this.getAttribute('data-yb')===j; }).classed('muted', false).classed('highlight', true).raise();
	}

	function clearHighlights(){
		hSvg.selectAll('rect').classed('muted', false).classed('highlight', false);
		sSvg.selectAll('circle').classed('muted', false).classed('highlight', false);
	}

</script>
</body>
</html>
"""

	page = page_template.replace('__POINTS__', json.dumps(points))
	page = page.replace('__COUNTS__', json.dumps(counts))
	page = page.replace('__XBINS__', json.dumps(x_bins))
	page = page.replace('__YBINS__', json.dumps(y_bins))
	page = page.replace('__X_COL__', x_col)
	page = page.replace('__Y_COL__', y_col)
	page = page.replace('__BINS__', str(bins))

	return page, 200, {"Content-Type": "text/html; charset=utf-8"}


if __name__ == "__main__":
	app.run(debug=True, threaded=True, host="0.0.0.0", port=5000)