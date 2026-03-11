# bot/app/use_cases/characters.py
import sqlite3

from bot.infra.repos.players_repo import PlayersRepo
from bot.infra.repos.characters_repo import CharactersRepo


class CharacterAlreadyExists(Exception):
    pass


class CharacterNotFound(Exception):
    pass


class NotCharacterOwner(Exception):
    pass


def ensure_player(discord_user_id: str, display_name: str) -> int:
    player = PlayersRepo.get_by_discord_id(discord_user_id)
    if player:
        return player["id"]
    return PlayersRepo.create(discord_user_id, display_name)


def create_character(discord_user_id: str, display_name: str, name: str):
    name = name.strip()

    if len(name) < 2 or len(name) > 32:
        raise ValueError("O nome deve ter entre 2 e 32 caracteres.")

    player_id = ensure_player(discord_user_id, display_name)

    try:
        char_id = CharactersRepo.create(player_id, name)
    except sqlite3.IntegrityError:
        raise CharacterAlreadyExists("Você já possui um personagem com esse nome.")

    return {"character_id": char_id, "name": name}


def list_characters(discord_user_id: str, display_name: str):
    player_id = ensure_player(discord_user_id, display_name)
    rows = CharactersRepo.list_by_player(player_id)

    return [
        {
            "character_id": r["id"],
            "name": r["name"],
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]


def set_character_active(
    actor_discord_user_id: str,
    actor_display_name: str,
    character_id: int,
    is_active: bool,
):
    """
    Ativa/Desativa um personagem.
    Regra: somente o dono do personagem pode alterar (nesta fase).
    """
    actor_player_id = ensure_player(actor_discord_user_id, actor_display_name)

    row = CharactersRepo.get_by_id(character_id)
    if not row:
        raise CharacterNotFound("Personagem não encontrado.")

    if row["player_id"] != actor_player_id:
        raise NotCharacterOwner("Você não tem permissão para alterar este personagem.")

    CharactersRepo.set_active(character_id, is_active)

    return {
        "character_id": row["id"],
        "name": row["name"],
        "is_active": is_active,
    }
