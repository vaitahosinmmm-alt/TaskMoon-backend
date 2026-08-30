from flask import Flask, request, jsonify
from database import (
    get_user,
    create_user,
    get_coins,
    add_coins,
    add_referral_commission,
    get_referral_count,
    get_history
)

app = Flask(__name__)


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


if __name__ == "__main__":

    print("🌙 TaskMoon API Started...")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
