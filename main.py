import asyncio
import logging
import sys
from app.core.bot import ScumBot
from app.core.config import config
from app.core.database import run_database_migrations

def main():
    # Error details are kept out of Discord messages, so make sure they reach the container logs.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not config.bot.token:
        print("Error: DISCORD_TOKEN is missing from environment variables.", file=sys.stderr)
        sys.exit(1)

    try:
        run_database_migrations()
    except Exception as e:
        print(f"[-] Migration failed: {e}", file=sys.stderr)
        sys.exit(1)

    bot = ScumBot()

    try:
        asyncio.run(bot.start(config.bot.token))
    except KeyboardInterrupt:
        print("\nBot shutting down gracefully...")

if __name__ == "__main__":
    main()