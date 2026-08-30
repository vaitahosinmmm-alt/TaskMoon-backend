import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "taskmoon.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            coins INTEGER NOT NULL DEFAULT 0,
            referrer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            uid TEXT NOT NULL,
            problem TEXT NOT NULL,
            message TEXT DEFAULT '',
            admin_reply TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = connect()
    user = conn.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return user


def create_user(user_id, username="", first_name="", referrer_id=None):
    conn = connect()

    existing = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if existing:
        conn.close()
        return False

    conn.execute("""
        INSERT INTO users
        (user_id, username, first_name, referrer_id)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        username or "",
        first_name or "",
        referrer_id
    ))

    conn.commit()
    conn.close()

    return True


def add_coins(user_id, amount, description=""):
    conn = connect()

    conn.execute(
        "UPDATE users SET coins = coins + ? WHERE user_id = ?",
        (amount, user_id)
    )

    conn.execute("""
        INSERT INTO history
        (user_id, type, amount, description)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        "EARN",
        amount,
        description
    ))

    conn.commit()
    conn.close()


def get_coins(user_id):
    user = get_user(user_id)

    if not user:
        return 0

    return user["coins"]


def add_referral_commission(referrer_id, task_coins):
    commission = task_coins * 10 // 100

    if commission <= 0:
        return 0

    add_coins(
        referrer_id,
        commission,
        f"Referral commission 10% from {task_coins} coins task"
    )

    return commission


def get_referral_count(user_id):
    conn = connect()

    result = conn.execute(
        "SELECT COUNT(*) AS total FROM users WHERE referrer_id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return result["total"]


def get_history(user_id, limit=20):
    conn = connect()

    rows = conn.execute("""
        SELECT type, amount, description, created_at
        FROM history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (
        user_id,
        limit
    )).fetchall()

    conn.close()

    return rows


init_db()

def create_support_chat(user_id, uid, problem, message=""):
    conn = connect()

    cur = conn.execute("""
        INSERT INTO support_chats
        (user_id, uid, problem, message, status)
        VALUES (?, ?, ?, ?, 'open')
    """, (
        user_id,
        uid,
        problem,
        message
    ))

    conn.commit()
    chat_id = cur.lastrowid
    conn.close()

    return chat_id


def get_support_chats():
    conn = connect()

    rows = conn.execute("""
        SELECT *
        FROM support_chats
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def get_support_chat(chat_id):
    conn = connect()

    row = conn.execute("""
        SELECT *
        FROM support_chats
        WHERE id = ?
    """, (chat_id,)).fetchone()

    conn.close()

    return row


def update_support_chat_message(chat_id, message):
    conn = connect()

    conn.execute("""
        UPDATE support_chats
        SET message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        message,
        chat_id
    ))

    conn.commit()
    conn.close()


def close_support_chat(chat_id):
    conn = connect()

    conn.execute("""
        UPDATE support_chats
        SET status = 'closed',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (chat_id,))

    conn.commit()
    conn.close()


def update_admin_reply(chat_id, admin_reply):
    conn = connect()

    conn.execute("""
        UPDATE support_chats
        SET admin_reply = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        admin_reply,
        chat_id
    ))

    conn.commit()
    conn.close()


def get_admin_reply(chat_id):
    conn = connect()

    row = conn.execute("""
        SELECT admin_reply
        FROM support_chats
        WHERE id = ?
    """, (chat_id,)).fetchone()

    conn.close()

    return row["admin_reply"] if row else None
