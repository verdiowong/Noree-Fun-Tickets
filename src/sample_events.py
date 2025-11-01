import boto3
from datetime import datetime, UTC
from decimal import Decimal


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
events_table = dynamodb.Table('Events')


# Sample Event 1: Summer Music Festival
event1 = {
    'event_id': '1',
    'title': 'Summer Music Festival',
    'description': 'An amazing outdoor music festival featuring top \
    artists from around the world. \
    Enjoy live performances, food trucks, and great vibes!',
    'venue': 'Central Park, Singapore',
    'date': '2025-07-15T18:00:00Z',
    'total_seats': Decimal('5000'),
    'price': Decimal('100.00'),
    'event_image': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZ\
    WlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVj\
    dCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iIzRBOTBFMiIvPjx0ZXh0IHg\
    9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMjQiIG\
    ZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+8J+OtiBNd\
    XNpYyBGZXN0aXZhbDwvdGV4dD48L3N2Zz4=',
    'venue_image': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZ\
    WlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVj\
    dCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iIzJFOEI1NyIvPjx0ZXh0IHg\
    9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMjQiIG\
    ZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+8J+MsyBDZ\
    W50cmFsIFBhcms8L3RleHQ+PC9zdmc+',
    'created_by': '123e4567-e89b-12d3-a456-426614174000',
    'created_at': datetime.now(UTC).isoformat()
}


# Sample Event 2: Tech Conference 2025
event2 = {
    'event_id': '2',
    'title': 'Tech Conference 2025',
    'description': 'Annual technology conference featuring industry \
    leaders, keynote speeches, and networking opportunities. Topics \
    include AI, Cloud Computing, and Web3.',
    'venue': 'Marina Bay Sands, Singapore',
    'date': '2025-09-20T09:00:00Z',
    'total_seats': Decimal('1000'),
    'price': Decimal('200.00'),
    'event_image': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIi\
    BoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj\
    48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iIzlCNTlCNiIvPj\
    x0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2\
    l6ZT0iMjQiIGZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLN\
    lbSI+8J+agCBUZWNoIENvbmZlcmVuY2U8L3RleHQ+PC9zdmc+',
    'venue_image': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIi\
    BoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj\
    48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI0U3NEMzQyIvPj\
    x0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2\
    l6ZT0iMjQiIGZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLj\
    NlbSI+8J+PqyBNYXJpbmEgQmF5IFNhbmRzPC90ZXh0Pjwvc3ZnPg==',
    'created_by': '123e4567-e89b-12d3-a456-426614174000',
    'created_at': datetime.now(UTC).isoformat()
}


def add_sample_events():
    try:
        # Add Event 1
        print("Adding Summer Music Festival...")
        events_table.put_item(Item=event1)
        print("✓ Summer Music Festival added successfully!")

        # Add Event 2
        print("Adding Tech Conference 2025...")
        events_table.put_item(Item=event2)
        print("✓ Tech Conference 2025 added successfully!")

        print("\n" + "="*50)
        print("Both sample events have been added to DynamoDB!")
        print("="*50)

        # Verify by scanning the table
        print("\nVerifying events in database:")
        response = events_table.scan()
        for item in response['Items']:
            print(f"\n- {item['title']}")
            print(f"  Venue: {item['venue']}")
            print(f"  Date: {item['date']}")
            print(f"  Seats: {item['total_seats']}")
            print(f"  Price: ${item['price']}")

    except Exception as e:
        print(f"Error adding events: {str(e)}")
        print("Make sure:")
        print("1. AWS credentials are configured (run 'aws configure')")
        print("2. The 'Events' table exists (run \
              create_dynamodb_tables.py first)")
        print("3. You have the necessary DynamoDB permissions")


if __name__ == '__main__':
    add_sample_events()
