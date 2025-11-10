from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, UTC
import uuid
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import os


app = Flask(__name__)
CORS(app)


# Initialise DynamoDB
# DynamoDB configuration - supports both local and AWS
def get_dynamodb_resource():
    """Get DynamoDB resource based on environment"""
    endpoint_url = os.environ.get('DYNAMODB_ENDPOINT')

    if endpoint_url:
        # Use local DynamoDB (for testing)
        return boto3.resource(
            'dynamodb',
            endpoint_url=endpoint_url,
            region_name='ap-southeast-1',
            aws_access_key_id='dummy',
            aws_secret_access_key='dummy'
        )
    else:
        # Use AWS DynamoDB (production)
        return boto3.resource('dynamodb', region_name='ap-southeast-1')


dynamodb = get_dynamodb_resource()
events_table = dynamodb.Table('Events')
bookings_table = dynamodb.Table('Bookings')


# Helper function to convert float to Decimal for DynamoDB
def convert_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_decimal(item) for item in obj]
    return obj


# Helper function to convert Decimal to float for JSON serialization
def convert_from_decimal(obj):
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    elif isinstance(obj, dict):
        return {k: convert_from_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_from_decimal(item) for item in obj]
    return obj


# Event class
class Event:
    def __init__(self, title, description, venue, date, total_seats,
                 price, event_image=None, venue_image=None,
                 created_by=None, event_id=None):
        self.event_id = event_id or str(uuid.uuid4())
        self.event_image = event_image
        self.title = title
        self.description = description
        self.venue = venue
        self.venue_image = venue_image
        self.date = date
        self.total_seats = total_seats
        self.price = price
        self.created_by = created_by
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self):
        return {
            'event_id': self.event_id,
            'event_image': self.event_image,
            'title': self.title,
            'description': self.description,
            'venue': self.venue,
            'venue_image': self.venue_image,
            'date': self.date,
            'total_seats': self.total_seats,
            'price': self.price,
            'created_by': self.created_by,
            'created_at': self.created_at
        }

    @staticmethod
    def from_dict(data):
        data = convert_from_decimal(data)
        return Event(
            title=data['title'],
            description=data['description'],
            venue=data['venue'],
            date=data['date'],
            total_seats=data['total_seats'],
            price=data.get('price'),
            event_image=data.get('event_image'),
            venue_image=data.get('venue_image'),
            created_by=data.get('created_by'),
            event_id=data['event_id']
        )


# Booking class
class Booking:
    def __init__(self, user_id, event_id, num_tickets=1,
                 booking_id=None, created_at=None):
        self.booking_id = booking_id or str(uuid.uuid4())
        self.user_id = user_id
        self.event_id = event_id
        self.num_tickets = num_tickets
        self.created_at = created_at or datetime.now(UTC).isoformat()

    def to_dict(self):
        return {
            'booking_id': self.booking_id,
            'user_id': self.user_id,
            'event_id': self.event_id,
            'num_tickets': self.num_tickets,
            'created_at': self.created_at
        }

    @staticmethod
    def from_dict(data):
        data = convert_from_decimal(data)
        return Booking(
            user_id=data['user_id'],
            event_id=data['event_id'],
            num_tickets=data['num_tickets'],
            booking_id=data['booking_id'],
            created_at=data.get('created_at')
        )


# Auth decorators
def require_admin(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Unauthorized'}), 401
        if 'admin' not in auth_header.lower():
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def require_auth(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


# Admin Routes
@app.route('/api/admin/events', methods=['POST'])
@require_admin
def create_event():
    data = request.get_json()

    # Validate required fields
    required_fields = ['title', 'description', 'venue', 'date', 'total_seats']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    event = Event(
        title=data['title'],
        description=data['description'],
        venue=data['venue'],
        date=data['date'],
        total_seats=data['total_seats'],
        price=data.get('price'),
        event_image=data.get('event_image'),
        venue_image=data.get('venue_image'),
        created_by=data.get('created_by'),
        event_id=data.get('event_id')
    )

    # Save to DynamoDB
    event_dict = convert_to_decimal(event.to_dict())
    events_table.put_item(Item=event_dict)

    return jsonify(event.to_dict()), 201


@app.route('/api/admin/events/<event_id>', methods=['GET'])
@require_admin
def get_event_admin(event_id):
    # Ensure event_id is string
    event_id = str(event_id)

    response = events_table.get_item(Key={'event_id': event_id})

    if 'Item' not in response:
        return jsonify({'error': 'Event not found'}), 404

    event = Event.from_dict(response['Item'])
    return jsonify(event.to_dict()), 200


@app.route('/api/admin/events', methods=['GET'])
@require_admin
def get_all_events_admin():
    response = events_table.scan()
    events = [Event.from_dict(item).to_dict() for item in response['Items']]
    return jsonify(events), 200


@app.route('/api/admin/events/<event_id>', methods=['PUT'])
@require_admin
def update_event(event_id):
    # Ensure event_id is string
    event_id = str(event_id)

    # Check if event exists
    response = events_table.get_item(Key={'event_id': event_id})
    if 'Item' not in response:
        return jsonify({'error': 'Event not found'}), 404

    data = request.get_json()
    event = Event.from_dict(response['Item'])

    # Update allowed fields
    for field in ['title', 'description', 'venue', 'date', 'total_seats',
                  'price', 'event_image', 'venue_image']:
        if field in data:
            setattr(event, field, data[field])

    # Save updated event
    event_dict = convert_to_decimal(event.to_dict())
    events_table.put_item(Item=event_dict)

    return jsonify(event.to_dict()), 200


@app.route('/api/admin/events/<event_id>', methods=['DELETE'])
@require_admin
def delete_event(event_id):
    # Ensure event_id is string
    event_id = str(event_id)

    # Check if event exists
    response = events_table.get_item(Key={'event_id': event_id})
    if 'Item' not in response:
        return jsonify({'error': 'Event not found'}), 404

    events_table.delete_item(Key={'event_id': event_id})
    return jsonify({'message': 'Event deleted successfully'}), 200


# User Routes
@app.route('/api/events', methods=['GET'])
@require_auth
def get_all_events():
    response = events_table.scan()
    events = [Event.from_dict(item).to_dict() for item in response['Items']]
    return jsonify(events), 200


@app.route('/api/events/<event_id>', methods=['GET'])
@require_auth
def get_event(event_id):
    # Ensure event_id is string
    event_id = str(event_id)

    response = events_table.get_item(Key={'event_id': event_id})

    if 'Item' not in response:
        return jsonify({'error': 'Event not found'}), 404

    event = Event.from_dict(response['Item'])
    return jsonify(event.to_dict()), 200


@app.route('/api/events/<event_id>/book', methods=['POST'])
@require_auth
def book_event(event_id):
    # Ensure event_id is string
    event_id = str(event_id)

    # Get event
    response = events_table.get_item(Key={'event_id': event_id})
    if 'Item' not in response:
        return jsonify({'error': 'Event not found'}), 404

    event = Event.from_dict(response['Item'])

    data = request.get_json() or {}
    num_tickets = int(data.get('num_tickets', 1))
    user_id = str(data.get('user_id', ''))

    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    if num_tickets <= 0:
        return jsonify({'error': 'Invalid ticket quantity'}), 400

    # Check availability
    if num_tickets > event.total_seats:
        return jsonify({'error': 'Not enough seats available'}), 400

    # Deduct booked seats
    event.total_seats -= num_tickets

    # Update event in DynamoDB
    events_table.update_item(
        Key={'event_id': event_id},
        UpdateExpression='SET total_seats = :seats',
        ExpressionAttributeValues={':seats': event.total_seats}
    )

    # Create booking
    booking = Booking(user_id=user_id, event_id=event_id,
                      num_tickets=num_tickets)
    booking_dict = convert_to_decimal(booking.to_dict())
    bookings_table.put_item(Item=booking_dict)

    return jsonify({
        'message': 'Booking successful',
        'booking': booking.to_dict(),
        'remaining_seats': event.total_seats
    }), 201


@app.route('/api/bookings', methods=['GET'])
@require_auth
def get_user_bookings():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    # Ensure user_id is string
    user_id = str(user_id)

    # Query bookings by user_id using GSI
    response = bookings_table.query(
        IndexName='UserIdIndex',
        KeyConditionExpression=Key('user_id').eq(user_id)
    )

    user_bookings = [Booking.from_dict(item).to_dict()
                     for item in response['Items']]
    return jsonify(user_bookings), 200


@app.route('/api/bookings/<booking_id>', methods=['DELETE'])
@require_auth
def cancel_booking(booking_id):
    # Ensure booking_id is string
    booking_id = str(booking_id)

    # Get booking
    response = bookings_table.get_item(Key={'booking_id': booking_id})
    if 'Item' not in response:
        return jsonify({'error': 'Booking not found'}), 404

    booking = Booking.from_dict(response['Item'])

    # Get associated event - ensure event_id is a string
    event_id = str(booking.event_id)
    event_response = events_table.get_item(Key={'event_id': event_id})
    if 'Item' not in event_response:
        return jsonify({'error': 'Associated event not found'}), 404

    event = Event.from_dict(event_response['Item'])

    # Restore seats
    event.total_seats += booking.num_tickets

    # Update event in DynamoDB
    events_table.update_item(
        Key={'event_id': event_id},
        UpdateExpression='SET total_seats = :seats',
        ExpressionAttributeValues={':seats': event.total_seats}
    )

    # Remove booking record
    bookings_table.delete_item(Key={'booking_id': booking_id})

    return jsonify({
        'message': 'Booking cancelled successfully',
        'restored_seats': booking.num_tickets,
        'updated_total_seats': event.total_seats
    }), 200


@app.route("/api/events/starting-soon", methods=["GET"])
def get_events_starting_soon():
    """
    Retrieve all events that start about 3 hours from now (±5 minutes tolerance).
    """
    try:
        now = datetime.now(timezone.utc)
        tolerance = timedelta(minutes=5)
        target_time = now + timedelta(hours=3)

        response = events_table.scan()
        items = response.get("Items", [])

        upcoming_events = []
        for item in items:
            try:
                event_date = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))

                # Check if event_date is within ±5 minutes of (now + 3h)
                if abs((event_date - target_time)) <= tolerance:
                    upcoming_events.append(convert_from_decimal(item))

            except Exception as e:
                print(f"Skipping event {item.get('event_id')}: invalid date format ({e})")

        return jsonify({
            "count": len(upcoming_events),
            "events": upcoming_events
        }), 200

    except Exception as e:
        print("Error fetching upcoming events:", e)
        return jsonify({"error": str(e)}), 500


@app.get("/health")
def health():
    """Liveness/health endpoint so clients can verify the service is up."""
    return jsonify({
        "status": "ok",
        "service": "ticket-booking"
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8084)
