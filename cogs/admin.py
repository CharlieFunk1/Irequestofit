import discord
from discord import app_commands
from discord.ext import commands


class AdminCog(commands.Cog):
    """Cog for admin configuration commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set-crafter-role", description="Set which role can fulfill requests (Admin only)")
    @app_commands.describe(role="The role that can claim and complete requests")
    @app_commands.default_permissions(administrator=True)
    async def set_crafter_role(self, interaction: discord.Interaction, role: discord.Role):
        """Set the crafter role for this server."""
        db = self.bot.db
        await db.set_crafter_role(interaction.guild_id, role.id)

        await interaction.response.send_message(
            f"Crafter role has been set to {role.mention}. Members with this role can now claim and fulfill requests.",
            ephemeral=True,
        )

    @app_commands.command(name="set-channel", description="Set the announcement channel for new requests (Admin only)")
    @app_commands.describe(channel="The channel where new requests will be posted")
    @app_commands.default_permissions(administrator=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the announcement channel for new requisitions."""
        db = self.bot.db
        await db.set_announcement_channel(interaction.guild_id, channel.id)

        await interaction.response.send_message(
            f"Announcement channel has been set to {channel.mention}. New requisitions will be posted there.",
            ephemeral=True,
        )

    @app_commands.command(name="settings", description="View current bot settings (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        """View current guild settings."""
        db = self.bot.db
        settings = await db.get_guild_settings(interaction.guild_id)

        embed = discord.Embed(
            title="Bot Settings",
            color=discord.Color.blurple(),
        )

        if settings:
            # Crafter role
            if settings["crafter_role_id"]:
                role = interaction.guild.get_role(settings["crafter_role_id"])
                role_text = role.mention if role else f"Role ID: {settings['crafter_role_id']} (not found)"
            else:
                role_text = "Not set"
            embed.add_field(name="Crafter Role", value=role_text, inline=False)

            # Announcement channel
            if settings["announcement_channel_id"]:
                channel = interaction.guild.get_channel(settings["announcement_channel_id"])
                channel_text = channel.mention if channel else f"Channel ID: {settings['announcement_channel_id']} (not found)"
            else:
                channel_text = "Not set"
            embed.add_field(name="Announcement Channel", value=channel_text, inline=False)
        else:
            embed.description = "No settings configured yet. Use `/set-crafter-role` and `/set-channel` to configure."

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
