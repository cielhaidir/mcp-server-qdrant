import argparse


def main():
    """
    Main entry point for the mcp-server-qdrant script defined
    in pyproject.toml. It runs the MCP server with a specific transport
    protocol.
    """

    # Parse the command-line arguments to determine the transport protocol.
    parser = argparse.ArgumentParser(description="mcp-server-qdrant")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to for SSE/HTTP transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to for SSE/HTTP transport (default: 8000)",
    )
    args = parser.parse_args()

    # Import is done here to make sure environment variables are loaded
    # only after we make the changes.
    from mcp_server_qdrant.server import mcp

    # Configure run parameters based on transport
    run_kwargs = {"transport": args.transport}
    
    if args.transport in ["sse", "streamable-http"]:
        run_kwargs.update({
            "host": args.host,
            "port": args.port,
        })
        print(f"Starting MCP server on {args.host}:{args.port} with {args.transport} transport")
    else:
        print(f"Starting MCP server with {args.transport} transport")

    mcp.run(**run_kwargs)
