import pytest
from moto import mock_aws
import boto3
from decimal import Decimal
from datetime import datetime, timezone
import src.app as app_module


@pytest.fixture(scope="session")
def mock_dynamodb_resource():
    """
    Creates an in-memory DynamoDB resource using moto.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        
        # Create mock Events table
        dynamodb.create_table(
            TableName="Events",
            KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "event_id", "AttributeType": "S"}
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )

        # Create mock Bookings table with GSI
        dynamodb.create_table(
            TableName="Bookings",
            KeySchema=[{"AttributeName": "booking_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "booking_id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "UserIdIndex",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5
                    }
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )

        yield dynamodb


@pytest.fixture(scope="session")
def mock_events_table(mock_dynamodb_resource):
    """
    Populates the mock Events table with realistic fake events.
    """
    table = mock_dynamodb_resource.Table("Events")

    events = [
        {
            'event_id': '1',
            'title': 'Rock Concert 2025',
            'description': 'An electrifying night of live rock music with top local bands.',
            'venue': 'Singapore Indoor Stadium',
            'date': '2025-08-15T20:00:00Z',
            'total_seats': Decimal('500'),
            'price': Decimal('120.00'),
            'event_image': 'data:image/svg+xml;base64,PHN2ZyB3aW...',
            'venue_image': 'data:image/svg+xml;base64,PHN2ZyB3aW...',
            'created_by': '111e4567-e89b-12d3-a456-426614174000',
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'event_id': '2',
            'title': 'Tech Conference 2025',
            'description': 'Annual technology conference featuring industry '
                           'leaders, keynote speeches, and networking opportunities. '
                           'Topics include AI, Cloud Computing, and Web3.',
            'venue': 'Marina Bay Sands, Singapore',
            'date': '2025-09-20T09:00:00Z',
            'total_seats': Decimal('1000'),
            'price': Decimal('200.00'),
            'event_image': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIi...',
            'venue_image': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIi...',
            'created_by': '123e4567-e89b-12d3-a456-426614174000',
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'event_id': '3',
            'title': 'Art Festival 2025',
            'description': 'A vibrant showcase of art, music, and performance in the city.',
            'venue': 'Esplanade Park, Singapore',
            'date': '2025-10-10T18:00:00Z',
            'total_seats': Decimal('300'),
            'price': Decimal('80.00'),
            'event_image': 'data:image/svg+xml;base64,PHN2ZyB3aW...',
            'venue_image': 'data:image/svg+xml;base64,PHN2ZyB3aW...',
            'created_by': '222e4567-e89b-12d3-a456-426614174000',
            'created_at': datetime.now(timezone.utc).isoformat()
        },
    ]

    with table.batch_writer() as batch:
        for e in events:
            batch.put_item(Item=e)

    return table


@pytest.fixture(scope="session")
def mock_bookings_table(mock_dynamodb_resource):
    """
    Returns the mock Bookings table.
    """
    return mock_dynamodb_resource.Table("Bookings")


@pytest.fixture(scope="session")
def test_client(mock_dynamodb_resource, mock_events_table, mock_bookings_table):
    """
    Creates a Flask test client and injects the mock DynamoDB resource into the app.
    """
    app_module.app.config["TESTING"] = True
    app_module.app.config["DEBUG"] = False

    # Override the module-level DynamoDB resource and tables
    app_module.dynamodb = mock_dynamodb_resource
    app_module.events_table = mock_events_table
    app_module.bookings_table = mock_bookings_table

    with app_module.app.test_client() as client:
        yield client
