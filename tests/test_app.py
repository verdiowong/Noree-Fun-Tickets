from src.app import make_jwt
from src.models import User
from src.app import USERS_BY_EMAIL, USERS_BY_ID


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.get_json()
    assert body["service"] == "admin-user-service"
    assert body["users"] == 0
    assert body["events"] == 0


def test_register_and_login(client):
    payload = (
        {"name": "Test", "email": "test@gmail.com", "password": "password"}
    )
    r = client.post("/api/users/register", json=payload)
    assert r.status_code == 201
    reg = r.get_json()
    assert reg["email"] == "test@gmail.com"

    r2 = (
        client.post("/api/users/login", json=(
            {"email": "test@gmail.com", "password": "password"})
        )
    )
    assert r2.status_code == 200
    data = r2.get_json()
    assert "token" in data
    assert "user_id" in data


def test_register_missing_fields(client):
    # missing name
    r = (
        client.post("/api/users/register", json=(
            {"email": "a@b.com", "password": "x"})
        )
    )
    assert r.status_code == 400
    # missing email
    r = client.post("/api/users/register", json={"name": "A", "password": "x"})
    assert r.status_code == 400
    # missing password
    r = (
        client.post("/api/users/register", json=(
            {"name": "A", "email": "a@b.com"})
        )
    )
    assert r.status_code == 400


def test_register_duplicate_email(client):
    payload = {"name": "Dup", "email": "dup@example.com", "password": "p"}
    r1 = client.post("/api/users/register", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/users/register", json=payload)
    assert r2.status_code == 409


def test_login_invalid_credentials(client):
    # no such user
    r = client.post("/api/users/login", json={"email": "noone@example.com", "password": "x"})
    assert r.status_code == 401
    # register then wrong password
    client.post("/api/users/register", json={"name": "X", "email": "x@example.com", "password": "right"})
    r = client.post("/api/users/login", json={"email": "x@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_register_email_case_normalization(client):
    # register with uppercase email
    client.post("/api/users/register", json=(
        {"name": "Case", "email": "UPPER@EX.COM", "password": "p"})
    )
    # login with lowercase
    r = client.post("/api/users/login", json={"email": "upper@ex.com", "password": "p"})
    assert r.status_code == 200


def test_profile_requires_auth(client):
    r = client.get("/api/users/profile")
    assert r.status_code == 401


def test_get_profile_with_token(client):
    # create user directly in-memory and generate a token
    u = User.new("Lebron", "lebronjames@lakers.com", "USER", "irrelevant-hash")
    USERS_BY_EMAIL[u.email] = u
    USERS_BY_ID[u.user_id] = u

    token = make_jwt(u)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/users/profile", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["email"] == "lebronjames@lakers.com"


def test_update_profile_change_name_and_password(client):
    # register and login
    client.post("/api/users/register", json={"name": "Up", "email": "up@example.com", "password": "old"})
    r = client.post("/api/users/login", json={"email": "up@example.com", "password": "old"})
    token = r.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # update name and password
    r2 = (
        client.put("/api/users/profile", headers=headers, json={"name": "Updated", "password": "newpass"})
    )
    assert r2.status_code == 200

    # old password should fail
    r_old = client.post("/api/users/login", json={"email": "up@example.com", "password": "old"})
    assert r_old.status_code == 401
    # new password works
    r_new = (
        client.post("/api/users/login", json={"email": "up@example.com", "password": "newpass"})
    )
    assert r_new.status_code == 200


def test_update_profile_no_changes(client):
    client.post("/api/users/register", json={"name": "NoChange", "email": "nc@example.com", "password": "p"})
    r = client.post("/api/users/login", json={"email": "nc@example.com", "password": "p"})
    token = r.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    # send empty body
    r2 = client.put("/api/users/profile", headers=headers, json={})
    assert r2.status_code == 200


def test_profile_with_malformed_or_invalid_token(client):
    # create a user normally
    u = User.new("M", "m@example.com", "USER", "h")
    USERS_BY_EMAIL[u.email] = u
    USERS_BY_ID[u.user_id] = u
    # malformed token
    headers = {"Authorization": "Bearer not.a.real.token"}
    r = client.get("/api/users/profile", headers=headers)
    assert r.status_code == 401


def test_admin_endpoints_and_errors(client):
    # delete without auth -> 401
    r = client.delete(f"/api/admin/users/some-id")
    assert r.status_code == 401

    # non-admin cannot access admin list
    user = User.new("User", "user@example.com", "USER", "h")
    USERS_BY_EMAIL[user.email] = user
    USERS_BY_ID[user.user_id] = user
    token_user = make_jwt(user)
    h_user = {"Authorization": f"Bearer {token_user}"}
    r = client.get("/api/admin/users", headers=h_user)
    assert r.status_code == 403

    # admin can list and delete users
    admin = User.new("Admin", "admin@example.com", "ADMIN", "h")
    USERS_BY_EMAIL[admin.email] = admin
    USERS_BY_ID[admin.user_id] = admin

    # create user to delete
    target = User.new("Target", "t@example.com", "USER", "h")
    USERS_BY_EMAIL[target.email] = target
    USERS_BY_ID[target.user_id] = target

    token_admin = make_jwt(admin)
    h_admin = {"Authorization": f"Bearer {token_admin}"}
    r_list = client.get("/api/admin/users", headers=h_admin)
    assert r_list.status_code == 200
    assert any(u["email"] == "t@example.com" for u in r_list.get_json())

    # delete works
    r_del = client.delete(f"/api/admin/users/{target.user_id}", headers=h_admin)
    assert r_del.status_code == 200
    assert target.user_id not in USERS_BY_ID

    # deleting non-existent user returns 404
    r_not = client.delete(f"/api/admin/users/{target.user_id}", headers=h_admin)
    assert r_not.status_code == 404
