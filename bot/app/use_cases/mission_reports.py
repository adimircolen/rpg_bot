from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from bot.infra.repos.mission_reports_repo import MissionReportsRepo
from bot.infra.repos.missions_repo import MissionsRepo
from bot.infra.repos.loot_repo import LootRepo
from bot.infra.repos.participations_repo import ParticipationsRepo
from bot.app.use_cases.characters import ensure_player


MISSION_STATUS_AWAITING_LOOT = "AWAITING_LOOT"
MISSION_STATUS_COMPLETED = "COMPLETED"


class MissionNotFound(Exception):
    pass


class PermissionDenied(Exception):
    pass


class InvalidStateError(Exception):
    pass


class ConflictError(Exception):
    pass


class ValidationError(Exception):
    pass


@dataclass(frozen=True)
class MissionReportDTO:
    mission_id: int
    version: int
    issued_by: str
    summary: str
    outcome: str | None
    impacts: str | None
    npcs: str | None
    notes: str | None


def _get_mission(mission_id: int):
    row = MissionsRepo.get_by_id(mission_id)
    if not row:
        raise MissionNotFound("Missao nao encontrada.")
    return row


def _clean_optional(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > max_len:
        raise ValidationError(f"Campo excede {max_len} caracteres.")
    return value


def issue_mission_report(
    actor_discord_user_id: str,
    mission_id: int,
    summary: str,
    outcome: str | None,
    impacts: str | None,
    npcs: str | None,
    notes: str | None,
    allow_override: bool = False,
) -> MissionReportDTO:
    mission = _get_mission(mission_id)

    if mission["status"] not in {MISSION_STATUS_AWAITING_LOOT, MISSION_STATUS_COMPLETED}:
        raise InvalidStateError("So e possivel emitir relatorio quando a missao esta em AWAITING_LOOT ou COMPLETED.")

    player_id = ensure_player(actor_discord_user_id, actor_discord_user_id)
    part = ParticipationsRepo.get_by_mission_and_player(mission_id, player_id)
    if not part:
        raise PermissionDenied("Somente participantes podem emitir o relatorio.")

    if MissionReportsRepo.get(mission_id):
        raise ConflictError("Ja existe relatorio para esta missao.")

    summary = (summary or "").strip()
    if len(summary) < 10 or len(summary) > 1500:
        raise ValidationError("Resumo deve ter entre 10 e 1500 caracteres.")

    outcome = _clean_optional(outcome, 1200)
    impacts = _clean_optional(impacts, 1200)
    npcs = _clean_optional(npcs, 1200)
    notes = _clean_optional(notes, 1200)

    payload = {
        "summary": summary,
        "outcome": outcome,
        "impacts": impacts,
        "npcs": npcs,
        "notes": notes,
        "character_id": int(part["character_id"]),
        "character_name": part["character_name"],
        "version": 1,
    }

    payload_json = json.dumps(payload, ensure_ascii=False)

    try:
        MissionReportsRepo.create(mission_id, actor_discord_user_id, payload_json, version=1)
    except sqlite3.IntegrityError:
        raise ConflictError("Ja existe relatorio para esta missao.")

    # ✅ Se o espólio já existir, adiciona bônus de relatório
    loot_row = LootRepo.get(mission_id)
    if loot_row:
        loot_payload = json.loads(loot_row["payload_json"])
        loot_payload["report_bonus"] = {
            "discord_user_id": str(actor_discord_user_id),
            "character_name": part["character_name"],
            "percent": 20,
        }
        LootRepo.update_payload(mission_id, json.dumps(loot_payload, ensure_ascii=False))

    return MissionReportDTO(
        mission_id=mission_id,
        version=1,
        issued_by=str(actor_discord_user_id),
        summary=summary,
        outcome=outcome,
        impacts=impacts,
        npcs=npcs,
        notes=notes,
    )


def get_mission_report(mission_id: int) -> MissionReportDTO:
    row = MissionReportsRepo.get(mission_id)
    if not row:
        raise MissionNotFound("Relatorio nao encontrado para esta missao.")

    payload = json.loads(row["payload_json"])
    return MissionReportDTO(
        mission_id=mission_id,
        version=int(row["version"]),
        issued_by=str(row["issued_by_discord_user_id"]),
        summary=payload.get("summary") or "",
        outcome=payload.get("outcome"),
        impacts=payload.get("impacts"),
        npcs=payload.get("npcs"),
        notes=payload.get("notes"),
    )
