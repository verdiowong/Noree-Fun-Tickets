from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, UTC
import uuid

app = Flask(__name__)
CORS(app)


# Event class matching the database schema
class Event:
    def __init__(self, title, description, venue, date, total_seats, \
                price, event_image=None, venue_image=None, \
                created_by=None, event_id=None):
        self.event_id = event_id or str(uuid.uuid4())
        self.event_image = event_image  # base64 string
        self.title = title
        self.description = description
        self.venue = venue
        self.venue_image = venue_image  # base64 string
        self.date = date  # ISO format timestamp
        self.total_seats = total_seats
        self.price = price
        self.created_by = created_by  # UUID of the user who created it
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
            'created_by': self.created_by,
            'created_at': self.created_at
        }


# Booking class
class Booking:
    def __init__(self, user_id, event_id, num_tickets=1):
        self.booking_id = str(uuid.uuid4())
        self.user_id = user_id
        self.event_id = event_id
        self.num_tickets = num_tickets
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self):
        return {
            'booking_id': self.booking_id,
            'user_id': self.user_id,
            'event_id': self.event_id,
            'num_tickets': self.num_tickets,
            'created_at': self.created_at
        }


# In-memory storage
events = {}


# In-memory booking storage
bookings = {}


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
        event_image=data.get('event_image'),
        venue_image=data.get('venue_image'),
        created_by=data.get('created_by'),
        event_id=data.get('event_id')  # Optional: allow custom ID for testing
    )
    events[event.event_id] = event
    return jsonify(event.to_dict()), 201


@app.route('/api/admin/events/<event_id>', methods=['GET'])
@require_admin
def get_event_admin(event_id):
    event = events.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    return jsonify(event.to_dict()), 200


@app.route('/api/admin/events', methods=['GET'])
@require_admin
def get_all_events_admin():
    return jsonify([event.to_dict() for event in events.values()]), 200


@app.route('/api/admin/events/<event_id>', methods=['PUT'])
@require_admin
def update_event(event_id):
    event = events.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    data = request.get_json()
    # Update allowed fields
    for field in ['title', 'description', 'venue', 'date', 'total_seats', 
                  'event_image', 'venue_image']:
        if field in data:
            setattr(event, field, data[field])
    
    return jsonify(event.to_dict()), 200


@app.route('/api/admin/events/<event_id>', methods=['DELETE'])
@require_admin
def delete_event(event_id):
    event = events.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    del events[event_id]
    return jsonify({'message': 'Event deleted successfully'}), 200


# User Routes
@app.route('/api/events', methods=['GET'])
@require_auth
def get_all_events():
    return jsonify([event.to_dict() for event in events.values()]), 200


# User get a single event
@app.route('/api/events/<event_id>', methods=['GET'])
@require_auth
def get_event(event_id):
    event = events.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    return jsonify(event.to_dict()), 200


# User booking event route
@app.route('/api/events/<event_id>/book', methods=['POST'])
@require_auth
def book_event(event_id):
    event = events.get(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    data = request.get_json() or {}
    num_tickets = int(data.get('num_tickets', 1))
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    if num_tickets <= 0:
        return jsonify({'error': 'Invalid ticket quantity'}), 400

    # Check availability
    if num_tickets > event.total_seats:
        return jsonify({'error': 'Not enough seats available'}), 400

    # Deduct booked seats
    event.total_seats -= num_tickets

    # Create booking
    booking = Booking(user_id=user_id, event_id=event_id, num_tickets=num_tickets)
    bookings[booking.booking_id] = booking

    return jsonify({
        'message': 'Booking successful',
        'booking': booking.to_dict(),
        'remaining_seats': event.total_seats
    }), 201


# View user's booking
@app.route('/api/bookings', methods=['GET'])
@require_auth
def get_user_bookings():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    user_bookings = [b.to_dict() for b in bookings.values() if b.user_id == user_id]
    return jsonify(user_bookings), 200


# Show cancel user's booking
@app.route('/api/bookings/<booking_id>', methods=['DELETE'])
@require_auth
def cancel_booking(booking_id):
    booking = bookings.get(booking_id)
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404

    event = events.get(booking.event_id)
    if not event:
        return jsonify({'error': 'Associated event not found'}), 404

    # Restore seats
    event.total_seats += booking.num_tickets

    # Remove booking record
    del bookings[booking_id]

    return jsonify({
        'message': 'Booking cancelled successfully',
        'restored_seats': booking.num_tickets,
        'updated_total_seats': event.total_seats
    }), 200


if __name__ == '__main__':
    # Sample events for testing
    sample1 = Event(
        title='Summer Music Festival',
        description='An amazing outdoor music festival featuring top artists',
        venue='Central Park, Singapore',
        date='2025-07-15T18:00:00Z',
        total_seats=5000,
        price = 100,
        event_image='data:image/png;base64,iVBORw0KGgo...',  # Placeholder
        venue_image='data:image/png;base64,iVBORw0KGgo...',  # Placeholder
        created_by='123e4567-e89b-12d3-a456-426614174000',
        event_id='1'
    )
    
    sample2 = Event(
        title='Tech Conference 2025',
        description='Annual technology conference with industry leaders',
        venue='Marina Bay Sands, Singapore',
        date='2025-09-20T09:00:00Z',
        total_seats=1000,
        price=200,
        event_image='data:image/png;base64,iVBORw0KGgo...',  # Placeholder
        venue_image='data:image/png;base64,iVBORw0KGgo...',  # Placeholder
        created_by='123e4567-e89b-12d3-a456-426614174000',
        event_id='2'
    )
    
    events[sample1.event_id] = sample1
    events[sample2.event_id] = sample2
    
    app.run(debug=True, host='0.0.0.0', port=5000)
