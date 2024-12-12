import asyncio
import signal
import sys
from os import getenv
from typing import Optional

from dotenv import load_dotenv

from src.bot import Bot
from src.utils.logger import logger

# Load environment variables
load_dotenv()

# Get configuration
TOKEN = getenv("TOKEN")
if not TOKEN:
    logger.critical("No TOKEN found in environment variables")
    sys.exit(1)

# Initialize bot
bot = Bot()


async def shutdown(signal: Optional[signal.Signals] = None):
    """
    Cleanly shut down the bot and close all connections.
    """
    if signal:
        logger.info(f"Received exit signal {signal.name}...")

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks...")
    await asyncio.gather(*tasks, return_exceptions=True)
    await bot.close()

    logger.info("Bot shutdown complete.")


def handle_exception(loop, context):
    """Handle exceptions that escape the event loop."""
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception: {msg}")
    asyncio.create_task(shutdown())


async def main():
    """Main entry point for the bot."""
    try:
        # Set up exception handler
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(handle_exception)

        # Use a platform-independent signal handler
        stop_event = asyncio.Event()

        def stop_event_handler():
            stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: stop_event_handler())

        logger.info("Starting bot...")
        # Start the bot in the background
        bot_task = asyncio.create_task(bot.start(TOKEN))

        # Wait for the stop event
        await stop_event.wait()

        logger.info("Shutdown initiated.")
        bot_task.cancel()
        await shutdown()

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        await shutdown()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    finally:
        logger.info("Program ended.")
