import logging
import uuid
from typing import Any

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.settings import METADATA_PATH

logger = logging.getLogger(__name__)

Metadata = dict[str, Any]
ArbitraryFilter = dict[str, Any]


class Entry(BaseModel):
    """
    A single entry in the Qdrant collection.
    """

    content: str
    metadata: Metadata | None = None


class QdrantConnector:
    """
    Encapsulates the connection to a Qdrant server and all the methods to interact with it.
    :param qdrant_url: The URL of the Qdrant server.
    :param qdrant_api_key: The API key to use for the Qdrant server.
    :param collection_name: The name of the default collection to use. If not provided, each tool will require
                            the collection name to be provided.
    :param embedding_provider: The embedding provider to use.
    :param qdrant_local_path: The path to the storage directory for the Qdrant client, if local mode is used.
    """

    def __init__(
        self,
        qdrant_url: str | None,
        qdrant_api_key: str | None,
        collection_name: str | None,
        embedding_provider: EmbeddingProvider,
        qdrant_local_path: str | None = None,
        field_indexes: dict[str, models.PayloadSchemaType] | None = None,
    ):
        self._qdrant_url = qdrant_url.rstrip("/") if qdrant_url else None
        self._qdrant_api_key = qdrant_api_key
        self._default_collection_name = collection_name
        self._embedding_provider = embedding_provider
        self._client = AsyncQdrantClient(
            location=qdrant_url, api_key=qdrant_api_key, path=qdrant_local_path
        )
        self._field_indexes = field_indexes

    async def get_collection_names(self) -> list[str]:
        """
        Get the names of all collections in the Qdrant server.
        :return: A list of collection names.
        """
        response = await self._client.get_collections()
        return [collection.name for collection in response.collections]

    async def store(self, entry: Entry, *, collection_name: str | None = None):
        """
        Store some information in the Qdrant collection, along with the specified metadata.
        :param entry: The entry to store in the Qdrant collection.
        :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                the default collection is used.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        await self._ensure_collection_exists(collection_name)

        # Embed the document
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.
        embeddings = await self._embedding_provider.embed_documents([entry.content])

        # Add to Qdrant
        vector_name = self._embedding_provider.get_vector_name()
        payload = {"document": entry.content, METADATA_PATH: entry.metadata}
        await self._client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=uuid.uuid4().hex,
                    vector={vector_name: embeddings[0]},
                    payload=payload,
                )
            ],
        )

    async def search(
        self,
        query: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[Entry]:
        """
        Find points in the Qdrant collection. If there are no entries found, an empty list is returned.
        :param query: The query to use for the search.
        :param collection_name: The name of the collection to search in, optional. If not provided,
                                the default collection is used.
        :param limit: The maximum number of entries to return.
        :param query_filter: The filter to apply to the query, if any.

        :return: A list of entries found.
        """
        collection_name = collection_name or self._default_collection_name
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Embed the query
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.

        query_vector = await self._embedding_provider.embed_query(query)
        vector_name = self._embedding_provider.get_vector_name()

        # Search in Qdrant
        search_results = await self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using=vector_name,
            limit=limit,
            query_filter=query_filter,
        )

        return [
            Entry(
                content=result.payload["document"],
                metadata=result.payload.get("metadata"),
            )
            for result in search_results.points
        ]

    async def get_point_by_id(
        self,
        point_id: str,
        *,
        collection_name: str | None = None,
    ) -> Entry | None:
        """
        Get a specific point by its ID.
        :param point_id: The ID of the point to retrieve.
        :param collection_name: The name of the collection to search in, optional. If not provided,
                                the default collection is used.
        :return: The entry if found, None otherwise.
        """
        collection_name = collection_name or self._default_collection_name
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return None

        try:
            points = await self._client.retrieve(
                collection_name=collection_name,
                ids=[point_id],
                with_payload=True,
            )
            
            if not points or len(points) == 0:
                return None
                
            point = points[0]
            return Entry(
                content=point.payload["document"],
                metadata=point.payload.get("metadata"),
            )
        except Exception as e:
            logger.error(f"Error retrieving point {point_id}: {e}")
            return None

    async def update_point(
        self,
        point_id: str,
        entry: Entry,
        *,
        collection_name: str | None = None,
    ) -> bool:
        """
        Update an existing point with new content and metadata.
        :param point_id: The ID of the point to update.
        :param entry: The new entry data to update the point with.
        :param collection_name: The name of the collection, optional. If not provided,
                                the default collection is used.
        :return: True if the point was updated successfully, False otherwise.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return False

        try:
            # Check if point exists
            existing_point = await self.get_point_by_id(point_id, collection_name=collection_name)
            if existing_point is None:
                return False

            # Embed the new document
            embeddings = await self._embedding_provider.embed_documents([entry.content])
            
            # Update the point
            vector_name = self._embedding_provider.get_vector_name()
            payload = {"document": entry.content, METADATA_PATH: entry.metadata}
            
            await self._client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector={vector_name: embeddings[0]},
                        payload=payload,
                    )
                ],
            )
            return True
        except Exception as e:
            logger.error(f"Error updating point {point_id}: {e}")
            return False

    async def delete_point(
        self,
        point_id: str,
        *,
        collection_name: str | None = None,
    ) -> bool:
        """
        Delete a point by its ID.
        :param point_id: The ID of the point to delete.
        :param collection_name: The name of the collection, optional. If not provided,
                                the default collection is used.
        :return: True if the point was deleted successfully, False otherwise.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return False

        try:
            # Check if point exists
            existing_point = await self.get_point_by_id(point_id, collection_name=collection_name)
            if existing_point is None:
                return False

            # Delete the point
            await self._client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=[point_id],
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting point {point_id}: {e}")
            return False

    async def list_points(
        self,
        *,
        collection_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[str, Entry]]:
        """
        List points in the collection with their IDs.
        :param collection_name: The name of the collection, optional. If not provided,
                                the default collection is used.
        :param limit: Maximum number of points to return.
        :param offset: Number of points to skip.
        :return: A list of tuples containing (point_id, entry).
        """
        collection_name = collection_name or self._default_collection_name
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        try:
            points = await self._client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                with_payload=True,
            )
            
            return [
                (
                    str(point.id),
                    Entry(
                        content=point.payload["document"],
                        metadata=point.payload.get("metadata"),
                    )
                )
                for point in points[0]  # points[0] contains the actual points
            ]
        except Exception as e:
            logger.error(f"Error listing points: {e}")
            return []

    async def _ensure_collection_exists(self, collection_name: str):
        """
        Ensure that the collection exists, creating it if necessary.
        :param collection_name: The name of the collection to ensure exists.
        """
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            # Create the collection with the appropriate vector size
            vector_size = self._embedding_provider.get_vector_size()

            # Use the vector name as defined in the embedding provider
            vector_name = self._embedding_provider.get_vector_name()
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    vector_name: models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    )
                },
            )

            # Create payload indexes if configured

            if self._field_indexes:
                for field_name, field_type in self._field_indexes.items():
                    await self._client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_type,
                    )
