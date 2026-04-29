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
	app.run(debug=True, host="0.0.0.0", port=5000)