import re
from typing import Optional

import httpx


async def search_youtube(query: str) -> Optional[str]:
    """Search YouTube and return the first video ID matching the query."""
    params = {"search_query": query}
    async with httpx.AsyncClient() as client:
        response = await client.get("https://www.youtube.com/results", params=params)
    search_results = re.findall(r"/watch\?v=(.{11})", response.text)
    return search_results[0] if search_results else None
