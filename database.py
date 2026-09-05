import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = None

class PooledConnection:
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if not self._returned:
            self._pool.putconn(self._conn)
            self._returned = True


def get_pool():
    global _pool
    if _pool is None:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise RuntimeError('DATABASE_URL is not set')
        _pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=5,
            timeout=10,
            kwargs={'row_factory': dict_row},
            open=True
        )
    return _pool


def connect():
    pool = get_pool()
    return PooledConnection(pool, pool.getconn())


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
    row = conn.execute("""
        SELECT MAX(CAST(SUBSTRING(uid FROM 3) AS INTEGER)) AS max_uid
        FROM users
        WHERE uid ~ '^TM[0-9]+$'
    """).fetchone()

    last_number = row["max_uid"] if row and row["max_uid"] is not None else 6000
    return "TM" + str(last_number + 1)


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



def deduct_coins(user_id, amount, description=""):
    conn = connect()

    row = conn.execute("""
        UPDATE users
        SET coins = coins - %s
        WHERE user_id = %s
          AND coins >= %s
        RETURNING coins
    """, (
        amount,
        user_id,
        amount
    )).fetchone()

    if not row:
        conn.rollback()
        conn.close()
        return False

    conn.execute("""
        INSERT INTO history
        (user_id, type, amount, description)
        VALUES (%s, %s, %s, %s)
    """, (
        user_id,
        "WITHDRAW",
        -amount,
        description
    ))

    conn.commit()
    conn.close()

    return True


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

    # Reuse existing open support chat for this user
    existing = conn.execute("""
        SELECT id
        FROM support_chats
        WHERE user_id = %s
          AND status = 'open'
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,)).fetchone()

    if existing:
        conn.close()
        return existing["id"]

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



def create_withdrawal_request(
    user_id,
    amount,
    method,
    number
):
    conn = connect()

    try:
        # Lock user row so simultaneous withdrawal requests are serialized
        user = conn.execute("""
            SELECT user_id
            FROM users
            WHERE user_id = %s
            FOR UPDATE
        """, (user_id,)).fetchone()

        if not user:
            conn.rollback()
            return False, None, "User not found"

        # Only one pending withdrawal per user
        pending = conn.execute("""
            SELECT id
            FROM withdrawals
            WHERE user_id = %s
              AND status = 'pending'
            LIMIT 1
        """, (user_id,)).fetchone()

        if pending:
            conn.rollback()
            return False, None, "A withdrawal is already pending"

        # Deduct coins atomically
        balance = conn.execute("""
            UPDATE users
            SET coins = coins - %s
            WHERE user_id = %s
              AND coins >= %s
            RETURNING coins
        """, (
            amount,
            user_id,
            amount
        )).fetchone()

        if not balance:
            conn.rollback()
            return False, None, "Insufficient balance"

        # Create withdrawal request
        withdrawal = conn.execute("""
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

        # Add withdrawal history
        conn.execute("""
            INSERT INTO history
            (user_id, type, amount, description)
            VALUES (%s, %s, %s, %s)
        """, (
            user_id,
            "WITHDRAW",
            -amount,
            "Withdrawal request"
        ))

        conn.commit()

        return True, withdrawal["id"], "Withdrawal request created"

    except Exception as e:
        conn.rollback()
        print("Withdrawal error:", e)
        return False, None, "Withdrawal request failed"

    finally:
        conn.close()


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


def get_user_withdrawals(user_id):
    conn = connect()

    try:
        rows = conn.execute("""
            SELECT id, amount, method, number, status, created_at, updated_at
            FROM withdrawals
            WHERE user_id = %s
            ORDER BY id DESC
        """, (user_id,)).fetchall()

        return rows

    finally:
        conn.close()


def update_withdrawal_status(
    withdrawal_id,
    status
):
    conn = connect()

    row = conn.execute("""
        SELECT user_id, amount, status
        FROM withdrawals
        WHERE id = %s
        FOR UPDATE
    """, (
        withdrawal_id,
    )).fetchone()

    if not row:
        conn.rollback()
        conn.close()
        return False, "Withdrawal not found"

    current_status = row["status"]

    if current_status != "pending":
        conn.rollback()
        conn.close()
        return False, "Withdrawal already processed"

    conn.execute("""
        UPDATE withdrawals
        SET status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (
        status,
        withdrawal_id
    ))

    if status == "rejected":
        conn.execute("""
            UPDATE users
            SET coins = coins + %s
            WHERE user_id = %s
        """, (
            row["amount"],
            row["user_id"]
        ))

        conn.execute("""
            INSERT INTO history
            (user_id, type, amount, description)
            VALUES (%s, %s, %s, %s)
        """, (
            row["user_id"],
            "REFUND",
            row["amount"],
            "Withdrawal rejected - refund"
        ))

    conn.commit()
    conn.close()

    return True, "Withdrawal status updated"


init_db()

def init_task_submissions():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_submissions (
            id BIGSERIAL PRIMARY KEY,
            task_id TEXT NOT NULL,
            task_title TEXT NOT NULL,
            user_id BIGINT NOT NULL,
            reward INTEGER NOT NULL,
            proof TEXT,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def create_task_submission(task_id, task_title, user_id, reward, proof="", note=""):
    conn = connect()
    row = conn.execute("""
        INSERT INTO task_submissions
        (task_id, task_title, user_id, reward, proof, note)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (task_id, task_title, user_id, reward, proof, note)).fetchone()
    conn.commit()
    conn.close()
    return row["id"]

def get_task_submissions(status=None):
    conn = connect()
    if status:
        rows = conn.execute("""
            SELECT *
            FROM task_submissions
            WHERE status = %s
            ORDER BY id ASC
        """, (status,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM task_submissions
            ORDER BY id ASC
        """).fetchall()
    conn.close()
    return rows

def update_task_submission(submission_id, status):
    conn = connect()
    row = conn.execute("""
        SELECT user_id, reward, status
        FROM task_submissions
        WHERE id = %s
        FOR UPDATE
    """, (submission_id,)).fetchone()

    if not row:
        conn.rollback()
        conn.close()
        return False, "Submission not found"

    if row["status"] != "pending":
        conn.rollback()
        conn.close()
        return False, "Submission already processed"

    conn.execute("""
        UPDATE task_submissions
        SET status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (status, submission_id))

    if status == "approved":
        conn.execute("""
            UPDATE users
            SET coins = coins + %s
            WHERE user_id = %s
        """, (row["reward"], row["user_id"]))

        conn.execute("""
            INSERT INTO history
            (user_id, type, amount, description)
            VALUES (%s, %s, %s, %s)
        """, (
            row["user_id"],
            "TASK_REWARD",
            row["reward"],
            "Task submission approved"
        ))

    conn.commit()
    conn.close()
    return True, "Submission status updated"

init_task_submissions()
