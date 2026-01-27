"""
Kendall.ai SSE/MCP Client

Direct connection to Kendall's MCP server to pull attribution data.
"""

import json
import requests
import sseclient
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Kendall MCP endpoint
KENDALL_URL = "https://mcp.kendall.ai/sse?store_id=1126&secret=1waF3I5RxGA0cyNjm0m0"


class KendallMCPClient:
    """Client for Kendall's MCP server."""

    def __init__(self, url: str = KENDALL_URL):
        self.url = url
        self.data_dir = Path(__file__).parent / "data" / "kendall"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _send_request(self, method: str, params: dict = None) -> dict:
        """Send JSON-RPC request over SSE and get response."""
        request_id = str(uuid.uuid4())

        # MCP uses JSON-RPC 2.0
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }

        # For SSE, we need to POST the request and listen for response
        # First, let's discover available tools
        response = requests.get(self.url, stream=True, timeout=30)

        client = sseclient.SSEClient(response)

        result = None
        for event in client.events():
            if event.data:
                try:
                    data = json.loads(event.data)
                    print(f"Received: {json.dumps(data, indent=2)[:500]}")
                    result = data
                    break
                except json.JSONDecodeError:
                    print(f"Raw event: {event.data[:200]}")

        return result

    def discover_tools(self):
        """Discover available MCP tools."""
        print("Connecting to Kendall MCP server...")
        print(f"URL: {self.url[:50]}...")

        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }

        try:
            response = requests.get(self.url, stream=True, timeout=30, headers=headers)
            print(f"Connection status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")

            client = sseclient.SSEClient(response)

            print("\nListening for events...")
            for i, event in enumerate(client.events()):
                print(f"\nEvent {i+1}:")
                print(f"  Type: {event.event}")
                if event.data:
                    try:
                        data = json.loads(event.data)
                        print(f"  Data: {json.dumps(data, indent=2)[:1000]}")
                    except:
                        print(f"  Raw: {event.data[:500]}")

                if i >= 5:  # Limit to first 5 events for discovery
                    break

        except Exception as e:
            print(f"Error: {e}")

    def save_data(self, data: dict, filename: str):
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath


def main():
    """Test the Kendall MCP client."""
    client = KendallMCPClient()
    client.discover_tools()


if __name__ == "__main__":
    main()
