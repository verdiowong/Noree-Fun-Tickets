import os

# Service URLs
# Service Discovery URLs (works when running in ECS/VPC)
# For local testing, override with environment variables pointing to localhost
BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://ticket-booking-service.tickets.local:8084")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payments.tickets.local:8083")

# SQS Configuration
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "https://sqs.ap-southeast-1.amazonaws.com/375039967321/booking-requests.fifo")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")

# DynamoDB Configuration
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "booking-requests-status")

# Polling configuration
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "1"))  # Seconds between polls
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "1"))  # Process one at a time for strict FCFS
WAIT_TIME = int(os.getenv("WAIT_TIME", "20"))  # Long polling wait time
VISIBILITY_TIMEOUT = int(os.getenv("VISIBILITY_TIMEOUT", "60"))  # Should be > processing time

