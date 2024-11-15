import asyncio
import logging

import discord

from src.audio_streamer import AudioStreamManager
from src.codec_checker import CodecChecker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],  # Log to console
)

logger = logging.getLogger(__name__)


class AudioSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.8):
        """
        Initialize an AudioSource instance.
        :param source: The FFmpeg audio source for Discord playback.
        :param data: Metadata about the audio stream.
        :param volume: The playback volume.
        """
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.url = data.get("webpage_url")
        self.uploader = data.get("uploader")
        logger.info(f"Initialized AudioSource for: {self.title} by {self.uploader}")

    @classmethod
    async def from_url(
        cls,
        url,
        *,
        audio_stream_manager: AudioStreamManager,
        codec_checker: CodecChecker,
        loop=None,
    ):
        """
        Create an AudioSource from a URL.
        :param url: The URL of the video to stream.
        :param audio_stream_manager: Instance of AudioStreamManager.
        :param codec_checker: Instance of CodecChecker.
        :param loop: Event loop for asynchronous tasks.
        :return: An instance of AudioSource.
        """
        logger.info(f"Fetching audio source for URL: {url}")
        if not audio_stream_manager or not codec_checker:
            logger.error("Missing dependencies: audio_stream_manager or codec_checker")
            raise ValueError("All dependencies must be provided.")

        loop = loop or asyncio.get_event_loop()

        try:
            # Define async tasks
            async def fetch_stream_url():
                logger.info("Fetching audio stream URL...")
                return audio_stream_manager.get_audio_stream(url)

            # TODO!: Metadata should also be cached and fetched from the cache
            async def fetch_metadata():
                logger.info("Fetching metadata...")
                return audio_stream_manager.get_metadata(url)

            # Run tasks in parallel
            stream_url, metadata = await asyncio.gather(
                fetch_stream_url(), fetch_metadata()
            )
            logger.info(f"Stream URL fetched: {stream_url}")
            logger.info(
                f"Metadata fetched: {metadata.get('title')} by {metadata.get('uploader')}"
            )

            # Check if the audio is Opus-encoded
            logger.info("Checking if the stream is Opus-encoded...")
            is_opus = codec_checker.is_opus_encoded(stream_url)
            if not is_opus:
                logger.warning(f"The audio stream at {stream_url} is not Opus-encoded.")

            # Prepare the FFmpeg audio source
            ffmpeg_options = {
                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2",
                "options": "-vn",
            }
            logger.info("Preparing FFmpeg audio source...")
            source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
            logger.info("AudioSource successfully prepared.")
            return cls(source, data=metadata)

        except Exception as e:
            logger.error(f"Error in from_url: {e}")
            raise
