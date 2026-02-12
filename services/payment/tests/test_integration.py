import pytest
import json
from decimal import Decimal


def test_health_check(client):
    """Check that the /health endpoint responds correctly."""
    res = client.get("/health")
    assert res.status_code == 200
    assert "Payment service is healthy" in res.get_json()["status"]


def test_verify_payment_missing_fields(client):
    """Ensure missing fields in /verify-intent are handled."""
    res = client.post("/api/payments/verify-intent", json={})
    assert res.status_code == 400
    assert "Missing" in res.get_json()["error"]


def test_refund_without_auth(client):
    """Check refund endpoint rejects missing Bearer token."""
    res = client.post("/api/payments/refund/sample123")
    assert res.status_code == 401
    assert "authorization" in res.get_json()["error"].lower()


def test_payment_status_mocked(monkeypatch, client):
    """Mock Stripe PaymentIntent.retrieve to simulate a 404-like case."""
    import stripe

    def fake_retrieve(pid):
        raise Exception("No such PaymentIntent")

    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", fake_retrieve)

    res = client.get("/api/bookings/status/fake_intent")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_create_payment_intent_mocked(monkeypatch, client):
    """
    Simulates creating and verifying a new Stripe payment intent.
    This mocks Stripe API and verifies DynamoDB insertion.
    """
    import stripe
    from datetime import datetime
    from src.payment import table

    # --- Step 1: Mock Stripe PaymentIntent ---
    class MockPaymentIntent:
        id = "pi_test_123"
        amount = 5000  # in cents ($50)
        currency = "sgd"
        status = "succeeded"
        created = int(datetime.utcnow().timestamp())

    def mock_create(**kwargs):
        return MockPaymentIntent()

    def mock_retrieve(pid):
        """Simulate retrieving a successful PaymentIntent."""
        return MockPaymentIntent()

    monkeypatch.setattr(stripe.PaymentIntent, "create", mock_create)
    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", mock_retrieve)

    # --- Step 2: Call verify endpoint (simulating client callback) ---
    booking_id = "booking_test_123"
    payload = {
        "payment_id": "pi_test_123",
        "booking_id": booking_id
    }

    res = client.post("/api/payments/verify-intent", json=payload)
    body = res.get_json()

    # --- Step 3: Assert HTTP response correctness ---
    assert res.status_code == 200
    assert "Payment verified" in body["message"]

    # --- Step 4: Validate DynamoDB record ---
    result = table.get_item(Key={"payment_id": "pi_test_123"})
    item = result.get("Item")
    assert item is not None, "Payment record should exist in DynamoDB"
    assert item["status"] == "completed"
    assert Decimal(item["amount"]) == Decimal(50)
    assert item["currency"] == "SGD"
