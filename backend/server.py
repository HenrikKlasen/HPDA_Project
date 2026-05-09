from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
from pathlib import Path

app = Flask(__name__)
CORS(app)
DB_PATH = 'vast_challenge.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM your_table_name')
        rows = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/<int:id>', methods=['GET'])
def get_data_by_id(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM your_table_name WHERE id = ?', (id,))
        row = cursor.fetchone()
        conn.close()
        return jsonify(dict(row)) if row else jsonify({'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['POST'])
def create_data():
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO your_table_name (column1, column2) VALUES (?, ?)',
                       (data['column1'], data['column2']))
        conn.commit()
        conn.close()
        return jsonify({'success': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/job_transitions", methods=["GET"])
def get_job_transitions():
    """Get job transitions data for interactive map visualization."""
    try:
        job_changes_path = Path(__file__).resolve().parent / "job_changes.json"
        if not job_changes_path.exists():
            return jsonify({"error": "job_changes.json not found"}), 404

        with open(job_changes_path, 'r') as f:
            job_changes = json.load(f)

        map_points_path = Path(__file__).resolve().parent / "map_points.csv"
        employer_coords = {}
        if map_points_path.exists():
            with open(map_points_path, 'r') as f:
                lines = f.readlines()
                for line in lines[1:]:
                    parts = line.strip().split(',')
                    if len(parts) >= 5:
                        emp_id = int(parts[0])
                        name = parts[1]
                        category = parts[2]
                        x = float(parts[3])
                        y = float(parts[4])
                        if category == "Employer":
                            employer_coords[emp_id] = {'name': name, 'x': x, 'y': y}

        links = []
        all_employers = set()

        for participant_id, transitions in job_changes.items():
            for transition in transitions:
                source = int(transition['source'])
                target = int(transition['target'])
                if source in employer_coords and target in employer_coords:
                    all_employers.add(source)
                    all_employers.add(target)
                    links.append({'source': source, 'target': target, 'value': 1})

        link_dict = {}
        for link in links:
            key = (link['source'], link['target'])
            link_dict[key] = link_dict.get(key, 0) + 1

        aggregated_links = [
            {'source': src, 'target': tgt, 'value': count}
            for (src, tgt), count in link_dict.items()
        ]

        employers_with_transitions = set()
        for link in aggregated_links:
            employers_with_transitions.add(link['source'])
            employers_with_transitions.add(link['target'])

        nodes = [
            {'id': emp_id, 'name': employer_coords[emp_id]['name'],
             'x': employer_coords[emp_id]['x'], 'y': employer_coords[emp_id]['y']}
            for emp_id in sorted(employers_with_transitions)
        ]

        links_with_ids = [
            {'source': link['source'], 'target': link['target'], 'value': link['value']}
            for link in aggregated_links
        ]

        return jsonify({'nodes': nodes, 'links': links_with_ids})

    except Exception as exc:
        return jsonify({"error": f"Failed to load job transitions: {exc}"}), 500


if __name__ == '__main__':
    table_names = [f'participantstatuslog{i}' for i in range(1, 73)] + ['financialjournal', 'checkinjournal', 'socialnetwork', 'traveljournal',
                                                                        'schools', 'buildings', 'pubs', 'employers', 'jobs', 'participants',
                                                                        'restaurants', 'apartments']

    @app.route('/api/search', methods=['POST'])
    def search_data():
        try:
            data = request.json
            table_name = data.get('table')
            search_criteria = data.get('criteria')

            if table_name not in table_names:
                return jsonify({'error': 'Invalid table'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            where_clause = ' AND '.join([f'{col} = ?' for col in search_criteria.keys()])
            values = list(search_criteria.values())

            query = f'SELECT * FROM {table_name} WHERE {where_clause}'
            cursor.execute(query, values)
            rows = cursor.fetchall()
            conn.close()

            return jsonify([dict(row) for row in rows])
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    app.run(debug=True, host='0.0.0.0', port=5000)