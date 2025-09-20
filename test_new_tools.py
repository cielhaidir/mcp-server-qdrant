#!/usr/bin/env python3
"""
Simple test script to verify that the new edit and delete tools are available
in the MCP server.
"""

import json
import sys
from typing import Any

# Add the src directory to the path so we can import our modules
sys.path.insert(0, 'src')

from mcp_server_qdrant.mcp_server import QdrantMCPServer
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)


def test_tools_registration():
    """Test that all expected tools are registered."""
    
    # Create server instance
    tool_settings = ToolSettings()
    qdrant_settings = QdrantSettings(
        location="http://localhost:6333",
        collection_name="test_collection",
        read_only=False  # Ensure edit/delete tools are enabled
    )
    embedding_provider_settings = EmbeddingProviderSettings()
    
    try:
        server = QdrantMCPServer(
            tool_settings=tool_settings,
            qdrant_settings=qdrant_settings,
            embedding_provider_settings=embedding_provider_settings,
        )
        
        # Get the registered tools
        tools = server.get_tools()
        tool_names = [tool.name for tool in tools]
        
        print("Registered tools:")
        for name in sorted(tool_names):
            print(f"  - {name}")
        
        # Check for expected tools
        expected_tools = ["qdrant-find", "qdrant-store", "qdrant-edit", "qdrant-delete", "qdrant-list"]
        
        missing_tools = []
        for expected in expected_tools:
            if expected not in tool_names:
                missing_tools.append(expected)
        
        if missing_tools:
            print(f"\n❌ Missing tools: {missing_tools}")
            return False
        else:
            print(f"\n✅ All expected tools are registered!")
            
            # Print tool descriptions
            print("\nTool descriptions:")
            for tool in tools:
                if tool.name.startswith("qdrant-"):
                    print(f"\n{tool.name}:")
                    print(f"  Description: {tool.description}")
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        properties = tool.inputSchema.get('properties', {})
                        if properties:
                            print("  Parameters:")
                            for param_name, param_info in properties.items():
                                param_desc = param_info.get('description', 'No description')
                                param_type = param_info.get('type', 'unknown')
                                print(f"    - {param_name} ({param_type}): {param_desc}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error creating server: {e}")
        return False


def test_read_only_mode():
    """Test that edit/delete tools are not available in read-only mode."""
    
    print("\n" + "="*60)
    print("Testing read-only mode (edit/delete tools should be disabled)")
    print("="*60)
    
    tool_settings = ToolSettings()
    qdrant_settings = QdrantSettings(
        location="http://localhost:6333",
        collection_name="test_collection",
        read_only=True  # Enable read-only mode
    )
    embedding_provider_settings = EmbeddingProviderSettings()
    
    try:
        server = QdrantMCPServer(
            tool_settings=tool_settings,
            qdrant_settings=qdrant_settings,
            embedding_provider_settings=embedding_provider_settings,
        )
        
        tools = server.get_tools()
        tool_names = [tool.name for tool in tools]
        
        print("Registered tools in read-only mode:")
        for name in sorted(tool_names):
            print(f"  - {name}")
        
        # In read-only mode, we should only have find and list tools
        expected_readonly_tools = ["qdrant-find", "qdrant-list"]
        forbidden_tools = ["qdrant-store", "qdrant-edit", "qdrant-delete"]
        
        # Check that forbidden tools are not present
        present_forbidden = [tool for tool in forbidden_tools if tool in tool_names]
        missing_expected = [tool for tool in expected_readonly_tools if tool not in tool_names]
        
        if present_forbidden:
            print(f"\n❌ Forbidden tools present in read-only mode: {present_forbidden}")
            return False
        elif missing_expected:
            print(f"\n❌ Expected read-only tools missing: {missing_expected}")
            return False
        else:
            print(f"\n✅ Read-only mode working correctly!")
            return True
            
    except Exception as e:
        print(f"❌ Error creating server in read-only mode: {e}")
        return False


if __name__ == "__main__":
    print("Testing MCP Server Tool Registration")
    print("="*60)
    
    # Test normal mode (all tools should be available)
    success1 = test_tools_registration()
    
    # Test read-only mode (edit/delete tools should be disabled)
    success2 = test_read_only_mode()
    
    if success1 and success2:
        print(f"\n🎉 All tests passed! The edit and delete tools are working correctly.")
        sys.exit(0)
    else:
        print(f"\n💥 Some tests failed!")
        sys.exit(1)