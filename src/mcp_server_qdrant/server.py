import logging
import sys

from mcp_server_qdrant.mcp_server import QdrantMCPServer
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

try:
    logger.info("Initializing MCP server settings...")
    
    tool_settings = ToolSettings()
    qdrant_settings = QdrantSettings()
    embedding_provider_settings = EmbeddingProviderSettings()
    
    logger.info(f"Qdrant URL: {qdrant_settings.location}")
    logger.info(f"Collection: {qdrant_settings.collection_name}")
    logger.info(f"Read-only mode: {qdrant_settings.read_only}")
    logger.info(f"Embedding provider: {embedding_provider_settings.provider_type}")
    
    logger.info("Creating MCP server instance...")
    mcp = QdrantMCPServer(
        tool_settings=tool_settings,
        qdrant_settings=qdrant_settings,
        embedding_provider_settings=embedding_provider_settings,
    )
    
    logger.info("MCP server initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize MCP server: {e}")
    raise
