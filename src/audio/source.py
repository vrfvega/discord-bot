import asyncio
import logging

import discord

from src.audio.stream_manager import StreamManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],  # Log to console
)

logger = logging.getLogger(__name__)


class Source(discord.PCMVolumeTransformer):
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
        audio_stream_manager: StreamManager,
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
        if not audio_stream_manager:
            logger.error("Missing dependencies: audio_stream_manager")
            raise ValueError("All dependencies must be provided.")

        loop = loop or asyncio.get_event_loop()

        try:
            # Get the audio stream URL and metadata
            stream_url, meta = await audio_stream_manager.get_stream_info(url)
            logger.info(f"Stream URL fetched: {stream_url}")
            logger.info(
                f"Metadata fetched: {meta.get("title")} by {meta.get("uploader")}"
            )
            # Prepare the FFmpeg audio source
            ffmpeg_options = {
                "before_options": (
                    "-reconnect 1 "
                    "-reconnect_streamed 1 "
                    "-reconnect_delay_max 2 "
                    "-probesize 32 "
                    "-analyzeduration 0 "
                    "-loglevel panic"
                ),
                "options": "-vn",
            }
            logger.info("Preparing FFmpeg audio source...")
            source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
            logger.info("AudioSource successfully prepared.")
            return cls(source, data=meta)

        except Exception as e:
            logger.error(f"Error in from_url: {e}")
            raise
