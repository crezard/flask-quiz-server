from flask import Flask, render_template, request, jsonify, g
import sqlite3
import datetime
import os
from dotenv import load_dotenv

# PostgreSQL 연결 라이브러리. 설치되어 있지 않으면 오류를 방지하기 위해 None 처리
try:
    import psycopg2
except ImportError:
    psycopg2 = None 

# .env 파일에서 환경 변수 로드 (로컬 테스트용). Render에서는 자동으로 로드됨.
load_dotenv()

# --- 서버 설정 및 DB 연결 ---

app = Flask(__name__)

# Render 환경 변수(DATABASE_URL)를 확인하여 PostgreSQL 사용 여부 결정
DATABASE_URL = os.environ.get('DATABASE_URL')
# Flask의 디버그 모드 설정 (Render 배포 시에는 자동으로 비활성화됨)
app.debug = os.environ.get('FLASK_DEBUG') == 'True' or not DATABASE_URL
# 서버가 모든 주소에서 접속을 허용하도록 설정
app.config['SERVER_NAME'] = '0.0.0.0:5000' if not DATABASE_URL else None 

# 데이터베이스 연결 함수: 환경에 따라 SQLite 또는 PostgreSQL 연결
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        if DATABASE_URL:
            # Render 환경 (PostgreSQL 연결)
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is not installed. Required for PostgreSQL.")
            db = g._database = psycopg2.connect(DATABASE_URL)
            db.row_factory = None # psycopg2는 row_factory를 지원하지 않습니다.
        else:
            # 로컬 환경 (SQLite 연결)
            db = g._database = sqlite3.connect('quiz_records.db')
            db.row_factory = sqlite3.Row # SQLite 결과를 딕셔너리 형태로 받기 위함
    return db

# 서버 종료 시 데이터베이스 연결 해제
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 데이터베이스 초기화 (records 테이블 생성)
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

# --- 라우팅 (페이지/API 주소 설정) ---

@app.route('/')
def index():
    return render_template('quiz_page.html')

# 기록 저장 (POST 요청 처리)
@app.route('/api/scores', methods=['POST'])
def save_score():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        if DATABASE_URL:
            # PostgreSQL 쿼리 (%s 사용)
            cursor.execute(
                "INSERT INTO records (user_name, score, accuracy, date_time) VALUES (%s, %s, %s, %s)",
                (data['user_name'], data['score'], data['accuracy'], timestamp)
            )
        else:
            # SQLite 쿼리 (? 사용)
            cursor.execute(
                "INSERT INTO records (user_name, score, accuracy, date_time) VALUES (?, ?, ?, ?)",
                (data['user_name'], data['score'], data['accuracy'], timestamp)
            )
        db.commit()
        return jsonify({"message": "Record saved successfully!"}), 201
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# 기록 조회 (GET 요청 처리)
@app.route('/api/scores', methods=['GET'])
def get_scores():
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT user_name, score, accuracy, date_time FROM records ORDER BY date_time DESC")
    
    if DATABASE_URL:
        # PostgreSQL 결과를 딕셔너리 리스트로 변환
        columns = [desc[0] for desc in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        # SQLite는 dict cursor를 사용했으므로 바로 딕셔너리 리스트로 변환
        records = [dict(row) for row in cursor.fetchall()]
        
    return jsonify(records), 200

# --- 서버 실행 ---

if __name__ == '__main__':
    # Flask 앱이 실행될 때 DB 초기화
    with app.app_context():
        init_db(get_db())
    # 로컬 테스트를 위해 0.0.0.0에서 실행
    app.run(host='0.0.0.0', debug=True)