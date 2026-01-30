import asyncio
import discord
from discord.ext import commands
from config import DISCORD_TOKEN
from database import Database


class RequisitionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Dune Awakening Equipment Requisition Bot",
        )

        self.db = Database()

    async def setup_hook(self):
        """Called when the bot is starting up."""
        # Connect to database
        await self.db.connect()
        print("Database connected.")

        # Load cogs
        await self.load_extension("cogs.requisition")
        await self.load_extension("cogs.admin")
        print("Cogs loaded.")

        # Sync slash commands
        await self.tree.sync()
        print("Commands synced.")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Connected to {len(self.guilds)} guild(s)")
        print("------")

    async def close(self):
        """Cleanup when bot is shutting down."""
        await self.db.close()
        await super().close()


async def main():
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables.")
        print("Please create a .env file with your bot token (see .env.example)")
        return

    bot = RequisitionBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
