from datetime import datetime, timezone
from decimal import Decimal
import os

import boto3
from boto3.dynamodb.conditions import Key
from flask import Flask, jsonify, request
from flask_cors import CORS
import stripe


AWS_REGION = os.environ.get("AWS_REGION")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table("payments")

stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__)
CORS(app)


def get_payment_intent_id(booking_id: str):
    """Fetch the Stripe payment_intent_id for a booking from DynamoDB."""
    try:
        response = table.query(
            KeyConditionExpression=Key("booking_id").eq(booking_id)
        )
        items = response.get("Items", [])
        if not items:
            return None
        return items[0].get("payment_intent_id")
    except Exception as exc:
        print(f"Error querying DynamoDB: {exc}")
        return None


@app.route("/health", methods=["GET"])
def health_check():
    """Simple health endpoint."""
    return jsonify({"status": "Payment service is healthy"}), 200


@app.route("/api/payments/create-intent", methods=["POST"])
def create_payment_intent():
    """Create a Stripe PaymentIntent and store a pending record."""
    data = request.get_json()
    required_fields = ["booking_id", "amount", "currency"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(float(data["amount"]) * 100),
            currency=data["currency"],
            payment_method_types=["card"],
            metadata={"booking_id": data["booking_id"]},
        )

        # Store initial payment record in DynamoDB
        # Note: booking_id is the partition key for easy lookup
        amount_dollars = (Decimal(intent.amount) / Decimal(100))

        if intent.status.upper() == "SUCCEEDED":
            amount_dollars = Decimal(intent.amount) / Decimal(100)
            table.put_item(
                Item={
                    "payment_id": intent.id,
                    "booking_id": intent.metadata.get("booking_id", "unknown"),
                    "amount": amount_dollars,
                    "currency": intent.currency.upper(),
                    "status": intent.status,
                    "created_at": datetime.fromtimestamp(intent.created, tz=timezone.utc).isoformat()
                }
            )

        return jsonify(
            {"client_secret": intent.client_secret, "payment_id": intent.id}
        ), 200

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/payments/verify-intent", methods=["POST"])
def verify_payment_intent():
    """Verify with Stripe and mark payment as completed."""
    data = request.get_json()
    payment_id = data.get("payment_id")
    booking_id = data.get("booking_id")

    if not payment_id or not booking_id:
        return jsonify({"error": "Missing payment_id or booking_id"}), 400

    try:
        intent = stripe.PaymentIntent.retrieve(payment_id)
        if intent.status == "succeeded":
            table.put_item(
                Item={
                    "payment_id": intent.id,
                    "booking_id": booking_id,
                    "amount": Decimal(intent.amount) / Decimal(100),
                    "currency": intent.currency.upper(),
                    "status": "completed",
                    "created_at": str(datetime.utcnow()),
                }
            )
            return jsonify({"message": "Payment verified and recorded"}), 200

        error_msg = (
            f"Payment not succeeded, current status: {intent.status}"
        )
        return jsonify({"error": error_msg}), 400

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/payments/refund/<booking_id>", methods=["POST"])
def process_refund(booking_id):
    """Process a refund for a booking."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify(
            {"error": "Missing or invalid authorization token"}
        ), 401

    try:
        data = request.get_json() or {}
        payment_id = get_payment_intent_id(booking_id)
        if not payment_id:
            return jsonify(
                {"error": "No payment_intent found for booking_id"}
            ), 404

        if "amount" in data and data["amount"] is not None:
            try:
                amount_cents = int(round(float(data["amount"]) * 100))
            except Exception:
                return jsonify(
                    {
                        "error": (
                            "Invalid amount value. Send numeric dollars, "
                            "e.g. 25.00"
                        )
                    }
                ), 400
            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=amount_cents,
                reason="requested_by_customer",
            )
        else:
            refund = stripe.Refund.create(payment_intent=payment_id)

        # Delete Item from DynamoDB after refund
        table.delete_item(Key={"booking_id": booking_id})

        # Return simplified refund info
        return jsonify({
            "refund_id": refund.id,
            "status": refund.status,
            "amount": refund.amount/100,  # Convert back to dollars
            "currency": refund.currency,
            "payment_intent": getattr(refund, "payment_intent", None)
        }), 200

    except stripe.StripeError as exc:
        err = getattr(exc, "json_body", None)
        err_msg = getattr(exc, "user_message", str(exc))
        return jsonify(
            {"error": "stripe_error", "message": err_msg, "details": err}
        ), 400

    except Exception as exc:
        return jsonify({"error": "internal_error", "message": str(exc)}), 500


@app.route("/api/bookings/status/<payment_id>", methods=["GET"])
def check_payment_status(payment_id):
    """Retrieve the current status of a PaymentIntent."""
    try:
        payment = stripe.PaymentIntent.retrieve(payment_id)
        booking_id = payment.metadata.get("booking_id", "unknown")
        return (
            jsonify(
                {
                    "payment_id": payment_id,
                    "booking_id": booking_id,
                    "status": payment.status.upper(),
                }
            ),
            200,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/healthz", methods=["GET"])
def healthz():
    """Liveness endpoint."""
    print("Health check from Payment Service!")
    return jsonify({"status": "ok", "service": "payment"}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8083)
