from flask import Flask, request, jsonify
from database import (
    get_user,
    create_user,
    get_coins,
    add_coins,
    add_referral_commission,
    get_referral_count,
    get_history,
    create_support_chat,
    get_support_chats,
    get_support_chat,
    update_support_chat_message,
    add_support_message,
    get_support_messages,
   
    update_admin_reply, close_support_chat,
    init_withdrawals,
    create_withdrawal,
    get_withdrawals,
    update_withdrawal_status
)

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "service": "TaskMoon API"
    })


@app.get("/user/<int:user_id>")
def user_info(user_id):

    user = get_user(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    return jsonify({
        "user_id": user["user_id"],
        "username": user["username"],
        "coins": user["coins"],
        "referrals": get_referral_count(user_id)
    })


@app.post("/task/complete")
def complete_task():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    reward = data.get("reward")

    if not isinstance(user_id, int):
        return jsonify({"error": "Invalid user_id"}), 400

    if not isinstance(reward, int) or reward <= 0:
        return jsonify({"error": "Invalid reward"}), 400

    user = get_user(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # User receives task reward
    add_coins(
        user_id,
        reward,
        f"Task completed: +{reward} coins"
    )

    # Referrer receives 10%
    referrer_id = user["referrer_id"]

    commission = 0

    if referrer_id:
        commission = add_referral_commission(
            referrer_id,
            reward
        )

    return jsonify({
        "success": True,
        "user_coins": get_coins(user_id),
        "referral_commission": commission
    })


@app.get("/history/<int:user_id>")
def history(user_id):

    rows = get_history(user_id)

    result = []

    for row in rows:
        result.append({
            "type": row["type"],
            "amount": row["amount"],
            "description": row["description"],
            "created_at": row["created_at"]
        })

    return jsonify(result)


@app.post("/support/chat")
def create_chat():
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    uid = str(data.get("uid", "")).strip()
    problem = str(data.get("problem", "")).strip()
    message = str(data.get("message", "")).strip()

    if not isinstance(user_id, int):
        return jsonify({"error": "Invalid user_id"}), 400

    if not uid:
        return jsonify({"error": "UID is required"}), 400

    if not problem:
        return jsonify({"error": "Problem is required"}), 400

    user = get_user(user_id)

    if not user:
        create_user(user_id, "", "", None)
        user = get_user(user_id)

    chat_id = create_support_chat(
        user_id,
        uid,
        problem,
        message
    )

    return jsonify({
        "success": True,
        "chat_id": chat_id,
        "status": "open"
    })


@app.post("/admin/support/reply")
def admin_support_reply():
    data = request.get_json(silent=True) or {}

    admin_id = data.get("admin_id")
    chat_id = data.get("chat_id")
    reply = str(data.get("reply", "")).strip()

    if admin_id != 7136507076:
        return jsonify({"error": "Unauthorized"}), 403

    if not isinstance(chat_id, int):
        return jsonify({"error": "Invalid chat_id"}), 400

    if not reply:
        return jsonify({"error": "Reply is required"}), 400

    chat = get_support_chat(chat_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    update_admin_reply(chat_id, reply)
    add_support_message(chat_id, "admin", reply)

    return jsonify({
        "success": True,
        "chat_id": chat_id,
        "admin_reply": reply
    })


@app.get("/support/messages/<int:chat_id>")
def support_messages_api(chat_id):

    user_id = request.args.get("user_id", type=int)

    if not isinstance(user_id, int):
        return jsonify({"error": "Invalid user_id"}), 400

    chat = get_support_chat(chat_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    if chat["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    rows = get_support_messages(chat_id)

    result = []

    for row in rows:
        result.append({
            "id": row["id"],
            "sender": row["sender"],
            "message": row["message"],
            "created_at": row["created_at"]
        })

    return jsonify({
        "success": True,
        "messages": result
    })


@app.get("/support/chat/<int:chat_id>")
def get_support_chat_api(chat_id):

    user_id = request.args.get("user_id", type=int)

    if not isinstance(user_id, int):
        return jsonify({"error": "Invalid user_id"}), 400

    chat = get_support_chat(chat_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    if chat["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({
        "success": True,
        "chat": {
            "id": chat["id"],
            "user_id": chat["user_id"],
            "uid": chat["uid"],
            "problem": chat["problem"],
            "message": chat["message"],
            "admin_reply": chat["admin_reply"],
            "status": chat["status"],
            "created_at": chat["created_at"],
            "updated_at": chat["updated_at"]
        }
    })


@app.post("/support/message")
def send_support_message():
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    chat_id = data.get("chat_id")
    message = str(data.get("message", "")).strip()

    if not isinstance(user_id, int):
        return jsonify({"error": "Invalid user_id"}), 400

    if not isinstance(chat_id, int):
        return jsonify({"error": "Invalid chat_id"}), 400

    if not message:
        return jsonify({"error": "Message is required"}), 400

    chat = get_support_chat(chat_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    if chat["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    if chat["status"] != "open":
        return jsonify({"error": "Chat is closed"}), 400

    update_support_chat_message(chat_id, message)
    add_support_message(chat_id, "user", message)

    return jsonify({
        "success": True,
        "chat_id": chat_id,
        "message": message
    })



@app.post("/withdraw")
def create_withdraw_request():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    amount = data.get("amount")
    method = str(data.get("method", "")).strip().lower()
    number = str(data.get("number", "")).strip()

    if not isinstance(user_id, int):
        return jsonify({"error": "Invalid user_id"}), 400

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    if method not in ("bkash", "nagad"):
        return jsonify({"error": "Method must be bKash or Nagad"}), 400

    if not number:
        return jsonify({"error": "Number is required"}), 400

    withdrawal_id = create_withdrawal(
        user_id,
        amount,
        method,
        number
    )

    return jsonify({
        "success": True,
        "withdrawal_id": withdrawal_id,
        "status": "pending"
    })


@app.get("/admin/withdrawals")
def admin_withdrawals():

    ADMIN_ID = 7136507076

    admin_id = request.args.get("admin_id", type=int)

    if admin_id != ADMIN_ID:
        return jsonify({"error": "Unauthorized"}), 403

    status = request.args.get("status")

    if status and status not in ("pending", "approved", "rejected"):
        return jsonify({"error": "Invalid status"}), 400

    rows = get_withdrawals(status)

    result = []

    for row in rows:
        result.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "amount": row["amount"],
            "method": row["method"],
            "number": row["number"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    return jsonify({
        "success": True,
        "withdrawals": result
    })


@app.post("/admin/withdrawal/status")
def admin_withdrawal_status():

    ADMIN_ID = 7136507076

    data = request.get_json(silent=True) or {}

    admin_id = data.get("admin_id")
    withdrawal_id = data.get("withdrawal_id")
    status = str(data.get("status", "")).strip().lower()

    if admin_id != ADMIN_ID:
        return jsonify({"error": "Unauthorized"}), 403

    if not isinstance(withdrawal_id, int):
        return jsonify({"error": "Invalid withdrawal_id"}), 400

    if status not in ("approved", "rejected"):
        return jsonify({"error": "Invalid status"}), 400

    rows = get_withdrawals()

    exists = any(row["id"] == withdrawal_id for row in rows)

    if not exists:
        return jsonify({"error": "Withdrawal not found"}), 404

    update_withdrawal_status(withdrawal_id, status)

    return jsonify({
        "success": True,
        "withdrawal_id": withdrawal_id,
        "status": status
    })



@app.get("/admin/users")
def admin_users():

    ADMIN_ID = 7136507076

    admin_id = request.args.get("admin_id", type=int)

    if admin_id != ADMIN_ID:
        return jsonify({"error": "Unauthorized"}), 403

    conn = __import__("sqlite3").connect("taskmoon.db")
    conn.row_factory = __import__("sqlite3").Row

    rows = conn.execute("""
        SELECT user_id, username, first_name, created_at
        FROM users
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    users = []

    for row in rows:
        users.append({
            "user_id": row["user_id"],
            "username": row["username"] or "",
            "first_name": row["first_name"] or "",
            "created_at": row["created_at"]
        })

    return jsonify({
        "success": True,
        "total_users": len(users),
        "users": users
    })


@app.get("/admin/support/chats")
def admin_support_chats():

    ADMIN_ID = 7136507076

    admin_id = request.args.get("admin_id", type=int)

    if admin_id != ADMIN_ID:
        return jsonify({"error": "Unauthorized"}), 403

    rows = get_support_chats()

    result = []

    for row in rows:
        result.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "uid": row["uid"],
            "problem": row["problem"],
            "message": row["message"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    return jsonify(result)


if __name__ == "__main__":

    print("🌙 TaskMoon API Started...")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
