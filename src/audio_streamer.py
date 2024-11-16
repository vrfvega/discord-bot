import asyncio
from typing import Union

import yt_dlp

from src.cache_manager import CacheEntry, CacheManager


class AudioStreamManager:
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.params = {
            "format": "bestaudio/best",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "cookiefile": "cookies.txt",
        }
        self.ytdl = yt_dlp.YoutubeDL(self.params)

    async def get_stream_info(self, url: str) -> Union[str, dict]:
        """Asynchronously retrieve the audio stream URL and metadata, using the cache if available."""
        entry = self.cache_manager.get_entry(url)

        if entry and entry.audio_stream_url:
            return entry.audio_stream_url, entry.metadata

        # Use asyncio.to_thread to run the blocking extract_info in a separate thread
        info = await asyncio.to_thread(self.ytdl.extract_info, url, download=False)
        stream_url = info["url"]
        metadata = {
            "title": info.get("title"),
            "webpage_url": info.get("webpage_url"),
            "uploader": info.get("uploader"),
        }

        self.cache_manager.save_entry(
            CacheEntry(source_url=url, audio_stream_url=stream_url, metadata=metadata)
        )
        return stream_url, metadata
