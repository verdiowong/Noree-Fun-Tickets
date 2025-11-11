import pytest
from src.payment import app, dynamodb

@pytest.fixture(scope="session")
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def setup_dynamodb():
    """Ensure 'payments' table exists before tests."""
    table_name = "payments"
    try:
        existing_tables = [t.name for t in dynamodb.tables.all()]
        if table_name not in existing_tables:
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": "payment_id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "payment_id", "AttributeType": "S"}],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            table.wait_until_exists()
            print("[TEST FIXTURE] Created DynamoDB table 'payments' with key: payment_id")
    except Exception as e:
        print(f"[TEST FIXTURE ERROR] Could not create table: {e}")
    yield


