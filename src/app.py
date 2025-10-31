from flask import Flask, jsonify, request
from flask_cors import CORS
from .config import BOOKING_SERVICE_URL, PAYMENT_SERVICE_URL
from .clients import post_json, _auth_headers


app = Flask(__name__)
CORS(app)


@app.get("/healthz")
def healthz():
    """Liveness/health endpoint so clients can verify the service is up."""
    return jsonify({
        "status": "ok",
        "service": "booking-coordinator"
    }), 200


@app.post("/api/orch/bookings")
def orchestrate_booking():
    """Coordinate a booking flow: validate input, create a booking in
    ticket-booking, then create a Stripe payment intent via the payment
    service and return both payloads to the client."""
    data = request.get_json() or {}
    for f in ("event_id", "num_tickets", "user_id", "amount", "currency"):
        if f not in data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing {f}"}}), 400

    headers = _auth_headers(request.headers)

    # 1) Create booking
    book_url = f"{BOOKING_SERVICE_URL}/api/events/{data['event_id']}/book"
    book_res = post_json(book_url, {
        "num_tickets": data["num_tickets"],
        "user_id": data["user_id"],
    }, headers)

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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5003)

