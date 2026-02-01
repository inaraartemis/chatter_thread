import sqlite3
import datetime

DB_FILE = "users.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                avatar TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("Database initialized.")
    except Exception as e:
        print(f"Database init error: {e}")

def add_user(username, avatar):
    try:
        conn = get_db()
        cursor = conn.cursor()
        created_at = datetime.datetime.now().isoformat()
        
        # Check if exists first to handle potential duplicate logic if caller doesn't
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            # Update avatar if user exists
            cursor.execute("UPDATE users SET avatar = ? WHERE username = ?", (avatar, username))
        else:
            cursor.execute("INSERT INTO users (username, avatar, created_at) VALUES (?, ?, ?)", 
                           (username, avatar, created_at))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error adding user: {e}")

def get_all_users():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        users = []
        for row in rows:
            users.append({
                "username": row["username"],
                "avatar": row["avatar"],
                "created_at": row["created_at"]
            })
        conn.close()
        return users
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []

def get_user(username):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"username": row["username"], "avatar": row["avatar"], "created_at": row["created_at"]}
        return None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None
