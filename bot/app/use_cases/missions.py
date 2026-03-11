# bot/app/use_cases/missions.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3
import secrets

from bot.infra.repos.missions_repo import MissionsRepo
from bot.infra.repos.participations_repo import ParticipationsRepo
from bot.infra.repos.characters_repo import CharactersRepo
from bot.app.use_cases.characters import ensure_player


# Status
MISSION_STATUS_SCHEDULED = "SCHEDULED"
MISSION_STATUS_IN_PROGRESS = "IN_PROGRESS"
MISSION_STATUS_AWAITING_LOOT = "AWAITING_LOOT"
MISSION_STATUS_COMPLETED = "COMPLETED"


# Errors
class MissionNotFound(Exception): ...
class ValidationError(Exception): ...
class PermissionDenied(Exception): ...
class InvalidStateError(Exception): ...
class ConflictError(Exception): ...


# DTOs
@dataclass(frozen=True)
class MissionDTO:
    id: int
    code: str
    title: str
    scheduled_at: str
    status: str
    dm_discord_user_id: str
    max_slots: int | None
    channel_id: str | None
    card_message_id: str | None


@dataclass(frozen=True)
class ParticipantDTO:
    player_display: str
    player_discord_id: str
    character_id: int
    character_name: str
    role: str  # INTERESTED|SELECTED|RESERVE


@dataclass(frozen=True)
class MissionCardDTO:
    id: int
    code: str
    title: str
    scheduled_at: str
    status: str
    dm_discord_user_id: str
    max_slots: int | None
    channel_id: str | None
    card_message_id: str | None
    participants: list[ParticipantDTO]


# Helpers
def _get_mission_row(mission_id: int):
    row = MissionsRepo.get_by_id(mission_id)
    if not row:
        raise MissionNotFound("Missão não encontrada.")
    return row


def _to_mission_dto(row) -> MissionDTO:
    return MissionDTO(
        id=row["id"],
        code=row["code"],
        title=row["title"],
        scheduled_at=row["scheduled_at"],
        status=row["status"],
        dm_discord_user_id=row["dm_discord_user_id"],
        max_slots=row["max_slots"],
        channel_id=row["channel_id"],
        card_message_id=row["card_message_id"],
    )


def _to_card(mission_id: int) -> MissionCardDTO:
    row = _get_mission_row(mission_id)
    parts = ParticipationsRepo.list_by_mission(mission_id)
    participants = [
        ParticipantDTO(
            player_display=p["player_display"],
            character_id=int(p["character_id"]),
            character_name=p["character_name"],
            role=p["role"],
        )
        for p in parts
    ]
    return MissionCardDTO(
        id=row["id"],
        code=row["code"],
        title=row["title"],
        scheduled_at=row["scheduled_at"],
        status=row["status"],
        dm_discord_user_id=row["dm_discord_user_id"],
        max_slots=row["max_slots"],
        channel_id=row["channel_id"],
        card_message_id=row["card_message_id"],
        participants=participants,
    )


def _make_unique_code(scheduled_at_iso: str) -> str:
    """
    Ex: MIS-20260217-2000-A1B2
    """
    try:
        dt = datetime.fromisoformat(scheduled_at_iso)
    except Exception:
        dt = datetime.now()

    ymd = dt.strftime("%Y%m%d")
    hm = dt.strftime("%H%M")
    suffix = secrets.token_hex(2).upper()  # 4 chars
    return f"MIS-{ymd}-{hm}-{suffix}"


# Public Use Cases (Creation / Query)
def create_mission(
    actor_discord_user_id: str,
    title: str,
    scheduled_at_iso: str,
    max_slots: int | None,
) -> MissionDTO:
    title = title.strip()
    if len(title) < 3 or len(title) > 80:
        raise ValidationError("O título deve ter entre 3 e 80 caracteres.")

    if max_slots is not None and (max_slots < 1 or max_slots > 99):
        raise ValidationError("Capacidade deve estar entre 1 e 99.")

    try:
        datetime.fromisoformat(scheduled_at_iso)
    except ValueError:
        raise ValidationError("scheduled_at inválido. Use formato ISO 8601.")

    last_err = None
    for _ in range(5):
        code = _make_unique_code(scheduled_at_iso)
        try:
            mission_id = MissionsRepo.create(
                code=code,
                title=title,
                scheduled_at=scheduled_at_iso,
                status=MISSION_STATUS_SCHEDULED,
                dm_discord_user_id=actor_discord_user_id,
                max_slots=max_slots,
            )
            row = MissionsRepo.get_by_id(mission_id)
            return _to_mission_dto(row)
        except sqlite3.IntegrityError as e:
            last_err = e
            continue

    raise ValidationError("Falha ao gerar código único para a missão. Tente novamente.")


def attach_mission_card(mission_id: int, channel_id: str, message_id: str) -> MissionDTO:
    _get_mission_row(mission_id)
    MissionsRepo.attach_card(mission_id, channel_id, message_id)
    row = MissionsRepo.get_by_id(mission_id)
    return _to_mission_dto(row)


def get_mission(mission_id: int) -> MissionDTO:
    row = _get_mission_row(mission_id)
    return _to_mission_dto(row)


def list_missions(limit: int = 10) -> list[MissionDTO]:
    rows = MissionsRepo.list_recent(limit=max(1, min(50, limit)))
    return [_to_mission_dto(r) for r in rows]


def get_mission_card(mission_id: int) -> MissionCardDTO:
    return _to_card(mission_id)


# Participation (inscrição ilimitada)
def join_mission(actor_discord_user_id: str, actor_display_name: str, mission_id: int, character_id: int) -> MissionCardDTO:
    row = _get_mission_row(mission_id)
    if row["status"] != MISSION_STATUS_SCHEDULED:
        raise InvalidStateError("Só é possível se inscrever quando a missão está agendada (SCHEDULED).")

    player_id = ensure_player(actor_discord_user_id, actor_display_name)

    if ParticipationsRepo.exists(mission_id, player_id):
        raise ConflictError("Você já está inscrito nesta missão.")

    ch = CharactersRepo.get_by_id(character_id)
    if not ch:
        raise ValidationError("Personagem não encontrado.")
    if int(ch["player_id"]) != int(player_id):
        raise PermissionDenied("Esse personagem não é seu.")
    if not bool(ch["is_active"]):
        raise ValidationError("Esse personagem está inativo. Ative-o antes de se inscrever.")

    try:
        ParticipationsRepo.add_interested(mission_id, player_id, character_id)
    except sqlite3.IntegrityError:
        raise ConflictError("Você já está inscrito nesta missão.")

    return _to_card(mission_id)


def leave_mission(actor_discord_user_id: str, actor_display_name: str, mission_id: int) -> MissionCardDTO:
    row = _get_mission_row(mission_id)
    if row["status"] != MISSION_STATUS_SCHEDULED:
        raise InvalidStateError("Só é possível remover inscrição quando a missão está agendada (SCHEDULED).")

    player_id = ensure_player(actor_discord_user_id, actor_display_name)
    ParticipationsRepo.remove(mission_id, player_id)
    return _to_card(mission_id)


# Convocação / reservas
def convocate_mission(
    actor_discord_user_id: str,
    mission_id: int,
    seats: int,
    allow_override: bool = False,
) -> MissionCardDTO:
    row = _get_mission_row(mission_id)
    if row["status"] != MISSION_STATUS_SCHEDULED:
        raise InvalidStateError("Só é possível convocar quando a missão está agendada (SCHEDULED).")
    if str(row["dm_discord_user_id"]) != str(actor_discord_user_id) and not allow_override:
        raise PermissionDenied("Somente o mestre pode convocar.")

    if seats < 1 or seats > 99:
        raise ValidationError("Vagas precisa estar entre 1 e 99.")

    ranked = ParticipationsRepo.list_interested_with_last_played(mission_id)
    if not ranked:
        raise ValidationError("Não há inscritos para convocar.")

    selected: list[int] = []
    reserve: list[int] = []

    for i, r in enumerate(ranked):
        cid = int(r["character_id"])
        if i < seats:
            selected.append(cid)
        else:
            reserve.append(cid)

    ParticipationsRepo.set_roles_bulk(mission_id, selected, reserve)
    return _to_card(mission_id)


def swap_selected_with_reserve(
    actor_discord_user_id: str,
    mission_id: int,
    selected_character_id: int,
    reserve_character_id: int,
    allow_override: bool = False,
) -> MissionCardDTO:
    row = _get_mission_row(mission_id)
    if row["status"] != MISSION_STATUS_SCHEDULED:
        raise InvalidStateError("Só é possível trocar antes de iniciar (SCHEDULED).")
    if str(row["dm_discord_user_id"]) != str(actor_discord_user_id) and not allow_override:
        raise PermissionDenied("Somente o mestre pode trocar convocados/reservas.")

    card = _to_card(mission_id)
    role_by_cid = {p.character_id: p.role for p in card.participants}

    if role_by_cid.get(selected_character_id) != "SELECTED":
        raise ValidationError("O primeiro personagem deve ser um CONVOCADO (SELECTED).")
    if role_by_cid.get(reserve_character_id) != "RESERVE":
        raise ValidationError("O segundo personagem deve ser um RESERVA (RESERVE).")

    ParticipationsRepo.swap_roles(mission_id, selected_character_id, reserve_character_id)
    return _to_card(mission_id)


def start_mission(actor_discord_user_id: str, mission_id: int, allow_override: bool = False) -> MissionCardDTO:
    row = _get_mission_row(mission_id)
    if row["status"] != MISSION_STATUS_SCHEDULED:
        raise InvalidStateError("Só é possível iniciar quando a missão está agendada (SCHEDULED).")
    if str(row["dm_discord_user_id"]) != str(actor_discord_user_id) and not allow_override:
        raise PermissionDenied("Somente o mestre pode iniciar a missão.")

    card = _to_card(mission_id)
    selected = [p for p in card.participants if p.role == "SELECTED"]
    if not selected:
        raise ValidationError("Antes de iniciar, faça a convocação (selecione convocados).")

    ParticipationsRepo.lock_mission(mission_id)
    MissionsRepo.update_status(mission_id, MISSION_STATUS_IN_PROGRESS)
    return _to_card(mission_id)


def finish_mission(actor_discord_user_id: str, mission_id: int, allow_override: bool = False) -> MissionCardDTO:
    row = _get_mission_row(mission_id)
    if row["status"] != MISSION_STATUS_IN_PROGRESS:
        raise InvalidStateError("Só é possível finalizar quando está em andamento (IN_PROGRESS).")
    if str(row["dm_discord_user_id"]) != str(actor_discord_user_id) and not allow_override:
        raise PermissionDenied("Somente o mestre pode finalizar.")

    MissionsRepo.update_status(mission_id, MISSION_STATUS_AWAITING_LOOT)
    return _to_card(mission_id)
