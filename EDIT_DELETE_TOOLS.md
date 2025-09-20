# Edit and Delete Tools for MCP Server Qdrant

This document describes the new edit and delete functionality added to the MCP server for Qdrant.

## New Tools

### 1. qdrant-list
**Purpose**: List memory points in Qdrant with their IDs and content.

**Parameters**:
- `collection_name` (string): The collection to list points from
- `limit` (integer, optional): Maximum number of points to return (1-1000, default: 100)
- `offset` (integer, optional): Number of points to skip for pagination (default: 0)

**Returns**: A list of formatted entries with their IDs.

**Example Usage**:
```json
{
  "tool": "qdrant-list",
  "arguments": {
    "collection_name": "my_memories",
    "limit": 50,
    "offset": 0
  }
}
```

### 2. qdrant-edit
**Purpose**: Edit an existing memory point in Qdrant by its ID.

**Parameters**:
- `point_id` (string): The ID of the point to edit
- `information` (string): New text content for the point
- `collection_name` (string): The collection containing the point to edit
- `metadata` (object, optional): New metadata for the point (any JSON is accepted)

**Returns**: Success or failure message.

**Example Usage**:
```json
{
  "tool": "qdrant-edit",
  "arguments": {
    "point_id": "abc123def456",
    "information": "Updated memory content",
    "collection_name": "my_memories",
    "metadata": {
      "updated_at": "2024-01-20",
      "version": 2
    }
  }
}
```

### 3. qdrant-delete
**Purpose**: Delete a memory point from Qdrant by its ID.

**Parameters**:
- `point_id` (string): The ID of the point to delete
- `collection_name` (string): The collection containing the point to delete

**Returns**: Success or failure message.

**Example Usage**:
```json
{
  "tool": "qdrant-delete",
  "arguments": {
    "point_id": "abc123def456",
    "collection_name": "my_memories"
  }
}
```

## Workflow Example

Here's a typical workflow for editing or deleting points:

1. **List points** to find the ID of the point you want to modify:
   ```json
   {
     "tool": "qdrant-list",
     "arguments": {
       "collection_name": "my_memories",
       "limit": 10
     }
   }
   ```

2. **Edit a point** using its ID:
   ```json
   {
     "tool": "qdrant-edit",
     "arguments": {
       "point_id": "found_id_from_list",
       "information": "Corrected information",
       "collection_name": "my_memories"
     }
   }
   ```

3. **Or delete a point** if it's no longer needed:
   ```json
   {
     "tool": "qdrant-delete",
     "arguments": {
       "point_id": "found_id_from_list",
       "collection_name": "my_memories"
     }
   }
   ```

## Security and Configuration

### Read-Only Mode
When the server is configured with `read_only=True`, the edit and delete tools are automatically disabled. Only the `qdrant-find` and `qdrant-list` tools will be available.

### Collection Configuration
If a default collection is configured in the server settings, the `collection_name` parameter becomes optional and will default to the configured collection.

### Environment Variables
When running in Docker, set the API key securely at runtime:

```bash
docker run -e QDRANT_API_KEY="your_secret_key" your_image
```

**Note**: The `QDRANT_API_KEY` environment variable has been removed from the Dockerfile for security reasons and should be provided at runtime.

## Error Handling

The tools include comprehensive error handling:

- **Point Not Found**: If you try to edit or delete a non-existent point, you'll get a clear error message
- **Collection Not Found**: If the specified collection doesn't exist, the operation will fail gracefully
- **Invalid IDs**: Malformed point IDs will be handled appropriately
- **Network Issues**: Connection problems with Qdrant will be reported

## Technical Implementation

### Core Methods Added
- `get_point_by_id()`: Retrieve a specific point by its ID
- `update_point()`: Update an existing point with new content and metadata
- `delete_point()`: Delete a point by its ID
- `list_points()`: List points with pagination support

### Safety Features
- All operations verify that points exist before modifying them
- Collection existence is checked before any operation
- Proper error logging for debugging
- Transactional safety with Qdrant's upsert mechanism

## Building and Deployment

The updated Dockerfile now builds from the local source code to include these new tools:

```bash
# Build the container
docker build -t mcp-server-qdrant .

# Run with your configuration
docker run -p 8000:8000 \
  -e QDRANT_URL="http://your-qdrant:6333" \
  -e QDRANT_API_KEY="your_secret_key" \
  -e COLLECTION_NAME="your_collection" \
  mcp-server-qdrant
```

## Testing

Run the included test script to verify the tools are properly registered:

```bash
python test_new_tools.py
```

This will test both normal mode (all tools available) and read-only mode (edit/delete tools disabled).