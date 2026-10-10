import asyncio
import sys
from app.core.bot import ScumBot
from app.core.config import Config
from app.core.database import run_database_migrations

def main():
    if not Config.DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN is missing from environment variables.", file=sys.stderr)
        sys.exit(1)

    try:
        run_database_migrations()
    except Exception as e:
        print(f"[-] Migration failed: {e}", file=sys.stderr)
        sys.exit(1)

    bot = ScumBot()

    try:
        asyncio.run(bot.start(Config.DISCORD_TOKEN))
    except KeyboardInterrupt:
        print("\nBot shutting down gracefully...")

if __name__ == "__main__":
    main()