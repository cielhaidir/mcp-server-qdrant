import json
import logging
from typing import Annotated, Any, Optional

from fastmcp import Context, FastMCP
from pydantic import Field
from qdrant_client import models

from mcp_server_qdrant.common.filters import make_indexes
from mcp_server_qdrant.common.func_tools import make_partial_function
from mcp_server_qdrant.common.wrap_filters import wrap_filters
from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.qdrant import ArbitraryFilter, Entry, Metadata, QdrantConnector
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)

logger = logging.getLogger(__name__)


# FastMCP is an alternative interface for declaring the capabilities
# of the server. Its API is based on FastAPI.
class QdrantMCPServer(FastMCP):
    """
    A MCP server for Qdrant.
    """

    def __init__(
        self,
        tool_settings: ToolSettings,
        qdrant_settings: QdrantSettings,
        embedding_provider_settings: Optional[EmbeddingProviderSettings] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        name: str = "mcp-server-qdrant",
        instructions: str | None = None,
        **settings: Any,
    ):
        self.tool_settings = tool_settings
        self.qdrant_settings = qdrant_settings

        if embedding_provider_settings and embedding_provider:
            raise ValueError(
                "Cannot provide both embedding_provider_settings and embedding_provider"
            )

        if not embedding_provider_settings and not embedding_provider:
            raise ValueError(
                "Must provide either embedding_provider_settings or embedding_provider"
            )

        self.embedding_provider_settings: Optional[EmbeddingProviderSettings] = None
        self.embedding_provider: Optional[EmbeddingProvider] = None

        if embedding_provider_settings:
            self.embedding_provider_settings = embedding_provider_settings
            self.embedding_provider = create_embedding_provider(
                embedding_provider_settings
            )
        else:
            self.embedding_provider_settings = None
            self.embedding_provider = embedding_provider

        assert self.embedding_provider is not None, "Embedding provider is required"

        self.qdrant_connector = QdrantConnector(
            qdrant_settings.location,
            qdrant_settings.api_key,
            qdrant_settings.collection_name,
            self.embedding_provider,
            qdrant_settings.local_path,
            make_indexes(qdrant_settings.filterable_fields_dict()),
        )

        super().__init__(name=name, instructions=instructions, **settings)

        self.setup_tools()

    def format_entry(self, entry: Entry) -> str:
        """
        Feel free to override this method in your subclass to customize the format of the entry.
        """
        entry_metadata = json.dumps(entry.metadata) if entry.metadata else ""
        return f"<entry><content>{entry.content}</content><metadata>{entry_metadata}</metadata></entry>"

    def setup_tools(self):
        """
        Register the tools in the server.
        """

        async def store(
            ctx: Context,
            information: Annotated[str, Field(description="Text to store")],
            collection_name: Annotated[
                str, Field(description="The collection to store the information in")
            ],
            # The `metadata` parameter is defined as non-optional, but it can be None.
            # If we set it to be optional, some of the MCP clients, like Cursor, cannot
            # handle the optional parameter correctly.
            metadata: Annotated[
                Metadata | None,
                Field(
                    description="Extra metadata stored along with memorised information. Any json is accepted."
                ),
            ] = None,
        ) -> str:
            """
            Store some information in Qdrant.
            :param ctx: The context for the request.
            :param information: The information to store.
            :param metadata: JSON metadata to store with the information, optional.
            :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                    the default collection is used.
            :return: A message indicating that the information was stored.
            """
            await ctx.debug(f"Storing information {information} in Qdrant")

            entry = Entry(content=information, metadata=metadata)

            await self.qdrant_connector.store(entry, collection_name=collection_name)
            if collection_name:
                return f"Remembered: {information} in collection {collection_name}"
            return f"Remembered: {information}"

        async def find(
            ctx: Context,
            query: Annotated[str, Field(description="What to search for")],
            collection_name: Annotated[
                str, Field(description="The collection to search in")
            ],
            query_filter: ArbitraryFilter | None = None,
        ) -> list[str] | None:
            """
            Find memories in Qdrant.
            :param ctx: The context for the request.
            :param query: The query to use for the search.
            :param collection_name: The name of the collection to search in, optional. If not provided,
                                    the default collection is used.
            :param query_filter: The filter to apply to the query.
            :return: A list of entries found or None.
            """

            # Log query_filter
            await ctx.debug(f"Query filter: {query_filter}")

            query_filter = models.Filter(**query_filter) if query_filter else None

            await ctx.debug(f"Finding results for query {query}")

            entries = await self.qdrant_connector.search(
                query,
                collection_name=collection_name,
                limit=self.qdrant_settings.search_limit,
                query_filter=query_filter,
            )
            if not entries:
                return None
            content = [
                f"Results for the query '{query}'",
            ]
            for entry in entries:
                content.append(self.format_entry(entry))
            return content

        find_foo = find
        store_foo = store

        filterable_conditions = (
            self.qdrant_settings.filterable_fields_dict_with_conditions()
        )

        if len(filterable_conditions) > 0:
            find_foo = wrap_filters(find_foo, filterable_conditions)
        elif not self.qdrant_settings.allow_arbitrary_filter:
            find_foo = make_partial_function(find_foo, {"query_filter": None})

        if self.qdrant_settings.collection_name:
            find_foo = make_partial_function(
                find_foo, {"collection_name": self.qdrant_settings.collection_name}
            )
            store_foo = make_partial_function(
                store_foo, {"collection_name": self.qdrant_settings.collection_name}
            )

        self.tool(
            find_foo,
            name="qdrant-find",
            description=self.tool_settings.tool_find_description,
        )

        # List tool (read-only operation)
        async def list_points(
            ctx: Context,
            collection_name: Annotated[
                str, Field(description="The collection to list points from")
            ],
            limit: Annotated[
                int, Field(description="Maximum number of points to return", ge=1, le=1000)
            ] = 100,
            offset: Annotated[
                int, Field(description="Number of points to skip", ge=0)
            ] = 0,
        ) -> list[str]:
            """
            List memory points in Qdrant with their IDs and content.
            :param ctx: The context for the request.
            :param collection_name: The name of the collection to list points from.
            :param limit: Maximum number of points to return (1-1000).
            :param offset: Number of points to skip for pagination.
            :return: A list of formatted entries with their IDs.
            """
            await ctx.debug(f"Listing points from collection {collection_name}")
            
            points_with_ids = await self.qdrant_connector.list_points(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
            )
            
            if not points_with_ids:
                return ["No points found in the collection."]
            
            content = [
                f"Found {len(points_with_ids)} points in collection '{collection_name}':",
            ]
            for point_id, entry in points_with_ids:
                content.append(f"<point><id>{point_id}</id>{self.format_entry(entry)}</point>")
            
            return content

        list_foo = list_points

        if self.qdrant_settings.collection_name:
            list_foo = make_partial_function(
                list_foo, {"collection_name": self.qdrant_settings.collection_name}
            )

        # Register the list tool (always available as it's read-only)
        self.tool(
            list_foo,
            name="qdrant-list",
            description=self.tool_settings.tool_list_description,
        )

        if not self.qdrant_settings.read_only:
            # Those methods can modify the database
            self.tool(
                store_foo,
                name="qdrant-store",
                description=self.tool_settings.tool_store_description,
            )

            # Edit tool
            async def edit_point(
                ctx: Context,
                point_id: Annotated[str, Field(description="The ID of the point to edit")],
                information: Annotated[str, Field(description="New text content for the point")],
                collection_name: Annotated[
                    str, Field(description="The collection containing the point to edit")
                ],
                metadata: Annotated[
                    Metadata | None,
                    Field(
                        description="New metadata for the point. Any json is accepted."
                    ),
                ] = None,
            ) -> str:
                """
                Edit an existing memory point in Qdrant by its ID.
                :param ctx: The context for the request.
                :param point_id: The ID of the point to edit.
                :param information: The new content for the point.
                :param collection_name: The name of the collection containing the point.
                :param metadata: New JSON metadata to store with the information, optional.
                :return: A message indicating the result of the edit operation.
                """
                await ctx.debug(f"Editing point {point_id} in collection {collection_name}")

                entry = Entry(content=information, metadata=metadata)
                success = await self.qdrant_connector.update_point(
                    point_id, entry, collection_name=collection_name
                )

                if success:
                    return f"Successfully updated point {point_id} in collection {collection_name}"
                else:
                    return f"Failed to update point {point_id}. Point may not exist or collection may not exist."

            # Delete tool
            async def delete_point(
                ctx: Context,
                point_id: Annotated[str, Field(description="The ID of the point to delete")],
                collection_name: Annotated[
                    str, Field(description="The collection containing the point to delete")
                ],
            ) -> str:
                """
                Delete a memory point from Qdrant by its ID.
                :param ctx: The context for the request.
                :param point_id: The ID of the point to delete.
                :param collection_name: The name of the collection containing the point.
                :return: A message indicating the result of the delete operation.
                """
                await ctx.debug(f"Deleting point {point_id} from collection {collection_name}")

                success = await self.qdrant_connector.delete_point(
                    point_id, collection_name=collection_name
                )

                if success:
                    return f"Successfully deleted point {point_id} from collection {collection_name}"
                else:
                    return f"Failed to delete point {point_id}. Point may not exist or collection may not exist."

            edit_foo = edit_point
            delete_foo = delete_point

            if self.qdrant_settings.collection_name:
                edit_foo = make_partial_function(
                    edit_foo, {"collection_name": self.qdrant_settings.collection_name}
                )
                delete_foo = make_partial_function(
                    delete_foo, {"collection_name": self.qdrant_settings.collection_name}
                )

            # Register the edit and delete tools
            self.tool(
                edit_foo,
                name="qdrant-edit",
                description=self.tool_settings.tool_edit_description,
            )

            self.tool(
                delete_foo,
                name="qdrant-delete",
                description=self.tool_settings.tool_delete_description,
            )
