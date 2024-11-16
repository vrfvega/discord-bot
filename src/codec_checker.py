import json
import subprocess

from src.cache_manager import CacheManager


class CodecChecker:
    def __init__(self, cache_manager: CacheManager):
        """
        Initialize CodecChecker with a CacheManager instance.
        :param cache_manager: An instance of CacheManager for managing cached entries.
        """
        self.cache_manager = cache_manager

    def is_opus_encoded(self, stream_url: str) -> bool:
        """
        Check if the given audio stream URL is Opus-encoded using ffprobe.
        Updates the cache with the result.
        :param stream_url: The URL of the audio stream.
        :return: True if Opus-encoded, False otherwise.
        """
        try:
            # Check cache first
            cached_entry = self.cache_manager.get_entry_by_stream_url(stream_url)
            if cached_entry and cached_entry.is_opus is not None:
                print(f"Cache hit: is_opus={cached_entry.is_opus} for {stream_url}")
                return cached_entry.is_opus

            # If not cached, use ffprobe to determine codec
            result = subprocess.run(
                [
                    "ffprobe",
                    "-i",
                    stream_url,
                    "-show_streams",
                    "-select_streams",
                    "a",
                    "-loglevel",
                    "error",
                    "-print_format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            metadata = json.loads(result.stdout)
            is_opus = any(
                stream.get("codec_name") == "opus"
                for stream in metadata.get("streams", [])
            )

            # Update cache with the result
            self.cache_manager.update_is_opus_by_stream_url(stream_url, is_opus)
            return is_opus
        except Exception as e:
            print(f"Error checking Opus encoding: {e}")
            return False
