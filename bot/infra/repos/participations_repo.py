from bot.infra.db.sqlite import get_connection


class ParticipationsRepo:
    @staticmethod
    def add_interested(mission_id: int, player_id: int, character_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO participations (mission_id, player_id, character_id, role)
            VALUES (?, ?, ?, 'INTERESTED')
            """,
            (mission_id, player_id, character_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def remove(mission_id: int, player_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM participations WHERE mission_id = ? AND player_id = ?",
            (mission_id, player_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def exists(mission_id: int, player_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM participations WHERE mission_id = ? AND player_id = ? LIMIT 1",
            (mission_id, player_id),
        )
        row = cur.fetchone()
        conn.close()
        return row is not None

    @staticmethod
    def list_by_mission(mission_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              pa.role            AS role,
              p.display_name     AS player_display,
              p.discord_user_id  AS player_discord_id,
              c.id               AS character_id,
              c.name             AS character_name,
              pa.joined_at       AS joined_at
            FROM participations pa
            JOIN players p    ON p.id = pa.player_id
            JOIN characters c ON c.id = pa.character_id
            WHERE pa.mission_id = ?
            ORDER BY pa.role, c.name
            """,
            (mission_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def list_interested_with_last_played(mission_id: int):
        """
        Retorna inscritos com last_played_at para convocação:
        - last_played_at = MAX(played_at) por character_id (onde played_at não é null)
        - null = nunca jogou (prioridade máxima)
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              pa.player_id        AS player_id,
              pa.character_id     AS character_id,
              pa.joined_at        AS joined_at,
              p.display_name      AS player_display,
              c.name              AS character_name,
              (
                SELECT MAX(played_at)
                FROM participations pa2
                WHERE pa2.character_id = pa.character_id
                  AND pa2.played_at IS NOT NULL
              ) AS last_played_at
            FROM participations pa
            JOIN players p    ON p.id = pa.player_id
            JOIN characters c ON c.id = pa.character_id
            WHERE pa.mission_id = ?
            ORDER BY
              (last_played_at IS NOT NULL) ASC,  -- NULL primeiro
              last_played_at ASC,
              joined_at ASC
            """,
            (mission_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def set_roles_bulk(mission_id: int, selected_character_ids: list[int], reserve_character_ids: list[int]) -> None:
        conn = get_connection()
        cur = conn.cursor()

        # Tudo vira INTERESTED primeiro (para evitar “sobras”)
        cur.execute(
            "UPDATE participations SET role = 'INTERESTED' WHERE mission_id = ?",
            (mission_id,),
        )

        if selected_character_ids:
            cur.execute(
                f"""
                UPDATE participations
                SET role = 'SELECTED'
                WHERE mission_id = ?
                  AND character_id IN ({",".join(["?"] * len(selected_character_ids))})
                """,
                (mission_id, *selected_character_ids),
            )

        if reserve_character_ids:
            cur.execute(
                f"""
                UPDATE participations
                SET role = 'RESERVE'
                WHERE mission_id = ?
                  AND character_id IN ({",".join(["?"] * len(reserve_character_ids))})
                """,
                (mission_id, *reserve_character_ids),
            )

        conn.commit()
        conn.close()

    @staticmethod
    def swap_roles(mission_id: int, selected_character_id: int, reserve_character_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE participations
            SET role = CASE
              WHEN character_id = ? THEN 'RESERVE'
              WHEN character_id = ? THEN 'SELECTED'
              ELSE role
            END
            WHERE mission_id = ?
              AND character_id IN (?, ?)
            """,
            (selected_character_id, reserve_character_id, mission_id, selected_character_id, reserve_character_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def lock_mission(mission_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE participations SET locked_at = CURRENT_TIMESTAMP WHERE mission_id = ? AND locked_at IS NULL",
            (mission_id,),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def mark_played_for_selected(mission_id: int) -> None:
        """
        Marca played_at para os participantes efetivos (SELECTED) da missão.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE participations
            SET played_at = CURRENT_TIMESTAMP
            WHERE mission_id = ?
              AND role = 'SELECTED'
            """,
            (mission_id,),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_by_mission_and_player(mission_id: int, player_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              pa.role            AS role,
              c.id               AS character_id,
              c.name             AS character_name,
              p.display_name     AS player_display
            FROM participations pa
            JOIN players p    ON p.id = pa.player_id
            JOIN characters c ON c.id = pa.character_id
            WHERE pa.mission_id = ?
              AND pa.player_id = ?
            LIMIT 1
            """,
            (mission_id, player_id),
        )
        row = cur.fetchone()
        conn.close()
        return row
