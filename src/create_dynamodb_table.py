import boto3


def create_tables():
    dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')

    # Create Events Table
    try:
        events_table = dynamodb.create_table(
            TableName='Events',
            KeySchema=[
                {
                    'AttributeName': 'event_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'event_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand pricing
        )
        print("Creating Events table...")
        events_table.wait_until_exists()
        print("Events table created successfully!")
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print("Events table already exists")

    # Create Bookings Table with GSI for user_id queries
    try:
        bookings_table = dynamodb.create_table(
            TableName='Bookings',
            KeySchema=[
                {
                    'AttributeName': 'booking_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'booking_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'UserIdIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'user_id',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("Creating Bookings table...")
        bookings_table.wait_until_exists()
        print("Bookings table created successfully!")
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print("Bookings table already exists")

    print("\nAll tables created successfully!")
    print("\nTable details:")
    print("- Events: Primary key = event_id")
    print("- Bookings: Primary key = booking_id, GSI = UserIdIndex (user_id)")


if __name__ == '__main__':
    create_tables()
