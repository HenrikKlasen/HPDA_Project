from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)
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