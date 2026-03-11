import sqlite3
from pathlib import Path

DB_PATH = Path("dragon_tavern.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    return {r[1] for r in rows}  # column name


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_user_id TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(player_id, name),
        FOREIGN KEY(player_id) REFERENCES players(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        scheduled_at TEXT NOT NULL,
        status TEXT NOT NULL,
        dm_discord_user_id TEXT NOT NULL,
        max_slots INTEGER NULL,
        cancel_reason TEXT NULL,
        channel_id TEXT NULL,
        card_message_id TEXT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ✅ participations schema v2
    # Auto-migrate: se existir tabela antiga sem colunas novas, recria.
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='participations'")
    exists = cur.fetchone() is not None

    if exists:
        cols = _table_columns(conn, "participations")
        needed = {"mission_id", "player_id", "character_id", "role", "joined_at", "locked_at", "played_at"}
        if not needed.issubset(cols):
            # MVP: recria (pode perder dados antigos)
            cur.execute("DROP TABLE IF EXISTS participations")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS participations (
        mission_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        character_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'INTERESTED', -- INTERESTED|SELECTED|RESERVE
        joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
        locked_at TEXT NULL,
        played_at TEXT NULL,
        PRIMARY KEY (mission_id, player_id),
        FOREIGN KEY(mission_id) REFERENCES missions(id),
        FOREIGN KEY(player_id) REFERENCES players(id),
        FOREIGN KEY(character_id) REFERENCES characters(id)
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_participations_character_played
    ON participations(character_id, played_at)
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS loot (
        mission_id INTEGER PRIMARY KEY,
        issued_by_discord_user_id TEXT NOT NULL,
        issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
        payload_json TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(mission_id) REFERENCES missions(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mission_reports (
        mission_id INTEGER PRIMARY KEY,
        issued_by_discord_user_id TEXT NOT NULL,
        issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
        payload_json TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(mission_id) REFERENCES missions(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS guild_config (
        guild_id TEXT PRIMARY KEY,
        loot_channel_id TEXT NULL,
        report_channel_id TEXT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
