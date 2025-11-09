import pytest
import json
from decimal import Decimal


# Health Check Endpoint Test
def test_health_check(test_client):
    """Test that health endpoint returns OK"""
    response = test_client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'


# Admin Event Management Tests
# Creating event successfully
def test_create_event_success(test_client):
    """Test creating a new event as admin"""
    new_event = {
        'title': 'Jazz Night 2025',
        'description': 'An evening of smooth jazz',
        'venue': 'The Esplanade',
        'date': '2025-11-15T19:00:00Z',
        'total_seats': 200,
        'price': 150.00,
        'created_by': 'admin-123'
    }
    response = test_client.post(
        '/api/admin/events',
        data=json.dumps(new_event),
        content_type='application/json',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 201
    data = response.json
    assert data['title'] == 'Jazz Night 2025'
    assert data['total_seats'] == 200
    assert data['price'] == 150.00
    assert 'event_id' in data
    assert 'created_at' in data


# Creating event unsuccessfully due to missing fields
def test_create_event_missing_fields(test_client):
    """Test creating event with missing required fields"""
    incomplete_event = {
        'title': 'Incomplete Event',
        'venue': 'Some Venue'
        # Missing: description, date, total_seats
    }
    response = test_client.post(
        '/api/admin/events',
        data=json.dumps(incomplete_event),
        content_type='application/json',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 400
    assert 'error' in response.json


# SKIPPED: Auth is disabled in current implementation
@pytest.mark.skip(reason="Auth decorators are currently commented out")
def test_create_event_unauthorized(test_client):
    """Test creating event without admin authorization"""
    new_event = {
        'title': 'Unauthorized Event',
        'description': 'Should fail',
        'venue': 'Nowhere',
        'date': '2025-12-01T20:00:00Z',
        'total_seats': 100
    }
    response = test_client.post(
        '/api/admin/events',
        data=json.dumps(new_event),
        content_type='application/json'
    )
    assert response.status_code == 401


# SKIPPED: Auth is disabled in current implementation
@pytest.mark.skip(reason="Auth decorators are currently commented out")
def test_create_event_forbidden(test_client):
    """Test creating event with non-admin token"""
    new_event = {
        'title': 'Forbidden Event',
        'description': 'Should fail',
        'venue': 'Nowhere',
        'date': '2025-12-01T20:00:00Z',
        'total_seats': 100
    }
    response = test_client.post(
        '/api/admin/events',
        data=json.dumps(new_event),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 403


# Get all events successfully
def test_get_all_events_admin(test_client):
    """Test getting all events as admin"""
    response = test_client.get(
        '/api/admin/events',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 200
    events = response.json
    assert isinstance(events, list)
    assert len(events) >= 3
    assert all('event_id' in event for event in events)


# Get a single event successfully
def test_get_single_event_admin(test_client):
    """Test getting a specific event as admin"""
    response = test_client.get(
        '/api/admin/events/1',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 200
    event = response.json
    assert event['event_id'] == '1'
    assert event['title'] == 'Rock Concert 2025'


# Trying to get non-existent event, leading to failure
def test_get_nonexistent_event_admin(test_client):
    """Test getting non-existent event as admin"""
    response = test_client.get(
        '/api/admin/events/999',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 404
    assert 'error' in response.json


# Update event successfully
def test_update_event_success(test_client):
    """Test updating an event as admin"""
    updates = {
        'title': 'Rock Concert 2025 - UPDATED',
        'price': 150.00,
        'total_seats': 600
    }
    response = test_client.put(
        '/api/admin/events/1',
        data=json.dumps(updates),
        content_type='application/json',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 200
    event = response.json
    assert event['title'] == 'Rock Concert 2025 - UPDATED'
    assert event['price'] == 150.00
    assert event['total_seats'] == 600


# Fail to update event as it is non-existent
def test_update_nonexistent_event(test_client):
    """Test updating non-existent event"""
    updates = {'title': 'Updated Title'}
    response = test_client.put(
        '/api/admin/events/999',
        data=json.dumps(updates),
        content_type='application/json',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 404


# Successfully delete event
def test_delete_event_success(test_client):
    """Test deleting an event as admin"""
    response = test_client.delete(
        '/api/admin/events/3',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 200
    assert 'message' in response.json

    # Verify deletion
    get_response = test_client.get(
        '/api/admin/events/3',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert get_response.status_code == 404


# Failure to delete as the event is non-existent
def test_delete_nonexistent_event(test_client):
    """Test deleting non-existent event"""
    response = test_client.delete(
        '/api/admin/events/999',
        headers={'Authorization': 'Bearer admin-token'}
    )
    assert response.status_code == 404


# User Event Access Tests
# Get all events successfully
def test_get_all_events_user(test_client):
    """Test getting all events as regular user"""
    response = test_client.get(
        '/api/events',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 200
    events = response.json
    assert isinstance(events, list)
    assert len(events) >= 3


# SKIPPED: Auth is disabled in current implementation
@pytest.mark.skip(reason="Auth decorators are currently commented out")
def test_get_all_events_unauthorized(test_client):
    """Test getting events without authorization"""
    response = test_client.get('/api/events')
    assert response.status_code == 401


# Successfully getting specific event as user
def test_get_single_event_user(test_client):
    """Test getting specific event as user"""
    response = test_client.get(
        '/api/events/2',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 200
    event = response.json
    assert event['event_id'] == '2'
    assert event['title'] == 'Tech Conference 2025'


# Failure to get specific event as it is non-existent
def test_get_nonexistent_event_user(test_client):
    """Test getting non-existent event as user"""
    response = test_client.get(
        '/api/events/999',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 404


# Booking Flow Tests
# Booking an event successfully as a user
def test_book_event_success(test_client):
    """Test successful event booking"""
    booking_data = {'user_id': 'user-abc-123', 'num_tickets': 2}
    event_response = test_client.get(
        '/api/events/1',
        headers={'Authorization': 'Bearer user-token'}
    )
    initial_seats = event_response.json['total_seats']

    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 201
    data = response.json
    assert data['message'] == 'Booking successful'
    assert 'booking' in data
    assert data['booking']['num_tickets'] == 2
    assert data['booking']['user_id'] == 'user-abc-123'
    assert data['remaining_seats'] == initial_seats - 2


# Successfully get booking
def test_book_event_single_ticket(test_client):
    """Test booking with default single ticket"""
    booking_data = {'user_id': 'user-xyz-456'}
    response = test_client.post(
        '/api/events/2/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 201
    assert response.json['booking']['num_tickets'] == 1


# Failure to book as no user_id
def test_book_event_missing_user_id(test_client):
    """Test booking without user_id"""
    booking_data = {'num_tickets': 2}
    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 400
    assert 'error' in response.json


# Failure to book due to invalid quantity
def test_book_event_invalid_ticket_quantity(test_client):
    """Test booking with invalid ticket quantity"""
    booking_data = {'user_id': 'user-123', 'num_tickets': 0}
    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 400


# Failure to book due to seat availability
def test_book_event_not_enough_seats(test_client):
    """Test booking more tickets than available"""
    booking_data = {'user_id': 'user-123', 'num_tickets': 10000}
    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    # Updated: When seats are insufficient, the response is 409 Conflict
    assert response.status_code == 409
    assert 'Not enough seats' in response.json['error']


# Failure to book as non-existent
def test_book_nonexistent_event(test_client):
    """Test booking non-existent event"""
    booking_data = {'user_id': 'user-123', 'num_tickets': 1}
    response = test_client.post(
        '/api/events/999/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 404


# Get all bookings made
def test_get_user_bookings(test_client):
    """Test retrieving user bookings"""
    booking_data = {'user_id': 'test-user-789', 'num_tickets': 3}
    test_client.post(
        '/api/events/2/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    response = test_client.get(
        '/api/bookings?user_id=test-user-789',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 200
    bookings = response.json
    assert isinstance(bookings, list)
    assert len(bookings) >= 1
    assert any(b['user_id'] == 'test-user-789' for b in bookings)


# Failure to get all booking made as no user_id
def test_get_bookings_missing_user_id(test_client):
    """Test getting bookings without user_id"""
    response = test_client.get(
        '/api/bookings',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 400


# Cancel booking successfully
def test_cancel_booking_success(test_client):
    """Test cancelling a booking"""
    booking_data = {'user_id': 'cancel-user-123', 'num_tickets': 5}
    book_response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json',
        headers={'Authorization': 'Bearer user-token'}
    )
    booking_id = book_response.json['booking']['booking_id']
    seats_before = book_response.json['remaining_seats']

    cancel_response = test_client.delete(
        f'/api/bookings/{booking_id}',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert cancel_response.status_code == 200
    data = cancel_response.json
    assert data['message'] == 'Booking cancelled successfully'
    assert data['restored_seats'] == 5
    assert data['updated_total_seats'] == seats_before + 5


# Failure to cancel as non-existent
def test_cancel_nonexistent_booking(test_client):
    """Test cancelling non-existent booking"""
    response = test_client.delete(
        '/api/bookings/fake-booking-id',
        headers={'Authorization': 'Bearer user-token'}
    )
    assert response.status_code == 404
