from flask import Flask, render_template, request, jsonify, g
import sqlite3
import datetime
import os
from dotenv import load_dotenv

try:
    import psycopg2
except ImportError:
    psycopg2 = None 

load_dotenv()

# --- 서버 설정 및 DB 연결 ---

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
app.debug = os.environ.get('FLASK_DEBUG') == 'True' or not DATABASE_URL
app.config['SERVER_NAME'] = '0.0.0.0:5000' if not DATABASE_URL else None 

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        if DATABASE_URL:
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is not installed. Required for PostgreSQL.")
            db = g._database = psycopg2.connect(DATABASE_URL)
            db.row_factory = None
        else:
            db = g._database = sqlite3.connect('quiz_records.db')
            db.row_factory = sqlite3.Row 
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db(db):
    cursor = db.cursor()
    if DATABASE_URL:
        # PostgreSQL 문법
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id SERIAL PRIMARY KEY,
                user_name VARCHAR(100) NOT NULL,
                score INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                date_time TIMESTAMP WITHOUT TIME ZONE NOT NULL
            );
        ''')
    else:
        # SQLite 문법
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                date_time TEXT NOT NULL
            );
        ''')
    db.commit()

# --- 라우팅 ---

@app.route('/')
def index():
    return render_template('quiz_page.html')

@app.route('/api/scores', methods=['POST'])
def save_score():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        if DATABASE_URL:
            cursor.execute(
                "INSERT INTO records (user_name, score, accuracy, date_time) VALUES (%s, %s, %s, %s)",
                (data['user_name'], data['score'], data['accuracy'], timestamp)
            )
        else:
            cursor.execute(
                "INSERT INTO records (user_name, score, accuracy, date_time) VALUES (?, ?, ?, ?)",
                (data['user_name'], data['score'], data['accuracy'], timestamp)
            )
        db.commit()
        return jsonify({"message": "Record saved successfully!"}), 201
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/scores', methods=['GET'])
def get_scores():
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT user_name, score, accuracy, date_time FROM records ORDER BY date_time DESC")
    
    if DATABASE_URL:
        columns = [desc[0] for desc in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        records = [dict(row) for row in cursor.fetchall()]
        
    return jsonify(records), 200

# --- 서버 실행 ---

if __name__ == '__main__':
    with app.app_context():
        init_db(get_db())
    app.run(host='0.0.0.0', debug=True)