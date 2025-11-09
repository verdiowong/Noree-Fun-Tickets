import os
import requests
from urllib import response
import uuid
import boto3
from flask import Flask, request, jsonify
from twilio.rest import Client
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from datetime import datetime

app = Flask(__name__)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
MAILJET_API_KEY = os.environ.get("MAILJET_API_KEY")
MAILJET_SECRET_KEY = os.environ.get("MAILJET_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION")
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table_notifications = dynamodb.Table("notifications")
table_notification_reminders = dynamodb.Table("notificationS_reminder")


# Utility function to simulate sending a notification
def send_notification(notification_type, data):
    # In real usage: integrate with email/SMS/push APIs (e.g., SendGrid, Twilio, Firebase)
    notification_id = str(uuid.uuid4())
    status = "SENT"  # Simulate success
    print(f"[{notification_type.upper()}] Notification sent to user {data.get('user_id')}")
    return {"notification_id": notification_id, "status": status}


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "Notification service is healthy"}), 200


# --- 1. Send confirmation email ---
@app.route("/api/notifications/email", methods=["POST"])
def send_email():
    data = request.get_json()
    required_fields = ["email", "subject", "message"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    response = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
        json={
            "Messages": [{
                "From": {"Email": "vishnul.2023@smu.edu.sg", "Name": "Your App"},
                "To": [{"Email": data["email"]}],
                "Subject": data["subject"],
                "TextPart": data["message"]
            }]
        }
    )

    if response.status_code == 200:
        response = send_notification("email", data)
        notification_id = str(uuid.uuid4())
        table_notifications.put_item(
        Item={
                "notification_id": notification_id,
                "user_id": data.get("user_id", str(uuid.uuid4())),  # optional fallback
                "type": "EMAIL",
                "message": data["message"],
                "status": "SENT",
                "created_at": str(datetime.utcnow())
            }
        )
        return jsonify({"message": "Email sent successfully"}), 200
    else:
        return jsonify({"error": "Failed to send email"}), 500


# --- 2. Send SMS update ---
@app.route("/api/notifications/sms", methods=["POST"])
def send_sms():
    data = request.get_json()
    required_fields = ["user_id", "phone_number", "message"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=data["message"],
        from_='+16077033565',
        to=data["phone_number"]
    )
    
    notification_id = str(uuid.uuid4())
    table_notifications.put_item(
        Item={
            "notification_id": notification_id,
            "user_id": data["user_id"],
            "type": "SMS",
            "message": data["message"],
            "status": "SENT",
            "created_at": str(datetime.utcnow())
        }
    )

    response = send_notification("sms", data)
    return jsonify(response), 200


# --- 3. Send push notification ---
@app.route("/api/notifications/push", methods=["POST"])
def send_push():
    data = request.get_json()
    required_fields = ["user_id",
                       "notification_id",
                       "booking_id" 
                       "event_id",
                       "seats_id",
                       "notification_type",
                       "message",
                       "status",
                       "reminder_time",
                       "created_at"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    

    notification_id = str(uuid.uuid4())
    table_notifications.put_item(
        Item={
            "notification_id": notification_id,
            "user_id": data["user_id"],
            "type": "PUSH",
            "message": data["message"],
            "status": "SENT",
            "created_at": str(datetime.utcnow())
        }
    )

    response = send_notification("push", data)
    return jsonify(response), 200



@app.route("/api/notifications/setreminder", methods=["GET"])
def get_reminders():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing required field: user_id"}), 400

    try:
        response = table_notification_reminders.query(
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(user_id)
        )

        reminders = response.get("Items", [])
        
        # Convert Decimal to float/int for JSON serialization
        def convert_decimals(obj):
            if isinstance(obj, list):
                return [convert_decimals(i) for i in obj]
            elif isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            elif isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            return obj
        
        return jsonify(convert_decimals(reminders)), 200
    except Exception as e:
        # If index doesn't exist or no data for user, return empty array
        print(f"Error fetching reminders: {str(e)}")
        return jsonify([]), 200


# --- 4. Set reminder notification ---
@app.route("/api/notifications/setreminder", methods=["POST"])
def set_reminder():
    data = request.get_json()
    required_fields = [
        "user_id",
        "notification_id",
        "booking_id",
        "event_id",
        "seats_id",
        "notification_type",
        "message",
        "status",
        "reminder_time",
        "created_at",
        "hide"
    ]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    

    reminder_id = str(uuid.uuid4())
    table_notification_reminders.put_item(
        Item={
            "reminder_id": reminder_id,
            "notification_id": data["notification_id"],
            "user_id": data["user_id"],
            "booking_id": data["booking_id"],
            "event_id": data["event_id"],
            "seat_ids": data["seats_id"],
            "type": data["notification_type"],
            "message": data["message"],
            "status": data["status"],
            "reminder_time": data["reminder_time"],
            "created_at": str(datetime.utcnow()),
            "hide": data["hide"]
        }
    )

    response = send_notification("reminder", data)
    return jsonify(response), 200


@app.route("/api/notifications/setreminder/<reminder_id>", methods=["PATCH"])
def update_reminder(reminder_id):
    data = request.get_json()
    update_expression = "SET "
    expression_attribute_values = {}
    first = True

    for key, value in data.items():
        if not first:
            update_expression += ", "
        update_expression += f"{key} = :{key}"
        expression_attribute_values[f":{key}"] = value
        first = False

    try:
        table_notification_reminders.update_item(
            Key={"reminder_id": reminder_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    response = {
        "reminder_id": reminder_id,
        "updated_fields": data
    }
    return jsonify(response), 200


@app.get("/health")
def healthz():
    """Liveness/health endpoint so clients can verify the service is up."""
    print("Health check from Notification Service!")
    return jsonify({
        "status": "ok",
        "service": "notification"
    }), 200



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8082)
