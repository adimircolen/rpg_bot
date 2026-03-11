# bot/infra/repos/characters_repo.py
from bot.infra.db.sqlite import get_connection


class CharactersRepo:
    @staticmethod
    def create(player_id: int, name: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO characters (player_id, name) VALUES (?, ?)",
            (player_id, name),
        )
        conn.commit()
        char_id = cur.lastrowid
        conn.close()
        return char_id

    @staticmethod
    def list_by_player(player_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM characters
            WHERE player_id = ?
            ORDER BY is_active DESC, name
            """,
            (player_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def get_by_id(character_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def set_active(character_id: int, is_active: bool) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE characters SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, character_id),
        )
        conn.commit()
        conn.close()
