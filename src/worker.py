"""
Worker service that polls SQS FIFO queue and processes booking requests in FCFS order.
"""
import json
import time
import boto3
import requests
from datetime import datetime, UTC
from decimal import Decimal
from typing import Dict, Any, Optional
from config import (
    BOOKING_SERVICE_URL, PAYMENT_SERVICE_URL, SQS_QUEUE_URL,
    AWS_REGION, DYNAMODB_TABLE, MAX_MESSAGES, WAIT_TIME, VISIBILITY_TIMEOUT
)

# Initialize AWS clients
sqs = boto3.client('sqs', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
status_table = dynamodb.Table(DYNAMODB_TABLE)


def update_status(request_id: str, status: str, data: Optional[Dict] = None, error: Optional[str] = None):
    """
    Update booking request status in DynamoDB.
    """
    try:
        item = {
            'request_id': request_id,
            'status': status,
            'updated_at': datetime.now(UTC).isoformat()
        }
        
        if data:
            item['data'] = data
        if error:
            item['error'] = error
        
        # Convert floats to Decimal for DynamoDB
        def convert_floats(obj):
            if isinstance(obj, float):
                return Decimal(str(obj))
            if isinstance(obj, dict):
                return {k: convert_floats(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_floats(i) for i in obj]
            return obj
        
        item = convert_floats(item)
        status_table.put_item(Item=item)
        print(f"✓ Updated status for {request_id}: {status}")
        
    except Exception as e:
        print(f"✗ Failed to update status in DynamoDB: {str(e)}")
        # Don't raise - status update failure shouldn't fail the booking


def process_booking(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single booking request.
    Returns dict with 'success' flag and result data or error.
    """
    request_id = message_body.get('request_id')
    print(f"Processing booking request: {request_id}")
    
    try:
        # Extract data from message
        event_id = message_body['event_id']
        num_tickets = message_body['num_tickets']
        user_id = message_body['user_id']
        amount = message_body['amount']
        currency = message_body['currency']
        seat_numbers = message_body.get('seat_numbers')
        
        # Prepare headers (no auth needed if services use IAM roles)
        headers = {
            'Content-Type': 'application/json'
        }
        
        # 1) Create booking
        booking_url = f"{BOOKING_SERVICE_URL}/api/events/{event_id}/book"
        booking_payload = {
            "num_tickets": num_tickets,
            "user_id": user_id
        }
        if seat_numbers:
            booking_payload["seat_numbers"] = seat_numbers
        
        print(f"  → Creating booking at: {booking_url}")
        booking_response = requests.post(
            booking_url,
            json=booking_payload,
            headers=headers,
            timeout=30
        )
        
        if booking_response.status_code >= 400:
            error_msg = f"Booking failed: {booking_response.text}"
            print(f"  ✗ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        booking_data = booking_response.json()
        booking = booking_data.get('booking') or booking_data
        booking_id = booking.get('booking_id')
        
        if not booking_id:
            error_msg = "No booking_id returned from booking service"
            print(f"  ✗ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        print(f"  ✓ Booking created: {booking_id}")
        
        # 2) Create payment intent
        payment_url = f"{PAYMENT_SERVICE_URL}/api/payments/create-intent"
        payment_payload = {
            "booking_id": booking_id,
            "amount": amount,
            "currency": currency
        }
        
        print(f"  → Creating payment intent at: {payment_url}")
        payment_response = requests.post(
            payment_url,
            json=payment_payload,
            headers=headers,
            timeout=30
        )
        
        if payment_response.status_code >= 400:
            error_msg = f"Payment intent failed: {payment_response.text}"
            print(f"  ✗ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        payment_data = payment_response.json()
        print(f"  ✓ Payment intent created: {payment_data.get('payment_id')}")
        
        return {
            'success': True,
            'booking': booking,
            'payment': payment_data
        }
        
    except requests.exceptions.Timeout:
        error_msg = 'Request timeout while processing booking'
        print(f"  ✗ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
    except requests.exceptions.RequestException as e:
        error_msg = f'Network error: {str(e)}'
        print(f"  ✗ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f'Unexpected error: {str(e)}'
        print(f"  ✗ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }


def poll_and_process():
    """
    Main loop: Poll SQS FIFO queue and process messages in order.
    This ensures FCFS processing.
    """
    print("=" * 60)
    print("Worker Service Started")
    print("=" * 60)
    print(f"Queue URL: {SQS_QUEUE_URL}")
    print(f"Region: {AWS_REGION}")
    print(f"Status Table: {DYNAMODB_TABLE}")
    print(f"Max Messages: {MAX_MESSAGES}")
    print(f"Wait Time: {WAIT_TIME}s (long polling)")
    print(f"Visibility Timeout: {VISIBILITY_TIMEOUT}s")
    print("-" * 60)
    print(f"Polling for messages (long polling, {WAIT_TIME}s wait)...")
    print("-" * 60)
    
    while True:
        try:
            # Long polling (efficient, waits up to WAIT_TIME seconds)
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=MAX_MESSAGES,  # Process one at a time for strict FCFS
                WaitTimeSeconds=WAIT_TIME,  # Long polling
                VisibilityTimeout=VISIBILITY_TIMEOUT,
                AttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            if not messages:
                # No messages, continue polling
                continue
            
            for message in messages:
                receipt_handle = message['ReceiptHandle']
                message_body_str = message['Body']
                
                try:
                    # Parse message body
                    message_body = json.loads(message_body_str)
                    request_id = message_body.get('request_id')
                    
                    print(f"\n[{datetime.now(UTC).strftime('%H:%M:%S')}] Processing: {request_id}")
                    
                    # Update status to processing
                    update_status(request_id, 'processing')
                    
                    # Process the booking
                    result = process_booking(message_body)
                    
                    if result['success']:
                        # Update status with success data
                        update_status(
                            request_id,
                            'completed',
                            data={
                                'booking': result.get('booking'),
                                'payment': result.get('payment')
                            }
                        )
                        
                        # Delete message from queue (acknowledge success)
                        sqs.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                        print(f"  ✓ Successfully processed and deleted message")
                        
                    else:
                        # Update status with error
                        update_status(
                            request_id,
                            'failed',
                            error=result.get('error')
                        )
                        
                        # Don't delete message - it will become visible again after visibility timeout
                        # This allows retry. After max retries, it goes to DLQ
                        print(f"  ✗ Processing failed, message will retry: {result.get('error')}")
                        
                except json.JSONDecodeError as e:
                    print(f"  ✗ Invalid JSON in message: {str(e)}")
                    # Delete malformed message to prevent infinite retries
                    sqs.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=receipt_handle
                    )
                    
                except Exception as e:
                    print(f"  ✗ Error processing message: {str(e)}")
                    # Don't delete - let it retry
                    
        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print("Worker service stopped by user")
            print("=" * 60)
            break
            
        except Exception as e:
            print(f"Error in polling loop: {str(e)}")
            time.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    poll_and_process()

