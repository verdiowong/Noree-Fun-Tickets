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
def test_create_event_success(test_client):
    """Test creating a new event"""
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
        content_type='application/json'
    )
    assert response.status_code == 201
    data = response.json
    assert data['title'] == 'Jazz Night 2025'
    assert data['total_seats'] == 200
    assert data['price'] == 150.00
    assert 'event_id' in data
    assert 'created_at' in data


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
        content_type='application/json'
    )
    assert response.status_code == 400
    assert 'error' in response.json


def test_get_all_events(test_client):
    """Test getting all events"""
    response = test_client.get('/api/admin/events')
    assert response.status_code == 200
    events = response.json
    assert isinstance(events, list)
    assert len(events) >= 3
    assert all('event_id' in event for event in events)


def test_get_single_event(test_client):
    """Test getting a specific event"""
    response = test_client.get('/api/admin/events/1')
    assert response.status_code == 200
    event = response.json
    assert event['event_id'] == '1'
    assert event['title'] == 'Rock Concert 2025'


def test_get_nonexistent_event(test_client):
    """Test getting non-existent event"""
    response = test_client.get('/api/admin/events/999')
    assert response.status_code == 404
    assert 'error' in response.json


def test_update_event_success(test_client):
    """Test updating an event"""
    updates = {
        'title': 'Rock Concert 2025 - UPDATED',
        'price': 150.00,
        'total_seats': 600
    }
    response = test_client.put(
        '/api/admin/events/1',
        data=json.dumps(updates),
        content_type='application/json'
    )
    assert response.status_code == 200
    event = response.json
    assert event['title'] == 'Rock Concert 2025 - UPDATED'
    assert event['price'] == 150.00
    assert event['total_seats'] == 600


def test_update_nonexistent_event(test_client):
    """Test updating non-existent event"""
    updates = {'title': 'Updated Title'}
    response = test_client.put(
        '/api/admin/events/999',
        data=json.dumps(updates),
        content_type='application/json'
    )
    assert response.status_code == 404


def test_delete_event_success(test_client):
    """Test deleting an event"""
    response = test_client.delete('/api/admin/events/3')
    assert response.status_code == 200
    assert 'message' in response.json

    # Verify deletion
    get_response = test_client.get('/api/admin/events/3')
    assert get_response.status_code == 404


def test_delete_nonexistent_event(test_client):
    """Test deleting non-existent event"""
    response = test_client.delete('/api/admin/events/999')
    assert response.status_code == 404


# User Event Access Tests
def test_get_all_events_user(test_client):
    """Test getting all events as user"""
    response = test_client.get('/api/events')
    assert response.status_code == 200
    events = response.json
    assert isinstance(events, list)
    assert len(events) >= 3


def test_get_single_event_user(test_client):
    """Test getting specific event as user"""
    response = test_client.get('/api/events/2')
    assert response.status_code == 200
    event = response.json
    assert event['event_id'] == '2'
    assert event['title'] == 'Tech Conference 2025'


def test_get_nonexistent_event_user(test_client):
    """Test getting non-existent event as user"""
    response = test_client.get('/api/events/999')
    assert response.status_code == 404


# Booking Flow Tests
def test_book_event_success(test_client):
    """Test successful event booking"""
    booking_data = {
        'user_id': 'user-abc-123',
        'num_tickets': 2,
        'seat_numbers': ['A1', 'A2']
    }
    event_response = test_client.get('/api/events/1')
    initial_seats = event_response.json['total_seats']

    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 201
    data = response.json
    assert data['message'] == 'Booking successful'
    assert 'booking' in data
    assert data['booking']['num_tickets'] == 2
    assert data['remaining_seats'] == initial_seats - 2


def test_book_event_single_ticket(test_client):
    """Test booking with default single ticket"""
    booking_data = {
        'user_id': 'user-xyz-456',
        'seat_numbers': ['B5']
    }
    response = test_client.post(
        '/api/events/2/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 201
    assert response.json['booking']['num_tickets'] == 1
    assert response.json['booking']['seat_numbers'] == ['B5']


def test_book_event_empty_seat_numbers(test_client):
    """Test booking with empty seat_numbers list"""
    booking_data = {
        'user_id': 'user-empty-seats',
        'num_tickets': 1,
        'seat_numbers': []
    }
    response = test_client.post(
        '/api/events/2/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 201
    assert response.json['booking']['seat_numbers'] == []


def test_book_event_no_seat_numbers_field(test_client):
    """Test booking without seat_numbers field"""
    booking_data = {'user_id': 'user-no-seats-field', 'num_tickets': 1}
    response = test_client.post(
        '/api/events/2/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 201
    assert response.json['booking']['seat_numbers'] == []


def test_book_event_invalid_seat_numbers_type(test_client):
    """Test booking with invalid seat_numbers type"""
    booking_data = {
        'user_id': 'user-invalid-seats',
        'num_tickets': 1,
        'seat_numbers': 'A1,A2'
    }
    response = test_client.post(
        '/api/events/2/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 400
    assert 'seat_numbers must be a list' in response.json['error']


def test_book_event_missing_user_id(test_client):
    """Test booking without user_id"""
    booking_data = {'num_tickets': 2, 'seat_numbers': ['C1', 'C2']}
    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 400
    assert 'error' in response.json


def test_book_event_invalid_ticket_quantity(test_client):
    """Test booking with invalid ticket quantity"""
    booking_data = {'user_id': 'user-123', 'num_tickets': 0, 'seat_numbers': []}
    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 400


def test_book_event_not_enough_seats(test_client):
    """Test booking more tickets than available"""
    booking_data = {'user_id': 'user-123', 'num_tickets': 10000, 'seat_numbers': []}
    response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 409
    assert 'Not enough seats' in response.json['error']


def test_book_nonexistent_event(test_client):
    """Test booking non-existent event"""
    booking_data = {
        'user_id': 'user-123',
        'num_tickets': 1,
        'seat_numbers': ['Z99']
    }
    response = test_client.post(
        '/api/events/999/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    assert response.status_code == 404


def test_get_user_bookings(test_client):
    """Test retrieving user bookings"""
    booking_data = {
        'user_id': 'test-user-789',
        'num_tickets': 3,
        'seat_numbers': ['D1', 'D2', 'D3']
    }
    test_client.post(
        '/api/events/2/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    response = test_client.get('/api/bookings?user_id=test-user-789')
    assert response.status_code == 200
    bookings = response.json
    assert isinstance(bookings, list)
    assert len(bookings) >= 1
    assert any(b['user_id'] == 'test-user-789' for b in bookings)
    user_booking = next(b for b in bookings if b['user_id'] == 'test-user-789')
    assert 'seat_numbers' in user_booking


def test_get_bookings_missing_user_id(test_client):
    """Test getting bookings without user_id"""
    response = test_client.get('/api/bookings')
    assert response.status_code == 400


def test_cancel_booking_success(test_client):
    """Test cancelling a booking"""
    booking_data = {
        'user_id': 'cancel-user-123',
        'num_tickets': 5,
        'seat_numbers': ['E1', 'E2', 'E3', 'E4', 'E5']
    }
    book_response = test_client.post(
        '/api/events/1/book',
        data=json.dumps(booking_data),
        content_type='application/json'
    )
    booking_id = book_response.json['booking']['booking_id']
    seats_before = book_response.json['remaining_seats']

    cancel_response = test_client.delete(f'/api/bookings/{booking_id}')
    assert cancel_response.status_code == 200
    data = cancel_response.json
    assert data['message'] == 'Booking cancelled successfully'
    assert data['restored_seats'] == 5
    assert data['updated_total_seats'] == seats_before + 5


def test_cancel_nonexistent_booking(test_client):
    """Test cancelling non-existent booking"""
    response = test_client.delete('/api/bookings/fake-booking-id')
    assert response.status_code == 404
