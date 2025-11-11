from datetime import datetime, UTC
from typing import Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from .cognito_client import build_cognito_client, CognitoClient
from .cognito_auth import build_verifier_from_env, CognitoVerifier

# API_KEY = "secret_5ebe2294ecd0e0f08eab7690d2a6ee69"

# -------------------------
# Config
# -------------------------
app = Flask(__name__)
CORS(app)

# Initialize Cognito client and verifier
cognito_client: Optional[CognitoClient] = build_cognito_client()
cognito_verifier: Optional[CognitoVerifier] = build_verifier_from_env()

# -------------------------
# Helpers: Cognito User Management
# -------------------------


def _get_user_by_id(uid: str) -> Optional[dict]:
    """Get user by user ID (Cognito username)."""
    if not cognito_client:
        return None
    try:
        return cognito_client.get_user_by_id(uid)
    except Exception:
        return None


def _get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email."""
    if not cognito_client:
        return None
    try:
        return cognito_client.get_user_by_email(email)
    except Exception:
        return None


# -------------------------
# Helpers: JWT + Auth
# -------------------------
# def decode_jwt_from_header() -> Optional[dict]:
#     """Return decoded claims from Cognito JWT token or None."""
#     if not cognito_verifier:
#         # Fallback to old JWT if Cognito not configured
#         return None
    
#     auth_header = request.headers.get("Authorization", "")
#     claims, error = cognito_verifier.verify_authorization_header(auth_header)
#     if error:
#         return None
#     return claims


# def require_auth(f):
#     def wrapper(*args, **kwargs):
#         claims = decode_jwt_from_header()
#         if not claims:
#             return jsonify({"error": "Unauthorized"}), 401

#         request.claims = claims  # attach to request context
#         return f(*args, **kwargs)

#     wrapper.__name__ = f.__name__
#     return wrapper


# def require_admin(f):
#     def wrapper(*args, **kwargs):
#         claims = decode_jwt_from_header()
#         if not claims:
#             return jsonify({"error": "Unauthorized"}), 401
        
#         # Check role from Cognito groups or custom attribute
#         role = claims.get("role")
#         if not role:
#             # Fallback: extract from groups if role not set
#             groups = claims.get("cognito:groups", [])
#             if "admin" in groups:
#                 role = "ADMIN"
#             elif "user" in groups:
#                 role = "USER"
#             else:
#                 role = "USER"  # Default to USER if no groups
        
#         if role != "ADMIN":
#             return jsonify({"error": "Forbidden"}), 403
#         request.claims = claims
#         return f(*args, **kwargs)

#     wrapper.__name__ = f.__name__
#     return wrapper


# -------------------------
# Health
# -------------------------
@app.route("/healthz", methods=["GET"])
def healthz():
    total_users = 0
    if cognito_client:
        try:
            total_users = cognito_client.count_users()
        except Exception:
            total_users = -1
    return jsonify({
        "status": "ok",
        "service": "admin-user-service",
        "users": total_users,
        "time": datetime.now(UTC).isoformat(),
        "cognito_enabled": cognito_client is not None

    }), 200


# -------------------------
# API: Register new user
# POST /api/users/register  {name, email, password}
# -> {user_id, name, email, role}
# -------------------------
@app.route("/api/users/register", methods=["POST"])
def register_user():
    if not cognito_client:
        return jsonify({"error": "Cognito not configured"}), 500
    
    data = request.get_json(force=True, silent=True) or {}
    for field in ("name", "email", "password"):
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    email = data["email"].lower()
    
    # Check if user already exists
    existing_user = _get_user_by_email(email)
    if existing_user:
        return jsonify({"error": "Email already exists"}), 409

    # Determine role: first user becomes ADMIN
    role = "USER"
    try:
        user_count = cognito_client.count_users()
        if user_count == 0:
            role = "ADMIN"
    except Exception:
        pass

    try:
        # Create user in Cognito
        user = cognito_client.create_user(
            email=email,
            name=data["name"],
            password=data["password"],
            role=role
        )
        
        # Return public user info (without sensitive data)
        return jsonify({
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "created_at": user["created_at"]
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500


# -------------------------
# API: Authenticate user (JWT)
# POST /api/users/login {email, password}
# -> {token, user_id, role}
# -------------------------
@app.route("/api/users/login", methods=["POST"])
def login():
    if not cognito_client:
        return jsonify({"error": "Cognito not configured"}), 500
    
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").lower()
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    try:
        # Authenticate with Cognito
        result = cognito_client.authenticate_user(email=email, password=password)
        
        return jsonify({
            "token": result["token"],
            "user_id": result["user_id"],
            "role": result["role"]
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500

# -------------------------
# API: Get user profile
# GET /api/users/profile   (Bearer <token>)

# -> {user_id, name, email, role, created_at}
# -------------------------


@app.route("/api/users/profile", methods=["GET"])
# @require_auth
def get_profile():
    uid = request.claims.get("sub") or request.claims.get("username")
    if not uid:
        return jsonify({"error": "Invalid token"}), 401

    user = _get_user_by_id(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Return public user info
    return jsonify({
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"]
    }), 200

# -------------------------
# API: Update profile

# PUT /api/users/profile  {name?, password?}
# -> {message: "Profile updated"}
# -------------------------


@app.route("/api/users/profile", methods=["PUT"])
# @require_auth
def update_profile():
    if not cognito_client:
        return jsonify({"error": "Cognito not configured"}), 500
    
    uid = request.claims.get("sub") or request.claims.get("username")
    if not uid:
        return jsonify({"error": "Invalid token"}), 401

    user = _get_user_by_id(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    email = user["email"]
    
    try:
        # Update user in Cognito
        cognito_client.update_user(
            email=email,
            name=data.get("name"),
            password=data.get("password"),
            role=None  # Don't allow users to change their own role
        )
        return jsonify({"message": "Profile updated"}), 200
    except Exception as e:
        return jsonify({"error": f"Update failed: {str(e)}"}), 500

# -------------------------

# ADMIN: view all users
# GET /api/admin/users   (Admin token)
# -> [{user_id, name, email, role}]


# -------------------------
@app.route("/api/admin/users", methods=["GET"])
# @require_admin
def admin_list_users():
    if not cognito_client:
        return jsonify({"error": "Cognito not configured"}), 500
    
    try:
        users = cognito_client.list_users(limit=100)
        # Return public user info
        public_users = [{
            "user_id": u["user_id"],
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "created_at": u["created_at"]
        } for u in users]
        return jsonify(public_users), 200
    except Exception as e:
        return jsonify({"error": f"Failed to list users: {str(e)}"}), 500


# -------------------------
# ADMIN: delete user
# DELETE /api/admin/users/<id>  (Admin token)
# -> {message: "User deleted"}
# -------------------------
@app.route("/api/admin/users/<user_id>", methods=["DELETE"])
# @require_admin
def admin_delete_user(user_id):
    if not cognito_client:
        return jsonify({"error": "Cognito not configured"}), 500
    
    user = _get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    try:
        cognito_client.delete_user(user["email"])
        return jsonify({"message": "User deleted"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to delete user: {str(e)}"}), 500


# -------------------------
# Seed for easy testing (Cognito)
# -------------------------
def _seed():
    if not cognito_client:
        return
    # Seed two users if User Pool is empty
    try:
        user_count = cognito_client.count_users()
        if user_count > 0:
            return
    except Exception:
        return
    
    try:
        # Create admin user
        cognito_client.create_user(
            email="admin@example.com",
            name="Demo Admin",
            password="AdminPass123!",
            role="ADMIN"
        )
        # Create regular user
        cognito_client.create_user(
            email="user@example.com",
            name="Demo User",
            password="UserPass123!",
            role="USER"
        )
    except Exception as e:
        print(f"Warning: Could not seed users: {e}")


if __name__ == "__main__":
    _seed()
    app.run(debug=True, host="0.0.0.0", port=8081)
