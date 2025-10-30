import os
import time
import jwt
from .models import User, Event
from datetime import datetime, UTC, timedelta
from typing import Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
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

# -------------------------
# In-memory "DB"
# -------------------------
USERS_BY_EMAIL: dict[str, User] = {}
USERS_BY_ID: dict[str, User] = {}
EVENTS: dict[str, Event] = {}

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
    return jsonify({
        "status": "ok",
        "service": "admin-user-service",
        "users": len(USERS_BY_ID),
        "events": len(EVENTS),
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
    if email in USERS_BY_EMAIL:
        return jsonify({"error": "Email already exists"}), 409

    # First user can be ADMIN for convenience (optional)
    role = "ADMIN" if not USERS_BY_EMAIL else "USER"
    pwd_hash = generate_password_hash(data["password"])

    user = User.new(
        name=data["name"],
        email=email,
        role=role,
        password_hash=pwd_hash
    )

    USERS_BY_EMAIL[user.email] = user
    USERS_BY_ID[user.user_id] = user

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
    u = USERS_BY_EMAIL.get(email)
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
    u = USERS_BY_ID.get(uid)
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
    u = USERS_BY_ID.get(uid)
    if not u:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    if "name" in data and data["name"]:
        u.name = data["name"]
    if "password" in data and data["password"]:
        u.password_hash = generate_password_hash(data["password"])
    return jsonify({"message": "Profile updated"}), 200

# -------------------------
# ADMIN: view all users
# GET /api/admin/users   (Admin token)
# -> [{user_id, name, email, role}]
# -------------------------
@app.route("/api/admin/users", methods=["GET"])
@require_admin
def admin_list_users():
    return jsonify([u.to_public() for u in USERS_BY_ID.values()]), 200

# -------------------------
# ADMIN: delete user
# DELETE /api/admin/users/<id>  (Admin token)
# -> {message: "User deleted"}
# -------------------------
@app.route("/api/admin/users/<user_id>", methods=["DELETE"])
@require_admin
def admin_delete_user(user_id):
    u = USERS_BY_ID.pop(user_id, None)
    if not u:
        return jsonify({"error": "User not found"}), 404
    USERS_BY_EMAIL.pop(u.email, None)
    return jsonify({"message": "User deleted"}), 200


# -------------------------
# Seed for easy testing
# -------------------------
def _seed():
    # first registered user becomes ADMIN, but we also pre-seed one here
    admin_pwd = generate_password_hash("adminpass")
    admin = User.new("Demo Admin", "admin@example.com", "ADMIN", admin_pwd)
    USERS_BY_EMAIL[admin.email] = admin
    USERS_BY_ID[admin.user_id] = admin

    user_pwd = generate_password_hash("userpass")
    user = User.new("Demo User", "user@example.com", "USER", user_pwd)
    USERS_BY_EMAIL[user.email] = user
    USERS_BY_ID[user.user_id] = user

if __name__ == "__main__":
    _seed()
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, host="0.0.0.0", port=port)
