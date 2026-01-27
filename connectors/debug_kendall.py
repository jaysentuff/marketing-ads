"""Debug Kendall MCP SSE connection."""

import asyncio
import httpx
import json

KENDALL_URL = "https://mcp.kendall.ai/sse?store_id=1126&secret=1waF3I5RxGA0cyNjm0m0"

async def debug_sse():
    print(f"Connecting to: {KENDALL_URL[:60]}...")
    print()

    headers = {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
    }

    timeout = httpx.Timeout(60.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("GET", KENDALL_URL, headers=headers) as response:
                print(f"Status: {response.status_code}")
                print(f"Headers: {dict(response.headers)}")
                print()

                if response.status_code != 200:
                    body = await response.aread()
                    print(f"Error body: {body.decode()}")
                    return

                print("Waiting for SSE events...")
                print("-" * 50)

                buffer = ""
                event_count = 0

                async for chunk in response.aiter_text():
                    buffer += chunk

                    # Parse SSE events
                    while "\n\n" in buffer:
                        event_text, buffer = buffer.split("\n\n", 1)
                        event_count += 1

                        print(f"\n=== Event {event_count} ===")

                        event_type = "message"
                        event_data = ""

                        for line in event_text.split("\n"):
                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                event_data = line[5:].strip()
                            elif line.startswith(":"):
                                # Comment/keepalive
                                print(f"Comment: {line}")

                        if event_type or event_data:
                            print(f"Type: {event_type}")
                            print(f"Data: {event_data[:500]}")

                            if event_data:
                                try:
                                    parsed = json.loads(event_data)
                                    print(f"Parsed: {json.dumps(parsed, indent=2)[:500]}")
                                except:
                                    pass

                        if event_count >= 5:
                            print("\n[Stopping after 5 events]")
                            return

        except httpx.TimeoutException as e:
            print(f"Timeout: {e}")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(debug_sse())
