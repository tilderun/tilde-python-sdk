import pytest
import respx

from cerebral.client import Client

BASE_URL = "https://cerebral.storage/api/v1"


@pytest.fixture
def mock_api():
    """respx mock router scoped to the Cerebral API base URL."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as rsps:
        yield rsps


@pytest.fixture
def client():
    """Client configured with a test API key."""
    c = Client(api_key="test-key")
    yield c
    c.close()


@pytest.fixture
def repo(client):
    """Repository resource for 'test-org/test-repo'."""
    return client.repository("test-org/test-repo")
