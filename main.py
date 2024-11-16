import asyncio
import os
import sys

import discord
from dotenv import load_dotenv

from src.bot.bot import Bot
from src.bot.cogs.music import Music

if sys.platform.startswith("darwin") and not discord.opus.is_loaded():
    discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")

load_dotenv()

DISCORD_TOKEN = os.getenv("TOKEN")


async def setup():
    bot = Bot()
    await bot.add_cog(Music(bot))
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(setup())
