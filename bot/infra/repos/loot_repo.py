# bot/infra/repos/loot_repo.py
from bot.infra.db.sqlite import get_connection


class LootRepo:
    @staticmethod
    def get(mission_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM loot WHERE mission_id = ?", (mission_id,))
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def create(mission_id: int, issued_by_discord_user_id: str, payload_json: str, version: int = 1) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO loot (mission_id, issued_by_discord_user_id, payload_json, version)
            VALUES (?, ?, ?, ?)
            """,
            (mission_id, issued_by_discord_user_id, payload_json, version),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def update_payload(mission_id: int, payload_json: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE loot SET payload_json = ? WHERE mission_id = ?",
            (payload_json, mission_id),
        )
        conn.commit()
        conn.close()
