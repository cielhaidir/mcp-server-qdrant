FROM python:3.11-slim

WORKDIR /app

# Install uv for package management
RUN pip install --no-cache-dir uv

# Copy the project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package and its dependencies
RUN uv pip install --system --no-cache-dir .

# Expose the default port for SSE transport
EXPOSE 8000

# Set environment variables with defaults that can be overridden at runtime
# Note: QDRANT_API_KEY should be set at runtime for security reasons
ENV QDRANT_URL=""
ENV COLLECTION_NAME="default-collection"
ENV EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"

# Run the server with SSE transport
CMD ["python", "-m", "mcp_server_qdrant.main", "--transport", "sse"]
