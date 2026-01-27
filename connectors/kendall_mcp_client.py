"""
Kendall.ai MCP Client using official SDK

Connects to Kendall's MCP server to pull attribution data.
"""

import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client


KENDALL_URL = "https://mcp.kendall.ai/sse?store_id=1126&secret=1waF3I5RxGA0cyNjm0m0"


async def main():
    print("Connecting to Kendall MCP server...")
    print(f"URL: {KENDALL_URL[:50]}...")

    try:
        async with sse_client(KENDALL_URL) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                print("Initializing session...")
                await session.initialize()

                # List available tools
                print("\nListing available tools...")
                tools = await session.list_tools()

                print(f"\nFound {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description[:100] if tool.description else 'No description'}")

                # Try to call a tool to get attribution data
                for tool in tools.tools:
                    if 'attribution' in tool.name.lower() or 'revenue' in tool.name.lower():
                        print(f"\nCalling {tool.name}...")
                        result = await session.call_tool(tool.name, {})
                        print(f"Result: {result}")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
