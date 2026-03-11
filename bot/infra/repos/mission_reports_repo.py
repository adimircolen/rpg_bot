from bot.infra.db.sqlite import get_connection


class MissionReportsRepo:
    @staticmethod
    def get(mission_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM mission_reports WHERE mission_id = ?", (mission_id,))
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def create(mission_id: int, issued_by_discord_user_id: str, payload_json: str, version: int = 1) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mission_reports (mission_id, issued_by_discord_user_id, payload_json, version)
            VALUES (?, ?, ?, ?)
            """,
            (mission_id, issued_by_discord_user_id, payload_json, version),
        )
        conn.commit()
        conn.close()
