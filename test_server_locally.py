#!/usr/bin/env python3
"""
Test script to verify the MCP server starts correctly and tools are available.
"""

import asyncio
import sys
import subprocess
import time
import requests
from threading import Thread
import signal
import os

# Add the src directory to the path
sys.path.insert(0, 'src')

def test_server_startup():
    """Test that the server starts up without errors."""
    print("Testing server startup...")
    
    # Set minimal environment variables
    env = os.environ.copy()
    env.update({
        'QDRANT_URL': 'http://localhost:6333',
        'COLLECTION_NAME': 'test_collection',
        'EMBEDDING_MODEL': 'sentence-transformers/all-MiniLM-L6-v2'
    })
    
    try:
        # Test stdio transport (should start and exit quickly)
        print("Testing stdio transport...")
        result = subprocess.run([
            sys.executable, '-m', 'mcp_server_qdrant.main', 
            '--transport', 'stdio'
        ], 
        env=env,
        input='',  # Empty input to make it exit
        text=True,
        capture_output=True,
        timeout=10
        )
        
        print(f"Stdio transport exit code: {result.returncode}")
        if result.stdout:
            print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")
            
        # Test server initialization (import only)
        print("\nTesting server initialization...")
        try:
            from mcp_server_qdrant.server import mcp
            print("✅ Server initialized successfully")
            
            # Get available tools
            tools = mcp.get_tools()
            print(f"Available tools: {[tool.name for tool in tools]}")
            
            expected_tools = ['qdrant-find', 'qdrant-list']  # Read-only by default
            if not any(setting.read_only for setting in []):  # Check if not read-only
                expected_tools.extend(['qdrant-store', 'qdrant-edit', 'qdrant-delete'])
            
            missing_tools = []
            for expected in expected_tools:
                if not any(tool.name == expected for tool in tools):
                    missing_tools.append(expected)
            
            if missing_tools:
                print(f"❌ Missing tools: {missing_tools}")
                return False
            else:
                print("✅ All expected tools are available")
                return True
                
        except Exception as e:
            print(f"❌ Server initialization failed: {e}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Server startup timed out")
        return False
    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        return False

def test_sse_server():
    """Test that SSE server starts and responds."""
    print("\nTesting SSE server startup...")
    
    env = os.environ.copy()
    env.update({
        'QDRANT_URL': 'http://localhost:6333',
        'COLLECTION_NAME': 'test_collection',
        'EMBEDDING_MODEL': 'sentence-transformers/all-MiniLM-L6-v2'
    })
    
    # Start SSE server in background
    process = None
    try:
        process = subprocess.Popen([
            sys.executable, '-m', 'mcp_server_qdrant.main',
            '--transport', 'sse',
            '--host', '127.0.0.1',
            '--port', '8001'  # Use different port to avoid conflicts
        ], 
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
        )
        
        # Give server time to start
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"❌ SSE server exited early with code {process.returncode}")
            print(f"Stdout: {stdout}")
            print(f"Stderr: {stderr}")
            return False
        
        # Try to connect to the server
        try:
            response = requests.get('http://127.0.0.1:8001/', timeout=5)
            print(f"✅ SSE server responding (status: {response.status_code})")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Could not connect to SSE server: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start SSE server: {e}")
        return False
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

if __name__ == "__main__":
    print("MCP Server Test Suite")
    print("=" * 50)
    
    success1 = test_server_startup()
    success2 = test_sse_server()
    
    if success1 and success2:
        print(f"\n🎉 All tests passed! Server is working correctly.")
        sys.exit(0)
    else:
        print(f"\n💥 Some tests failed!")
        sys.exit(1)