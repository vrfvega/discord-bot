import asyncio
from os import getenv

import discord
import lavalink
from discord.ext import commands

from src.utils.logger import logger


class Bot(commands.Bot):
    def __init__(self):
        # Enhanced intents configuration
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
        )

        self.initial_extensions = ["src.cogs.music"]

    async def setup_hook(self) -> None:
        """Initialize bot components and load extensions."""
        try:
            # Setup Lavalink client
            await self._setup_lavalink()

            # Load extensions
            for extension in self.initial_extensions:
                try:
                    await self.load_extension(extension)
                    logger.info(f"Loaded extension: {extension}")
                except Exception as e:
                    logger.error(f"Failed to load extension {extension}: {e}")

            # Sync commands
            my_guild = discord.Object(id=713553988359946250)

            self.tree.copy_global_to(guild=my_guild)
            await self.tree.sync(guild=my_guild)
            logger.info(f"Synced slash commands for {self.user}")

        except Exception as e:
            logger.error(f"Error in setup_hook: {e}")
            raise

    async def _setup_lavalink(self) -> None:
        """Setup Lavalink client with error handling and reconnection logic."""
        try:
            # Set up lavalink attribute that the Music cog expects
            self.lavalink = lavalink.Client(
                self.user.id
            )  # Changed from self.lavalink_client to self.lavalink

            # Load Lavalink configuration from environment variables
            host = getenv("LAVALINK_HOST", "0.0.0.0")
            port = int(getenv("LAVALINK_PORT", "2333"))
            password = getenv("LAVALINK_PASSWORD", "youshallnotpass")
            region = getenv("LAVALINK_REGION", "us")

            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    self.lavalink.add_node(  # Changed from self.lavalink_client to self.lavalink
                        host=host,
                        port=port,
                        password=password,
                        region=region,
                        name=f"node-{region}",
                    )
                    logger.info(
                        f"Successfully connected to Lavalink node at {host}:{port}"
                    )
                    break

                except Exception as e:
                    retry_count += 1
                    if retry_count == max_retries:
                        logger.error(
                            f"Failed to connect to Lavalink after {max_retries} attempts: {e}"
                        )
                        raise
                    logger.warning(
                        f"Attempt {retry_count} failed, retrying in 5 seconds..."
                    )
                    await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error setting up Lavalink: {e}")
            raise

    async def on_error(self, event_method: str, *args, **kwargs):
        """Global error handler for all events."""
        logger.error(f"Error in {event_method}:", exc_info=True)

    async def close(self):
        """Clean up resources before shutting down."""
        if hasattr(self, "lavalink"):
            await self.lavalink.close()
        await super().close()
