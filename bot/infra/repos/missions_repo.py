# bot/infra/repos/missions_repo.py
from bot.infra.db.sqlite import get_connection


class MissionsRepo:
    @staticmethod
    def create(code: str, title: str, scheduled_at: str, status: str, dm_discord_user_id: str, max_slots: int | None):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO missions (code, title, scheduled_at, status, dm_discord_user_id, max_slots)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (code, title, scheduled_at, status, dm_discord_user_id, max_slots),
        )
        conn.commit()
        mission_id = cur.lastrowid
        conn.close()
        return mission_id

    @staticmethod
    def get_by_id(mission_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def list_recent(limit: int = 20):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM missions
            ORDER BY datetime(scheduled_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def attach_card(mission_id: int, channel_id: str, message_id: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE missions SET channel_id = ?, card_message_id = ? WHERE id = ?",
            (channel_id, message_id, mission_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def update_status(mission_id: int, status: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE missions SET status = ? WHERE id = ?", (status, mission_id))
        conn.commit()
        conn.close()
