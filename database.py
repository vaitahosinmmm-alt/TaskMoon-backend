import os
import psycopg
from psycopg.rows import dict_row


def connect():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    return psycopg.connect(
        database_url,
        row_factory=dict_row
    )


def init_support_messages():
    conn = connect()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id BIGSERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def init_withdrawals():
    conn = connect()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount INTEGER NOT NULL,
            method TEXT NOT NULL,
            number TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def init_db():
    conn = connect()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            uid TEXT UNIQUE,
            coins INTEGER NOT NULL DEFAULT 0,
            referrer_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_chats (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
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

    init_support_messages()
    init_withdrawals()


def get_user(user_id):
    conn = connect()

    user = conn.execute(
        "SELECT * FROM users WHERE user_id = %s",
        (user_id,)
    ).fetchone()

    conn.close()
    return user


def generate_uid(conn):
    import random

    while True:
        uid = "TM" + str(random.randint(100000, 999999))

        exists = conn.execute(
            "SELECT 1 FROM users WHERE uid = %s",
            (uid,)
        ).fetchone()

        if not exists:
            return uid


def get_user_by_uid(uid):
    conn = connect()

    user = conn.execute(
        "SELECT * FROM users WHERE uid = %s",
        (uid,)
    ).fetchone()

    conn.close()
    return user


def create_user(
    user_id,
    username="",
    first_name="",
    referrer_id=None
):
    conn = connect()

    existing = conn.execute(
        "SELECT user_id FROM users WHERE user_id = %s",
        (user_id,)
    ).fetchone()

    if existing:
        conn.close()
        return False

    uid = generate_uid(conn)

    conn.execute("""
        INSERT INTO users
        (user_id, username, first_name, uid, referrer_id)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        user_id,
        username or "",
        first_name or "",
        uid,
        referrer_id
    ))

    conn.commit()
    conn.close()

    return uid


def add_coins(user_id, amount, description=""):
    conn = connect()

    conn.execute(
        "UPDATE users SET coins = coins + %s WHERE user_id = %s",
        (amount, user_id)
    )

    conn.execute("""
        INSERT INTO history
        (user_id, type, amount, description)
        VALUES (%s, %s, %s, %s)
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
        "SELECT COUNT(*) AS total FROM users WHERE referrer_id = %s",
        (user_id,)
    ).fetchone()

    conn.close()

    return result["total"]


def get_history(user_id, limit=20):
    conn = connect()

    rows = conn.execute("""
        SELECT type, amount, description, created_at
        FROM history
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT %s
    """, (
        user_id,
        limit
    )).fetchall()

    conn.close()

    return rows


def create_support_chat(
    user_id,
    uid,
    problem,
    message=""
):
    conn = connect()

    row = conn.execute("""
        INSERT INTO support_chats
        (user_id, uid, problem, message, status)
        VALUES (%s, %s, %s, %s, 'open')
        RETURNING id
    """, (
        user_id,
        uid,
        problem,
        message
    )).fetchone()

    conn.commit()
    conn.close()

    return row["id"]


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
        WHERE id = %s
    """, (chat_id,)).fetchone()

    conn.close()

    return row


def update_support_chat_message(chat_id, message):
    conn = connect()

    conn.execute("""
        UPDATE support_chats
        SET message = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (
        message,
        chat_id
    ))

    conn.commit()
    conn.close()


def add_support_message(chat_id, sender, message):
    conn = connect()

    conn.execute("""
        INSERT INTO support_messages
        (chat_id, sender, message)
        VALUES (%s, %s, %s)
    """, (
        chat_id,
        sender,
        message
    ))

    conn.commit()
    conn.close()


def get_support_messages(chat_id):
    conn = connect()

    rows = conn.execute("""
        SELECT id, chat_id, sender, message, created_at
        FROM support_messages
        WHERE chat_id = %s
        ORDER BY id ASC
    """, (chat_id,)).fetchall()

    conn.close()

    return rows


def close_support_chat(chat_id):
    conn = connect()

    conn.execute("""
        UPDATE support_chats
        SET status = 'closed',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (chat_id,))

    conn.commit()
    conn.close()


def update_admin_reply(chat_id, admin_reply):
    conn = connect()

    conn.execute("""
        UPDATE support_chats
        SET admin_reply = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
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
        WHERE id = %s
    """, (chat_id,)).fetchone()

    conn.close()

    return row["admin_reply"] if row else None


def create_withdrawal(
    user_id,
    amount,
    method,
    number
):
    conn = connect()

    row = conn.execute("""
        INSERT INTO withdrawals
        (user_id, amount, method, number, status)
        VALUES (%s, %s, %s, %s, 'pending')
        RETURNING id
    """, (
        user_id,
        amount,
        method,
        number
    )).fetchone()

    conn.commit()
    conn.close()

    return row["id"]


def get_withdrawals(status=None):
    conn = connect()

    if status:
        rows = conn.execute("""
            SELECT *
            FROM withdrawals
            WHERE status = %s
            ORDER BY id DESC
        """, (status,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM withdrawals
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return rows


def update_withdrawal_status(
    withdrawal_id,
    status
):
    conn = connect()

    conn.execute("""
        UPDATE withdrawals
        SET status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (
        status,
        withdrawal_id
    ))

    conn.commit()
    conn.close()


init_db()
