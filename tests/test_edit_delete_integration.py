import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp_server_qdrant.qdrant import QdrantConnector, Entry
from mcp_server_qdrant.embeddings.base import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""
    
    def __init__(self):
        self.vector_size = 384
        self.vector_name = "default"
    
    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        # Return mock embeddings
        return [[0.1] * self.vector_size for _ in documents]
    
    async def embed_query(self, query: str) -> list[float]:
        # Return mock query embedding
        return [0.1] * self.vector_size
    
    def get_vector_size(self) -> int:
        return self.vector_size
    
    def get_vector_name(self) -> str:
        return self.vector_name


@pytest.fixture
def mock_qdrant_client():
    """Create a mock Qdrant client for testing."""
    client = AsyncMock()
    client.collection_exists.return_value = True
    client.retrieve.return_value = []
    client.upsert.return_value = None
    client.delete.return_value = None
    client.scroll.return_value = ([], None)
    return client


@pytest.fixture
def qdrant_connector(mock_qdrant_client):
    """Create a QdrantConnector instance with mocked client."""
    embedding_provider = MockEmbeddingProvider()
    connector = QdrantConnector(
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
        collection_name="test_collection",
        embedding_provider=embedding_provider,
    )
    connector._client = mock_qdrant_client
    return connector


class TestEditDeleteFunctionality:
    """Test cases for edit and delete functionality."""

    @pytest.mark.asyncio
    async def test_get_point_by_id_existing_point(self, qdrant_connector, mock_qdrant_client):
        """Test retrieving an existing point by ID."""
        # Mock response for existing point
        mock_point = MagicMock()
        mock_point.payload = {
            "document": "Test content",
            "metadata": {"author": "test"}
        }
        mock_qdrant_client.retrieve.return_value = [mock_point]
        
        result = await qdrant_connector.get_point_by_id("test_id")
        
        assert result is not None
        assert result.content == "Test content"
        assert result.metadata == {"author": "test"}

    @pytest.mark.asyncio
    async def test_get_point_by_id_nonexistent_point(self, qdrant_connector, mock_qdrant_client):
        """Test retrieving a non-existent point by ID."""
        mock_qdrant_client.retrieve.return_value = []
        
        result = await qdrant_connector.get_point_by_id("nonexistent_id")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_update_point_success(self, qdrant_connector, mock_qdrant_client):
        """Test successful point update."""
        # Mock existing point
        mock_point = MagicMock()
        mock_point.payload = {
            "document": "Old content",
            "metadata": {"version": 1}
        }
        mock_qdrant_client.retrieve.return_value = [mock_point]
        
        new_entry = Entry(content="Updated content", metadata={"version": 2})
        result = await qdrant_connector.update_point("test_id", new_entry)
        
        assert result is True
        mock_qdrant_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_point_nonexistent(self, qdrant_connector, mock_qdrant_client):
        """Test updating a non-existent point."""
        mock_qdrant_client.retrieve.return_value = []
        
        new_entry = Entry(content="Updated content", metadata={"version": 2})
        result = await qdrant_connector.update_point("nonexistent_id", new_entry)
        
        assert result is False
        mock_qdrant_client.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_point_success(self, qdrant_connector, mock_qdrant_client):
        """Test successful point deletion."""
        # Mock existing point
        mock_point = MagicMock()
        mock_point.payload = {
            "document": "Content to delete",
            "metadata": None
        }
        mock_qdrant_client.retrieve.return_value = [mock_point]
        
        result = await qdrant_connector.delete_point("test_id")
        
        assert result is True
        mock_qdrant_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_point_nonexistent(self, qdrant_connector, mock_qdrant_client):
        """Test deleting a non-existent point."""
        mock_qdrant_client.retrieve.return_value = []
        
        result = await qdrant_connector.delete_point("nonexistent_id")
        
        assert result is False
        mock_qdrant_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_points_success(self, qdrant_connector, mock_qdrant_client):
        """Test successful point listing."""
        # Mock points list
        mock_point1 = MagicMock()
        mock_point1.id = "id1"
        mock_point1.payload = {"document": "Content 1", "metadata": {"tag": "test1"}}
        
        mock_point2 = MagicMock()
        mock_point2.id = "id2"
        mock_point2.payload = {"document": "Content 2", "metadata": None}
        
        mock_qdrant_client.scroll.return_value = ([mock_point1, mock_point2], None)
        
        result = await qdrant_connector.list_points(limit=10)
        
        assert len(result) == 2
        assert result[0][0] == "id1"
        assert result[0][1].content == "Content 1"
        assert result[1][0] == "id2"
        assert result[1][1].content == "Content 2"

    @pytest.mark.asyncio
    async def test_list_points_empty_collection(self, qdrant_connector, mock_qdrant_client):
        """Test listing points from an empty collection."""
        mock_qdrant_client.scroll.return_value = ([], None)
        
        result = await qdrant_connector.list_points()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_collection_not_exists(self, qdrant_connector, mock_qdrant_client):
        """Test operations on non-existent collection."""
        mock_qdrant_client.collection_exists.return_value = False
        
        # Test get_point_by_id
        result = await qdrant_connector.get_point_by_id("test_id")
        assert result is None
        
        # Test update_point
        entry = Entry(content="test", metadata=None)
        result = await qdrant_connector.update_point("test_id", entry)
        assert result is False
        
        # Test delete_point
        result = await qdrant_connector.delete_point("test_id")
        assert result is False
        
        # Test list_points
        result = await qdrant_connector.list_points()
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__])