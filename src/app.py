from flask import Flask, jsonify, request
from flask_cors import CORS
from config import ADMIN_SERVICE_URL, BOOKING_SERVICE_URL, PAYMENT_SERVICE_URL, NOTIFICATION_SERVICE_URL
from clients import post_json, _auth_headers, request_json
from auth import build_verifier_from_env


app = Flask(__name__)
CORS(app)
_verifier = build_verifier_from_env()


@app.get("/healthz")
def healthz():
    """Liveness/health endpoint so clients can verify the service is up."""
    print("Health check LATEST!!!")
    return jsonify({
        "status": "ok",
        "service": "booking-coordinator"
    }), 200


@app.post("/api/orch/bookings")
def orchestrate_booking():
    """Coordinate a booking flow: validate input, create a booking in
    ticket-booking, then create a Stripe payment intent via the payment
    service and return both payloads to the client."""
    # Dev mode: If Cognito is not configured, skip JWT enforcement
    claims = None
    if _verifier:
        claims, err = _verifier.verify_authorization_header(request.headers.get("Authorization"))
        if err:
            return jsonify({"error": {"code": "UNAUTHORIZED", "message": err}}), 401

    data = request.get_json() or {}
    for f in ("event_id", "num_tickets", "user_id", "amount", "currency"):
        if f not in data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing {f}"}}), 400

    headers = _auth_headers(request.headers)

    # 1) Create booking
    book_url = f"{BOOKING_SERVICE_URL}/api/events/{data['event_id']}/book"
    # Use token subject when available; otherwise fall back to client value (dev)
    effective_user_id = (claims or {}).get("sub") if claims else data.get("user_id")
    booking_data = {
        "num_tickets": data["num_tickets"],
        "user_id": effective_user_id,
    }
    # Include seats array if provided
    if "seats" in data:
        booking_data["seats"] = data["seats"]
    
    book_res = post_json(book_url, booking_data, headers)

    if book_res.status_code >= 400:
        return jsonify({"error": {"code": "BOOKING_FAILED", "message": book_res.text}}), 400

    booking_payload = book_res.json()
    booking = booking_payload.get("booking") or booking_payload
    booking_id = booking.get("booking_id")
    if not booking_id:
        return jsonify({"error": {"code": "BOOKING_INVALID_RESPONSE", "message": "No booking_id returned"}}), 502

    # 2) Create payment intent
    pay_url = f"{PAYMENT_SERVICE_URL}/api/payments/create-intent"
    pay_res = post_json(pay_url, {
        "booking_id": booking_id,
        "amount": data["amount"],
        "currency": data["currency"],
    }, headers)

    if pay_res.status_code >= 400:
        return jsonify({"error": {"code": "PAYMENT_INTENT_FAILED", "message": pay_res.text}}), 400

    payment = pay_res.json()
    return jsonify({"booking": booking, "payment": payment}), 201


@app.post("/api/orch/bookings/notify")
def orchestrate_booking_and_notify():
    """Create booking -> create payment intent -> send notifications.
    Input JSON:
      required: event_id, num_tickets, user_id, amount, currency
      optional notification fields:
        email, subject, message, phone_number
    Behavior: notification failures do not cancel booking/payment; returns warnings.
    """
    # Dev mode: If Cognito is not configured, skip JWT enforcement
    claims = None
    if _verifier:
        claims, err = _verifier.verify_authorization_header(request.headers.get("Authorization"))
        if err:
            return jsonify({"error": {"code": "UNAUTHORIZED", "message": err}}), 401

    data = request.get_json() or {}
    for f in ("event_id", "num_tickets", "user_id", "amount", "currency"):
        if f not in data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing {f}"}}), 400

    headers = _auth_headers(request.headers)

    # 1) Create booking
    book_url = f"{BOOKING_SERVICE_URL}/api/events/{data['event_id']}/book"
    effective_user_id = (claims or {}).get("sub") if claims else data.get("user_id")
    booking_data = {
        "num_tickets": data["num_tickets"],
        "user_id": effective_user_id,
    }
    # Include seats array if provided
    if "seats" in data:
        booking_data["seats"] = data["seats"]
    
    book_res = post_json(book_url, booking_data, headers)
    if book_res.status_code >= 400:
        return jsonify({"error": {"code": "BOOKING_FAILED", "message": book_res.text}}), 400

    booking_payload = book_res.json()
    booking = booking_payload.get("booking") or booking_payload
    booking_id = booking.get("booking_id")
    if not booking_id:
        return jsonify({"error": {"code": "BOOKING_INVALID_RESPONSE", "message": "No booking_id returned"}}), 502

    # 2) Create payment intent
    pay_url = f"{PAYMENT_SERVICE_URL}/api/payments/create-intent"
    pay_res = post_json(pay_url, {
        "booking_id": booking_id,
        "amount": data["amount"],
        "currency": data["currency"],
    }, headers)
    if pay_res.status_code >= 400:
        return jsonify({"error": {"code": "PAYMENT_INTENT_FAILED", "message": pay_res.text}}), 400
    payment = pay_res.json()

    # 3) Notifications (optional)
    warnings = []
    try:
        # Email
        if data.get("email") and data.get("subject") and data.get("message"):
            email_url = f"{NOTIFICATION_SERVICE_URL}/api/notifications/email"
            email_payload = {
                "email": data["email"],
                "subject": data["subject"],
                "message": data["message"],
                "user_id": effective_user_id,
            }
            email_res = post_json(email_url, email_payload, headers)
            if email_res.status_code >= 400:
                warnings.append({"type": "email", "message": email_res.text})

        # SMS
        if data.get("phone_number") and data.get("message"):
            sms_url = f"{NOTIFICATION_SERVICE_URL}/api/notifications/sms"
            sms_payload = {
                "user_id": effective_user_id,
                "phone_number": data["phone_number"],
                "message": data["message"],
            }
            sms_res = post_json(sms_url, sms_payload, headers)
            if sms_res.status_code >= 400:
                warnings.append({"type": "sms", "message": sms_res.text})
    except Exception as e:
        warnings.append({"type": "notifications", "message": str(e)})

    resp = {"booking": booking, "payment": payment}
    if warnings:
        resp["warnings"] = warnings
    return jsonify(resp), 201

@app.post("/api/orch/payments/confirm")
def orchestrate_payment_confirm():
    """Confirm a pending payment by forwarding to the payment service.
    Expects a Stripe test PaymentMethod id (e.g. pm_card_visa)."""
    data = request.get_json() or {}
    for f in ("payment_id", "stripe_token"):
        if f not in data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing {f}"}}), 400

    headers = _auth_headers(request.headers)
    url = f"{PAYMENT_SERVICE_URL}/api/payments/confirm"
    res = post_json(url, {"payment_id": data["payment_id"], "stripe_token": data["stripe_token"]}, headers)
    if res.status_code >= 400:
        return jsonify({"error": {"code": "PAYMENT_CONFIRM_FAILED", "message": res.text}}), 400
    return jsonify(res.json()), 200


@app.post("/api/orch/payments/refund/<booking_id>")
def orchestrate_refund(booking_id: str):
    """Process a refund for a booking by delegating to the payment service.
    Accepts an optional amount to perform a partial refund."""
    headers = _auth_headers(request.headers)
    data = request.get_json() or {}
    url = f"{PAYMENT_SERVICE_URL}/api/payments/refund/{booking_id}"
    res = post_json(url, data, headers)
    if res.status_code >= 400:
        return jsonify({"error": {"code": "REFUND_FAILED", "message": res.text}}), 400
    return jsonify(res.json()), 200


# --- Generic orchestrator (frontend gateway) ---
@app.post("/api/orchestrator")
def proxy_to_service():
    """General-purpose gateway: routes requests to target microservice.
    Body format: { service, endpoint, method, data }
    - service: one of [admin, events, bookings, payment, notifications]
    - endpoint: path beginning with '/'
    - method: HTTP verb to use when calling target service (default GET)
    - data: JSON payload for non-GET methods; for GET, sent as query params
    """
    payload = request.get_json(silent=True) or {}
    service = (payload.get("service") or "").strip().lower()
    endpoint = payload.get("endpoint") or ""
    method = (payload.get("method") or "GET").upper()
    data = payload.get("data")

    allow_unauth = (service == "admin" and endpoint in ("/api/users/login", "/api/users/register"))

    claims = None
    if not allow_unauth and _verifier:
        claims, err = _verifier.verify_authorization_header(request.headers.get("Authorization"))
        if err:
            return jsonify({"success": False, "message": err}), 401
        # Enforce admin-only for admin endpoints when auth is enabled
        if endpoint.startswith("/api/admin"):
            groups = claims.get("cognito:groups") or []
            role_claim = claims.get("role")
            is_admin = (isinstance(groups, list) and ("ADMIN" in groups)) or role_claim == "ADMIN"
            if not is_admin:
                return jsonify({"success": False, "message": "Forbidden: admin role required"}), 403

    if not service or not endpoint:
        return jsonify({
            "success": False,
            "message": "Missing required fields: service, endpoint"
        }), 400

    # Map logical service names to base URLs
    base_url_map = {
        "admin": ADMIN_SERVICE_URL,
        "payment": PAYMENT_SERVICE_URL,
        "notifications": NOTIFICATION_SERVICE_URL,
        # events and bookings are both served by ticket-booking service
        "events": BOOKING_SERVICE_URL,
        "bookings": BOOKING_SERVICE_URL,
        # backward-compat aliases
        "booking": BOOKING_SERVICE_URL,
    }

    base = base_url_map.get(service)
    if not base:
        return jsonify({
            "success": False,
            "message": f"Unknown service: {service}"
        }), 400

    print("service called:", service)
    print("endpoint called:", endpoint)
    print("method called:", method)
    print("url called:", f"{base}")
    print("target_url called:", f"{base}{endpoint}")

    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    target_url = f"{base}{endpoint}"

    headers = _auth_headers(request.headers)
    # Inject user context for downstream services
    if not allow_unauth and _verifier and claims:
        headers["X-User-Id"] = claims.get("sub", "")
        roles = claims.get("cognito:groups") or []
        if isinstance(roles, list):
            headers["X-User-Roles"] = ",".join(roles)

    # For GET, treat data as query params; otherwise send JSON body
    params = data if (method == "GET" and isinstance(data, dict)) else None
    json_body = None if method == "GET" else data

    res = request_json(method, target_url, headers=headers, json=json_body, params=params)

    # Attempt to pass through JSON response; on non-JSON, wrap as text
    try:
        body = res.json()
    except Exception:
        body = {"message": res.text}

    status = res.status_code
    success = 200 <= status < 300
    return jsonify({
        "success": success,
        "data": body if success else None,
        "message": None if success else body.get("error") or body.get("message") or "Request failed"
    }), status

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)

