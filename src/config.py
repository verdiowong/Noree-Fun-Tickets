import os


# Service base URLs
ADMIN_SERVICE_URL = os.getenv("ADMIN_SERVICE_URL", "http://admin.tickets.local:8081")
BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://ticket-booking-service.tickets.local:8084")
# BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://10.0.11.26:8084")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payments.tickets.local:8083")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notifications.tickets.local:8082")

# Networking and resiliency
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_MS", "5000")) / 1000.0
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
