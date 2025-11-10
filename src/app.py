import json
import uuid
import boto3
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import (
    ADMIN_SERVICE_URL, BOOKING_SERVICE_URL, PAYMENT_SERVICE_URL, 
    NOTIFICATION_SERVICE_URL, SQS_QUEUE_URL, AWS_REGION
)
from clients import post_json, _auth_headers, request_json
from auth import build_verifier_from_env


app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://main.d1j4ffe4p8np66.amplifyapp.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

_verifier = build_verifier_from_env()

# Initialize SQS client
sqs = boto3.client('sqs', region_name=AWS_REGION)


@app.get("/healthz")
def healthz():
    """Liveness/health endpoint so clients can verify the service is up."""
    print("Health check LATEST!!!")
    return jsonify({
        "status": "ok",
        "service": "booking-coordinator"
    }), 200


# @app.post("/api/orch/bookings")
# def orchestrate_booking():
#     """
#     Enqueue booking request to SQS FIFO for FCFS processing.
#     Returns a request_id that can be used to check status.
#     """
#     # Auth check
#     claims = None
#     if _verifier:
#         claims, err = _verifier.verify_authorization_header(request.headers.get("Authorization"))
#         if err:
#             return jsonify({"error": {"code": "UNAUTHORIZED", "message": err}}), 401

#     data = request.get_json() or {}
#     for f in ("event_id", "num_tickets", "user_id", "amount", "currency"):
#         if f not in data:
#             return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing {f}"}}), 400

#     # Generate unique request ID
#     request_id = str(uuid.uuid4())
#     effective_user_id = (claims or {}).get("sub") if claims else data.get("user_id")
    
#     # Prepare message for SQS
#     message_body = {
#         "request_id": request_id,
#         "event_id": data["event_id"],
#         "num_tickets": data["num_tickets"],
#         "user_id": effective_user_id,
#         "amount": data["amount"],
#         "currency": data["currency"],
#         "seats": data.get("seats"),  # Optional
#         # Don't store auth header - worker will use IAM roles
#     }

#     try:
#         # Send message to SQS FIFO
#         # CRITICAL: MessageGroupId and MessageDeduplicationId are REQUIRED for FIFO
#         response = sqs.send_message(
#             QueueUrl=SQS_QUEUE_URL,
#             MessageBody=json.dumps(message_body),
#             MessageGroupId=str(data["event_id"]),  # REQUIRED: Ensures FCFS per event
#             MessageDeduplicationId=request_id,  # REQUIRED: Prevents duplicates
#             MessageAttributes={
#                 'RequestId': {
#                     'DataType': 'String',
#                     'StringValue': request_id
#                 },
#                 'EventId': {
#                     'DataType': 'String',
#                     'StringValue': str(data["event_id"])
#                 },
#                 'UserId': {
#                     'DataType': 'String',
#                     'StringValue': str(effective_user_id)
#                 }
#             }
#         )
        
#         return jsonify({
#             "request_id": request_id,
#             "status": "queued",
#             "message": "Booking request has been queued for processing",
#             "sqs_message_id": response.get('MessageId')
#         }), 202  # 202 Accepted
        
#     except Exception as e:
#         print(f"SQS Error: {str(e)}")
#         return jsonify({
#             "error": {
#                 "code": "QUEUE_ERROR",
#                 "message": f"Failed to queue booking: {str(e)}"
#             }
#         }), 500


@app.get("/api/orch/bookings/status/<request_id>")
def check_booking_status(request_id: str):
    """
    Check the status of a queued booking request from DynamoDB.
    """
    from decimal import Decimal
    from botocore.exceptions import ClientError
    
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    status_table = dynamodb.Table('booking-requests-status')
    
    try:
        response = status_table.get_item(Key={'request_id': request_id})
        
        if 'Item' not in response:
            return jsonify({
                "request_id": request_id,
                "status": "not_found",
                "message": "Request not found. It may still be queued or the worker hasn't processed it yet."
            }), 404
        
        item = response['Item']
        
        # Convert Decimal to float for JSON
        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj) if obj % 1 else int(obj)
            if isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_decimals(i) for i in obj]
            return obj
        
        return jsonify({
            "request_id": request_id,
            "status": item.get('status'),
            "data": convert_decimals(item.get('data', {})),
            "updated_at": item.get('updated_at')
        }), 200
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'ResourceNotFoundException':
            # Table doesn't exist yet - return a helpful message
            return jsonify({
                "request_id": request_id,
                "status": "table_not_created",
                "message": "Status table not created yet. Run create_status_table.py to create it."
            }), 503  # Service Unavailable
        else:
            print(f"Error checking status: {str(e)}")
            return jsonify({
                "error": {
                    "code": "STATUS_ERROR",
                    "message": str(e)
                }
            }), 500
    except Exception as e:
        print(f"Error checking status: {str(e)}")
        return jsonify({
            "error": {
                "code": "STATUS_ERROR",
                "message": str(e)
            }
        }), 500


@app.post("/api/orch/bookings")
def orchestrate_booking_sync():
    """
    Synchronous booking endpoint (original implementation).
    Use this for testing or immediate processing.
    """
    print("Synchronous booking endpoint called")
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
    effective_user_id = (claims or {}).get("sub") if claims else data.get("user_id")
    
    # Process booking immediately (original logic)
    return _process_booking(data, effective_user_id, headers)


def _process_booking(data, user_id, headers):
    """Internal function to process a booking (used by sync endpoint and worker)."""
    # 1) Create booking
    book_url = f"{BOOKING_SERVICE_URL}/api/events/{data['event_id']}/book"
    booking_data = {
        "num_tickets": data["num_tickets"],
        "user_id": user_id,
    }
    if "seats" in data and data["seats"]:
        booking_data["seats"] = data["seats"]

    print("Booking URL:", book_url)
    print("Booking data:", booking_data)
    print("Headers:", headers)
    
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

    print("PAYMENT URL:", pay_url)
    print("PAYMENT REQUEST:", {
        "booking_id": booking_id,
        "amount": data["amount"],
        "currency": data["currency"],
    })
    print("PAYMENT RESPONSE:", pay_res.status_code, pay_res.text)


    if pay_res.status_code >= 400:
        return jsonify({"error": {"code": "PAYMENT_INTENT_FAILED", "message": pay_res.text}}), 400

    payment = pay_res.json()
    print("PAYMENT SERVICE RESPONSE JSON:", payment)
    return jsonify({
        "success": True,
        "booking": booking,
        "payment": {
        "payment_id": payment.get("payment_id") or payment.get("paymentId"),
        "client_secret": payment.get("client_secret") or payment.get("clientSecret"),
            "amount": payment.get("amount"),
            "currency": payment.get("currency")
        }
    }), 201


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
    Verifies the payment intent with Stripe."""
    data = request.get_json() or {}
    for f in ("payment_id", "booking_id"):
        if f not in data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing {f}"}}), 400

    headers = _auth_headers(request.headers)
    url = f"{PAYMENT_SERVICE_URL}/api/payments/verify-intent"
    res = post_json(url, {"payment_id": data["payment_id"], "booking_id": data["booking_id"]}, headers)
    if res.status_code >= 400:
        return jsonify({"error": {"code": "PAYMENT_CONFIRM_FAILED", "message": res.text}}), 400
    return jsonify(res.json()), 200

# @app.post("/api/orch/payments/confirm")
# def orchestrate_payment_confirm():
#     """Confirm a pending payment by forwarding to the payment service.
#     Expects a Stripe test PaymentMethod id (e.g. pm_card_visa)."""
#     data = request.get_json() or {}
#     for f in ("payment_id", "stripe_token"):
#         if f not in data:
#             return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing {f}"}}), 400

#     headers = _auth_headers(request.headers)
#     url = f"{PAYMENT_SERVICE_URL}/api/payments/confirm"
#     res = post_json(url, {"payment_id": data["payment_id"], "stripe_token": data["stripe_token"]}, headers)
#     if res.status_code >= 400:
#         return jsonify({"error": {"code": "PAYMENT_CONFIRM_FAILED", "message": res.text}}), 400
#     return jsonify(res.json()), 200


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


@app.post("/internal/scheduler-trigger")
def scheduler_trigger():
    """
    Endpoint for EventBridge Scheduler to invoke periodically.
    This can trigger internal orchestrations or background checks.
    """
    print("Scheduler trigger received!")
    payload = request.get_json(silent=True) or {}
    print("Payload:", payload)

    # Example: Call a microservice or perform a periodic check
    # Example below just pings the booking service health endpoint:
    try:
        health_url = f"{BOOKING_SERVICE_URL}/healthz"
        res = request_json("GET", health_url, headers={})
        print("Booking service health:", res.status_code)
    except Exception as e:
        print("Health check failed:", e)

    return jsonify({"status": "triggered", "source": "eventbridge", "payload": payload}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)

