import os
import jwt
from models import User
from datetime import datetime, UTC, timedelta
from typing import Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
load_dotenv()
# -------------------------
# Config
# -------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_TTL_MIN = 60

app = Flask(__name__)
CORS(app)
AWS_REGION = os.getenv("AWS_REGION")
dynamodb = (
    boto3.resource('dynamodb', region_name=AWS_REGION) if AWS_REGION else None
)
users_table = dynamodb.Table('Users') if dynamodb else None

# -------------------------
# Persistence helpers (DynamoDB)

# -------------------------


def _user_to_item(u: User) -> dict:
    return {
        "user_id": u.user_id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "password_hash": u.password_hash,
        "created_at": u.created_at,
    }


def _item_to_user(item: dict) -> User:
    return User(
        user_id=item["user_id"],
        name=item["name"],
        email=item["email"],
        role=item.get("role", "USER"),
        password_hash=item.get("password_hash", ""),
        created_at=item.get("created_at")
    )


def _get_user_by_id(uid: str) -> Optional[User]:
    if not users_table:
        return None
    resp = users_table.get_item(Key={"user_id": uid})
    item = resp.get("Item")
    return _item_to_user(item) if item else None


def _get_user_by_email(email: str) -> Optional[User]:
    if not users_table:
        return None
    # Prefer a GSI on email; fallback to scan for demo
    resp = users_table.scan(
        FilterExpression=Key("email").eq(email)
    )
    items = resp.get("Items", [])
    return _item_to_user(items[0]) if items else None


def _put_user(u: User) -> None:
    if not users_table:
        return
    users_table.put_item(Item=_user_to_item(u))


def _delete_user(uid: str) -> bool:
    if not users_table:
        return False
    users_table.delete_item(Key={"user_id": uid})
    return True


# -------------------------
# Helpers: JWT + Auth
# -------------------------
def make_jwt(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "name": user.name,
        "role": user.role,      # 'ADMIN' or 'USER'
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TTL_MIN)).timestamp()),

    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_jwt_from_header() -> Optional[dict]:
    """Return decoded claims or None."""
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

        return claims
    except Exception:

        return None


def require_auth(f):
    def wrapper(*args, **kwargs):
        claims = decode_jwt_from_header()
        if not claims:
            return jsonify({"error": "Unauthorized"}), 401

        request.claims = claims  # attach to request context
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


def require_admin(f):
    def wrapper(*args, **kwargs):
        claims = decode_jwt_from_header()
        if not claims:
            return jsonify({"error": "Unauthorized"}), 401
        if claims.get("role") != "ADMIN":
            return jsonify({"error": "Forbidden"}), 403
        request.claims = claims
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


# -------------------------
# Health
# -------------------------
@app.route("/healthz", methods=["GET"])
def healthz():
    total_users = 0
    if users_table:
        try:
            scan = users_table.scan(Select='COUNT')
            total_users = scan.get('Count', 0)
        except Exception:
            total_users = -1
    return jsonify({
        "status": "ok",
        "service": "admin-user-service",
        "users": total_users,
        "time": datetime.now(UTC).isoformat()

    }), 200


# -------------------------
# API: Register new user
# POST /api/users/register  {name, email, password}
# -> {user_id, name, email, role}
# -------------------------
@app.route("/api/users/register", methods=["POST"])
def register_user():
    data = request.get_json(force=True, silent=True) or {}
    for field in ("name", "email", "password"):
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    email = data["email"].lower()
    if _get_user_by_email(email):
        return jsonify({"error": "Email already exists"}), 409

    # First user can be ADMIN for convenience (optional)
    # First user heuristic: if table empty, make ADMIN
    role = "USER"
    try:
        if users_table:
            cnt = users_table.scan(Select='COUNT').get('Count', 0)
            if cnt == 0:
                role = "ADMIN"
    except Exception:
        pass
    pwd_hash = generate_password_hash(data["password"])

    user = User.new(
        name=data["name"],
        email=email,
        role=role,
        password_hash=pwd_hash
    )

    _put_user(user)

    public = user.to_public()
    return jsonify(public), 201


# -------------------------
# API: Authenticate user (JWT)
# POST /api/users/login {email, password}
# -> {token, user_id, role}
# -------------------------
@app.route("/api/users/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").lower()
    pwd = data.get("password")
    u = _get_user_by_email(email)
    if not u or not check_password_hash(u.password_hash, pwd or ""):
        return jsonify({"error": "Invalid credentials"}), 401

    token = make_jwt(u)

    return jsonify({"token": token, "user_id": u.user_id, "role": u.role}), 200

# -------------------------
# API: Get user profile
# GET /api/users/profile   (Bearer <token>)

# -> {user_id, name, email, role, created_at}
# -------------------------


@app.route("/api/users/profile", methods=["GET"])
@require_auth
def get_profile():
    uid = request.claims["sub"]

    u = _get_user_by_id(uid)
    if not u:

        return jsonify({"error": "User not found"}), 404
    return jsonify(u.to_public()), 200

# -------------------------
# API: Update profile

# PUT /api/users/profile  {name?, password?}
# -> {message: "Profile updated"}
# -------------------------


@app.route("/api/users/profile", methods=["PUT"])
@require_auth
def update_profile():
    uid = request.claims["sub"]
    u = _get_user_by_id(uid)
    if not u:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    changed = False
    if "name" in data and data["name"]:
        u.name = data["name"]
        changed = True

    if "password" in data and data["password"]:
        u.password_hash = generate_password_hash(data["password"])
        changed = True

    if changed:
        _put_user(u)
    return jsonify({"message": "Profile updated"}), 200

# -------------------------

# ADMIN: view all users
# GET /api/admin/users   (Admin token)
# -> [{user_id, name, email, role}]


# -------------------------
@app.route("/api/admin/users", methods=["GET"])
@require_admin
def admin_list_users():
    users = []

    if users_table:
        resp = users_table.scan()
        users = (
            [_item_to_user(item).to_public() for item in resp.get('Items', [])]
        )
    return jsonify(users), 200


# -------------------------
# ADMIN: delete user
# DELETE /api/admin/users/<id>  (Admin token)
# -> {message: "User deleted"}
# -------------------------
@app.route("/api/admin/users/<user_id>", methods=["DELETE"])
@require_admin
def admin_delete_user(user_id):
    u = _get_user_by_id(user_id)
    if not u:
        return jsonify({"error": "User not found"}), 404
    _delete_user(user_id)
    return jsonify({"message": "User deleted"}), 200


# -------------------------
# Seed for easy testing
# -------------------------
def _seed():
    if not users_table:
        return
    # Seed two users if table empty
    try:
        cnt = users_table.scan(Select='COUNT').get('Count', 0)
        if cnt > 0:
            return
    except Exception:
        return
    admin_pwd = generate_password_hash("adminpass")
    admin = User.new("Demo Admin", "admin@example.com", "ADMIN", admin_pwd)
    _put_user(admin)
    user_pwd = generate_password_hash("userpass")
    user = User.new("Demo User", "user@example.com", "USER", user_pwd)
    _put_user(user)


if __name__ == "__main__":
    _seed()
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, host="0.0.0.0", port=port)
