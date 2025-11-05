from flask import Flask, request, jsonify
import os
import stripe
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key


AWS_REGION = os.environ.get("AWS_REGION")
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
table = dynamodb.Table('payments')

app = Flask(__name__)

# Set your Stripe secret key
# In production, you’d store this securely in environment variables



# ---- Helper: replace this with your real DB lookup if you persist mapping ----
def get_payment_intent_id(booking_id):
    try:
        # Query DynamoDB for the given booking_id (must be a partition key)
        response = table.query(
            KeyConditionExpression=Key("booking_id").eq(booking_id)
        )
        items = response.get("Items", [])
        
        if not items:
            return None  # no matching record found

        # Return the payment_intent_id from the first matching item
        return items[0].get("payment_intent_id")

    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        return None


# --- 1. Create Stripe payment intent ---
@app.route("/api/payments/create-intent", methods=["POST"])
def create_payment_intent():
    data = request.get_json()
    required_fields = ["booking_id", "amount", "currency"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # Create payment intent via Stripe API
        intent = stripe.PaymentIntent.create(
            amount=int(float(data["amount"]) * 100),  # Convert to cents
            currency=data["currency"],
            payment_method_types=["card"],
            metadata={"booking_id": data["booking_id"]},
        )

        status = intent.status.upper()
        if status != "SUCCEEDED":
            # Store initial payment record in DynamoDB
            amount_dollars = (Decimal(intent.amount) / Decimal(100))
            table.put_item(Item={
                'payment_id': intent.id,
                'booking_id': intent.metadata.get("booking_id", "unknown"),
                'amount': amount_dollars,
                'currency': intent.currency.upper(),
                'status': "pending",
                'created_at': intent.created
            })

        return jsonify({
            "client_secret": intent.client_secret,
            "payment_id": intent.id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 2. Confirm payment via Stripe ---
@app.route("/api/payments/confirm", methods=["POST"])
def confirm_payment():
    data = request.get_json()
    required_fields = ["payment_id", "stripe_token"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # Confirm the payment with the token (simulated confirmation)
        payment = stripe.PaymentIntent.confirm(
            data["payment_id"],
            payment_method=data["stripe_token"]
        )

        status = payment.status.upper()
        result = "SUCCESS" if status == "SUCCEEDED" else "FAILED"
    
        if result == "SUCCESS":
            # add payment record to DynamoDB
            table.update_item(
                Key={'payment_id': data["payment_id"]},
                UpdateExpression="SET #st = :s",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":s": "completed"}
            )

        return jsonify({"payment_id": data["payment_id"], "status": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 3. Process refund ---
@app.route("/api/payments/refund/<booking_id>", methods=["POST"])
def process_refund(booking_id):
    # Auth check (keep your existing logic)
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid authorization token"}), 401

    try:
        data = request.get_json() or {}

        #Try DB lookup first (recommended)
        payment_id = get_payment_intent_id(booking_id)

        if not payment_id:
            return jsonify({"error": "No payment_intent found for booking_id"}), 404

        # 3) Create refund: full (no amount) or partial (amount provided in dollars)
        if "amount" in data and data["amount"] is not None:
            # Accept amount from client as dollars (float/int) -> convert to cents
            try:
                amount_cents = int(round(float(data["amount"]) * 100))
            except Exception:
                return jsonify({"error": "Invalid amount value. Send numeric dollars, e.g. 25.00"}), 400

            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=amount_cents,
                reason="requested_by_customer"
            )
        else:
            # full refund
            refund = stripe.Refund.create(payment_intent=payment_id)
        
        # Delete Item from DynamoDB after refund
        table.delete_item(Key={"payment_id": payment_id})
        
        # Return simplified refund info
        return jsonify({
            "refund_id": refund.id,
            "status": refund.status,
            "amount": refund.amount/100,  # Convert back to dollars
            "currency": refund.currency,
            "payment_intent": getattr(refund, "payment_intent", None)
        }), 200

    except stripe.StripeError as e:
        # Extract Stripe error details where possible
        err = getattr(e, "json_body", None)
        err_msg = e.user_message if hasattr(e, "user_message") else str(e)
        return jsonify({
            "error": "stripe_error",
            "message": err_msg,
            "details": err
        }), 400

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500
    

# --- 4. Check payment status ---
@app.route("/api/bookings/status/<id>", methods=["GET"])
def check_payment_status(id):
    #payment_id = find_payment_intent_by_booking(booking_id)
    payment_id  = "pi_3SITcmRwIyBNO0h915CYU5qe"  # Mocked for demo
    try:
        # Retrieve from Stripe (or mock if not found)
        payment = stripe.PaymentIntent.retrieve(payment_id)
        booking_id = payment.metadata.get("booking_id", "unknown")

        return jsonify({
            "payment_id": id,
            "booking_id": booking_id,
            "status": payment.status.upper()
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
