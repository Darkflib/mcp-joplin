#!/usr/bin/env python3
"""
Test script for the Joplin MCP Server.

This script tests the MCP server functionality by simulating MCP protocol calls.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config
from src.logging_config import setup_logging
from src.server import create_mcp_server


async def test_mcp_server():
    """Test the MCP server functionality."""
    try:
        print("🧪 Testing Joplin MCP Server...")

        # Load configuration
        config_manager = load_config("config.json")
        config = config_manager.get_config()

        # Setup logging
        setup_logging(level="INFO", format_type="text")

        # Create and initialize the server
        print("📦 Initializing server...")
        joplin_server = await create_mcp_server(config)

        # Test server info
        print("\n📋 Server Information:")
        server_info = await joplin_server.get_server_info()
        print(f"  • Name: {server_info['name']}")
        print(f"  • Version: {server_info['version']}")
        print(f"  • Tools: {server_info['tools_count']}")
        print(f"  • Connection Status: {server_info['connection_status']['status']}")

        # Test health check
        print("\n🏥 Health Check:")
        health = await joplin_server.health_check()
        print(f"  • Overall Status: {health['status']}")
        print(
            f"  • Connection: {'✅' if health.get('connection', {}).get('connected') else '❌'}"
        )
        print(
            f"  • Response Time: {health.get('connection', {}).get('response_time_ms', 'N/A')}ms"
        )

        # Test tool listing
        print("\n🔧 Available Tools:")
        tools = await joplin_server.list_tools()
        for tool in tools:
            print(f"  • {tool.name}: {tool.description}")

        # Test a simple tool call (list notebooks)
        print("\n📓 Testing 'list_notebooks' tool:")
        try:
            from src.tools.list_notebooks import list_notebooks_handler

            # Execute the tool
            result = await list_notebooks_handler({})

            if result:
                # Parse the JSON response
                response_data = json.loads(result[0].text)
                notebooks = response_data.get("notebooks", [])
                print(f"  • Found {len(notebooks)} notebooks")

                # Show first few notebooks
                for i, notebook in enumerate(notebooks[:3]):
                    print(f"    {i+1}. {notebook.get('title', 'Untitled')}")

                if len(notebooks) > 3:
                    print(f"    ... and {len(notebooks) - 3} more")
            else:
                print("  • No result returned")

        except Exception as e:
            print(f"  • Error testing tool: {e}")

        print("\n✅ MCP Server test completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        if "joplin_server" in locals():
            await joplin_server.shutdown()


async def test_connection_only():
    """Test just the connection to Joplin."""
    try:
        print("🔗 Testing Joplin connection...")

        # Load configuration
        config_manager = load_config("config.json")
        config = config_manager.get_config()

        # Setup logging
        setup_logging(level="INFO", format_type="text")

        # Test just the connection
        from src.services.connection_manager import ConnectionManager

        async with ConnectionManager(config["joplin"]) as conn_mgr:
            print("📡 Attempting to connect to Joplin...")
            success = await conn_mgr.ensure_connected()

            if success:
                print("✅ Connected to Joplin successfully!")

                # Get connection status
                status = await conn_mgr.get_connection_status()
                print(f"  • URL: {status['base_url']}")
                print(f"  • Status: {status['status']}")
                print(f"  • Timeout: {status['timeout']}s")

                # Perform health check
                health = await conn_mgr.health_check()
                print(
                    f"  • Health: {'✅ Healthy' if health['connected'] else '❌ Unhealthy'}"
                )
                if health.get("response_time_ms"):
                    print(f"  • Response Time: {health['response_time_ms']}ms")

            else:
                print("❌ Failed to connect to Joplin")
                return False

        return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--connection-only":
        success = asyncio.run(test_connection_only())
    else:
        success = asyncio.run(test_mcp_server())

    sys.exit(0 if success else 1)
