from bot.infra.db.sqlite import get_connection


class PlayersRepo:

    @staticmethod
    def get_by_discord_id(discord_user_id: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM players WHERE discord_user_id = ?",
            (discord_user_id,)
        )
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def create(discord_user_id: str, display_name: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO players (discord_user_id, display_name) VALUES (?, ?)",
            (discord_user_id, display_name)
        )
        conn.commit()
        player_id = cur.lastrowid
        conn.close()
        return player_id
