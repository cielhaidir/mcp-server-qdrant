FROM python:3.11-slim

WORKDIR /app

# Install uv for package management
RUN pip install --no-cache-dir uv

# Copy the project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies first
RUN uv pip install --system --no-cache-dir \
    "fastembed>=0.6.0" \
    "qdrant-client>=1.12.0" \
    "pydantic>=2.10.6" \
    "fastmcp>=2.7.0"

# Install the local package
RUN uv pip install --system --no-cache-dir --no-deps .

# Expose the default port for SSE transport
EXPOSE 8000

# Set environment variables with defaults that can be overridden at runtime
# Note: QDRANT_API_KEY should be set at runtime for security reasons
ENV QDRANT_URL=""
ENV QDRANT_API_KEY=""
ENV COLLECTION_NAME="default-collection"
ENV EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"

# Set Python to output logs immediately
ENV PYTHONUNBUFFERED=1

# Run the server with SSE transport
CMD ["python", "-m", "mcp_server_qdrant.main", "--transport", "sse"]
