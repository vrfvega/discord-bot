import yt_dlp

from src.cache_manager import CacheEntry, CacheManager


class AudioStreamManager:
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.params = {
            "format": "bestaudio[acodec=opus]/bestaudio/best",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
        }
        self.ytdl = yt_dlp.YoutubeDL(self.params)

    def get_audio_stream(self, url: str) -> str:
        """Retrieve the audio stream URL, using the cache if available."""
        entry = self.cache_manager.get_entry(url)

        if entry and entry.audio_stream_url:
            return entry.audio_stream_url

        info = self.ytdl.extract_info(url, download=False)
        audio_stream_url = info["url"]
        
        self.cache_manager.save_entry(
            CacheEntry(source_url=url, audio_stream_url=audio_stream_url)
        )
        return audio_stream_url

    def get_metadata(self, url: str) -> dict:
        """Retrieve metadata about the audio stream."""
        # Fetch using yt-dlp and cache the result
        info = self.ytdl.extract_info(url, download=False)
        metadata = {
            "title": info.get("title"),
            "webpage_url": info.get("webpage_url"),
            "uploader": info.get("uploader"),
        }
        return metadata
