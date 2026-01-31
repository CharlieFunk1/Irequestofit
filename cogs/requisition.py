import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import os
from data.equipment import (
    CATEGORIES, get_items_for_category, get_item_costs,
    get_full_sets, get_set_items, get_set_total_costs
)

# Path to guild logo image
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "guildlogo.png")


async def update_queue_message(bot, guild):
    """Update the auto-updating queue message in the configured channel.

    Deletes the old queue message and posts a new one with current pending requests.
    """
    db = bot.db
    settings = await db.get_guild_settings(guild.id)

    if not settings or not settings.get("queue_channel_id"):
        return  # No queue channel configured

    channel = guild.get_channel(settings["queue_channel_id"])
    if not channel:
        return  # Channel not found

    # Try to delete old queue message
    if settings.get("queue_message_id"):
        try:
            old_message = await channel.fetch_message(settings["queue_message_id"])
            await old_message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass  # Message already deleted or can't delete

    # Get active requests (pending and claimed)
    requests = await db.get_active_requests()

    # Build the queue embed
    embed = discord.Embed(
        title="Requisitions Queue",
        description="Use `/claim <id>` to claim a request" if requests else "No active requests",
        color=discord.Color.orange(),
    )

    if requests:
        total_plastanium = 0
        total_spice = 0
        for req in requests[:15]:  # Limit to 15
            plast = req.get("plastanium_cost", 0)
            spice = req.get("spice_cost", 0)
            total_plastanium += plast
            total_spice += spice

            # Build claimed status
            if req.get("crafter_id"):
                claimed_text = f"<@{req['crafter_id']}>"
            else:
                claimed_text = ""

            embed.add_field(
                name=f"**#{req['id']}** - {req['item_name']} x{req['quantity']}",
                value=f"**Character:** {req['character_name']}\n**Plastanium:** {plast}\n**Spice Melange:** {spice}\n**Claimed:** {claimed_text}",
                inline=False,
            )

        if total_plastanium > 0 or total_spice > 0:
            embed.set_footer(text=f"Total materials needed: {total_plastanium} Plastanium, {total_spice} Spice")

        if len(requests) > 15:
            embed.description = f"Showing 15 of {len(requests)} active requests. Use `/claim <id>` to claim."

    # Add guild logo as thumbnail
    embed.set_thumbnail(url="attachment://guildlogo.png")

    # Post new queue message
    try:
        file = discord.File(LOGO_PATH, filename="guildlogo.png")
        new_message = await channel.send(embed=embed, file=file)
        await db.set_queue_message_id(guild.id, new_message.id)
    except (discord.Forbidden, discord.HTTPException):
        pass  # Can't post to channel


# Time period choices for history commands
class TimePeriod:
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"


class CategorySelect(discord.ui.Select):
    """Dropdown for selecting equipment category."""

    def __init__(self):
        options = [
            discord.SelectOption(label=category, value=category)
            for category in CATEGORIES
            if get_items_for_category(category)  # Only show categories with items
        ]
        # Add Full Armor Sets option at the beginning
        options.insert(0, discord.SelectOption(
            label="Full Armor Sets",
            value="Full Armor Sets",
            description="Request a complete armor set"
        ))
        super().__init__(
            placeholder="Select a category...",
            options=options,
            custom_id="category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        if category == "Full Armor Sets":
            view = FullSetSelectView()
            await interaction.response.edit_message(
                content="**Full Armor Sets**\nSelect a set to request all pieces:",
                view=view,
            )
        else:
            view = ItemSelectView(category)
            await interaction.response.edit_message(
                content=f"**Category:** {category}\nNow select an item:",
                view=view,
            )


class CategorySelectView(discord.ui.View):
    """View containing the category dropdown."""

    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(CategorySelect())


class FullSetSelect(discord.ui.Select):
    """Dropdown for selecting a full armor set."""

    def __init__(self):
        options = []
        for set_name in get_full_sets():
            plast, spice = get_set_total_costs(set_name)
            options.append(discord.SelectOption(
                label=set_name,
                value=set_name,
                description=f"Total: {plast} Plastanium, {spice} Spice"
            ))
        super().__init__(
            placeholder="Select an armor set...",
            options=options,
            custom_id="full_set_select",
        )

    async def callback(self, interaction: discord.Interaction):
        set_name = self.values[0]
        db = interaction.client.db
        saved_name = await db.get_character_name(interaction.user.id)
        if saved_name:
            modal = FullSetModalQuick(set_name, saved_name)
        else:
            modal = FullSetModal(set_name)
        await interaction.response.send_modal(modal)


class FullSetSelectView(discord.ui.View):
    """View containing the full set dropdown."""

    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(FullSetSelect())


class FullSetModal(discord.ui.Modal):
    """Modal for requesting a full armor set (first time users)."""

    def __init__(self, set_name: str):
        super().__init__(title=f"Request {set_name}")
        self.set_name = set_name

        self.character_name = discord.ui.TextInput(
            label="Character Name (saved for future requests)",
            placeholder="Your in-game character name",
            max_length=50,
            required=True,
        )
        self.add_item(self.character_name)

    async def on_submit(self, interaction: discord.Interaction):
        db = interaction.client.db
        await db.set_character_name(interaction.user.id, self.character_name.value)

        items = get_set_items(self.set_name)
        request_ids = []
        total_plastanium = 0
        total_spice = 0

        for item_name, category in items:
            plast, spice = get_item_costs(category, item_name)
            total_plastanium += plast
            total_spice += spice
            request_id = await db.create_request(
                requester_id=interaction.user.id,
                requester_name=interaction.user.display_name,
                character_name=self.character_name.value,
                category=category,
                item_name=item_name,
                quantity=1,
                plastanium_cost=plast,
                spice_cost=spice,
            )
            request_ids.append(request_id)

        # Create embed for the set request
        embed = discord.Embed(
            title="New Full Set Requisition",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Request IDs", value=", ".join(f"#{rid}" for rid in request_ids), inline=False)
        embed.add_field(name="Set", value=self.set_name, inline=True)
        embed.add_field(name="Pieces", value=str(len(items)), inline=True)
        embed.add_field(name="Character", value=self.character_name.value, inline=True)
        embed.add_field(name="Requested By", value=interaction.user.mention, inline=True)
        embed.add_field(
            name="Total Materials",
            value=f"Plastanium: {total_plastanium}\nSpice Melange: {total_spice}",
            inline=False,
        )
        embed.set_footer(text="Use /claim to fulfill individual pieces")
        embed.set_thumbnail(url="attachment://guildlogo.png")

        await interaction.response.send_message(
            f"Your requisition for **{self.set_name}** ({len(items)} pieces) has been submitted!\nRequest IDs: {', '.join(f'#{rid}' for rid in request_ids)}\nTotal Materials: {total_plastanium} Plastanium, {total_spice} Spice",
            ephemeral=True,
        )

        # Post to announcement channel
        settings = await db.get_guild_settings(interaction.guild_id)
        if settings and settings.get("announcement_channel_id"):
            channel = interaction.guild.get_channel(settings["announcement_channel_id"])
            if channel:
                file = discord.File(LOGO_PATH, filename="guildlogo.png")
                role_mention = ""
                if settings.get("crafter_role_id"):
                    role_mention = f"<@&{settings['crafter_role_id']}> "
                await channel.send(content=f"{role_mention}New full set requisition!", embed=embed, file=file)

        await update_queue_message(interaction.client, interaction.guild)


class FullSetModalQuick(discord.ui.Modal):
    """Modal for requesting a full armor set (returning users)."""

    def __init__(self, set_name: str, character_name: str):
        super().__init__(title=f"Request {set_name}")
        self.set_name = set_name
        self.saved_character_name = character_name

        # Just a confirmation field
        self.confirm = discord.ui.TextInput(
            label=f"Confirm request for {character_name}",
            placeholder="Type 'yes' to confirm",
            default="yes",
            max_length=10,
            required=True,
        )
        self.add_item(self.confirm)

    async def on_submit(self, interaction: discord.Interaction):
        db = interaction.client.db

        items = get_set_items(self.set_name)
        request_ids = []
        total_plastanium = 0
        total_spice = 0

        for item_name, category in items:
            plast, spice = get_item_costs(category, item_name)
            total_plastanium += plast
            total_spice += spice
            request_id = await db.create_request(
                requester_id=interaction.user.id,
                requester_name=interaction.user.display_name,
                character_name=self.saved_character_name,
                category=category,
                item_name=item_name,
                quantity=1,
                plastanium_cost=plast,
                spice_cost=spice,
            )
            request_ids.append(request_id)

        # Create embed for the set request
        embed = discord.Embed(
            title="New Full Set Requisition",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Request IDs", value=", ".join(f"#{rid}" for rid in request_ids), inline=False)
        embed.add_field(name="Set", value=self.set_name, inline=True)
        embed.add_field(name="Pieces", value=str(len(items)), inline=True)
        embed.add_field(name="Character", value=self.saved_character_name, inline=True)
        embed.add_field(name="Requested By", value=interaction.user.mention, inline=True)
        embed.add_field(
            name="Total Materials",
            value=f"Plastanium: {total_plastanium}\nSpice Melange: {total_spice}",
            inline=False,
        )
        embed.set_footer(text="Use /claim to fulfill individual pieces")
        embed.set_thumbnail(url="attachment://guildlogo.png")

        await interaction.response.send_message(
            f"Your requisition for **{self.set_name}** ({len(items)} pieces) has been submitted!\nRequest IDs: {', '.join(f'#{rid}' for rid in request_ids)}\nTotal Materials: {total_plastanium} Plastanium, {total_spice} Spice",
            ephemeral=True,
        )

        # Post to announcement channel
        settings = await db.get_guild_settings(interaction.guild_id)
        if settings and settings.get("announcement_channel_id"):
            channel = interaction.guild.get_channel(settings["announcement_channel_id"])
            if channel:
                file = discord.File(LOGO_PATH, filename="guildlogo.png")
                role_mention = ""
                if settings.get("crafter_role_id"):
                    role_mention = f"<@&{settings['crafter_role_id']}> "
                await channel.send(content=f"{role_mention}New full set requisition!", embed=embed, file=file)

        await update_queue_message(interaction.client, interaction.guild)


class ItemSelect(discord.ui.Select):
    """Dropdown for selecting specific equipment item."""

    def __init__(self, category: str):
        self.category = category
        items = get_items_for_category(category)
        options = []
        for item in items[:25]:  # Discord limit is 25 options
            plastanium, spice = get_item_costs(category, item)
            if plastanium > 0 or spice > 0:
                description = f"Cost: {plastanium} Plastanium, {spice} Spice"
            else:
                description = "Cost: Not set"
            options.append(discord.SelectOption(label=item, value=item, description=description))

        super().__init__(
            placeholder="Select an item...",
            options=options,
            custom_id="item_select",
        )

    async def callback(self, interaction: discord.Interaction):
        item = self.values[0]
        # Check if user has a saved character name
        db = interaction.client.db
        saved_name = await db.get_character_name(interaction.user.id)
        if saved_name:
            modal = RequestModalQuick(self.category, item, saved_name)
        else:
            modal = RequestModal(self.category, item)
        await interaction.response.send_modal(modal)


class ItemSelectView(discord.ui.View):
    """View containing the item dropdown."""

    def __init__(self, category: str):
        super().__init__(timeout=300)
        self.add_item(ItemSelect(category))


class RequestModal(discord.ui.Modal):
    """Modal form for entering request details (first time users)."""

    def __init__(self, category: str, item: str):
        super().__init__(title="Equipment Requisition")
        self.category = category
        self.item = item

        self.quantity = discord.ui.TextInput(
            label="Quantity",
            placeholder="Enter quantity (1-99)",
            default="1",
            max_length=2,
            required=True,
        )
        self.add_item(self.quantity)

        self.character_name = discord.ui.TextInput(
            label="Character Name (saved for future requests)",
            placeholder="Your in-game character name",
            max_length=50,
            required=True,
        )
        self.add_item(self.character_name)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate quantity
        try:
            qty = int(self.quantity.value)
            if qty < 1 or qty > 99:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Invalid quantity. Please enter a number between 1 and 99.",
                ephemeral=True,
            )
            return

        # Get database from bot
        db = interaction.client.db

        # Save character name for future requests
        await db.set_character_name(interaction.user.id, self.character_name.value)

        # Get item costs
        plastanium, spice = get_item_costs(self.category, self.item)
        total_plastanium = plastanium * qty
        total_spice = spice * qty

        # Create the request
        request_id = await db.create_request(
            requester_id=interaction.user.id,
            requester_name=interaction.user.display_name,
            character_name=self.character_name.value,
            category=self.category,
            item_name=self.item,
            quantity=qty,
            plastanium_cost=plastanium,
            spice_cost=spice,
        )

        # Create embed for the request
        embed = discord.Embed(
            title="New Equipment Requisition",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
        embed.add_field(name="Item", value=self.item, inline=True)
        embed.add_field(name="Quantity", value=str(qty), inline=True)
        embed.add_field(name="Category", value=self.category, inline=True)
        embed.add_field(name="Character", value=self.character_name.value, inline=True)
        embed.add_field(name="Requested By", value=interaction.user.mention, inline=True)

        # Add material costs if set
        if total_plastanium > 0 or total_spice > 0:
            embed.add_field(
                name="Materials Required",
                value=f"Plastanium: {total_plastanium}\nSpice Melange: {total_spice}",
                inline=False,
            )

        embed.set_footer(text="Use /claim to fulfill this request")

        # Add guild logo as thumbnail
        embed.set_thumbnail(url="attachment://guildlogo.png")

        # Send confirmation to user
        cost_info = ""
        if total_plastanium > 0 or total_spice > 0:
            cost_info = f"\nMaterials: {total_plastanium} Plastanium, {total_spice} Spice"

        await interaction.response.send_message(
            f"Your requisition for **{qty}x {self.item}** has been submitted! (ID: #{request_id}){cost_info}",
            ephemeral=True,
        )

        # Post to announcement channel if configured
        settings = await db.get_guild_settings(interaction.guild_id)
        if settings and settings["announcement_channel_id"]:
            channel = interaction.guild.get_channel(settings["announcement_channel_id"])
            if channel:
                file = discord.File(LOGO_PATH, filename="guildlogo.png")
                # Mention crafter role if configured
                role_mention = ""
                if settings.get("crafter_role_id"):
                    role_mention = f"<@&{settings['crafter_role_id']}> "
                await channel.send(content=f"{role_mention}New requisition request!", embed=embed, file=file)

        # Update auto-updating queue
        await update_queue_message(interaction.client, interaction.guild)


class RequestModalQuick(discord.ui.Modal):
    """Modal form for returning users with saved character name."""

    def __init__(self, category: str, item: str, character_name: str):
        super().__init__(title="Equipment Requisition")
        self.category = category
        self.item = item
        self.saved_character_name = character_name

        self.quantity = discord.ui.TextInput(
            label="Quantity",
            placeholder="Enter quantity (1-99)",
            default="1",
            max_length=2,
            required=True,
        )
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate quantity
        try:
            qty = int(self.quantity.value)
            if qty < 1 or qty > 99:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Invalid quantity. Please enter a number between 1 and 99.",
                ephemeral=True,
            )
            return

        # Get database from bot
        db = interaction.client.db

        # Get item costs
        plastanium, spice = get_item_costs(self.category, self.item)
        total_plastanium = plastanium * qty
        total_spice = spice * qty

        # Create the request with saved character name
        request_id = await db.create_request(
            requester_id=interaction.user.id,
            requester_name=interaction.user.display_name,
            character_name=self.saved_character_name,
            category=self.category,
            item_name=self.item,
            quantity=qty,
            plastanium_cost=plastanium,
            spice_cost=spice,
        )

        # Create embed for the request
        embed = discord.Embed(
            title="New Equipment Requisition",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
        embed.add_field(name="Item", value=self.item, inline=True)
        embed.add_field(name="Quantity", value=str(qty), inline=True)
        embed.add_field(name="Category", value=self.category, inline=True)
        embed.add_field(name="Character", value=self.saved_character_name, inline=True)
        embed.add_field(name="Requested By", value=interaction.user.mention, inline=True)

        # Add material costs if set
        if total_plastanium > 0 or total_spice > 0:
            embed.add_field(
                name="Materials Required",
                value=f"Plastanium: {total_plastanium}\nSpice Melange: {total_spice}",
                inline=False,
            )

        embed.set_footer(text="Use /claim to fulfill this request")

        # Add guild logo as thumbnail
        embed.set_thumbnail(url="attachment://guildlogo.png")

        # Send confirmation to user
        cost_info = ""
        if total_plastanium > 0 or total_spice > 0:
            cost_info = f"\nMaterials: {total_plastanium} Plastanium, {total_spice} Spice"

        await interaction.response.send_message(
            f"Your requisition for **{qty}x {self.item}** has been submitted! (ID: #{request_id}){cost_info}",
            ephemeral=True,
        )

        # Post to announcement channel if configured
        settings = await db.get_guild_settings(interaction.guild_id)
        if settings and settings["announcement_channel_id"]:
            channel = interaction.guild.get_channel(settings["announcement_channel_id"])
            if channel:
                file = discord.File(LOGO_PATH, filename="guildlogo.png")
                # Mention crafter role if configured
                role_mention = ""
                if settings.get("crafter_role_id"):
                    role_mention = f"<@&{settings['crafter_role_id']}> "
                await channel.send(content=f"{role_mention}New requisition request!", embed=embed, file=file)

        # Update auto-updating queue
        await update_queue_message(interaction.client, interaction.guild)


class EditCategorySelect(discord.ui.Select):
    """Dropdown for selecting category when editing a request."""

    def __init__(self, request_id: int):
        self.request_id = request_id
        options = [
            discord.SelectOption(label=category, value=category)
            for category in CATEGORIES
            if get_items_for_category(category)
        ]
        super().__init__(
            placeholder="Select a category...",
            options=options,
            custom_id="edit_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        view = EditItemSelectView(self.request_id, category)
        await interaction.response.edit_message(
            content=f"**Editing Request #{self.request_id}**\n**Category:** {category}\nNow select an item:",
            view=view,
        )


class EditCategorySelectView(discord.ui.View):
    """View for category selection when editing."""

    def __init__(self, request_id: int):
        super().__init__(timeout=300)
        self.add_item(EditCategorySelect(request_id))


class EditItemSelect(discord.ui.Select):
    """Dropdown for selecting item when editing a request."""

    def __init__(self, request_id: int, category: str):
        self.request_id = request_id
        self.category = category
        items = get_items_for_category(category)
        options = []
        for item in items[:25]:
            plastanium, spice = get_item_costs(category, item)
            if plastanium > 0 or spice > 0:
                description = f"Cost: {plastanium} Plastanium, {spice} Spice"
            else:
                description = "Cost: Not set"
            options.append(discord.SelectOption(label=item, value=item, description=description))

        super().__init__(
            placeholder="Select an item...",
            options=options,
            custom_id="edit_item_select",
        )

    async def callback(self, interaction: discord.Interaction):
        item = self.values[0]
        modal = EditRequestModal(self.request_id, self.category, item)
        await interaction.response.send_modal(modal)


class EditItemSelectView(discord.ui.View):
    """View for item selection when editing."""

    def __init__(self, request_id: int, category: str):
        super().__init__(timeout=300)
        self.add_item(EditItemSelect(request_id, category))


class EditRequestModal(discord.ui.Modal):
    """Modal for editing request quantity."""

    def __init__(self, request_id: int, category: str, item: str):
        super().__init__(title=f"Edit Request #{request_id}")
        self.request_id = request_id
        self.category = category
        self.item = item

        self.quantity = discord.ui.TextInput(
            label="Quantity",
            placeholder="Enter quantity (1-99)",
            default="1",
            max_length=2,
            required=True,
        )
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity.value)
            if qty < 1 or qty > 99:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Invalid quantity. Please enter a number between 1 and 99.",
                ephemeral=True,
            )
            return

        db = interaction.client.db

        plastanium, spice = get_item_costs(self.category, self.item)

        success = await db.update_request(
            request_id=self.request_id,
            user_id=interaction.user.id,
            category=self.category,
            item_name=self.item,
            quantity=qty,
            plastanium_cost=plastanium,
            spice_cost=spice,
        )

        if success:
            total_plastanium = plastanium * qty
            total_spice = spice * qty
            cost_info = ""
            if total_plastanium > 0 or total_spice > 0:
                cost_info = f"\nMaterials: {total_plastanium} Plastanium, {total_spice} Spice"

            await interaction.response.send_message(
                f"Request #{self.request_id} has been updated to **{qty}x {self.item}**!{cost_info}",
                ephemeral=True,
            )

            # Update auto-updating queue
            await update_queue_message(interaction.client, interaction.guild)
        else:
            await interaction.response.send_message(
                f"Could not update request #{self.request_id}. Make sure it still exists and is pending.",
                ephemeral=True,
            )


class RequisitionCog(commands.Cog):
    """Cog for handling requisition commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="request", description="Create a new equipment requisition")
    async def request(self, interaction: discord.Interaction):
        """Open the requisition form with category selection."""
        view = CategorySelectView()
        await interaction.response.send_message(
            "**Equipment Requisition**\nSelect a category to begin:",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="set-character", description="Set or update your in-game character name")
    @app_commands.describe(name="Your in-game character name")
    async def set_character(self, interaction: discord.Interaction, name: str):
        """Set or update the user's saved character name."""
        db = self.bot.db
        await db.set_character_name(interaction.user.id, name)
        await interaction.response.send_message(
            f"Your character name has been set to **{name}**. This will be used for all future requests.",
            ephemeral=True,
        )

    @app_commands.command(name="my-requests", description="View your pending and active requests")
    async def my_requests(self, interaction: discord.Interaction):
        """View the user's own requests."""
        db = self.bot.db
        requests = await db.get_user_requests(interaction.user.id)

        if not requests:
            await interaction.response.send_message(
                "You have no pending or active requests.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Your Requisitions",
            color=discord.Color.blue(),
        )

        for req in requests[:10]:  # Limit to 10 to avoid embed limits
            status_emoji = "⏳" if req["status"] == "pending" else "🔨"
            crafter_info = f" (Crafter: {req['crafter_name']})" if req["crafter_name"] else ""
            costs = ""
            if req.get("plastanium_cost", 0) > 0 or req.get("spice_cost", 0) > 0:
                costs = f"\nMaterials: {req.get('plastanium_cost', 0)} Plast, {req.get('spice_cost', 0)} Spice"
            embed.add_field(
                name=f"{status_emoji} #{req['id']} - {req['item_name']}",
                value=f"Qty: {req['quantity']} | Character: {req['character_name']}{crafter_info}{costs}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cancel", description="Cancel your own pending request")
    @app_commands.describe(request_id="The ID of the request to cancel")
    async def cancel(self, interaction: discord.Interaction, request_id: int):
        """Cancel a user's own pending request."""
        db = self.bot.db
        success = await db.cancel_request(request_id, interaction.user.id)

        if success:
            await interaction.response.send_message(
                f"Request #{request_id} has been cancelled.",
                ephemeral=True,
            )
            # Update auto-updating queue
            await update_queue_message(self.bot, interaction.guild)
        else:
            await interaction.response.send_message(
                f"Could not cancel request #{request_id}. Make sure it exists, belongs to you, and is still pending.",
                ephemeral=True,
            )

    @app_commands.command(name="edit-request", description="Edit your own pending request")
    @app_commands.describe(request_id="The ID of the request to edit")
    async def edit_request(self, interaction: discord.Interaction, request_id: int):
        """Edit a user's own pending request."""
        db = self.bot.db
        request = await db.get_request(request_id)

        if not request:
            await interaction.response.send_message(
                f"Request #{request_id} not found.",
                ephemeral=True,
            )
            return

        if request["requester_id"] != interaction.user.id:
            await interaction.response.send_message(
                f"Request #{request_id} does not belong to you.",
                ephemeral=True,
            )
            return

        if request["status"] != "pending":
            await interaction.response.send_message(
                f"Request #{request_id} cannot be edited because it is {request['status']}.",
                ephemeral=True,
            )
            return

        view = EditCategorySelectView(request_id)
        await interaction.response.send_message(
            f"**Editing Request #{request_id}**\nCurrent: {request['quantity']}x {request['item_name']}\n\nSelect a new category:",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="queue", description="View all pending requisitions (Crafter only)")
    async def queue(self, interaction: discord.Interaction):
        """View all pending requests. Requires Crafter role."""
        db = self.bot.db

        # Check for crafter role
        settings = await db.get_guild_settings(interaction.guild_id)
        if settings and settings["crafter_role_id"]:
            role = interaction.guild.get_role(settings["crafter_role_id"])
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(
                    "You need the Crafter role to use this command.",
                    ephemeral=True,
                )
                return

        requests = await db.get_active_requests()

        if not requests:
            await interaction.response.send_message(
                "No active requisitions in the queue.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Requisitions Queue",
            description="Use `/claim <id>` to claim a request",
            color=discord.Color.orange(),
        )

        total_plastanium = 0
        total_spice = 0
        for req in requests[:15]:  # Limit to 15
            plast = req.get("plastanium_cost", 0)
            spice = req.get("spice_cost", 0)
            total_plastanium += plast
            total_spice += spice

            # Build claimed status
            if req.get("crafter_id"):
                claimed_text = f"<@{req['crafter_id']}>"
            else:
                claimed_text = ""

            embed.add_field(
                name=f"**#{req['id']}** - {req['item_name']} x{req['quantity']}",
                value=f"**Character:** {req['character_name']}\n**Plastanium:** {plast}\n**Spice Melange:** {spice}\n**Claimed:** {claimed_text}",
                inline=False,
            )

        if total_plastanium > 0 or total_spice > 0:
            embed.set_footer(text=f"Total materials needed: {total_plastanium} Plastanium, {total_spice} Spice")

        # Add guild logo as thumbnail
        embed.set_thumbnail(url="attachment://guildlogo.png")
        file = discord.File(LOGO_PATH, filename="guildlogo.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    @app_commands.command(name="claim", description="Claim a pending request to fulfill (Crafter only)")
    @app_commands.describe(request_id="The ID of the request to claim")
    async def claim(self, interaction: discord.Interaction, request_id: int):
        """Claim a request to fulfill."""
        db = self.bot.db

        # Check for crafter role
        settings = await db.get_guild_settings(interaction.guild_id)
        if settings and settings["crafter_role_id"]:
            role = interaction.guild.get_role(settings["crafter_role_id"])
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(
                    "You need the Crafter role to use this command.",
                    ephemeral=True,
                )
                return

        success = await db.claim_request(request_id, interaction.user.id, interaction.user.display_name)

        if success:
            request = await db.get_request(request_id)
            costs = ""
            if request.get("plastanium_cost", 0) > 0 or request.get("spice_cost", 0) > 0:
                costs = f"\nMaterials: {request.get('plastanium_cost', 0)} Plastanium, {request.get('spice_cost', 0)} Spice"
            await interaction.response.send_message(
                f"You have claimed request #{request_id}: **{request['quantity']}x {request['item_name']}** for {request['character_name']}{costs}",
                ephemeral=True,
            )

            # Post notification to announcement channel
            settings = await db.get_guild_settings(interaction.guild_id)
            if settings and settings.get("announcement_channel_id"):
                channel = interaction.guild.get_channel(settings["announcement_channel_id"])
                if channel:
                    await channel.send(
                        f"{interaction.user.mention} has claimed request #{request_id}: **{request['quantity']}x {request['item_name']}** for {request['character_name']} - <@{request['requester_id']}>"
                    )

            # Update auto-updating queue
            await update_queue_message(self.bot, interaction.guild)
        else:
            await interaction.response.send_message(
                f"Could not claim request #{request_id}. It may not exist or already be claimed.",
                ephemeral=True,
            )

    @app_commands.command(name="unclaim", description="Release a claimed request (Crafter only)")
    @app_commands.describe(request_id="The ID of the request to unclaim")
    async def unclaim(self, interaction: discord.Interaction, request_id: int):
        """Release a claimed request back to the queue."""
        db = self.bot.db
        success = await db.unclaim_request(request_id, interaction.user.id)

        if success:
            await interaction.response.send_message(
                f"Request #{request_id} has been released back to the queue.",
                ephemeral=True,
            )
            # Update auto-updating queue
            await update_queue_message(self.bot, interaction.guild)
        else:
            await interaction.response.send_message(
                f"Could not unclaim request #{request_id}. Make sure it exists and you have it claimed.",
                ephemeral=True,
            )

    @app_commands.command(name="complete", description="Mark a claimed request as completed (Crafter only)")
    @app_commands.describe(request_id="The ID of the request to complete")
    async def complete(self, interaction: discord.Interaction, request_id: int):
        """Mark a request as completed and notify the requester."""
        db = self.bot.db
        request = await db.complete_request(request_id, interaction.user.id)

        if request:
            await interaction.response.send_message(
                f"Request #{request_id} has been marked as completed!",
                ephemeral=True,
            )

            # Try to DM the requester
            try:
                requester = await self.bot.fetch_user(request["requester_id"])
                embed = discord.Embed(
                    title="Requisition Completed!",
                    description=f"Your request for **{request['quantity']}x {request['item_name']}** has been fulfilled!",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Character", value=request["character_name"], inline=True)
                embed.add_field(name="Crafter", value=interaction.user.display_name, inline=True)
                await requester.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass  # User has DMs disabled or other error

            # Update auto-updating queue (completed requests are removed from pending)
            await update_queue_message(self.bot, interaction.guild)
        else:
            await interaction.response.send_message(
                f"Could not complete request #{request_id}. Make sure it exists and you have it claimed.",
                ephemeral=True,
            )

    @app_commands.command(name="my-claims", description="View your claimed requests (Crafter only)")
    async def my_claims(self, interaction: discord.Interaction):
        """View requests claimed by the crafter."""
        db = self.bot.db
        requests = await db.get_claimed_requests(interaction.user.id)

        if not requests:
            await interaction.response.send_message(
                "You have no claimed requests.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Your Claimed Requests",
            description="Use `/complete <id>` when finished",
            color=discord.Color.purple(),
        )

        total_plastanium = 0
        total_spice = 0
        for req in requests[:10]:
            costs = ""
            if req.get("plastanium_cost", 0) > 0 or req.get("spice_cost", 0) > 0:
                costs = f"\nMaterials: {req.get('plastanium_cost', 0)} Plast, {req.get('spice_cost', 0)} Spice"
                total_plastanium += req.get("plastanium_cost", 0)
                total_spice += req.get("spice_cost", 0)
            embed.add_field(
                name=f"#{req['id']} - {req['item_name']} x{req['quantity']}",
                value=f"Character: {req['character_name']} | By: {req['requester_name']}{costs}",
                inline=False,
            )

        if total_plastanium > 0 or total_spice > 0:
            embed.set_footer(text=f"Total materials: {total_plastanium} Plastanium, {total_spice} Spice")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _get_date_range(self, period: str) -> tuple[datetime | None, datetime | None]:
        """Convert a time period string to start/end datetime."""
        now = datetime.utcnow()
        end_date = now

        if period == TimePeriod.TODAY:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == TimePeriod.WEEK:
            start_date = now - timedelta(days=7)
        elif period == TimePeriod.MONTH:
            start_date = now - timedelta(days=30)
        else:  # ALL
            start_date = None
            end_date = None

        return start_date, end_date

    @app_commands.command(name="history", description="View completed requisitions history")
    @app_commands.describe(
        period="Time period to view",
        show_details="Show individual requests instead of just totals"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="Today", value="today"),
        app_commands.Choice(name="Last 7 days", value="week"),
        app_commands.Choice(name="Last 30 days", value="month"),
        app_commands.Choice(name="All time", value="all"),
    ])
    async def history(
        self,
        interaction: discord.Interaction,
        period: str = "week",
        show_details: bool = False
    ):
        """View completed requisitions history with totals."""
        db = self.bot.db
        start_date, end_date = self._get_date_range(period)

        period_labels = {
            "today": "Today",
            "week": "Last 7 Days",
            "month": "Last 30 Days",
            "all": "All Time"
        }
        period_label = period_labels.get(period, period)

        # Get material totals
        material_totals = await db.get_material_totals(start_date, end_date)

        if show_details:
            # Show individual completed requests
            requests = await db.get_completed_requests(start_date, end_date)

            if not requests:
                await interaction.response.send_message(
                    f"No completed requisitions found for {period_label}.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=f"Completed Requisitions - {period_label}",
                color=discord.Color.green(),
            )

            for req in requests[:15]:
                completed_str = str(req['completed_at'])[:10] if req['completed_at'] else "N/A"
                costs = ""
                if req.get("plastanium_cost", 0) > 0 or req.get("spice_cost", 0) > 0:
                    costs = f"\nMaterials: {req.get('plastanium_cost', 0)} Plast, {req.get('spice_cost', 0)} Spice"
                embed.add_field(
                    name=f"#{req['id']} - {req['item_name']} x{req['quantity']}",
                    value=f"For: {req['character_name']} ({req['requester_name']})\nCrafter: {req['crafter_name']} | {completed_str}{costs}",
                    inline=False,
                )

            footer_text = f"Total Materials: {material_totals['total_plastanium']} Plastanium, {material_totals['total_spice']} Spice"
            if len(requests) > 15:
                footer_text = f"Showing 15 of {len(requests)} requests | " + footer_text
            embed.set_footer(text=footer_text)

        else:
            # Show totals per requester
            totals = await db.get_requester_totals(start_date, end_date)

            if not totals:
                await interaction.response.send_message(
                    f"No completed requisitions found for {period_label}.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=f"Requisition Totals by Requester - {period_label}",
                color=discord.Color.green(),
            )

            total_items = 0
            total_requests = 0
            for entry in totals[:20]:
                plast = entry.get('total_plastanium', 0) or 0
                spice = entry.get('total_spice', 0) or 0
                embed.add_field(
                    name=f"{entry['character_name']}",
                    value=f"{entry['total_items']} items ({entry['request_count']} requests)\n{plast} Plast, {spice} Spice\n{entry['requester_name']}",
                    inline=True,
                )
                total_items += entry['total_items']
                total_requests += entry['request_count']

            embed.set_footer(text=f"Total: {total_items} items | {material_totals['total_plastanium']} Plastanium, {material_totals['total_spice']} Spice")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="crafter-stats", description="View crafter production statistics")
    @app_commands.describe(period="Time period to view")
    @app_commands.choices(period=[
        app_commands.Choice(name="Today", value="today"),
        app_commands.Choice(name="Last 7 days", value="week"),
        app_commands.Choice(name="Last 30 days", value="month"),
        app_commands.Choice(name="All time", value="all"),
    ])
    async def crafter_stats(self, interaction: discord.Interaction, period: str = "week"):
        """View statistics for crafters."""
        db = self.bot.db
        start_date, end_date = self._get_date_range(period)

        period_labels = {
            "today": "Today",
            "week": "Last 7 Days",
            "month": "Last 30 Days",
            "all": "All Time"
        }
        period_label = period_labels.get(period, period)

        totals = await db.get_crafter_totals(start_date, end_date)

        if not totals:
            await interaction.response.send_message(
                f"No completed requisitions found for {period_label}.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Crafter Leaderboard - {period_label}",
            color=discord.Color.gold(),
        )

        total_items = 0
        total_plastanium = 0
        total_spice = 0
        for i, entry in enumerate(totals[:10], 1):
            medal = ""
            if i == 1:
                medal = " :first_place:"
            elif i == 2:
                medal = " :second_place:"
            elif i == 3:
                medal = " :third_place:"

            plast = entry.get('total_plastanium', 0) or 0
            spice = entry.get('total_spice', 0) or 0
            embed.add_field(
                name=f"#{i} {entry['crafter_name']}{medal}",
                value=f"{entry['total_items']} items ({entry['request_count']} requests)\n{plast} Plast, {spice} Spice",
                inline=False,
            )
            total_items += entry['total_items']
            total_plastanium += plast
            total_spice += spice

        embed.set_footer(text=f"Total: {total_items} items | {total_plastanium} Plastanium, {total_spice} Spice")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="item-stats", description="View most requested items")
    @app_commands.describe(period="Time period to view")
    @app_commands.choices(period=[
        app_commands.Choice(name="Today", value="today"),
        app_commands.Choice(name="Last 7 days", value="week"),
        app_commands.Choice(name="Last 30 days", value="month"),
        app_commands.Choice(name="All time", value="all"),
    ])
    async def item_stats(self, interaction: discord.Interaction, period: str = "week"):
        """View most requested items."""
        db = self.bot.db
        start_date, end_date = self._get_date_range(period)

        period_labels = {
            "today": "Today",
            "week": "Last 7 Days",
            "month": "Last 30 Days",
            "all": "All Time"
        }
        period_label = period_labels.get(period, period)

        totals = await db.get_item_totals(start_date, end_date)

        if not totals:
            await interaction.response.send_message(
                f"No completed requisitions found for {period_label}.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Most Requested Items - {period_label}",
            color=discord.Color.blue(),
        )

        total_plastanium = 0
        total_spice = 0
        for entry in totals[:15]:
            plast = entry.get('total_plastanium', 0) or 0
            spice = entry.get('total_spice', 0) or 0
            embed.add_field(
                name=f"{entry['item_name']}",
                value=f"{entry['total_quantity']} crafted ({entry['request_count']} requests)\n{plast} Plast, {spice} Spice\n*{entry['category']}*",
                inline=True,
            )
            total_plastanium += plast
            total_spice += spice

        embed.set_footer(text=f"Total Materials: {total_plastanium} Plastanium, {total_spice} Spice")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="material-stats", description="View total materials used")
    @app_commands.describe(period="Time period to view")
    @app_commands.choices(period=[
        app_commands.Choice(name="Today", value="today"),
        app_commands.Choice(name="Last 7 days", value="week"),
        app_commands.Choice(name="Last 30 days", value="month"),
        app_commands.Choice(name="All time", value="all"),
    ])
    async def material_stats(self, interaction: discord.Interaction, period: str = "week"):
        """View total material usage statistics."""
        db = self.bot.db
        start_date, end_date = self._get_date_range(period)

        period_labels = {
            "today": "Today",
            "week": "Last 7 Days",
            "month": "Last 30 Days",
            "all": "All Time"
        }
        period_label = period_labels.get(period, period)

        totals = await db.get_material_totals(start_date, end_date)

        embed = discord.Embed(
            title=f"Material Usage - {period_label}",
            color=discord.Color.orange(),
        )

        embed.add_field(
            name="Plastanium Ingots",
            value=f"{totals['total_plastanium']}",
            inline=True,
        )
        embed.add_field(
            name="Spice Melange",
            value=f"{totals['total_spice']}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RequisitionCog(bot))
