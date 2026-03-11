from bot.infra.db.sqlite import get_connection


class GuildConfigRepo:
    @staticmethod
    def get(guild_id: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def set_loot_channel(guild_id: str, channel_id: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, loot_channel_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
              loot_channel_id = excluded.loot_channel_id,
              updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, channel_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def set_report_channel(guild_id: str, channel_id: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, report_channel_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
              report_channel_id = excluded.report_channel_id,
              updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, channel_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def clear_loot_channel(guild_id: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE guild_config SET loot_channel_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?",
            (guild_id,),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def clear_report_channel(guild_id: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE guild_config SET report_channel_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?",
            (guild_id,),
        )
        conn.commit()
        conn.close()
