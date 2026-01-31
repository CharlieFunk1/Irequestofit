import aiosqlite
from datetime import datetime, timedelta
from typing import Optional
from config import DATABASE_PATH


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Establish database connection and create tables."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._migrate_tables()

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()

    async def _create_tables(self):
        """Create necessary tables if they don't exist."""
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id INTEGER NOT NULL,
                requester_name TEXT NOT NULL,
                character_name TEXT NOT NULL,
                category TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                plastanium_cost INTEGER DEFAULT 0,
                spice_cost INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                crafter_id INTEGER,
                crafter_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                claimed_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                crafter_role_id INTEGER,
                announcement_channel_id INTEGER,
                queue_channel_id INTEGER,
                queue_message_id INTEGER
            )
        """)
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                character_name TEXT NOT NULL
            )
        """)
        await self._connection.commit()

    async def _migrate_tables(self):
        """Add new columns to existing tables if they don't exist."""
        try:
            await self._connection.execute(
                "ALTER TABLE requests ADD COLUMN plastanium_cost INTEGER DEFAULT 0"
            )
            await self._connection.commit()
        except:
            pass  # Column already exists

        try:
            await self._connection.execute(
                "ALTER TABLE requests ADD COLUMN spice_cost INTEGER DEFAULT 0"
            )
            await self._connection.commit()
        except:
            pass  # Column already exists

        try:
            await self._connection.execute(
                "ALTER TABLE guild_settings ADD COLUMN queue_channel_id INTEGER"
            )
            await self._connection.commit()
        except:
            pass  # Column already exists

        try:
            await self._connection.execute(
                "ALTER TABLE guild_settings ADD COLUMN queue_message_id INTEGER"
            )
            await self._connection.commit()
        except:
            pass  # Column already exists

    # Request operations
    async def create_request(
        self,
        requester_id: int,
        requester_name: str,
        character_name: str,
        category: str,
        item_name: str,
        quantity: int,
        plastanium_cost: int = 0,
        spice_cost: int = 0,
    ) -> int:
        """Create a new requisition request. Returns the request ID."""
        # Multiply costs by quantity
        total_plastanium = plastanium_cost * quantity
        total_spice = spice_cost * quantity

        cursor = await self._connection.execute(
            """
            INSERT INTO requests (requester_id, requester_name, character_name, category, item_name, quantity, plastanium_cost, spice_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (requester_id, requester_name, character_name, category, item_name, quantity, total_plastanium, total_spice),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_request(self, request_id: int) -> Optional[dict]:
        """Get a single request by ID."""
        cursor = await self._connection.execute(
            "SELECT * FROM requests WHERE id = ?", (request_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_user_requests(self, user_id: int) -> list[dict]:
        """Get all requests for a user that are not completed or cancelled."""
        cursor = await self._connection.execute(
            """
            SELECT * FROM requests
            WHERE requester_id = ? AND status IN ('pending', 'claimed')
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_pending_requests(self) -> list[dict]:
        """Get all pending requests."""
        cursor = await self._connection.execute(
            """
            SELECT * FROM requests
            WHERE status = 'pending'
            ORDER BY created_at ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_active_requests(self) -> list[dict]:
        """Get all active requests (pending and claimed)."""
        cursor = await self._connection.execute(
            """
            SELECT * FROM requests
            WHERE status IN ('pending', 'claimed')
            ORDER BY created_at ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_claimed_requests(self, crafter_id: int) -> list[dict]:
        """Get all requests claimed by a specific crafter."""
        cursor = await self._connection.execute(
            """
            SELECT * FROM requests
            WHERE crafter_id = ? AND status = 'claimed'
            ORDER BY claimed_at DESC
            """,
            (crafter_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def cancel_request(self, request_id: int, user_id: int) -> bool:
        """Cancel a request. Returns True if successful."""
        cursor = await self._connection.execute(
            """
            UPDATE requests
            SET status = 'cancelled'
            WHERE id = ? AND requester_id = ? AND status = 'pending'
            """,
            (request_id, user_id),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def clear_pending_requests(self) -> int:
        """Cancel all pending requests. Returns the number of requests cleared."""
        cursor = await self._connection.execute(
            """
            UPDATE requests
            SET status = 'cancelled'
            WHERE status = 'pending'
            """
        )
        await self._connection.commit()
        return cursor.rowcount

    async def update_request(
        self,
        request_id: int,
        user_id: int,
        category: str,
        item_name: str,
        quantity: int,
        plastanium_cost: int,
        spice_cost: int,
    ) -> bool:
        """Update a pending request. Returns True if successful."""
        total_plastanium = plastanium_cost * quantity
        total_spice = spice_cost * quantity

        cursor = await self._connection.execute(
            """
            UPDATE requests
            SET category = ?, item_name = ?, quantity = ?, plastanium_cost = ?, spice_cost = ?
            WHERE id = ? AND requester_id = ? AND status = 'pending'
            """,
            (category, item_name, quantity, total_plastanium, total_spice, request_id, user_id),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def claim_request(self, request_id: int, crafter_id: int, crafter_name: str) -> bool:
        """Claim a pending request. Returns True if successful."""
        cursor = await self._connection.execute(
            """
            UPDATE requests
            SET status = 'claimed', crafter_id = ?, crafter_name = ?, claimed_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (crafter_id, crafter_name, datetime.utcnow(), request_id),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def unclaim_request(self, request_id: int, crafter_id: int) -> bool:
        """Unclaim a request. Returns True if successful."""
        cursor = await self._connection.execute(
            """
            UPDATE requests
            SET status = 'pending', crafter_id = NULL, crafter_name = NULL, claimed_at = NULL
            WHERE id = ? AND crafter_id = ? AND status = 'claimed'
            """,
            (request_id, crafter_id),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def complete_request(self, request_id: int, crafter_id: int) -> Optional[dict]:
        """Complete a claimed request. Returns the request if successful."""
        request = await self.get_request(request_id)
        if not request or request["crafter_id"] != crafter_id or request["status"] != "claimed":
            return None

        await self._connection.execute(
            """
            UPDATE requests
            SET status = 'completed', completed_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow(), request_id),
        )
        await self._connection.commit()
        return request

    # Guild settings operations
    async def get_guild_settings(self, guild_id: int) -> Optional[dict]:
        """Get settings for a guild."""
        cursor = await self._connection.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_crafter_role(self, guild_id: int, role_id: int):
        """Set the crafter role for a guild."""
        await self._connection.execute(
            """
            INSERT INTO guild_settings (guild_id, crafter_role_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET crafter_role_id = ?
            """,
            (guild_id, role_id, role_id),
        )
        await self._connection.commit()

    async def set_announcement_channel(self, guild_id: int, channel_id: int):
        """Set the announcement channel for a guild."""
        await self._connection.execute(
            """
            INSERT INTO guild_settings (guild_id, announcement_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET announcement_channel_id = ?
            """,
            (guild_id, channel_id, channel_id),
        )
        await self._connection.commit()

    async def set_queue_channel(self, guild_id: int, channel_id: int):
        """Set the queue channel for a guild."""
        await self._connection.execute(
            """
            INSERT INTO guild_settings (guild_id, queue_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET queue_channel_id = ?
            """,
            (guild_id, channel_id, channel_id),
        )
        await self._connection.commit()

    async def set_queue_message_id(self, guild_id: int, message_id: int):
        """Set the queue message ID for a guild."""
        await self._connection.execute(
            """
            UPDATE guild_settings SET queue_message_id = ? WHERE guild_id = ?
            """,
            (message_id, guild_id),
        )
        await self._connection.commit()

    # User profile operations
    async def get_character_name(self, user_id: int) -> Optional[str]:
        """Get the saved character name for a user."""
        cursor = await self._connection.execute(
            "SELECT character_name FROM user_profiles WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["character_name"] if row else None

    async def set_character_name(self, user_id: int, character_name: str):
        """Save or update the character name for a user."""
        await self._connection.execute(
            """
            INSERT INTO user_profiles (user_id, character_name)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET character_name = ?
            """,
            (user_id, character_name, character_name),
        )
        await self._connection.commit()

    # History and statistics operations
    async def get_completed_requests(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get completed requests within a time range."""
        if start_date and end_date:
            cursor = await self._connection.execute(
                """
                SELECT * FROM requests
                WHERE status = 'completed'
                AND completed_at >= ? AND completed_at <= ?
                ORDER BY completed_at DESC
                """,
                (start_date, end_date),
            )
        elif start_date:
            cursor = await self._connection.execute(
                """
                SELECT * FROM requests
                WHERE status = 'completed' AND completed_at >= ?
                ORDER BY completed_at DESC
                """,
                (start_date,),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT * FROM requests
                WHERE status = 'completed'
                ORDER BY completed_at DESC
                """
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_requester_totals(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get total items requested per person within a time range."""
        if start_date and end_date:
            cursor = await self._connection.execute(
                """
                SELECT requester_id, requester_name, character_name,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_items,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                AND completed_at >= ? AND completed_at <= ?
                GROUP BY requester_id, character_name
                ORDER BY total_items DESC
                """,
                (start_date, end_date),
            )
        elif start_date:
            cursor = await self._connection.execute(
                """
                SELECT requester_id, requester_name, character_name,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_items,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed' AND completed_at >= ?
                GROUP BY requester_id, character_name
                ORDER BY total_items DESC
                """,
                (start_date,),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT requester_id, requester_name, character_name,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_items,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                GROUP BY requester_id, character_name
                ORDER BY total_items DESC
                """
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_crafter_totals(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get total items crafted per crafter within a time range."""
        if start_date and end_date:
            cursor = await self._connection.execute(
                """
                SELECT crafter_id, crafter_name,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_items,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                AND completed_at >= ? AND completed_at <= ?
                GROUP BY crafter_id
                ORDER BY total_items DESC
                """,
                (start_date, end_date),
            )
        elif start_date:
            cursor = await self._connection.execute(
                """
                SELECT crafter_id, crafter_name,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_items,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed' AND completed_at >= ?
                GROUP BY crafter_id
                ORDER BY total_items DESC
                """,
                (start_date,),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT crafter_id, crafter_name,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_items,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                GROUP BY crafter_id
                ORDER BY total_items DESC
                """
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_item_totals(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get total of each item type crafted within a time range."""
        if start_date and end_date:
            cursor = await self._connection.execute(
                """
                SELECT item_name, category,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_quantity,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                AND completed_at >= ? AND completed_at <= ?
                GROUP BY item_name
                ORDER BY total_quantity DESC
                """,
                (start_date, end_date),
            )
        elif start_date:
            cursor = await self._connection.execute(
                """
                SELECT item_name, category,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_quantity,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed' AND completed_at >= ?
                GROUP BY item_name
                ORDER BY total_quantity DESC
                """,
                (start_date,),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT item_name, category,
                       COUNT(*) as request_count,
                       SUM(quantity) as total_quantity,
                       SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                GROUP BY item_name
                ORDER BY total_quantity DESC
                """
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_material_totals(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Get total plastanium and spice used within a time range."""
        if start_date and end_date:
            cursor = await self._connection.execute(
                """
                SELECT SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                AND completed_at >= ? AND completed_at <= ?
                """,
                (start_date, end_date),
            )
        elif start_date:
            cursor = await self._connection.execute(
                """
                SELECT SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed' AND completed_at >= ?
                """,
                (start_date,),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT SUM(plastanium_cost) as total_plastanium,
                       SUM(spice_cost) as total_spice
                FROM requests
                WHERE status = 'completed'
                """
            )
        row = await cursor.fetchone()
        return {
            "total_plastanium": row["total_plastanium"] or 0,
            "total_spice": row["total_spice"] or 0,
        }
