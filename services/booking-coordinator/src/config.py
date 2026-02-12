import os


AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
# Service base URLs
ADMIN_SERVICE_URL = os.environ.get("ADMIN_SERVICE_URL", "http://admin.tickets.local:8081")
BOOKING_SERVICE_URL = os.environ.get("BOOKING_SERVICE_URL", "http://ticket-booking-service.tickets.local:8084")
# BOOKING_SERVICE_URL = os.environ.get("BOOKING_SERVICE_URL", "http://10.0.11.26:8084")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://payments.tickets.local:8083")
NOTIFICATION_SERVICE_URL = os.environ.get("NOTIFICATION_SERVICE_URL", "http://notifications.tickets.local:8082")

SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "https://sqs.ap-southeast-1.amazonaws.com/375039967321/booking-requests.fifo")

SQS_NOTIFICATION_QUEUE_URL = os.environ.get("NOTIFICATIONS_QUEUE_URL", "https://sqs.ap-southeast-1.amazonaws.com/375039967321/notifications-queue")

AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
# Networking and resiliency
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT_MS", "5000")) / 1000.0
RETRY_MAX_ATTEMPTS = int(os.environ.get("RETRY_MAX_ATTEMPTS", "3"))

