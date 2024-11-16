import asyncio
import logging
from typing import Union


import yt_dlp
import pytubefix

from src.cache_manager import CacheEntry, CacheManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],  # Log to console
)

logger = logging.getLogger(__name__)


class AudioStreamManager:
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        

    async def get_stream_info(self, url: str) -> Union[str, dict]:
        """
        Asynchronously retrieve the audio stream URL and metadata, using the cache if available.
        :param url: The URL of the video to extract audio stream information from.
        :return: The audio stream URL and metadata as a dictionary.
        """
        
        # Check cache for the URL
        entry = self.cache_manager.get_entry(url)
        if entry:
            logger.info(f"Cache hit for URL: {url}")
            return entry.stream_url, entry.meta

        try:
            # Use pytubefix to fetch video information
            logger.info(f"Fetching video info for URL: {url}")
            yt = await asyncio.to_thread(pytubefix.YouTube, url)  # Run in a thread since pytubefix is blocking

            # Select the best audio stream
            audio_stream = yt.streams.filter(only_audio=True).first()
            if not audio_stream:
                raise ValueError("No audio streams available for this URL.")

            # Prepare metadata
            stream_url = audio_stream.url
            meta = {
                "title": yt.title,
                "webpage_url": yt.watch_url,
                "uploader": yt.author,
            }

            # Save to cache
            self.cache_manager.save_entry(
                CacheEntry(source_url=url, stream_url=stream_url, meta=meta)
            )
            logger.info(f"Stream info fetched successfully for URL: {url}")

            return stream_url, meta

        except Exception as e:
            
            logger.error(f"Failed to fetch stream info for URL {url}: {e}")
            raise
