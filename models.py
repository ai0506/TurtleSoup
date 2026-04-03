import sqlite3
import json
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            points INTEGER DEFAULT 100,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            surface TEXT NOT NULL,
            bottom TEXT NOT NULL,
            points_json TEXT NOT NULL,
            difficulty TEXT DEFAULT '中等',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN difficulty TEXT DEFAULT \'中等\'')
    except sqlite3.OperationalError:
        pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (question_id) REFERENCES questions (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password_hash, points, role) VALUES (?, ?, ?, ?)",
            ('admin', generate_password_hash('admin123'), 999999, 'admin')
        )
    
    conn.commit()
    conn.close()

def load_questions_from_json(json_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    with open(json_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    for q in questions:
        cursor.execute(
            "INSERT OR REPLACE INTO questions (id, title, surface, bottom, points_json, difficulty) VALUES (?, ?, ?, ?, ?, ?)",
            (q['id'], q['title'], q['surface'], q['bottom'], json.dumps(q['points'], ensure_ascii=False), q.get('difficulty', '中等'))
        )
    
    conn.commit()
    conn.close()

class User(UserMixin):
    def __init__(self, id, username, password_hash, points, role):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.points = points
        self.role = role
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def get(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['password_hash'], row['points'], row['role'])
        return None
    
    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['password_hash'], row['points'], row['role'])
        return None
    
    @staticmethod
    def create(username, password, points=100, role='user'):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, points, role) VALUES (?, ?, ?, ?)",
                (username, generate_password_hash(password), points, role)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return User.get(user_id)
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    def update_points(self, delta):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE id = ?", (delta, self.id))
        conn.commit()
        cursor.execute("SELECT points FROM users WHERE id = ?", (self.id,))
        self.points = cursor.fetchone()['points']
        conn.close()
    
    @staticmethod
    def get_all():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        return [User(row['id'], row['username'], row['password_hash'], row['points'], row['role']) for row in rows]
    
    @staticmethod
    def delete(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def update_role(self, new_role):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, self.id))
        conn.commit()
        self.role = new_role
        conn.close()
    
    def update_points_direct(self, new_points):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, self.id))
        conn.commit()
        self.points = new_points
        conn.close()

class Question:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def get(question_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    
    @staticmethod
    def create(question_id, title, surface, bottom, points, difficulty='中等'):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO questions (id, title, surface, bottom, points_json, difficulty) VALUES (?, ?, ?, ?, ?, ?)",
                (question_id, title, surface, bottom, json.dumps(points, ensure_ascii=False), difficulty)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    @staticmethod
    def update(question_id, title, surface, bottom, points, difficulty='中等'):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE questions SET title = ?, surface = ?, bottom = ?, points_json = ?, difficulty = ? WHERE id = ?",
            (title, surface, bottom, json.dumps(points, ensure_ascii=False), difficulty, question_id)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete(question_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
        conn.close()

class Session:
    @staticmethod
    def create(user_id, question_id, name):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (user_id, question_id, name) VALUES (?, ?, ?)",
            (user_id, question_id, name)
        )
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        return session_id
    
    @staticmethod
    def get(session_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    
    @staticmethod
    def get_by_user_and_question(user_id, question_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND question_id = ? ORDER BY updated_at DESC LIMIT 1",
            (user_id, question_id)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    
    @staticmethod
    def get_all_by_user(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT s.*, q.title FROM sessions s JOIN questions q ON s.question_id = q.id WHERE s.user_id = ? ORDER BY s.updated_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def update_timestamp(session_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete(session_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()

class Message:
    @staticmethod
    def create(session_id, role, content, summary=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, summary) VALUES (?, ?, ?, ?)",
            (session_id, role, content, summary)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_by_session(session_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
